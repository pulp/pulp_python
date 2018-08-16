import itertools
import json
import logging

from gettext import gettext as _
from urllib.parse import urljoin

from packaging import specifiers
from rest_framework import serializers

from pulpcore.plugin.models import Artifact, ProgressBar, Repository
from pulpcore.plugin.stages import (
    DeclarativeArtifact,
    DeclarativeContent,
    DeclarativeVersion,
    Stage
)

from pulp_python.app.models import (
    DistributionDigest,
    ProjectSpecifier,
    PythonPackageContent,
    PythonRemote,
)
from pulp_python.app.utils import parse_metadata

log = logging.getLogger(__name__)


def sync(remote_pk, repository_pk):
    """
    Sync content from the remote repository.

    Create a new version of the repository that is synchronized with the remote.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.

    Raises:
        serializers: ValidationError

    """
    remote = PythonRemote.objects.get(pk=remote_pk)
    repository = Repository.objects.get(pk=repository_pk)

    if not remote.url:
        raise serializers.ValidationError(
            detail=_("A remote must have a url attribute to sync."))

    first_stage = PythonFirstStage(remote)
    DeclarativeVersion(first_stage, repository).create()


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
        self.remote = remote

    async def __call__(self, in_q, out_q):
        """
        Build and emit `DeclarativeContent` from the remote metadata.

        Fetch and parse the remote metadata, use the Project Specifiers on the Remote
        to determine which Python packages should be synced.

        Args:
            in_q (asyncio.Queue): Unused because the first stage doesn't read from an input queue.
            out_q (asyncio.Queue): The out_q to send `DeclarativeContent` objects to.

        """
        project_specifiers = ProjectSpecifier.objects.filter(remote=self.remote)

        with ProgressBar(message='Fetching Project Metadata') as pb:
            # Group multiple specifiers to the same project together, so that we only have to fetch
            # the metadata once, and can re-use it if there are multiple specifiers.
            for name, project_specifiers in itertools.groupby(project_specifiers,
                                                              key=lambda x: x.name):
                # Fetch the metadata from PyPI
                metadata = await self.get_project_metadata(name)
                pb.increment()

                # Determine which packages from the project match the criteria in the specifiers
                packages = await self.get_relevant_packages(metadata, project_specifiers)

                # For each package, create Declarative objects to pass into the next stage
                for entry in packages:
                    url = entry.pop('url')

                    artifact = Artifact(sha256=entry.pop('sha256_digest'))
                    package = PythonPackageContent(**entry)

                    da = DeclarativeArtifact(artifact, url, entry['filename'], self.remote)
                    dc = DeclarativeContent(content=package, d_artifacts=[da])

                    await out_q.put(dc)
        await out_q.put(None)

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
        downloader = self.remote.get_downloader(metadata_url)
        await downloader.run()
        with open(downloader.path) as metadata_file:
            return json.load(metadata_file)

    async def get_relevant_packages(self, metadata, project_specifiers):
        """
        Provided project metadata and specifiers, return the matching packages.

        Compare the defined specifiers against the project metadata and create a deduplicated
        list of metadata for the packages matching the criteria.

        Args:
            metadata (dict): Metadata about the project from PyPI.
            project_specifiers (iterable): An iterable of project_specifiers.

        Returns:
            list: List of dictionaries containing Python package metadata

        """
        remote_packages = []
        # If there is than one specifier, then there is a possibility that they may overlap,
        # which means we need to do extra checks for deduplication.
        cache = set()

        for project_specifier in project_specifiers:
            digests = DistributionDigest.objects.filter(project_specifier=project_specifier)

            # Happy path! Very speed, much fast!
            # Add all of the packages in the project without any further checks, apart from dedup.
            if not (project_specifier.version_specifier or digests.exists()):
                for version, packages in metadata['releases'].items():
                    for package in packages:
                        # deduplicate
                        if package['filename'] in cache:
                            continue

                        package_metadata = parse_metadata(metadata['info'], version, package)
                        remote_packages.append(package_metadata)
                        cache.add(package['filename'])

                return remote_packages

            # (else) we actually have to check the metadata... :(
            for version, packages in metadata['releases'].items():
                for package in packages:
                    # deduplicate
                    if package['filename'] in cache:
                        continue

                    specifier = specifiers.SpecifierSet(project_specifier.version_specifier)
                    # Note: SpecifierSet("").contains(version) will return True for
                    # released versions
                    # SpecifierSet("").contains('3.0.0') returns True
                    # SpecifierSet("").contains('3.0.0b1') returns False
                    if specifier.contains(version):

                        # add the package if the project specifier does not have an
                        # associated digest
                        if not digests.exists():
                            package_metadata = parse_metadata(metadata['info'], version, package)
                            remote_packages.append(package_metadata)
                            cache.add(package['filename'])

                        # otherwise check each digest to see if it matches the specifier
                        else:
                            for digest_type, digest in package['digests'].items():
                                if digests.filter(type=digest_type, digest=digest).exists():
                                    package_metadata = parse_metadata(
                                        metadata['info'], version, package
                                    )
                                    remote_packages.append(package_metadata)
                                    cache.add(package['filename'])
                                    break
        return remote_packages
