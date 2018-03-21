import json
import logging

from collections import namedtuple
from gettext import gettext as _
from urllib.parse import urljoin

from celery import shared_task
from django.db.models import Q
from rest_framework import serializers

from pulpcore.plugin import models
from pulpcore.plugin.changeset import (
    BatchIterator,
    ChangeSet,
    PendingArtifact,
    PendingContent,
    SizedIterable,
)
from pulpcore.plugin.tasking import WorkingDirectory, UserFacingTask

from pulp_python.app import models as python_models


log = logging.getLogger(__name__)


Delta = namedtuple('Delta', ('additions', 'removals'))


@shared_task(base=UserFacingTask)
def sync(importer_pk, repository_pk):
    importer = python_models.PythonImporter.objects.get(pk=importer_pk)
    repository = models.Repository.objects.get(pk=repository_pk)

    if not importer.feed_url:
        raise serializers.ValidationError(
            detail=_("An importer must have a feed_url attribute to sync."))

    base_version = models.RepositoryVersion.latest(repository)

    with models.RepositoryVersion.create(repository) as new_version:
        with WorkingDirectory():
            log.info(
                _('Creating RepositoryVersion: repository={repository} importer={importer}')
                .format(repository=repository.name, importer=importer.name)
            )

            inventory = _fetch_inventory(base_version)
            remote_metadata = _fetch_remote(importer)
            remote_keys = set([content['filename'] for content in remote_metadata])

            mirror = importer.sync_mode == 'mirror'
            delta = _find_delta(inventory=inventory, remote=remote_keys, mirror=mirror)

            additions = _build_additions(delta, remote_metadata)
            removals = _build_removals(delta, base_version)
            changeset = ChangeSet(importer, new_version, additions=additions, removals=removals)
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


def _fetch_remote(importer):
    """
    Fetch contentunits available in the remote repository.

    Returns:
        list: of contentunit metadata.
    """
    remote = []

    metadata_urls = [urljoin(importer.feed_url, 'pypi/%s/json' % project)
                     for project in json.loads(importer.projects)]

    for metadata_url in metadata_urls:
        downloader = importer.get_downloader(metadata_url)
        downloader.fetch()

        metadata = json.load(open(downloader.path))
        for version, packages in metadata['releases'].items():
            for package in packages:
                remote.append(_parse_metadata(metadata['info'], version, package))

    return remote


def _find_delta(inventory, remote, mirror=False):
    """
    Using the existing and remote set of filenames, determine the set of content to be
    added and deleted from the repository.

    Parameters:
        inventory (set): existing natural keys (filename) of content associated
            with the repository
        remote (set): metadata keys (filename) of packages on the remote index
        mirror (bool): When true, any content removed from remote repository is added to
            the delta.removals. When false, delta.removals is an empty set.

    Returns:
        Delta (namedtuple): tuple of content to add, and content to remove from the repository
    """

    additions = remote - inventory
    removals = inventory - remote if mirror else set()

    return Delta(additions=additions, removals=removals)


def _parse_metadata(project, version, distribution):
    """
    Create a dictionary of metadata needed to create a PythonContentUnit from
    the project, version, and distribution metadata

    Args:
        project (dict): of metadata relevant to the entire Python project
        version (string): version of distribution
        distribution (dict): of metadata of a single Python distribution

    Returns:
        dictionary: of useful python metadata
    """

    package = {}

    package['filename'] = distribution['filename']
    package['packagetype'] = distribution['packagetype']
    package['name'] = project['name']
    package['version'] = version
    package['metadata_version'] = project.get('metadata_version')
    package['summary'] = project.get('summary')
    package['description'] = project.get('description')
    package['keywords'] = project.get('keywords')
    package['home_page'] = project.get('home_page')
    package['download_url'] = project.get('download_url')
    package['author'] = project.get('author')
    package['author_email'] = project.get('author_email')
    package['maintainer'] = project.get('maintainer')
    package['maintainer_email'] = project.get('maintainer_email')
    package['license'] = project.get('license')
    package['requires_python'] = project.get('requires_python')
    package['project_url'] = project.get('project_url')
    package['platform'] = project.get('platform')
    package['supported_platform'] = project.get('supported_platform')
    package['requires_dist'] = json.dumps(project.get('requires_dist', []))
    package['provides_dist'] = json.dumps(project.get('provides_dist', []))
    package['obsoletes_dist'] = json.dumps(project.get('obsoletes_dist', []))
    package['requires_external'] = json.dumps(project.get('requires_external', []))
    package['url'] = distribution['url']
    package['md5_digest'] = distribution['md5_digest']

    return package


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
            artifact = models.Artifact(md5=entry.pop('md5_digest'))

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
