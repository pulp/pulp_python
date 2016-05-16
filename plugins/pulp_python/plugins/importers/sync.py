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
    Download json metadata for each project in the parent step's list `self._project_names`. Each
    project contains metadata for one or more packges, and in this step, a unit is created for
    each package.
    """

    def __init__(self, *args, **kwargs):
        """
        Injects download requests into the call to the parent class's __init__
        """
        kwargs['downloads'] = self.generate_download_requests()
        super(DownloadMetadataStep, self).__init__(*args, **kwargs)

    def download_failed(self, report):
        """
        This method is bound to a Nectar event listener which is called when the step fails to
        download json metadata for a particular project. It closes the StringIO that we were using
        to store the download to free memory.

        :param report: The report that details the download
        :type  report: nectar.report.DownloadReport
        """
        report.destination.close()
        super(DownloadMetadataStep, self).download_failed(report)

    def download_succeeded(self, report):
        """
        This method is bound to a Nectar event listener which is called each time the step
        successfully downloads json metadata for a project. Each package described in the project's
        json is initialized and placed in the parent step's list of units that are available to be
        downloaded.

        :param report: The report that details the download
        :type  report: nectar.report.DownloadReport
        """
        _logger.info(_('Processing metadata retrieved from %(url)s.') % {'url': report.url})
        with contextlib.closing(report.destination) as destination:
            destination.seek(0)
            self._process_metadata(destination.read())

        super(DownloadMetadataStep, self).download_succeeded(report)

    def generate_download_requests(self):
        """
        For each project name in the parent step's list of projects, yield a Nectar DownloadRequest
        for the project's json metadata.

        :return: A generator that yields DownloadRequests for a project's json metadata.
        :rtype:  generator
        """
        metadata_urls = [urljoin(self.parent._feed_url, 'pypi/%s/json/' % pn)
                         for pn in self.parent._project_names]
        for u in metadata_urls:
            if self.canceled:
                return
            yield request.DownloadRequest(u, StringIO(), {})

    def _process_metadata(self, metadata):
        """
        Parses the project's json metadata to determine which packages are available from the feed
        repository. Each available package is initialized and added to the parent step's list of
        available_units.

        :param metadata: Project metadata in JSON format that describes each available package.
        :type  metadata: basestring
        """
        metadata = json.loads(metadata)
        for version, packages in metadata['releases'].items():
            for package in packages:
                unit = models.Package.from_json(package, version, metadata['info'])
                self.parent.available_units.append(unit)


class DownloadPackagesStep(publish_step.DownloadStep):
    """
    Retrieves package bits for each request. Once the bits are successfully downloaded, the
    cooresponding unit (models.Package) is saved into the database and associated to the repository.
    """

    def download_succeeded(self, report):
        """
        When the package's bits are successfully downloaded, the checksum is verified, the package
        is moved to its final location, and the models.Package object is saved into the database
        and associated to the repository.

        TODO (asmacdo) Outstanding question:

        Should we update the package data after it is downloaded? In a normal sync from PYPI, the
        package object is initialized from the JSON data. There are some fields that are specific
        to the project rather than the package, and these will be incorrect if we only get this
        information from the JSON and the info changed from release to release.

        Benefits of update after successful download:
            1. More fields can be accurately populated without the risk of "drift"
            2. We can update the checksum to a better algorithm
            3. Update logic is the same as upload, so they would produce identical data
        Drawbacks of update:
            1. Must crack open each compressed package and parse, pretty slow.
            2. Packages would have 2 phases of completeness. Minimal until downloaded, full after.

        package.update_from_file(report.destination)

        :param report: The report that details the download
        :type  report: nectar.report.DownloadReport
        """
        _logger.info(_('Processing package retrieved from %(url)s.') % {'url': report.url})
        package = report.data
        checksum = models.Package.checksum(report.destination, package._checksum_type)
        if checksum != package._checksum:
            report.state = 'failed'
            report.error_report = {'expected_checksum': package._checksum,
                                   'actual_checksum': checksum}
            return self.download_failed(report)

        package.set_storage_path(os.path.basename(report.destination))

        # If the same package was simultaniously created by another task, it is possible that this
        # will attempt to save a duplicate unit into the database. In that case, catch the error,
        # retrieve the unit, and associate it to this repo.
        try:
            package.save()
        except mongoengine.NotUniqueError:
            package = models.Package.objects.get(filename=package.filename)

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
        Initialize the SyncStep and its child steps.

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
        self._project_names = config.get(constants.CONFIG_KEY_PACKAGE_NAMES, [])
        if self._project_names:
            self._project_names = self._project_names.split(',')

        # Download the json metadata for each project, initialize packages, and place them in the
        # available units list.
        self.available_units = []
        self.add_child(
            DownloadMetadataStep(
                'sync_step_download_metadata',
                repo=repo, config=config, conduit=conduit, working_dir=self.get_working_dir(),
                description=_('Downloading Python metadata.')))

        # Populate a list of `self.get_local_units_step.units_to_download`.
        self.get_local_units_step = GetLocalUnitsStep(constants.IMPORTER_TYPE_ID,
                                                      available_units=self.available_units)
        self.add_child(self.get_local_units_step)

        # Download each package in the units to download list.
        self.add_child(
            DownloadPackagesStep(
                'sync_step_download_packages', downloads=self.generate_download_requests(),
                repo=repo, config=config, conduit=conduit, working_dir=self.get_working_dir(),
                description=_('Downloading and processing Python packages.')))

    def generate_download_requests(self):
        """
        Yield a Nectar Download request for each package that wasn't available locally.

        :return: A generator that yields DownloadReqests for the Package files.
        :rtype:  generator
        """
        for package in self.get_local_units_step.units_to_download:
            destination = os.path.join(self.get_working_dir(), os.path.basename(package.url))
            yield request.DownloadRequest(package.url, destination, package)

    def sync(self):
        """
        Perform the repository synchronization.

        :return: The final sync report.
        :rtype:  pulp.plugins.model.SyncReport
        """
        self.process_lifecycle()
        repo_controller.rebuild_content_unit_counts(self.get_repo().repo_obj)
        return self._build_final_report()
