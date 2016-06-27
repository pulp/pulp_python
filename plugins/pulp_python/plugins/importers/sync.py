"""
This module contains the necessary means for a necessary means for syncing packages from PyPI.
"""
import contextlib
from cStringIO import StringIO
from gettext import gettext as _
import json
import logging
import os
from urlparse import urljoin

import mongoengine
from nectar import request
from pulp.common.plugins import importer_constants
from pulp.plugins.util import publish_step
from pulp.plugins.util.publish_step import GetLocalUnitsStep
from pulp.server.controllers import repository as repo_controller

from pulp_python.common import constants
from pulp_python.plugins import models


_logger = logging.getLogger(__name__)


class DownloadMetadataStep(publish_step.DownloadStep):
    """
    This DownloadStep subclass contains the code to process the downloaded manifests and determine
    what is available from the feed. It does this as it gets each metadata file to spread the load
    on the database.
    """

    def __init__(self, *args, **kwargs):
        """
        Injects download requests into the call to the parent class's __init__
        """
        kwargs['downloads'] = self.generate_download_requests()
        super(DownloadMetadataStep, self).__init__(*args, **kwargs)

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
        downloaded. It reads the manifest and adds each available unit to the parent step's
        "available_units" attribute.

        It also adds each unit's download URL to the parent step's "unit_urls" attribute. Each key
        is a models.Package object.

        :param report: The report that details the download
        :type  report: nectar.report.DownloadReport
        """
        _logger.info(_('Processing metadata retrieved from %(url)s.') % {'url': report.url})
        with contextlib.closing(report.destination) as destination:
            destination.seek(0)
            self._process_manifest(destination.read())

        super(DownloadMetadataStep, self).download_succeeded(report)

    def generate_download_requests(self):
        """
        For each package name that the user has requested, yield a Nectar DownloadRequest for its
        metadata file in JSON format.

        :return: A generator that yields DownloadRequests for the metadata files.
        :rtype:  generator
        """
        # We need to retrieve the manifests for each of our packages
        manifest_urls = [urljoin(self.parent._feed_url, 'pypi/%s/json/' % pn)
                         for pn in self.parent._package_names]
        for u in manifest_urls:
            if self.canceled:
                return
            yield request.DownloadRequest(u, StringIO(), {})

    def _process_manifest(self, manifest):
        """
        This method reads the given package manifest to determine which versions of the package are
        available at the feed repo. It reads the manifest and adds each available unit to the parent
        step's "available_units" attribute.

        It also adds each unit's download URL to the parent step's "unit_urls" attribute. Each key

        :param manifest: A package manifest in JSON format, describing the versions of a package
                         that are available for download.
        :type  manifest: basestring
        """
        manifest = json.loads(manifest)
        name = manifest['info']['name']
        for version, packages in manifest['releases'].items():
            for package in packages:
                if package['packagetype'] == 'sdist' and package['filename'][-4:] != '.zip':
                    unit = models.Package(name=name, version=version,
                                          _checksum=package['md5_digest'],
                                          _checksum_type='md5')
                    url = package['url']
                    self.parent.available_units.append(unit)
                    self.parent.unit_urls[unit] = url


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

        checksum = models.Package.checksum(report.destination, report.data._checksum_type)
        if checksum != report.data._checksum:
            report.state = 'failed'
            report.error_report = {'expected_checksum': report.data._checksum,
                                   'actual_checksum': checksum}
            return self.download_failed(report)

        package = models.Package.from_archive(report.destination)
        package.set_storage_path(os.path.basename(report.destination))

        try:
            package.save()
        except mongoengine.NotUniqueError:
            package = models.Package.objects.get(name=package.name, version=package.version)

        package.import_content(report.destination)
        repo_controller.associate_single_unit(self.get_repo().repo_obj, package)
        super(DownloadPackagesStep, self).download_succeeded(report)


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

        # these are populated by DownloadMetadataStep
        self.available_units = []
        self.unit_urls = {}

        self.add_child(
            DownloadMetadataStep(
                'sync_step_download_metadata',
                repo=repo, config=config, conduit=conduit, working_dir=self.get_working_dir(),
                description=_('Downloading Python metadata.')))

        self.get_local_units_step = GetLocalUnitsStep(constants.IMPORTER_TYPE_ID,
                                                      available_units=self.available_units)
        self.add_child(self.get_local_units_step)

        self.add_child(
            DownloadPackagesStep(
                'sync_step_download_packages', downloads=self.generate_download_requests(),
                repo=repo, config=config, conduit=conduit, working_dir=self.get_working_dir(),
                description=_('Downloading and processing Python packages.')))

    def generate_download_requests(self):
        """
        For each package that wasn't available locally, yield a Nectar
        DownloadRequest for its url attribute.

        :return: A generator that yields DownloadReqests for the Package files.
        :rtype:  generator
        """
        for p in self.get_local_units_step.units_to_download:
            url = self.unit_urls.pop(p)
            destination = os.path.join(self.get_working_dir(), os.path.basename(url))
            yield request.DownloadRequest(url, destination, p)

    def sync(self):
        """
        Perform the repository synchronization.

        :return: The final sync report.
        :rtype:  pulp.plugins.model.SyncReport
        """
        self.process_lifecycle()
        repo_controller.rebuild_content_unit_counts(self.get_repo().repo_obj)
        return self._build_final_report()
