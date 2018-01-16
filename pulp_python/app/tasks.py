from collections import namedtuple
from contextlib import contextmanager, suppress
import json

from gettext import gettext as _
from urllib.parse import urljoin, urlparse
import logging
import os

from celery import shared_task
from django.db import transaction
from django.db.models import Q
from pulpcore.plugin import models
from pulpcore.plugin.tasks import working_dir_context, UserFacingTask

from pulpcore.plugin.changeset import (
    ChangeSet,
    PendingArtifact,
    PendingContent,
    SizedIterable,
)

from pulp_python.app import models as python_models
# from pulp_python.manifest import Manifest

log = logging.getLogger(__name__)


# Natural key.
Delta = namedtuple('Delta', ('additions', 'removals'))


class repository_version_context:
    """
    """
    def __init__(self, importer):
        self.importer = importer

        self.base_version = None
        with suppress(models.RepositoryVersion.DoesNotExist):
            self.base_version = self.importer.repository.versions.exclude(complete=False).latest()

        with transaction.atomic():
            self.new_version = models.RepositoryVersion(repository=self.importer.repository)
            self.new_version.number = self.importer.repository.last_version + 1
            self.importer.repository.last_version = self.new_version.number
            self.new_version.save()
            self.importer.repository.save()

    def __enter__(self):
           return self

    def __exit__(self, exc_type, exc_val, traceback):
        # Exceptions are reraised by the context manager by default.
        if exc_val:
            self.new_version.delete()
            return
        else:
            with transaction.atomic():
                self.new_version.complete = True
                self.new_version.save()
                self.created_resource = models.CreatedResource(content_object=self.new_version)
                self.created_resource.save()
            return True


@shared_task(base=UserFacingTask)
def sync(importer_pk):
    importer = python_models.PythonImporter.objects.get(pk=importer_pk)

    with repository_version_context(importer) as rv:
        # import rpdb
        # rpdb.set_trace()
        with working_dir_context():
            log.info(
                _('Creating RepositoryVersion: repository=%(repository)s importer=%(importer)s'),
                {
                    'repository': importer.repository.name,
                    'importer': importer.name
                })
            inventory = _fetch_inventory(rv.base_version)
            remote_metadata = _fetch_remote(importer)
            remote_keys = set([content['filename'] for content in remote_metadata])

            mirror = importer.sync_mode == 'mirror'
            delta = _find_delta(inventory=inventory, remote=remote_keys,
                                mirror=mirror)
            additions = SizedIterable(
                _build_additions(delta.additions, remote_metadata),
                len(delta.additions))
            removals = SizedIterable(
                _build_removals(delta.removals, rv.base_version),
                len(delta.removals))
            changeset = ChangeSet(importer, rv.new_version, additions=additions, removals=removals)
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
    if version is not None:
        q_set = version.content()
        if q_set:
            for content in (c.cast() for c in q_set):
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
        parsed_url = urlparse(metadata_url)

        download = importer.get_futures_downloader(metadata_url, os.path.basename(parsed_url.path))
        download()

        metadata = json.load(open(download.writer.path))
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


def _build_additions(additions, remote_metadata):
    """
    Generate the content to be added.

    Returns:
        generator: A generator of content to be added.
    """
    for entry in remote_metadata:
        if(entry['filename'] not in additions):
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


def _build_removals(removals, version):
    """
    Generate the content to be removed.

    Args:
        removals (set): of filenames to remove
        version (pulpcore.plugin.models.RepositoryVersion): of repository to remove contents
            from
    Returns:
        generator: A generator of content to be removed.
    """
    q = Q()
    for content_key in removals:
        q |= Q(pythonpackagecontent__filename=content_key)
        q_set = version.content().filter(q)
        q_set = q_set.only('id')
        for content in q_set:
            yield content
