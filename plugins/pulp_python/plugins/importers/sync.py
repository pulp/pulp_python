"""
This module contains the necessary means for a necessary means for syncing packages from PyPI.
"""
from cStringIO import StringIO
from gettext import gettext as _
import json
import logging
import os
import shutil
from urlparse import urljoin

from nectar import request
from pulp.common.plugins import importer_constants
from pulp.plugins.util import publish_step
from pulp.server.db.model import criteria

from pulp_python.common import constants
from pulp_python.plugins import models


_logger = logging.getLogger(__name__)


class DownloadMetadataStep(publish_step.DownloadStep):
    """
    This DownloadStep subclass contains the code to process the downloaded manifests and decide what
    to download from the feed. It does this as it gets each metadata file to spread the load on the
    database.
    """

    def download_failed(self, report):
        """
        This method is called by Nectar when we were unable to download the metadata file for a
        particular Python package. It closes the StringIO that we were using to store the download
        to free memory.

        :param report: The report that details the download
        :type  report: nectar.report.DownloadReport
        """
        report.destination.close()

        super(DownloadMetadataStep, self).download_failed(report)

    def download_succeeded(self, report):
        """
        This method is called by Nectar for each package metadata file after it is successfully
        downloaded. It reads the manifest, and queries Pulp to find out which packages need to be
        downloaded. It will add any packages that need to be downloaded to the SyncStep's
        _packages_to_download attribute. Each package to download is a dictionary with the following
        keys: name, version, url, and checksum. Each key indexes a basestring, and the checksum is
        an md5 checksum as provided by PyPI.

        :param report: The report that details the download
        :type  report: nectar.report.DownloadReport
        """
        _logger.info(_('Processing metadata retrieved from %(url)s.') % {'url': report.url})
        report.destination.seek(0)
        self.parent.parent._packages_to_download.extend(
            self._process_manifest(report.destination.read(), self.conduit))
        report.destination.close()

        super(DownloadMetadataStep, self).download_succeeded(report)

    @staticmethod
    def _process_manifest(manifest, conduit):
        """
        This method reads the given package manifest to determine which versions of the package are
        available at the feed repo. It then compares these versions to the versions that are in the
        repository that is being synchronized, as well as to the versions that are available in
        Pulp. For packages that are in Pulp but are not in the repository, it will create the
        association without downloading the packages. For package versions which are not available
        in Pulp, it will return a list of dictionaries describing the missing packages so that the
        DownloadPackagesStep can retrieve them later. Each dictionary has the following keys: name,
        version, url, and checksum. The checksum is given in md5, as per the upstream PyPI feed.

        :param manifest: A package manifest in JSON format, describing the versions of a package
                         that are available for download.
        :type  manifest: basestring
        :param conduit:  The sync conduit. This is used to query Pulp for available packages.
        :type  conduit:  pulp.plugins.conduits.repo_sync.RepoSyncConduit
        :return:         A list of dictionaries, describing the packages that need to be downloaded.
        :rtype:          list
        """
        manifest = json.loads(manifest)
        name = manifest['info']['name']
        all_versions = set(manifest['releases'].keys())

        # Find the versions that we have in Pulp
        search = criteria.Criteria(filters={'name': name}, fields=['name', 'version'])
        versions_in_pulp = set(
            [u.unit_key['version'] for u in
             conduit.search_all_units(constants.PACKAGE_TYPE_ID, criteria=search)])

        # Find the versions that we have in the repo already
        search = criteria.UnitAssociationCriteria(unit_filters={'name': name},
                                                  unit_fields=['name', 'version'])
        versions_in_repo = set([u.unit_key['version'] for u in
                                conduit.get_units(criteria=search)])

        # These versions are in Pulp, but are not associated with this repository. Associate them.
        versions_to_associate = list(versions_in_pulp - versions_in_repo)
        if versions_to_associate:
            conduit.associate_existing(
                constants.PACKAGE_TYPE_ID,
                [{'name': name, 'version': v} for v in versions_to_associate])

        # We don't have these versions in Pulp yet. Let's download them!
        versions_to_dl = all_versions - versions_in_pulp
        packages_to_dl = []
        for v in versions_to_dl:
            for package in manifest['releases'][v]:
                if package['packagetype'] == 'sdist' and package['filename'][-4:] != '.zip':
                    packages_to_dl.append({'name': name, 'version': v, 'url': package['url'],
                                           'checksum': package['md5_digest']})
        return packages_to_dl


class DownloadPackagesStep(publish_step.DownloadStep):
    """
    This DownloadStep retrieves the packages from the feed, processes each package for its metadata,
    and adds the unit to the repository in Pulp.
    """

    def download_succeeded(self, report):
        """
        This method processes a downloaded Python package. It opens the package and reads its
        PKG-INFO metadata file to determine all of its metadata. This step can be slow for larger
        packages since it needs to decompress them to do this. Despite it being slower to do this
        than it would be to read the metadata from the metadata file we downloaded earlier, we do
        not get the metadata for older versions from that file. Thus, this is the only reliable way
        to represent the metadata for different versions of a package. It also has the benefit of
        code reuse for determining the metadata, as the upload code also acquires the metadata this
        way.

        This method also ensures that the checksum of the downloaded package matches the checksum
        that was listed in the manifest. If everything checks out, the package is added to the
        repository and moved to the proper storage path.

        :param report: The report that details the download
        :type  report: nectar.report.DownloadReport
        """
        _logger.info(_('Processing package retrieved from %(url)s.') % {'url': report.url})

        checksum = models.Package.checksum(report.destination, 'md5')
        if checksum != report.data['checksum']:
            report.state = 'failed'
            report.error_report = {'expected_checksum': report.data['checksum'],
                                   'actual_checksum': checksum}
            return self.download_failed(report)

        package = models.Package.from_archive(report.destination)
        package.init_unit(self.conduit)

        # Move the package into its proper place
        shutil.move(report.destination, package.storage_path)

        package.save_unit(self.conduit)

        super(DownloadPackagesStep, self).download_succeeded(report)


class GetMetadataStep(publish_step.PluginStep):
    """
    This step creates all the required download requests for each package that the user has asked us
    to synchronize.
    """

    def __init__(self, repo, conduit, config, working_dir):
        """
        Initialize the GetMetadataStep, adding a child step that actually does the Metadata
        downloading and processing.

        :param repo:        metadata describing the repository
        :type  repo:        pulp.plugins.model.Repository
        :param conduit:     provides access to relevant Pulp functionality
        :type  conduit:     pulp.plugins.conduits.repo_sync.RepoSyncConduit
        :param config:      plugin configuration
        :type  config:      pulp.plugins.config.PluginCallConfiguration
        :param working_dir: The working directory path that can be used for temporary storage
        :type  working_dir: basestring
        """
        super(GetMetadataStep, self).__init__('sync_step_metadata', repo, conduit, config,
                                              working_dir, constants.IMPORTER_TYPE_ID)
        self.description = _('Downloading and processing metadata.')

        # This step does the real work
        self.add_child(
            DownloadMetadataStep(
                'sync_step_download_metadata', downloads=self.generate_download_requests(),
                repo=repo, config=config, conduit=conduit, working_dir=working_dir,
                description=_('Downloading Python metadata.')))

    def generate_download_requests(self):
        """
        For each package name that the user has requested, yield a Nectar DownloadRequest for its
        metadata file in JSON format.

        :return: A generator that yields DownloadReqests for the metadata files.
        :rtype:  generator
        """
        # We need to retrieve the manifests for each of our packages
        manifest_urls = [urljoin(self.parent._feed_url, 'pypi/%s/json/' % pn)
                         for pn in self.parent._package_names]
        for u in manifest_urls:
            yield request.DownloadRequest(u, StringIO(), {})


class SyncStep(publish_step.PluginStep):
    """
    This Step is the top level step in this module. It arranges all the other necessary steps for
    a Python repository sync.
    """

    def __init__(self, repo, conduit, config, working_dir):
        """
        Initialize the SyncStep, adding the appropriate child steps.

        :param repo:        metadata describing the repository
        :type  repo:        pulp.plugins.model.Repository
        :param conduit:     provides access to relevant Pulp functionality
        :type  conduit:     pulp.plugins.conduits.repo_sync.RepoSyncConduit
        :param config:      plugin configuration
        :type  config:      pulp.plugins.config.PluginCallConfiguration
        :param working_dir: The working directory path that can be used for temporary storage
        :type  working_dir: basestring
        """
        super(SyncStep, self).__init__('sync_step_main', repo, conduit, config, working_dir,
                                       constants.IMPORTER_TYPE_ID)
        self.description = _('Synchronizing %(id)s repository.') % {'id': repo.id}

        self._feed_url = config.get(importer_constants.KEY_FEED)
        self._package_names = config.get(constants.CONFIG_KEY_PACKAGE_NAMES, [])
        if self._package_names:
            self._package_names = self._package_names.split(',')

        # Populated by the GetMetadataStep
        self._packages_to_download = []

        self.add_child(GetMetadataStep(repo, conduit, config, working_dir))

        self.add_child(
            DownloadPackagesStep(
                'sync_step_download_packages', downloads=self.generate_download_requests(),
                repo=repo, config=config, conduit=conduit, working_dir=working_dir,
                description=_('Downloading and processing Python packages.')))

    def generate_download_requests(self):
        """
        For each package that is listed in self._packages_to_download, yield a Nectar
        DownloadRequest for its url attribute.

        :return: A generator that yields DownloadReqests for the Package files.
        :rtype:  generator
        """
        for p in self._packages_to_download:
            yield request.DownloadRequest(p['url'], os.path.join(self.working_dir,
                                                                 os.path.basename(p['url'])), p)

    def sync(self):
        """
        Perform the repository synchronization.

        :return: The final sync report.
        :rtype:  pulp.plugins.model.SyncReport
        """
        self.process_lifecycle()
        return self._build_final_report()
