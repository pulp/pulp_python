"""
This module contains tests for the pulp_python.plugins.importers.sync module.
"""
from cStringIO import StringIO
from gettext import gettext as _
import os
import types
import unittest

import mock
import mongoengine
from pulp.plugins.util.publish_step import GetLocalUnitsStep

from pulp_python.common import constants
from pulp_python.plugins import models
from pulp_python.plugins.importers import sync


# This was taken from https://pypi.python.org/pypi/numpy/json, but was trimmed for brevity. It's a
# good piece of sample data, as it contains 5 versions (1.8.0, 1.8.1, 1.8.2, 1.9.0, and 1.9.1), tar
# archives, zip files, and wheel packages. Though we do not yet handle zip or wheel archives, we do
# need to ensure that their presense does not cause any problems for Pulp until we do support them.
NUMPY_MANIFEST = """{
    "info": {
        "maintainer": null,
        "docs_url": "",
        "requires_python": null,
        "maintainer_email": null,
        "cheesecake_code_kwalitee_id": null,
        "keywords": null,
        "package_url": "http://pypi.python.org/pypi/numpy",
        "author": "NumPy Developers",
        "author_email": "numpy-discussion@scipy.org",
        "download_url": "http://sourceforge.net/projects/numpy/files/NumPy/",
        "platform": "Windows,Linux,Solaris,Mac OS-X,Unix",
        "version": "1.9.1",
        "cheesecake_documentation_id": null,
        "_pypi_hidden": false,
        "description": "NumPy is a general-purpose array-processing package designed to \
efficiently manipulate large multi-dimensional arrays of arbitrary \
records without sacrificing too much speed for small multi-dimensional \
arrays.  NumPy is built on the Numeric code base and adds features \
introduced by numarray as well as an extended C-API and the ability to \
create arrays of arbitrary type which also makes NumPy suitable for \
interfacing with general-purpose data-base applications. \
\
There are also basic facilities for discrete fourier transform, \
basic linear algebra and random number generation.",
        "release_url": "http://pypi.python.org/pypi/numpy/1.9.1",
        "downloads": {
            "last_month": 187293,
            "last_week": 3433,
            "last_day": 300
        },
        "_pypi_ordering": 29,
        "classifiers": [
            "Development Status :: 5 - Production/Stable",
            "Intended Audience :: Developers",
            "Intended Audience :: Science/Research",
            "License :: OSI Approved",
            "Operating System :: MacOS",
            "Operating System :: Microsoft :: Windows",
            "Operating System :: POSIX",
            "Operating System :: Unix",
            "Programming Language :: C",
            "Programming Language :: Python",
            "Programming Language :: Python :: 3",
            "Topic :: Scientific/Engineering",
            "Topic :: Software Development"
        ],
        "name": "numpy",
        "bugtrack_url": null,
        "license": "BSD",
        "summary": "NumPy: array processing for numbers, strings, records, and objects.",
        "home_page": "http://www.numpy.org",
        "stable_version": null,
        "cheesecake_installability_id": null
    },
    "releases": {
        "1.9.1": [
            {
                "has_sig": false,
                "upload_time": "2014-11-02T20:05:25",
                "comment_text": "",
                "python_version": "cp27",
                "url": "https://pypi.python.org/packages/cp27/n/numpy/numpy-1.9.1-cp27-none-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64.whl",
                "md5_digest": "f3ae60e3ab0af99e6b3b1ecd204ddd01",
                "downloads": 50733,
                "filename": "numpy-1.9.1-cp27-none-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64.whl",
                "packagetype": "bdist_wheel",
                "size": 3593838
            },
            {
                "has_sig": false,
                "upload_time": "2014-11-02T20:05:32",
                "comment_text": "",
                "python_version": "cp33",
                "url": "https://pypi.python.org/packages/cp33/n/numpy/numpy-1.9.1-cp33-cp33m-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64.whl",
                "md5_digest": "5efbc811a9148cbdc019e8f3dabe6bc1",
                "downloads": 1406,
                "filename": "numpy-1.9.1-cp33-cp33m-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64.whl",
                "packagetype": "bdist_wheel",
                "size": 3586070
            },
            {
                "has_sig": false,
                "upload_time": "2014-11-02T20:05:39",
                "comment_text": "",
                "python_version": "cp34",
                "url": "https://pypi.python.org/packages/cp34/n/numpy/numpy-1.9.1-cp34-cp34m-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64.whl",
                "md5_digest": "db34cba02448c02bc6935d1473a0965d",
                "downloads": 10373,
                "filename": "numpy-1.9.1-cp34-cp34m-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64.whl",
                "packagetype": "bdist_wheel",
                "size": 3579338
            },
            {
                "has_sig": true,
                "upload_time": "2014-11-02T13:20:14",
                "comment_text": "",
                "python_version": "source",
                "url": "https://pypi.python.org/packages/source/n/numpy/numpy-1.9.1.tar.gz",
                "md5_digest": "78842b73560ec378142665e712ae4ad9",
                "downloads": 420090,
                "filename": "numpy-1.9.1.tar.gz",
                "packagetype": "sdist",
                "size": 3978007
            },
            {
                "has_sig": true,
                "upload_time": "2014-11-02T13:20:20",
                "comment_text": "",
                "python_version": "source",
                "url": "https://pypi.python.org/packages/source/n/numpy/numpy-1.9.1.zip",
                "md5_digest": "223532d8e1bdaff5d30936439701d6e1",
                "downloads": 195612,
                "filename": "numpy-1.9.1.zip",
                "packagetype": "sdist",
                "size": 4487635
            }
        ],
        "1.9.0": [
            {
                "has_sig": false,
                "upload_time": "2014-09-10T18:22:11",
                "comment_text": "",
                "python_version": "cp27",
                "url": "https://pypi.python.org/packages/cp27/n/numpy/numpy-1.9.0-cp27-none-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.whl",
                "md5_digest": "3e9e1f02a6c48897ca296b43eee11e18",
                "downloads": 30600,
                "filename": "numpy-1.9.0-cp27-none-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.whl",
                "packagetype": "bdist_wheel",
                "size": 12015866
            },
            {
                "has_sig": false,
                "upload_time": "2014-09-10T18:22:16",
                "comment_text": "",
                "python_version": "cp33",
                "url": "https://pypi.python.org/packages/cp33/n/numpy/numpy-1.9.0-cp33-cp33m-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.whl",
                "md5_digest": "063ea9e4adf4e419e007ba79c8333f7c",
                "downloads": 1575,
                "filename": "numpy-1.9.0-cp33-cp33m-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.whl",
                "packagetype": "bdist_wheel",
                "size": 12005718
            },
            {
                "has_sig": false,
                "upload_time": "2014-09-10T18:22:22",
                "comment_text": "",
                "python_version": "cp34",
                "url": "https://pypi.python.org/packages/cp34/n/numpy/numpy-1.9.0-cp34-cp34m-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.whl",
                "md5_digest": "b4962c57999b42e1cb6a78ea8fb913f3",
                "downloads": 6532,
                "filename": "numpy-1.9.0-cp34-cp34m-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.whl",
                "packagetype": "bdist_wheel",
                "size": 12005833
            },
            {
                "has_sig": true,
                "upload_time": "2014-09-07T09:55:54",
                "comment_text": "",
                "python_version": "source",
                "url": "https://pypi.python.org/packages/source/n/numpy/numpy-1.9.0.tar.gz",
                "md5_digest": "510cee1c6a131e0a9eb759aa2cc62609",
                "downloads": 271629,
                "filename": "numpy-1.9.0.tar.gz",
                "packagetype": "sdist",
                "size": 3962108
            },
            {
                "has_sig": true,
                "upload_time": "2014-09-07T09:56:02",
                "comment_text": "",
                "python_version": "source",
                "url": "https://pypi.python.org/packages/source/n/numpy/numpy-1.9.0.zip",
                "md5_digest": "d4789bcd8305b5efcfefb3ed029dd632",
                "downloads": 92662,
                "filename": "numpy-1.9.0.zip",
                "packagetype": "sdist",
                "size": 4476753
            }
        ],
        "1.8.0": [
            {
                "has_sig": false,
                "upload_time": "2013-10-30T22:34:42",
                "comment_text": "",
                "python_version": "source",
                "url": "https://pypi.python.org/packages/source/n/numpy/numpy-1.8.0.tar.gz",
                "md5_digest": "2a4b0423a758706d592abb6721ec8dcd",
                "downloads": 422157,
                "filename": "numpy-1.8.0.tar.gz",
                "packagetype": "sdist",
                "size": 3779617
            },
            {
                "has_sig": false,
                "upload_time": "2013-10-30T22:36:34",
                "comment_text": "",
                "python_version": "source",
                "url": "https://pypi.python.org/packages/source/n/numpy/numpy-1.8.0.zip",
                "md5_digest": "6c918bb91c0cfa055b16b13850cfcd6e",
                "downloads": 147913,
                "filename": "numpy-1.8.0.zip",
                "packagetype": "sdist",
                "size": 4285801
            }
        ],
        "1.8.1": [
            {
                "has_sig": false,
                "upload_time": "2014-06-19T17:09:19",
                "comment_text": "",
                "python_version": "cp27",
                "url": "https://pypi.python.org/packages/cp27/n/numpy/numpy-1.8.1-cp27-none-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.whl",
                "md5_digest": "b1127fadbfce9bc0f324ce52fe8efa48",
                "downloads": 24569,
                "filename": "numpy-1.8.1-cp27-none-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.whl",
                "packagetype": "bdist_wheel",
                "size": 12046643
            },
            {
                "has_sig": false,
                "upload_time": "2014-06-19T17:09:25",
                "comment_text": "",
                "python_version": "cp33",
                "url": "https://pypi.python.org/packages/cp33/n/numpy/numpy-1.8.1-cp33-cp33m-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.whl",
                "md5_digest": "d943838035a805925fcbf53204aff1a9",
                "downloads": 1587,
                "filename": "numpy-1.8.1-cp33-cp33m-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.whl",
                "packagetype": "bdist_wheel",
                "size": 12023644
            },
            {
                "has_sig": false,
                "upload_time": "2014-06-19T17:09:31",
                "comment_text": "",
                "python_version": "cp34",
                "url": "https://pypi.python.org/packages/cp34/n/numpy/numpy-1.8.1-cp34-cp34m-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.whl",
                "md5_digest": "31152d55a97cbd655c4eb743d93c4f96",
                "downloads": 4853,
                "filename": "numpy-1.8.1-cp34-cp34m-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.whl",
                "packagetype": "bdist_wheel",
                "size": 12023472
            },
            {
                "has_sig": true,
                "upload_time": "2014-03-25T23:19:20",
                "comment_text": "",
                "python_version": "source",
                "url": "https://pypi.python.org/packages/source/n/numpy/numpy-1.8.1.tar.gz",
                "md5_digest": "be95babe263bfa3428363d6db5b64678",
                "downloads": 478961,
                "filename": "numpy-1.8.1.tar.gz",
                "packagetype": "sdist",
                "size": 3794076
            },
            {
                "has_sig": true,
                "upload_time": "2014-03-25T23:20:40",
                "comment_text": "",
                "python_version": "source",
                "url": "https://pypi.python.org/packages/source/n/numpy/numpy-1.8.1.zip",
                "md5_digest": "b8b3a99d6ed0913543abb49911205e95",
                "downloads": 187598,
                "filename": "numpy-1.8.1.zip",
                "packagetype": "sdist",
                "size": 4291919
            }
        ],
        "1.8.2": [
            {
                "has_sig": false,
                "upload_time": "2014-08-10T00:21:28",
                "comment_text": "",
                "python_version": "cp27",
                "url": "https://pypi.python.org/packages/cp27/n/numpy/numpy-1.8.2-cp27-none-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.whl",
                "md5_digest": "8f64631e257598f99f3da6ec09a5e8bd",
                "downloads": 16439,
                "filename": "numpy-1.8.2-cp27-none-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.whl",
                "packagetype": "bdist_wheel",
                "size": 12046098
            },
            {
                "has_sig": false,
                "upload_time": "2014-08-10T00:21:35",
                "comment_text": "",
                "python_version": "cp33",
                "url": "https://pypi.python.org/packages/cp33/n/numpy/numpy-1.8.2-cp33-cp33m-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.whl",
                "md5_digest": "50408059e6930e8985011260e6c592c7",
                "downloads": 1165,
                "filename": "numpy-1.8.2-cp33-cp33m-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.whl",
                "packagetype": "bdist_wheel",
                "size": 12023848
            },
            {
                "has_sig": false,
                "upload_time": "2014-08-10T00:21:39",
                "comment_text": "",
                "python_version": "cp34",
                "url": "https://pypi.python.org/packages/cp34/n/numpy/numpy-1.8.2-cp34-cp34m-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.whl",
                "md5_digest": "399ace641d77bc1324864921bab63625",
                "downloads": 3420,
                "filename": "numpy-1.8.2-cp34-cp34m-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.whl",
                "packagetype": "bdist_wheel",
                "size": 12023508
            },
            {
                "has_sig": true,
                "upload_time": "2014-08-09T12:19:55",
                "comment_text": "",
                "python_version": "source",
                "url": "https://pypi.python.org/packages/source/n/numpy/numpy-1.8.2.tar.gz",
                "md5_digest": "cdd1a0d14419d8a8253400d8ca8cba42",
                "downloads": 138383,
                "filename": "numpy-1.8.2.tar.gz",
                "packagetype": "sdist",
                "size": 3792998
            },
            {
                "has_sig": true,
                "upload_time": "2014-08-09T12:20:04",
                "comment_text": "",
                "python_version": "source",
                "url": "https://pypi.python.org/packages/source/n/numpy/numpy-1.8.2.zip",
                "md5_digest": "082008bc89e27021fa9fbc59da18784f",
                "downloads": 41132,
                "filename": "numpy-1.8.2.zip",
                "packagetype": "sdist",
                "size": 4294210
            }
        ]
    },
    "urls": [
        {
            "has_sig": false,
            "upload_time": "2014-11-02T20:05:25",
            "comment_text": "",
            "python_version": "cp27",
            "url": "https://pypi.python.org/packages/cp27/n/numpy/numpy-1.9.1-cp27-none-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64.whl",
            "md5_digest": "f3ae60e3ab0af99e6b3b1ecd204ddd01",
            "downloads": 50733,
            "filename": "numpy-1.9.1-cp27-none-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64.whl",
            "packagetype": "bdist_wheel",
            "size": 3593838
        },
        {
            "has_sig": false,
            "upload_time": "2014-11-02T20:05:32",
            "comment_text": "",
            "python_version": "cp33",
            "url": "https://pypi.python.org/packages/cp33/n/numpy/numpy-1.9.1-cp33-cp33m-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64.whl",
            "md5_digest": "5efbc811a9148cbdc019e8f3dabe6bc1",
            "downloads": 1406,
            "filename": "numpy-1.9.1-cp33-cp33m-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64.whl",
            "packagetype": "bdist_wheel",
            "size": 3586070
        },
        {
            "has_sig": false,
            "upload_time": "2014-11-02T20:05:39",
            "comment_text": "",
            "python_version": "cp34",
            "url": "https://pypi.python.org/packages/cp34/n/numpy/numpy-1.9.1-cp34-cp34m-\
macosx_10_6_intel.macosx_10_9_intel.macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64.whl",
            "md5_digest": "db34cba02448c02bc6935d1473a0965d",
            "downloads": 10373,
            "filename": "numpy-1.9.1-cp34-cp34m-macosx_10_6_intel.macosx_10_9_intel.\
macosx_10_9_x86_64.macosx_10_10_intel.macosx_10_10_x86_64.whl",
            "packagetype": "bdist_wheel",
            "size": 3579338
        },
        {
            "has_sig": true,
            "upload_time": "2014-11-02T13:20:14",
            "comment_text": "",
            "python_version": "source",
            "url": "https://pypi.python.org/packages/source/n/numpy/numpy-1.9.1.tar.gz",
            "md5_digest": "78842b73560ec378142665e712ae4ad9",
            "downloads": 420090,
            "filename": "numpy-1.9.1.tar.gz",
            "packagetype": "sdist",
            "size": 3978007
        },
        {
            "has_sig": true,
            "upload_time": "2014-11-02T13:20:20",
            "comment_text": "",
            "python_version": "source",
            "url": "https://pypi.python.org/packages/source/n/numpy/numpy-1.9.1.zip",
            "md5_digest": "223532d8e1bdaff5d30936439701d6e1",
            "downloads": 195612,
            "filename": "numpy-1.9.1.zip",
            "packagetype": "sdist",
            "size": 4487635
        }
    ]
}
"""


class TestDownloadMetadataStep(unittest.TestCase):
    """
    This class tests the DownloadMetadataStep class.
    """

    def test_generate_download_requests(self):
        """
        Ensure that requests for metadata are correctly constructed.
        """
        step = sync.DownloadMetadataStep('sync_step_download_metadata')
        step.parent = mock.MagicMock()
        step.parent._feed_url = 'http://pulpproject.org/'
        step.parent._project_names = ['foo']

        requests = list(step.generate_download_requests())

        self.assertEqual(len(requests), 1)
        request = requests[0]
        self.assertEqual(request.url, 'http://pulpproject.org/pypi/foo/json/')
        self.assertEqual(type(request.destination), type(StringIO()))

    def test_generate_download_requests_canceled(self):
        """
        Ensure that download requests are not generated if the sync has been canceled.
        """
        step = sync.DownloadMetadataStep('sync_step_download_metadata')
        step.parent = mock.MagicMock()
        step.parent._feed_url = 'http://pulpproject.org/'
        step.parent._project_names = ['foo']
        step.canceled = True

        requests = list(step.generate_download_requests())

        self.assertEqual(len(requests), 0)

    @mock.patch('pulp_python.plugins.importers.sync.publish_step.DownloadStep.download_failed')
    def test_download_failed(self, super_download_failed):
        """
        Ensure that download_failed() closes the destination file and calls the superclass handler.
        """
        report = mock.MagicMock()
        step = sync.DownloadMetadataStep('sync_step_download_metadata')

        step.download_failed(report)

        report.destination.close.assert_called_once_with()
        super_download_failed.assert_called_once_with(report)

    @mock.patch('pulp_python.plugins.importers.sync.DownloadMetadataStep._process_metadata')
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.DownloadStep.download_succeeded')
    def test_download_succeeded(self, super_download_succeeded, _process_metadata):
        """
        Ensure that download_succeeded() properly handles the downloaded metadata.
        """
        report = mock.MagicMock()
        step = sync.DownloadMetadataStep('sync_step_download_metadata', conduit=mock.MagicMock())
        step.parent = mock.MagicMock()
        # Let's start with some packages to download to make sure the handler adds to it correctly
        report.destination.read.return_value = NUMPY_MANIFEST

        step.download_succeeded(report)

        report.destination.close.assert_called_once_with()
        super_download_succeeded.assert_called_once_with(report)
        _process_metadata.assert_called_once_with(NUMPY_MANIFEST)

    @mock.patch('pulp_python.plugins.importers.sync.models.Package.from_json')
    def test__process_metadata(self, mock_from_json):
        step = sync.DownloadMetadataStep('sync_step_download_metadata', conduit=mock.MagicMock())
        step.parent = mock.MagicMock()
        step._process_metadata(NUMPY_MANIFEST)
        # 1.9.1 has 5 units, 1.9.0 has 5, 1.8.0 has 2, 1.8.1 has 5, 1.8.2 has 5. Total should be 22.
        self.assertEqual(mock_from_json.call_count, 22)


class TestDownloadPackagesStep(unittest.TestCase):
    """
    This class tests the DownloadPackagesStep class.
    """
    @mock.patch('pulp_python.plugins.importers.sync.models.Package.checksum')
    @mock.patch('pulp_python.plugins.importers.sync.DownloadPackagesStep.download_failed')
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.DownloadStep.download_succeeded')
    def test_download_succeeded_checksum_bad(self, super_download_succeeded,
                                             download_failed, checksum):
        """
        Test the download_succeeded() method when the checksum of the downloaded package is
        incorrect.
        """
        report = mock.MagicMock()
        report.data._checksum = 'expected checksum'
        report.data._checksum_type = 'md5'
        step = sync.DownloadPackagesStep('sync_step_download_packages', conduit=mock.MagicMock())
        checksum.return_value = 'bad checksum'

        step.download_succeeded(report)

        # Since the checksum was bad, the superclass download_succeeded should not have been called
        self.assertEqual(super_download_succeeded.call_count, 0)
        # The report should have been altered to indicate the failure and then passed to
        # download_failed()
        self.assertEqual(report.state, 'failed')
        self.assertEqual(
            report.error_report,
            {'expected_checksum': 'expected checksum', 'actual_checksum': 'bad checksum'})
        download_failed.assert_called_once_with(report)
        # Make sure the checksum was calculated with the correct data
        checksum.assert_called_once_with(report.destination, 'md5')
        # The unit should not have been saved since the download failed
        self.assertEqual(report.data.save.call_count, 0)

    @mock.patch('pulp.server.controllers.repository.associate_single_unit', spec_set=True)
    @mock.patch('pulp_python.plugins.importers.sync.models.Package.checksum')
    @mock.patch('pulp_python.plugins.importers.sync.DownloadPackagesStep.download_failed')
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.DownloadStep.download_succeeded')
    def test_download_succeeded_checksum_good(self, super_download_succeeded, download_failed,
                                              checksum, mock_associate):
        """
        Test the download_succeeded() method when the checksum of the downloaded package is correct.
        """
        report = mock.MagicMock()
        report.destination = '/tmp/foo.tar.gz'
        report.data._checksum = 'good checksum'
        report.data._checksum_type = 'md5'
        step = sync.DownloadPackagesStep('sync_step_download_packages', conduit=mock.MagicMock())
        step.parent = mock.MagicMock()
        checksum.return_value = 'good checksum'

        step.download_succeeded(report)

        # Download failed should not have been called
        self.assertEqual(download_failed.call_count, 0)
        # Make sure the checksum was calculated with the correct data
        checksum.assert_called_once_with(report.destination, 'md5')
        report.data.set_storage_path.assert_called_once_with(os.path.basename(report.destination))
        report.data.save.assert_called_once_with()
        report.data.import_content.assert_called_once_with(report.destination)
        mock_associate.assert_called_once_with(step.parent.get_repo.return_value.repo_obj,
                                               report.data)

    @mock.patch('pulp.server.controllers.repository.associate_single_unit', spec_set=True)
    @mock.patch('pulp_python.plugins.importers.sync.models.Package.checksum')
    @mock.patch('pulp_python.plugins.importers.sync.models.Package.objects')
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.DownloadStep.download_succeeded')
    def test_download_succeeded_not_unique(self, super_download_succeeded, mock_objects,
                                           checksum, mock_associate):
        """
        Test download_succeeded when the checksum is correct, but the unit already exists.
        """
        report = mock.MagicMock()
        report.destination = '/tmp/foo.tar.gz'
        report.data.name = 'foo'
        report.data.version = '1.0.0'
        report.data._checksum = 'good checksum'
        report.data._checksum_type = 'md5'
        step = sync.DownloadPackagesStep('sync_step_download_packages', conduit=mock.MagicMock())
        step.parent = mock.MagicMock()
        checksum.return_value = 'good checksum'
        report.data.save.side_effect = mongoengine.NotUniqueError

        step.download_succeeded(report)

        report.data.set_storage_path.assert_called_once_with(os.path.basename(report.destination))
        mock_objects.get.return_value.import_content.assert_called_once_with(report.destination)
        report.data.save.assert_called_once_with()
        mock_associate.assert_called_once_with(step.parent.get_repo.return_value.repo_obj,
                                               mock_objects.get.return_value)
        mock_objects.get.assert_called_once_with(filename=report.data.filename)


class TestSyncStep(unittest.TestCase):
    """
    This class contains tests for the SyncStep class.
    """
    @mock.patch('pulp_python.plugins.importers.sync.DownloadPackagesStep.__init__',
                side_effect=sync.DownloadPackagesStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.PluginStep.__init__',
                side_effect=sync.publish_step.PluginStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.SyncStep.generate_download_requests',
                autospec=True)
    def test___init___no_packages(self, generate_download_requests, super___init__,
                                  download_packages___init__):
        """
        Test the __init__() method when the user has not specified any packages to sync.
        """
        repo = mock.MagicMock()
        repo.id = 'cool_repo'
        conduit = mock.MagicMock()
        config = mock.MagicMock()
        working_dir = '/some/dir'

        def fake_get(key, default=None):
            if key == constants.CONFIG_KEY_PACKAGE_NAMES:
                return default
            return 'http://example.com/'

        config.get.side_effect = fake_get

        step = sync.SyncStep(repo, conduit, config, working_dir)

        # The superclass __init__ method gets called four times. Once directly by this __init__, and
        # three more times by the substeps it creates.
        self.assertEqual(super___init__.call_count, 4)
        # Let's assert that the direct call was cool.
        self.assertEqual(
            super___init__.mock_calls[0],
            mock.call(step, 'sync_step_main', repo, conduit, config, working_dir,
                      constants.IMPORTER_TYPE_ID))
        self.assertEqual(step.description, _('Synchronizing cool_repo repository.'))
        # Assert that the feed url and packages names are correct
        self.assertEqual(step._feed_url, 'http://example.com/')
        self.assertEqual(step._project_names, [])
        self.assertEqual(step.available_units, [])
        # Three child steps should have been added
        self.assertEqual(len(step.children), 3)
        self.assertEqual(type(step.children[0]), sync.DownloadMetadataStep)
        self.assertEqual(type(step.children[1]), GetLocalUnitsStep)
        self.assertEqual(type(step.children[2]), sync.DownloadPackagesStep)
        # Make sure the steps were initialized properly
        downloads = generate_download_requests.return_value
        download_packages___init__.assert_called_once_with(
            step.children[2], 'sync_step_download_packages', downloads=downloads, repo=repo,
            config=config, conduit=conduit, working_dir=working_dir,
            description=_('Downloading and processing Python packages.'))

    @mock.patch('pulp_python.plugins.importers.sync.DownloadPackagesStep.__init__',
                side_effect=sync.DownloadPackagesStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.PluginStep.__init__',
                side_effect=sync.publish_step.PluginStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.SyncStep.generate_download_requests',
                autospec=True)
    def test___init___one_package(self, generate_download_requests, super___init__,
                                  download_packages___init__):
        """
        Test the __init__() method when the user has specified one package to sync.
        """
        repo = mock.MagicMock()
        repo.id = 'cool_repo'
        conduit = mock.MagicMock()
        config = mock.MagicMock()
        working_dir = '/some/dir'

        def fake_get(key, default=None):
            if key == constants.CONFIG_KEY_PACKAGE_NAMES:
                return 'numpy'
            return 'http://example.com/'

        config.get.side_effect = fake_get

        step = sync.SyncStep(repo, conduit, config, working_dir)

        # The superclass __init__ method gets called four times. Once directly by this __init__, and
        # three more times by the substeps it creates.
        self.assertEqual(super___init__.call_count, 4)
        # Let's assert that the direct call was cool.
        self.assertEqual(
            super___init__.mock_calls[0],
            mock.call(step, 'sync_step_main', repo, conduit, config, working_dir,
                      constants.IMPORTER_TYPE_ID))
        self.assertEqual(step.description, _('Synchronizing cool_repo repository.'))
        # Assert that the feed url and packages names are correct
        self.assertEqual(step._feed_url, 'http://example.com/')
        self.assertEqual(step._project_names, ['numpy'])
        self.assertEqual(step.available_units, [])
        # Three child steps should have been added
        self.assertEqual(len(step.children), 3)
        self.assertEqual(type(step.children[0]), sync.DownloadMetadataStep)
        self.assertEqual(type(step.children[1]), GetLocalUnitsStep)
        self.assertEqual(type(step.children[2]), sync.DownloadPackagesStep)
        # Make sure the steps were initialized properly
        downloads = generate_download_requests.return_value
        download_packages___init__.assert_called_once_with(
            step.children[2], 'sync_step_download_packages', downloads=downloads, repo=repo,
            config=config, conduit=conduit, working_dir=working_dir,
            description=_('Downloading and processing Python packages.'))

    @mock.patch('pulp_python.plugins.importers.sync.DownloadPackagesStep.__init__',
                side_effect=sync.DownloadPackagesStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.PluginStep.__init__',
                side_effect=sync.publish_step.PluginStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.SyncStep.generate_download_requests',
                autospec=True)
    def test___init___three_packages(self, generate_download_requests, super___init__,
                                     download_packages___init__):
        """
        Test the __init__() method when the user has specified three packages to sync.
        """
        repo = mock.MagicMock()
        repo.id = 'cool_repo'
        conduit = mock.MagicMock()
        config = mock.MagicMock()
        working_dir = '/some/dir'

        def fake_get(key, default=None):
            if key == constants.CONFIG_KEY_PACKAGE_NAMES:
                return 'numpy,scipy,django'
            return 'http://example.com/'

        config.get.side_effect = fake_get

        step = sync.SyncStep(repo, conduit, config, working_dir)

        # The superclass __init__ method gets called four times. Once directly by this __init__, and
        # three more times by the substeps it creates.
        self.assertEqual(super___init__.call_count, 4)
        # Let's assert that the direct call was cool.
        self.assertEqual(
            super___init__.mock_calls[0],
            mock.call(step, 'sync_step_main', repo, conduit, config, working_dir,
                      constants.IMPORTER_TYPE_ID))
        self.assertEqual(step.description, _('Synchronizing cool_repo repository.'))
        # Assert that the feed url and packages names are correct
        self.assertEqual(step._feed_url, 'http://example.com/')
        self.assertEqual(step._project_names, ['numpy', 'scipy', 'django'])
        self.assertEqual(step.available_units, [])
        # Three child steps should have been added
        self.assertEqual(len(step.children), 3)
        self.assertEqual(type(step.children[0]), sync.DownloadMetadataStep)
        self.assertEqual(type(step.children[1]), GetLocalUnitsStep)
        self.assertEqual(type(step.children[2]), sync.DownloadPackagesStep)
        # Make sure the steps were initialized properly
        downloads = generate_download_requests.return_value
        download_packages___init__.assert_called_once_with(
            step.children[2], 'sync_step_download_packages', downloads=downloads, repo=repo,
            config=config, conduit=conduit, working_dir=working_dir,
            description=_('Downloading and processing Python packages.'))

    def test_generate_download_requests(self):
        """
        Ensure correct operation from generate_download_requests().
        """
        repo = mock.MagicMock()
        conduit = mock.MagicMock()
        config = mock.MagicMock()
        # mock the feed url
        working_dir = '/some/dir'
        config.get.return_value = 'mock/feed'

        step = sync.SyncStep(repo, conduit, config, working_dir)
        u1 = models.Package(name='foo', version='1.2.0', path='url/1.2.tar.gz')
        u2 = models.Package(name='foo', version='1.3.0', path='url/1.3.tar.gz')
        u1._feed_url = u2._feed_url = "feed/"
        step.get_local_units_step.units_to_download.extend([u1, u2])

        requests = step.generate_download_requests()

        self.assertTrue(isinstance(requests, types.GeneratorType))
        # For the remainder of our tests, it will be more useful if requests is a list
        requests = list(requests)
        self.assertEqual(len(requests), 2)
        request_urls = [r.url for r in requests]
        self.assertEqual(request_urls, ['mock/feed/packages/url/1.2.tar.gz',
                                        'mock/feed/packages/url/1.3.tar.gz'])

        # The destinations should both have been paths constructed from the filename
        request_destinations = [r.destination for r in requests]
        self.assertEqual(request_destinations, ['/some/dir/1.2.tar.gz', '/some/dir/1.3.tar.gz'])
        requests_data = [r.data for r in requests]
        self.assertEqual(requests_data, step.get_local_units_step.units_to_download)

    @mock.patch('pulp.server.controllers.repository.rebuild_content_unit_counts', spec_set=True)
    @mock.patch('pulp_python.plugins.importers.sync.SyncStep._build_final_report',
                autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.SyncStep.process_lifecycle',
                autospec=True)
    def test_sync(self, process_lifecycle, _build_final_report, mock_rebuild):
        """
        Ensure that sync() makes the correct calls.
        """
        repo = mock.MagicMock()
        conduit = mock.MagicMock()
        config = mock.MagicMock()
        working_dir = '/some/dir'
        step = sync.SyncStep(repo, conduit, config, working_dir)

        step.sync()

        process_lifecycle.assert_called_once_with(step)
        _build_final_report.assert_called_once_with(step)
        mock_rebuild.assert_called_once_with(repo.repo_obj)
