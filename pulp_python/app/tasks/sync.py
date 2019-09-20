import collections
import json
import logging

from gettext import gettext as _
from urllib.parse import urljoin

from aiohttp.client_exceptions import ClientResponseError
from packaging import specifiers
from rest_framework import serializers

from pulpcore.plugin.models import Artifact, ProgressReport, Remote, Repository
from pulpcore.plugin.stages import (
    DeclarativeArtifact,
    DeclarativeContent,
    DeclarativeVersion,
    Stage
)

from pulp_python.app.models import (
    ProjectSpecifier,
    PythonPackageContent,
    PythonRemote,
)
from pulp_python.app.utils import parse_metadata

log = logging.getLogger(__name__)


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
            detail=_("A remote must have a url attribute to sync."))

    first_stage = PythonFirstStage(remote)
    DeclarativeVersion(first_stage, repository, mirror).create()


class PythonFirstStage(Stage):
    """
    First stage of the Asyncio Stage Pipeline.

    Create a :class:`~pulpcore.plugin.stages.DeclarativeContent` object for each content unit
    that should exist in the new :class:`~pulpcore.plugin.models.RepositoryVersion`.
    """

    def __init__(self, remote):
        """
        The first stage of a pulp_python sync pipeline.

        Args:
            remote (PythonRemote): The remote data to be used when syncing

        """
        super().__init__()
        self.remote = remote

    async def run(self):
        """
        Build and emit `DeclarativeContent` from the remote metadata.

        Fetch and parse the remote metadata, use the Project Specifiers on the Remote
        to determine which Python packages should be synced.

        Args:
            in_q (asyncio.Queue): Unused because the first stage doesn't read from an input queue.
            out_q (asyncio.Queue): The out_q to send `DeclarativeContent` objects to.

        """
        ps = ProjectSpecifier.objects.filter(remote=self.remote)

        deferred_download = (self.remote.policy != Remote.IMMEDIATE)

        with ProgressReport(message='Fetching Project Metadata', code='fetching.project') as pb:
            # Group multiple specifiers to the same project together, so that we only have to fetch
            # the metadata once, and can re-use it if there are multiple specifiers.
            for name, project_specifiers in groupby_unsorted(ps, key=lambda x: x.name):
                # Fetch the metadata from PyPI
                pb.increment()
                try:
                    metadata = await self.get_project_metadata(name)
                except ClientResponseError as e:
                    # Project doesn't exist, log a message and move on
                    log.info(_("HTTP 404 'Not Found' for url '{url}'\n"
                               "Does project '{name}' exist on the remote repository?").format(
                        url=e.request_info.url,
                        name=name
                    ))
                    continue
                project_specifiers = list(project_specifiers)

                # Determine which packages from the project match the criteria in the specifiers
                packages = await self.get_relevant_packages(
                    metadata=metadata,
                    includes=[
                        specifier for specifier in project_specifiers if not specifier.exclude
                    ],
                    excludes=[
                        specifier for specifier in project_specifiers if specifier.exclude
                    ],
                    prereleases=self.remote.prereleases
                )

                # For each package, create Declarative objects to pass into the next stage
                for entry in packages:
                    url = entry.pop('url')

                    artifact = Artifact(sha256=entry.pop('sha256_digest'))
                    package = PythonPackageContent(**entry)

                    da = DeclarativeArtifact(
                        artifact,
                        url,
                        entry['filename'],
                        self.remote,
                        deferred_download=deferred_download
                    )
                    dc = DeclarativeContent(content=package, d_artifacts=[da])

                    await self.put(dc)

    async def get_project_metadata(self, project_name):
        """
        Get the metadata for a given project name from PyPI.

        Args:
            project_name (str): The name of a project, e.g. "Django".

        Returns:
            dict: Python project metadata from PyPI.

        """
        metadata_url = urljoin(
            self.remote.url, 'pypi/{project}/json'.format(project=project_name)
        )
        downloader = self.remote.get_downloader(url=metadata_url)
        await downloader.run()
        with open(downloader.path) as metadata_file:
            return json.load(metadata_file)

    async def get_relevant_packages(self, metadata, includes, excludes, prereleases):
        """
        Provided project metadata and specifiers, return the matching packages.

        Compare the defined specifiers against the project metadata and create a deduplicated
        list of metadata for the packages matching the criteria.

        Args:
            metadata (dict): Metadata about the project from PyPI.
            includes (iterable): An iterable of project_specifiers for package versions to include.
            excludes (iterable): An iterable of project_specifiers for package versions to exclude.
            prereleases (bool): Whether or not to include pre-release package versions in the sync.

        Returns:
            list: List of dictionaries containing Python package metadata

        """
        # The set of project release metadata, in the format {"version": [package1, package2, ...]}
        releases = metadata['releases']
        # The packages we want to return
        remote_packages = []

        # Delete versions/packages matching the exclude specifiers.
        for exclude_specifier in excludes:
            # Fast path: If one of the specifiers matches all versions and we don't have any
            # digests to reference, clear the whole dict, we're done.
            if not exclude_specifier.version_specifier:
                releases.clear()
                break

            # Slow path: We have to check all the metadata.
            for version, packages in list(releases.items()):  # Prevent iterator invalidation.
                specifier = specifiers.SpecifierSet(
                    exclude_specifier.version_specifier,
                    prereleases=prereleases
                )
                # First check the version specifer, if it matches, check the digests and delete
                # matching packages. If there are no digests, delete them all.
                if specifier.contains(version):
                    del releases[version]

        for version, packages in releases.items():
            for include_specifier in includes:
                # Fast path: If one of the specifiers matches all versions and we don't have any
                # digests to reference, return all of the packages for the version.
                if prereleases and not include_specifier.version_specifier:
                    for package in packages:
                        remote_packages.append(parse_metadata(metadata['info'], version, package))
                    # This breaks the inner loop, e.g. don't check any other include_specifiers.
                    # We want to continue the outer loop.
                    break

                specifier = specifiers.SpecifierSet(
                    include_specifier.version_specifier,
                    prereleases=prereleases
                )

                # First check the version specifer, if it matches, check the digests and include
                # matching packages. If there are no digests, include them all.
                if specifier.contains(version):
                    for package in packages:
                        remote_packages.append(
                            parse_metadata(metadata['info'], version, package)
                        )
        return remote_packages


def groupby_unsorted(seq, key=lambda x: x):
    """
    Group items by a key.

    This function is similar to itertools.groupby() except it doesn't choke when grouping
    non-consecutive items together.

    From: http://code.activestate.com/recipes/580800-groupby-for-unsorted-input/#c1

    Args:
        seq: A sequence
        key: A key function to sort by (default: {lambda x: x})

    Yields:
        Groups in the format tuple(group_key, [*items])

    """
    indexes = collections.defaultdict(list)
    for i, elem in enumerate(seq):
        indexes[key(elem)].append(i)
    for k, idxs in indexes.items():
        yield k, (seq[i] for i in idxs)
