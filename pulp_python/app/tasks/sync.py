import logging

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
from pulp_python.app.utils import parse_metadata

from bandersnatch.mirror import Mirror
from bandersnatch.master import Master
from bandersnatch.configuration import BandersnatchConfig
from packaging.requirements import Requirement

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
        # TODO Change Bandersnatch internal API to take proxy settings in from config parameters
        if self.remote.proxy_url:
            environ['http_proxy'] = self.remote.proxy_url
        # local & global timeouts defaults to 10secs and 5 hours
        async with Master(self.remote.url) as master:
            if self.remote.proxy_url:
                environ.pop('http_proxy')
            deferred_download = self.remote.policy != Remote.IMMEDIATE
            with ProgressReport(
                message="Fetching Project Metadata", code="fetching.project"
            ) as p:
                pmirror = PulpMirror(
                    serial=0,  # Serial currently isn't supported by Pulp
                    master=master,
                    workers=self.remote.download_concurrency,
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
        self.progress_report = progress_report
        self.deferred_download = deferred_download

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
                self._filter_packages()
                logger.info(f"Trying to reach serial: {self.target_serial}")
                pkg_count = len(self.packages_to_sync)
                logger.info(f"{pkg_count} packages to sync.")
                return
            except Exception as e:
                """Handle different exceptions if it is XMLRPC error or Mirror error"""
                logger.info("Encountered an error in Master {}".format(e))
                pass
        """
        If we reach here, then the Mirror most likely doesn't support XMLRPC.
        Could raise an exception or try to manually find all the packages from the index page,
        Or just keep packages_to_sync empty and have the sync do no work
        """

    async def process_package(self, package):
        """Filters the package and creates content from it"""
        # Don't save anything if our metadata filters all fail.
        self.progress_report.increment()
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
            for package in dists:
                entry = parse_metadata(pkg.info, version, package)
                url = entry.pop("url")

                artifact = Artifact(sha256=entry.pop("sha256_digest"))
                package = PythonPackageContent(**entry)

                da = DeclarativeArtifact(
                    artifact,
                    url,
                    entry["filename"],
                    self.python_stage.remote,
                    deferred_download=self.deferred_download,
                )
                dc = DeclarativeContent(content=package, d_artifacts=[da])

                await self.python_stage.put(dc)

    def finalize_sync(self):
        """No work to be done currently"""
        pass

    def on_error(self, exception, **kwargs):
        """
        TODO
        This should have some error checking
        """
        pass
