import json
import os

from collections import namedtuple
from logging import getLogger
from urllib.parse import urljoin, urlparse

from django.db import models

from pulpcore.plugin.models import (Artifact, Content, Importer, Publisher)

from pulpcore.plugin.changeset import (
    ChangeSet,
    PendingArtifact,
    PendingContent,
    SizedIterable
)

log = getLogger(__name__)

Delta = namedtuple('Delta', ('additions', 'removals'))

PACKAGE_TYPES = (("bdist_dmg", "bdist_dmg"), ("bdist_dumb", "bdist_dumb"),
                 ("bdist_egg", "bdist_egg"), ("bdist_msi", "bdist_msi"),
                 ("bdist_rpm", "bdist_rpm"), ("bdist_wheel", "bdist_wheel"),
                 ("bdist_wininst", "bdist_wininst"), ("sdist", "sdist"))


class Classifier(models.Model):
    """
    Custom tags for classifier

    Fields:

        name (models.TextField): The name of the classifier

    Relations:

        python_package_content (models.ForeignKey): The PythonPackageContent this classifier
        is associated with.

    """

    name = models.TextField()
    python_package_content = models.ForeignKey("PythonPackageContent", related_name="classifiers",
                                               related_query_name="classifier")


class PythonPackageContent(Content):
    """
    A Content Type representing Python's Distribution Package as
    defined in pep-0426 and pep-0345
    https://www.python.org/dev/peps/pep-0491/
    https://www.python.org/dev/peps/pep-0345/
    """

    TYPE = 'python'
    filename = models.TextField(unique=True, db_index=True, blank=False)
    packagetype = models.TextField(blank=False, choices=PACKAGE_TYPES)
    name = models.TextField(blank=False)
    version = models.TextField(blank=False)
    metadata_version = models.TextField(null=True)
    summary = models.TextField(null=True)
    description = models.TextField(null=True)
    keywords = models.TextField(null=True)
    home_page = models.TextField(null=True)
    download_url = models.TextField(null=True)
    author = models.TextField(null=True)
    author_email = models.TextField(null=True)
    maintainer = models.TextField(null=True)
    maintainer_email = models.TextField(null=True)
    license = models.TextField(null=True)
    requires_python = models.TextField(null=True)
    project_url = models.TextField(null=True)
    platform = models.TextField(null=True)
    supported_platform = models.TextField(null=True)
    requires_dist = models.TextField(default="[]", blank=False)
    provides_dist = models.TextField(default="[]", blank=False)
    obsoletes_dist = models.TextField(default="[]", blank=False)
    requires_external = models.TextField(default="[]", blank=False)


class PythonPublisher(Publisher):
    """
    A Publisher for PythonContent.

    Define any additional fields for your new publisher if needed.
    A ``publish`` method should be defined.
    It is responsible for publishing metadata and artifacts
    which belongs to a specific repository.
    """

    TYPE = 'python'

    def publish(self):
        """
        Publish the repository.
        """
        raise NotImplementedError


class PythonImporter(Importer):
    """
    An Importer for Python Content.

    Attributes:
        projects (list): A list of python projects to sync
    """

    TYPE = 'python'
    projects = models.TextField(null=True)

    def _fetch_inventory(self, version):
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

    def _fetch_remote(self):
        """
        Fetch contentunits available in the remote repository.

        Returns:
            list: of contentunit metadata.
        """
        remote = []

        metadata_urls = [urljoin(self.feed_url, 'pypi/%s/json' % project)
                         for project in json.loads(self.projects)]

        for metadata_url in metadata_urls:
            parsed_url = urlparse(metadata_url)

            download = self.get_futures_downloader(metadata_url, os.path.basename(parsed_url.path))
            download()

            metadata = json.load(open(download.writer.path))
            for version, packages in metadata['releases'].items():
                for package in packages:
                    remote.append(self._parse_metadata(metadata['info'], version, package))

        return remote

    def _find_delta(self, inventory, remote, mirror=False):
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

    def _parse_metadata(cls, project, version, distribution):
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

    def _build_additions(self, additions, remote_metadata):
        """
        Generate the content to be added.

        Returns:
            generator: A generator of content to be added.
        """
        for entry in remote_metadata:
            if(entry['filename'] not in additions):
                continue

            url = entry.pop('url')
            artifact = Artifact(md5=entry.pop('md5_digest'))

            package = PythonPackageContent(**entry)
            content = PendingContent(
                package,
                artifacts={
                    PendingArtifact(model=artifact, url=url, relative_path=entry['filename'])
                })
            yield content

    def _build_removals(self, removals, version):
        """
        Generate the content to be removed.

        Args:
            removals (set): of filenames to remove
            version (pulpcore.plugin.models.RepositoryVersion): of repository to remove contents
                from
        Returns:
            generator: A generator of content to be removed.
        """
        q = models.Q()
        for content_key in removals:
            q |= models.Q(pythonpackagecontent__filename=content_key)
            q_set = version.content().filter(q)
            q_set = q_set.only('id')
            for content in q_set:
                yield content

    def sync(self, new_version, base_version):
        """
        Sync the python projects listed on a :class:`pulp_python.app.models.PythonImporter`
        from a remote repository

        Args:
            new_version (pulpcore.plugin.models.RepositoryVersion): the new version to which
                content should be added and removed.
            base_version (pulpcore.plugin.models.RepositoryVersion): the targeted pre-existing
                version or None if one does not exist.

        """

        inventory = self._fetch_inventory(base_version)
        remote_metadata = self._fetch_remote()
        remote_keys = set([content['filename'] for content in remote_metadata])

        mirror = self.sync_mode == 'mirror'
        delta = self._find_delta(inventory=inventory, remote=remote_keys,
                                 mirror=mirror)

        additions = SizedIterable(
            self._build_additions(delta.additions, remote_metadata),
            len(delta.additions))
        removals = SizedIterable(
            self._build_removals(delta.removals, base_version),
            len(delta.removals))
        changeset = ChangeSet(self, new_version, additions=additions, removals=removals)
        changeset.apply_and_drain()
