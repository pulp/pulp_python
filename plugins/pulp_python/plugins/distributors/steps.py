import collections
from gettext import gettext as _
import itertools
import json
import logging
import os
from xml.etree import cElementTree as ElementTree

import pkg_resources
from pulp.plugins.util.publish_step import AtomicDirectoryPublishStep, PluginStep
from pulp.server.controllers import repository as repo_controller

from pulp_python.common import constants
from pulp_python.plugins import models
from pulp_python.plugins.distributors import configuration


logger = logging.getLogger(__name__)


class PublishContentStep(PluginStep):
    """
    Publish Content
    """

    def __init__(self):
        """
        Initialize the PublishContentStep.
        """
        super(PublishContentStep, self).__init__(constants.PUBLISH_STEP_CONTENT)
        self.context = None
        self.redirect_context = None
        self.description = _('Publishing Python Content.')

    def process_main(self):
        """
        Publish all the python files themselves by creating the symlinks to the storage paths.
        """
        for name, packages in _get_projects(self.get_conduit().repo_id).items():
            for package in packages:
                relative_path = _get_package_path(name, package['filename'])
                symlink_path = os.path.join(self.parent.web_working_dir, relative_path)
                if not os.path.exists(os.path.dirname(symlink_path)):
                    os.makedirs(os.path.dirname(symlink_path))
                os.symlink(package['storage_path'], symlink_path)


class PublishMetadataStep(PluginStep):
    """
    Publish Metadata (refs, branch heads, etc)
    """

    def __init__(self):
        """
        Initialize the PublishMetadataStep.
        """
        super(PublishMetadataStep, self).__init__(constants.PUBLISH_STEP_METADATA)
        self.context = None
        self.redirect_context = None
        self.description = _('Publishing Python Metadata.')

    def process_main(self):
        """
        Publish all the python metadata.
        """
        # Make the simple/ directory and put the correct index.html in it
        simple_path = os.path.join(self.parent.web_working_dir, 'simple')
        api_path = os.path.join(self.parent.web_working_dir, 'pypi')
        os.makedirs(simple_path)
        simple_index_path = os.path.join(simple_path, 'index.html')

        projects = _get_projects(self.get_conduit().repo_id)

        with open(simple_index_path, 'w') as index:
            html = ElementTree.Element('html')
            head = ElementTree.SubElement(html, 'head')
            title = ElementTree.SubElement(head, 'title')
            title.text = 'Simple Index'
            ElementTree.SubElement(head, 'meta', {'name': 'api-version', 'value': '2'})
            body = ElementTree.SubElement(html, 'body')
            # For each package, we need to make a reference in index.html and also make a directory
            # with its own index.html for the package
            for name, packages in projects.items():
                element = ElementTree.SubElement(body, 'a', {'href': name})
                element.text = name
                ElementTree.SubElement(body, 'br')
                PublishMetadataStep._create_package_index(name, simple_path, packages)

            index.write(ElementTree.tostring(html, 'utf8'))

        for name, packages in projects.items():
            project_metadata_path = os.path.join(api_path, name, 'json')
            os.makedirs(project_metadata_path)
            project_index_metadata_path = os.path.join(project_metadata_path, 'index.json')
            with open(project_index_metadata_path, 'w') as meta_json:
                data = PublishMetadataStep._create_metadata(name, packages)
                meta_json.write(json.dumps(data))

    @staticmethod
    def _create_package_index(name, simple_path, packages):
        """
        Create a folder in simple_path named after the package, and then create a package index
        file in that path.

        :param name:        The name of the package
        :type  name:        basestring
        :param simple_path: The path to the simple/ publish folder
        :type  simple_path: basestring
        :param packages:    A list of dictionaries of the form
                            {'version': VERSION, 'filename': FILENAME, 'checksum': MD5SUM,
                             'checksum_type': TYPE}.
        :type  packages:    list
        """
        # Now we need a subfolder for this package with its own index
        package_path = os.path.join(simple_path, name)
        os.makedirs(package_path)
        package_index_path = os.path.join(package_path, 'index.html')
        with open(package_index_path, 'w') as package_index:
            html = ElementTree.Element('html')
            head = ElementTree.SubElement(html, 'head')
            title = ElementTree.SubElement(head, 'title')
            title.text = 'Links for %s' % name
            ElementTree.SubElement(head, 'meta', {'name': 'api-version', 'value': '2'})
            body = ElementTree.SubElement(html, 'body')
            heading = ElementTree.SubElement(body, 'h1')
            heading.text = title.text
            for package in packages:
                href = '../../%s#%s=%s' % (_get_package_path(name, package['filename']),
                                           package['checksum_type'], package['checksum'])
                node = ElementTree.SubElement(body, 'a', {'href': href, 'rel': 'internal'})
                node.text = package['filename']
                ElementTree.SubElement(body, 'br')

            package_index.write(ElementTree.tostring(html, 'utf8'))

    @staticmethod
    def _create_metadata(name, packages):
        """
        Generate json metadata for the project and its packages.

        The structure of the data is designed to mimic the json api of PyPI. The data will be
        for a single Python project (eg. SciPy). The inner dictionary 'info' specifies details of
        the project that should be applicable for all packages. The inner dictionary 'releases'
        contains keys for each version and the value is a list of dictionaries, each representing
        the metadata for a single package of that version.

        More information on the PyPI API can be found here: https://wiki.python.org/moin/PyPIJSON

        :param name: Name of the project
        :type  name: basestring
        :param packages: metadata for each package of the project
        :type  packages: list of dicts
        :return: metadata for all packages of the project
        :rtype:  dict
        """
        info = {'name': name}
        releases = collections.defaultdict(list)
        # For all versions, version > None is True
        latest_version = None

        for package in packages:

            # info dict applies to all packages in this project, populated from the latest release.
            version = package['version']
            parsed_version = pkg_resources.parse_version(version)
            if parsed_version > latest_version:
                info['author'] = package['author'],
                info['summary'] = package['summary'],
                latest_version = parsed_version

            href = '../../../%s#%s=%s' % (_get_package_path(name, package['filename']),
                                          package['checksum_type'], package['checksum'])

            # package data is specific to an individual file
            package_data = {
                'filename': package['filename'],
                'packagetype': package['packagetype'],
                'url': href,
                'md5_digest': package['md5_digest'],
            }
            releases[version].append(package_data)

        return {'info': info, 'releases': releases}


class PythonPublisher(PluginStep):
    """
    Publisher class that is responsible for the actual publishing
    of a repository via a web server.
    """

    def __init__(self, repo, publish_conduit, config):
        """
        :param repo:            Pulp managed Python repository
        :type  repo:            pulp.plugins.model.Repository
        :param publish_conduit: Conduit providing access to relative Pulp functionality
        :type  publish_conduit: pulp.plugins.conduits.repo_publish.RepoPublishConduit
        :param config:          Pulp configuration for the distributor
        :type  config:          pulp.plugins.config.PluginCallConfiguration
        """
        super(PythonPublisher, self).__init__(constants.PUBLISH_STEP_PUBLISHER,
                                              repo, publish_conduit, config)

        publish_dir = configuration.get_web_publish_dir(repo, config)
        if not os.path.exists(self.get_working_dir()):
            os.makedirs(self.get_working_dir())
        self.web_working_dir = os.path.join(self.get_working_dir(), repo.id)
        master_publish_dir = configuration.get_master_publish_dir(repo, config)
        atomic_publish_step = AtomicDirectoryPublishStep(self.get_working_dir(),
                                                         [(repo.id, publish_dir)],
                                                         master_publish_dir,
                                                         step_type=constants.PUBLISH_STEP_OVER_HTTP)
        atomic_publish_step.description = _('Making files available via web.')

        self.add_child(PublishMetadataStep())
        self.add_child(PublishContentStep())
        self.add_child(atomic_publish_step)


def _get_package_path(name, filename):
    """
    Return a relative URL from the repo directory to the package symlink.

    :param name:     The name of the package
    :type  name:     basestring
    :param filename: The filename of the package
    :type  filename: basestring
    :return:         The relative path within the working directory where the package symlink
                     should be placed.
    :rtype:          basestring
    """
    return os.path.join('packages', 'source', name[0], name, filename)


def _get_projects(repo_id):
    """
    Build and return a data structure of the available projects. The keys each index a list of
    dictionaries. The inner dictionaries are of the form
    {'version': VERSION, 'filename': FILENAME, 'checksum': MD5SUM, 'checksum_type': TYPE,
     'storage_path': PATH}

    :param repo_id: ID of the repo being published.
    :type  repo_id: basestring
    :return:        A dictionary of all the packages in the repo to be published
    :rtype:         dict
    """
    fields = ('filename', 'url', 'packagetype', 'md5_digest', '_checksum', '_checksum_type',
              'version', 'name', 'author', '_storage_path')
    packages = {}
    unit_querysets = repo_controller.get_unit_model_querysets(repo_id, models.Package)
    unit_querysets = (q.only(*fields) for q in unit_querysets)

    for pac in itertools.chain(*unit_querysets):
        packages.setdefault(pac.name, []).append({
            'filename': pac.filename,
            'name': pac.name,
            'url': pac.url,
            'packagetype': pac.packagetype,
            'md5_digest': pac.md5_digest,
            'checksum_type': pac._checksum_type,
            'version': pac.version,
            'author': pac.author,
            'summary': pac.summary,
            'checksum': pac._checksum,
            'storage_path': pac.storage_path,
        })

    return packages
