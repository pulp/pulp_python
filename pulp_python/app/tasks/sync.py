import logging
import tempfile
from typing import Dict, Set

from aiohttp import ClientResponseError, ClientError
from collections import defaultdict
from itertools import chain
from lxml.etree import LxmlError
from gettext import gettext as _
from os import environ

from rest_framework import serializers

from pulpcore.plugin.models import Artifact, ProgressReport, Remote, Repository
from pulpcore.plugin.stages import (
    DeclarativeArtifact,
    DeclarativeContent,
    DeclarativeVersion,
    Stage,
)

from pulp_python.app.models import (
    PythonPackageContent,
    PythonRemote,
)
from pulp_python.app.utils import parse_json, parse_metadata, PYPI_LAST_SERIAL
from pypi_simple import parse_repo_index_page

from bandersnatch.mirror import Mirror
from bandersnatch.master import Master
from bandersnatch.configuration import BandersnatchConfig
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from urllib.parse import urljoin, urlsplit, urlunsplit

logger = logging.getLogger(__name__)


def sync(remote_pk, repository_pk, mirror):
    """
    Sync content from the remote repository.

    Create a new version of the repository that is synchronized with the remote.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.
        mirror (boolean): True for mirror mode, False for additive mode.

    Raises:
        serializers: ValidationError

    """
    remote = PythonRemote.objects.get(pk=remote_pk)
    repository = Repository.objects.get(pk=repository_pk)

    if not remote.url:
        raise serializers.ValidationError(
            detail=_("A remote must have a url attribute to sync.")
        )

    first_stage = PythonBanderStage(remote)
    DeclarativeVersion(first_stage, repository, mirror).create()


def create_bandersnatch_config(remote):
    """Modifies the global Bandersnatch config state for this sync"""
    config = BandersnatchConfig().config
    config["mirror"]["master"] = remote.url
    config["mirror"]["workers"] = str(remote.download_concurrency)
    if not config.has_section("plugins"):
        config.add_section("plugins")
    config["plugins"]["enabled"] = "blocklist_release\n"
    if remote.includes:
        if not config.has_section("allowlist"):
            config.add_section("allowlist")
        config["plugins"]["enabled"] += "allowlist_release\nallowlist_project\n"
        config["allowlist"]["packages"] = "\n".join(remote.includes)
    if remote.excludes:
        if not config.has_section("blocklist"):
            config.add_section("blocklist")
        config["plugins"]["enabled"] += "blocklist_project\n"
        config["blocklist"]["packages"] = "\n".join(remote.excludes)
    if not remote.prereleases:
        config["plugins"]["enabled"] += "prerelease_release\n"
    if remote.package_types:
        rrfm = "regex_release_file_metadata"
        config["plugins"]["enabled"] += rrfm
        if not config.has_section(rrfm):
            config.add_section(rrfm)
        config[rrfm]["any:release_file.packagetype"] = "\n".join(remote.package_types)
    if remote.keep_latest_packages:
        config["plugins"]["enabled"] += "latest_release\n"
        if not config.has_section("latest_release"):
            config.add_section("latest_release")
        config["latest_release"]["keep"] = str(remote.keep_latest_packages)
    if remote.exclude_platforms:
        config["plugins"]["enabled"] += "exclude_platform\n"
        if not config.has_section("blocklist"):
            config.add_section("blocklist")
        config["blocklist"]["platforms"] = "\n".join(remote.exclude_platforms)


class PythonBanderStage(Stage):
    """
    Python Package Syncing Stage using Bandersnatch
    """

    def __init__(self, remote):
        """Initialize the stage and Bandersnatch config"""
        super().__init__()
        self.remote = remote
        create_bandersnatch_config(remote)

    async def run(self):
        """
        If includes is specified, then only sync those,else try to sync all other packages
        """
        # Prevent bandersnatch from reading actual .netrc file, set to nonexistent file
        # See discussion on https://github.com/pulp/pulp_python/issues/581
        fake_netrc = tempfile.NamedTemporaryFile(dir=".", delete=False)
        environ["NETRC"] = fake_netrc.name
        # TODO Change Bandersnatch internal API to take proxy settings in from config parameters
        if proxy_url := self.remote.proxy_url:
            if self.remote.proxy_username or self.remote.proxy_password:
                parsed_proxy = urlsplit(proxy_url)
                creds = f"{self.remote.proxy_username}:{self.remote.proxy_password}"
                netloc = f"{creds}@{parsed_proxy.netloc}"
                proxy_url = urlunsplit((parsed_proxy.scheme, netloc, "", "", ""))
            environ['http_proxy'] = proxy_url
            environ['https_proxy'] = proxy_url
        # Bandersnatch includes leading slash when forming API urls
        url = self.remote.url.rstrip("/")
        # local & global timeouts defaults to 10secs and 5 hours
        async with Master(url) as master:
            deferred_download = self.remote.policy != Remote.IMMEDIATE
            workers = self.remote.download_concurrency or self.remote.DEFAULT_DOWNLOAD_CONCURRENCY
            async with ProgressReport(
                message="Fetching Project Metadata", code="sync.fetching.project"
            ) as p:
                pmirror = PulpMirror(
                    serial=0,  # Serial currently isn't supported by Pulp
                    master=master,
                    workers=workers,
                    deferred_download=deferred_download,
                    python_stage=self,
                    progress_report=p,
                )
                packages_to_sync = None
                if self.remote.includes:
                    packages_to_sync = [
                        Requirement(pkg).name for pkg in self.remote.includes
                    ]
                await pmirror.synchronize(packages_to_sync)
                if pmirror.sync_dependencies:
                    depth = 1
                    while pmirror.dependencies_to_sync and depth <= 25:  # ensure no circular loops
                        logger.info(_("Syncing dependencies: depth {}").format(depth))
                        depth += 1
                        packages_to_sync = list(pmirror.dependencies_to_sync.keys())
                        pmirror.allow_filter.allowlist_release_requirements = list(
                            chain(*pmirror.dependencies_to_sync.values())
                        )
                        logger.info(
                            f"Re-initialized release plugin {pmirror.allow_filter.name}, filtering "
                            + f"{pmirror.allow_filter.allowlist_release_requirements}"
                        )
                        pmirror.dependencies_to_sync.clear()
                        await pmirror.synchronize(packages_to_sync)
                    if pmirror.dependencies_to_sync:
                        logger.warning(_("Reached dependency sync depth limit! Breaking out"))


class PulpMirror(Mirror):
    """
    Pulp Mirror Class to perform syncing using Bandersnatch
    """

    def __init__(
        self, serial, master, workers, deferred_download, python_stage, progress_report
    ):
        """Initialize Bandersnatch Mirror"""
        super().__init__(master=master, workers=workers)
        self.synced_serial = serial
        self.python_stage = python_stage
        self.remote = self.python_stage.remote
        self.progress_report = progress_report
        self.deferred_download = deferred_download
        self.sync_dependencies = self.remote.includes and self.remote.sync_dependencies
        if self.sync_dependencies:
            # Find the allowlist_filter, so we can update it when syncing dependencies
            for fil in self.filters.filter_release_plugins():
                if fil.name == "allowlist_release":
                    self.allow_filter = fil
                    break
            self.already_synced: Dict[str, Set[str]] = defaultdict(set)
            self.dependencies_to_sync: Dict[str, Set[Requirement]] = defaultdict(set)

    async def determine_packages_to_sync(self):
        """
        Calling this means that includes wasn't specified,
        so try to get all of the packages from Mirror (hopefully PyPi)
        """
        number_xmlrpc_attempts = 3
        for attempt in range(number_xmlrpc_attempts):
            logger.info(
                "Attempt {} to get package list from {}".format(
                    attempt, self.master.url
                )
            )
            try:
                if not self.synced_serial:
                    logger.info("Syncing all packages.")
                    # First get the current serial, then start to sync.
                    all_packages = await self.master.all_packages()
                    self.packages_to_sync.update(all_packages)
                    self.target_serial = max(
                        [self.synced_serial] + [int(v) for v in self.packages_to_sync.values()]
                    )
                else:
                    logger.info("Syncing based on changelog.")
                    changed_packages = await self.master.changed_packages(
                        self.synced_serial
                    )
                    self.packages_to_sync.update(changed_packages)
                    self.target_serial = max(
                        [self.synced_serial] + [int(v) for v in self.packages_to_sync.values()]
                    )
                break
            except (ClientError, ClientResponseError, LxmlError):
                # Retry if XMLRPC endpoint failed, server might not support it.
                continue
        else:
            logger.info("Failed to get package list using XMLRPC, trying parse simple page.")
            url = urljoin(self.python_stage.remote.url, "simple/")
            downloader = self.python_stage.remote.get_downloader(url=url)
            result = await downloader.run()
            with open(result.path) as f:
                index = parse_repo_index_page(f.read())
                self.packages_to_sync.update({p: 0 for p in index.projects})
                self.target_serial = result.headers.get(PYPI_LAST_SERIAL, 0)

        self._filter_packages()
        if self.target_serial:
            logger.info(f"Trying to reach serial: {self.target_serial}")
        pkg_count = len(self.packages_to_sync)
        logger.info(f"{pkg_count} packages to sync.")

    async def process_package(self, package):
        """Filters the package and creates content from it"""
        # Don't save anything if our metadata filters all fail.
        await self.progress_report.aincrement()
        if not package.filter_metadata(self.filters.filter_metadata_plugins()):
            return None

        package.filter_all_releases_files(self.filters.filter_release_file_plugins())
        package.filter_all_releases(self.filters.filter_release_plugins())
        await self.create_content(package)

    async def create_content(self, pkg):
        """
        Take the filtered package, separate into releases and
        create a Content Unit to put into the pipeline
        """
        for version, dists in pkg.releases.items():
            if self.sync_dependencies:
                if version in self.already_synced[pkg.name]:
                    continue
                self.already_synced[pkg.name].add(version)

                for req_spec in await self.get_required_dists(pkg, version):
                    req = Requirement(req_spec)
                    req.name = canonicalize_name(req.name)
                    req.specifier.prereleases = True
                    if req.marker:
                        if "extra == " in str(req.marker):
                            # Only sync the required dependency if we specified the correct 'extra'
                            extras = set()
                            for cur_allow_pkg in self.allow_filter.allowlist_release_requirements:
                                if cur_allow_pkg.name == pkg.name:
                                    extras |= cur_allow_pkg.extras
                            extra = str(req.marker).rpartition("extra == ")[2].strip("'\"")
                            if extra not in extras:
                                continue

                    self.dependencies_to_sync[req.name].add(req)

            for package in dists:
                entry = parse_metadata(pkg.info, version, package)
                url = entry.pop("url")

                artifact = Artifact(sha256=entry["sha256"])
                package = PythonPackageContent(**entry)

                da = DeclarativeArtifact(
                    artifact=artifact,
                    url=url,
                    relative_path=entry["filename"],
                    remote=self.python_stage.remote,
                    deferred_download=self.deferred_download,
                )
                dc = DeclarativeContent(content=package, d_artifacts=[da])

                await self.python_stage.put(dc)

    def finalize_sync(self, *args, **kwargs):
        """No work to be done currently"""
        pass

    def on_error(self, exception, **kwargs):
        """
        TODO
        This should have some error checking
        """
        pass

    async def get_required_dists(self, pkg, version):
        """Returns a list of required dists from given package version."""
        # TODO: Can this logic live in Bandersnatch?
        url = urljoin(self.remote.url, f"pypi/{pkg.name}/{version}/json")
        downloader = self.remote.get_downloader(url=url)
        try:
            result = await downloader.run()
        except ClientResponseError:
            return []
        else:
            return parse_json(result).get("info", {}).get("requires_dist", []) or []
