from gettext import gettext as _
import itertools
import logging
import os
from xml.etree import cElementTree as ElementTree

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
        for name, packages in _get_packages(self.get_conduit().repo_id).items():
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
        os.makedirs(simple_path)
        simple_index_path = os.path.join(simple_path, 'index.html')

        packages = _get_packages(self.get_conduit().repo_id)

        with open(simple_index_path, 'w') as index:
            html = ElementTree.Element('html')
            head = ElementTree.SubElement(html, 'head')
            title = ElementTree.SubElement(head, 'title')
            title.text = 'Simple Index'
            ElementTree.SubElement(head, 'meta', {'name': 'api-version', 'value': '2'})
            body = ElementTree.SubElement(html, 'body')
            # For each package, we need to make a reference in index.html and also make a directory
            # with its own index.html for the package
            for name, packages in packages.items():
                element = ElementTree.SubElement(body, 'a', {'href': name})
                element.text = name
                ElementTree.SubElement(body, 'br')
                PublishMetadataStep._create_package_index(name, simple_path, packages)

            index.write(ElementTree.tostring(html, 'utf8'))

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


def _get_packages(repo_id):
    """
    Build and return a data structure of the available packages. The keys each index a list of
    dictionaries. The inner dictionaries are of the form
    {'version': VERSION, 'filename': FILENAME, 'checksum': MD5SUM, 'checksum_type': TYPE,
     'storage_path': PATH}

    :param repo_id: ID of the repo being published.
    :type  repo_id: basestring
    :return:        A dictionary of all the packages in the repo to be published
    :rtype:         dict
    """
    packages = {}
    fields = ('version', 'filename', '_checksum', '_checksum_type', 'name', '_storage_path')
    unit_querysets = repo_controller.get_unit_model_querysets(repo_id, models.Package)
    unit_querysets = (q.only(*fields) for q in unit_querysets)
    for p in itertools.chain(*unit_querysets):
        packages.setdefault(p.name, []).append(
            {'version': p.version,
             'filename': p.filename,
             'checksum': p._checksum,
             'checksum_type': p._checksum_type,
             'storage_path': p.storage_path})
    return packages
