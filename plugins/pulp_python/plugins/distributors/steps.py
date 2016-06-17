import collections
from gettext import gettext as _
import json
import logging
import os
from xml.etree import cElementTree as ElementTree

from pulp.plugins.util.publish_step import AtomicDirectoryPublishStep, PluginStep

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
        repo_id = self.get_conduit().repo_id
        for package in models.Package.objects.packages_in_repo(repo_id):
            symlink_path = os.path.join(self.parent.web_working_dir, 'packages', package.src_path)
            if not os.path.exists(os.path.dirname(symlink_path)):
                os.makedirs(os.path.dirname(symlink_path))
            os.symlink(package.storage_path, symlink_path)


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
        repo_id = self.get_conduit().repo_id
        projects = models.Package.objects.packages_by_project(repo_id)
        self.write_simple_api(projects)
        self.write_json_api(projects)

    def write_simple_api(self, projects):
        """
        Create a master index that contains references to the index of each project.

        The structure of the data is designed to mimic the simple api of PyPI. The data will be
        for all Python projects in the repository.

        More information about this API can be found here: https://wiki.python.org/moin/PyPISimple

        :param projects: keys are project names, values are packages of that name
        :type  projects: dict
        """
        simple_path = os.path.join(self.parent.web_working_dir, 'simple')
        simple_index_path = os.path.join(simple_path, 'index.html')
        os.makedirs(simple_path)
        with open(simple_index_path, 'w') as index:
            html = ElementTree.Element('html')
            head = ElementTree.SubElement(html, 'head')
            title = ElementTree.SubElement(head, 'title')
            title.text = 'Simple Index'
            ElementTree.SubElement(head, 'meta', {'name': 'api-version', 'value': '2'})
            body = ElementTree.SubElement(html, 'body')
            # Create a reference in index.html that points to the index for each project.
            for project_name, packages in projects.items():
                element = ElementTree.SubElement(body, 'a', {'href': project_name})
                element.text = project_name
                ElementTree.SubElement(body, 'br')
                PublishMetadataStep._create_project_index(project_name, simple_path, packages)

            index.write(ElementTree.tostring(html, 'utf8'))

    @staticmethod
    def _create_project_index(project_name, simple_path, packages):
        """
        Create a project index.html in a project subdirectory that contains references to each
        package of the project.

        :param project_name: The name of the project
        :type  project_name: basestring
        :param simple_path: The path to the simple publish directory
        :type  simple_path: basestring
        :param packages: A list of packages
        :type  packages: list of pulp_python.plugins.models.Package
        """
        project_path = os.path.join(simple_path, project_name)
        os.makedirs(project_path)
        package_index_path = os.path.join(project_path, 'index.html')
        with open(package_index_path, 'w') as package_index:
            html = ElementTree.Element('html')
            head = ElementTree.SubElement(html, 'head')
            title = ElementTree.SubElement(head, 'title')
            title.text = 'Links for %s' % project_name
            ElementTree.SubElement(head, 'meta', {'name': 'api-version', 'value': '2'})
            body = ElementTree.SubElement(html, 'body')
            heading = ElementTree.SubElement(body, 'h1')
            heading.text = title.text
            for package in packages:
                href = '../../packages/%s' % package.checksum_url
                node = ElementTree.SubElement(body, 'a', {'href': href, 'rel': 'internal'})
                node.text = package['filename']
                ElementTree.SubElement(body, 'br')

            package_index.write(ElementTree.tostring(html, 'utf8'))

    def write_json_api(self, projects):
        """
        Create a json file for each project in the repository.

        The structure of the data is designed to mimic the json api of PyPI. The data will be
        for a single Python project (eg. SciPy). The inner dictionary 'info' specifies details of
        the project that should be applicable for all packages. The inner dictionary 'releases'
        contains keys for each version and the value is a list of dictionaries, each representing
        the metadata for a single package of that version.

        More information on the PyPI API can be found here: https://wiki.python.org/moin/PyPIJSON

        :param projects: keys are project names, values are lists of packages of that project
        :type  projects: dict
        """
        api_path = os.path.join(self.parent.web_working_dir, 'pypi')
        for project_name, packages in projects.items():
            project_metadata_path = os.path.join(api_path, project_name, 'json')
            os.makedirs(project_metadata_path)
            project_index_metadata_path = os.path.join(project_metadata_path, 'index.json')
            with open(project_index_metadata_path, 'w') as project_json:
                data = PublishMetadataStep._create_project_metadata(project_name, packages)
                project_json.write(json.dumps(data))

    @staticmethod
    def _create_project_metadata(name, packages):
        """
        Generate metadata for the project and each of its packages.

        :param name: Name of the project
        :type  name: basestring
        :param packages: list of package to include
        :type  packages: list of pulp_python.plugins.models.Package
        :return: metadata for the project and all of its packages
        :rtype:  dict
        """
        releases = collections.defaultdict(list)
        latest_version = None

        for package in packages:
            releases[package.version].append(package.package_specific_metadata)

            # For all versions, version > None is True
            if package.parsed_version > latest_version:
                # Project level metadata is populated by the latest package
                info = package.project_metadata
                latest_version = package.parsed_version

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
