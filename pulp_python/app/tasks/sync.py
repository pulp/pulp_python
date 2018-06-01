import json
import logging

from collections import namedtuple
from gettext import gettext as _
from urllib.parse import urljoin

from django.db.models import Q
from packaging import specifiers
from rest_framework import serializers

from pulpcore.plugin import models
from pulpcore.plugin.changeset import (
    BatchIterator,
    ChangeSet,
    PendingArtifact,
    PendingContent,
    SizedIterable,
)
from pulpcore.plugin.tasking import WorkingDirectory

from pulp_python.app import models as python_models
from pulp_python.app.utils import parse_metadata

log = logging.getLogger(__name__)


Delta = namedtuple('Delta', ('additions', 'removals'))


def sync(remote_pk, repository_pk):
    remote = python_models.PythonRemote.objects.get(pk=remote_pk)
    repository = models.Repository.objects.get(pk=repository_pk)

    if not remote.url:
        raise serializers.ValidationError(
            detail=_("A remote must have a url attribute to sync."))

    base_version = models.RepositoryVersion.latest(repository)

    with models.RepositoryVersion.create(repository) as new_version:
        with WorkingDirectory():
            log.info(
                _('Creating RepositoryVersion: repository={repository} remote={remote}')
                .format(repository=repository.name, remote=remote.name)
            )

            project_specifiers = python_models.ProjectSpecifier.objects.filter(remote=remote).all()

            inventory_keys = _fetch_inventory(base_version)
            remote_metadata = _fetch_specified_metadata(remote, project_specifiers)
            remote_keys = set([content['filename'] for content in remote_metadata])

            delta = _find_delta(inventory=inventory_keys, remote=remote_keys)

            additions = _build_additions(delta, remote_metadata)
            removals = _build_removals(delta, base_version)
            changeset = ChangeSet(remote, new_version, additions=additions, removals=removals)
            changeset.apply_and_drain()


def _fetch_inventory(version):
    """
    Fetch the contentunits in the specified repository version

    Args:
        version (pulpcore.plugin.models.RepositoryVersion): version of repository to fetch
            content units from

    Returns:
        set: of contentunit filenames.
    """
    inventory = set()
    if version:
        for content in python_models.PythonPackageContent.objects.filter(
                pk__in=version.content).only("filename"):
            inventory.add(content.filename)
    return inventory


def _fetch_specified_metadata(remote, project_specifiers):
    """
    Fetch content units matching the project specifiers available in
    the remote repository.

    Returns:
        list: of contentunit metadata.
    """
    remote_units = []
    for project in project_specifiers:

        digests = python_models.DistributionDigest.objects.filter(project_specifier=project)

        metadata_url = urljoin(remote.url, 'pypi/%s/json' % project.name)
        downloader = remote.get_downloader(metadata_url)

        downloader.fetch()

        metadata = json.load(open(downloader.path))
        for version, packages in metadata['releases'].items():
            for package in packages:
                # If neither specifiers nor digests have been set, then we should add the unit
                if not project.version_specifier and not digests.exists():
                    remote_units.append(parse_metadata(metadata['info'], version, package))
                    continue

                specifier = specifiers.SpecifierSet(project.version_specifier)

                # Note: SpecifierSet("").contains(version) will return true for released versions
                # SpecifierSet("").contains('3.0.0') returns True
                # SpecifierSet("").contains('3.0.0b1') returns False
                if specifier.contains(version):

                    # add the package if the project specifier does not have an associated digest
                    if not digests.exists():
                        remote_units.append(parse_metadata(metadata['info'], version, package))

                    # otherwise check each digest to see if it matches the specifier
                    else:
                        for type, digest in package['digests'].items():
                            if digests.filter(type=type, digest=digest).exists():
                                remote_units.append(parse_metadata(metadata['info'],
                                                                   version,
                                                                   package))
                                break
    return remote_units


def _find_delta(inventory, remote):
    """
    Using the existing and remote set of filenames, determine the set of content to be
    added and deleted from the repository.

    Parameters:
        inventory (set): existing natural keys (filename) of content associated
            with the repository
        remote (set): metadata keys (filename) of packages on the remote index

    Returns:
        Delta (namedtuple): tuple of content to add, and content to remove from the repository
    """

    additions = remote - inventory
    removals = inventory - remote

    return Delta(additions=additions, removals=removals)


def _build_additions(delta, remote_metadata):
    """
    Generate the content to be added.

    Args:
        delta (namedtuple): tuple of content to add, and content to remove from the repository
        remote_metadata (list): list of contentunit metadata

    Returns:
        The PythonPackageContent to be added to the repository.
    """
    def generate():
        for entry in remote_metadata:
            if entry['filename'] not in delta.additions:
                continue

            url = entry.pop('url')
            artifact = models.Artifact(sha256=entry.pop('sha256_digest'))

            package = python_models.PythonPackageContent(**entry)
            content = PendingContent(
                package,
                artifacts={
                    PendingArtifact(model=artifact, url=url, relative_path=entry['filename'])
                })
            yield content

    return SizedIterable(generate(), len(delta.additions))


def _build_removals(delta, version):
    """
    Generate the content to be removed.

    Args:
        delta (namedtuple): tuple of content to add, and content to remove from the repository
        version (pulpcore.plugin.models.RepositoryVersion): of repository to remove contents
            from
    Returns:
        The PythonPackageContent to be removed from the repository.
    """
    def generate():
        for removals in BatchIterator(delta.removals):
            q = Q()
            for content_key in removals:
                q |= Q(pythonpackagecontent__filename=content_key)
            q_set = version.content.filter(q)
            q_set = q_set.only('id')
            for content in q_set:
                yield content

    return SizedIterable(generate(), len(delta.removals))
