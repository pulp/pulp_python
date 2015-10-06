"""
This module contains tests for the pulp_python.plugins.importers.sync module.
"""
from cStringIO import StringIO
from gettext import gettext as _
import os
import types
import unittest

import mock
from pulp.server.db.model import criteria

from pulp_python.common import constants
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
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.DownloadStep.download_failed')
    def test_download_failed(self, super_download_failed):
        """
        Ensure that the download_failed() method closes the destination file and calls the
        superclass handler.
        """
        report = mock.MagicMock()
        step = sync.DownloadMetadataStep('sync_step_download_metadata')

        step.download_failed(report)

        report.destination.close.assert_called_once_with()
        super_download_failed.assert_called_once_with(report)

    @mock.patch('pulp_python.plugins.importers.sync.DownloadMetadataStep._process_manifest')
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.DownloadStep.download_succeeded')
    def test_download_succeeded(self, super_download_succeeded, _process_manifest):
        """
        Ensure the download_succeeded() method properly handles the downloaded metadata.
        """
        report = mock.MagicMock()
        conduit = mock.MagicMock()
        step = sync.DownloadMetadataStep('sync_step_download_metadata', conduit=conduit)
        step.parent = mock.MagicMock()
        # Let's start with some packages to download to make sure the handler adds to it correctly
        step.parent.parent._packages_to_download = [{'a': 1}]
        report.destination.read.return_value = NUMPY_MANIFEST
        _process_manifest.return_value = [{'b': 2}, {'c': 3}]

        step.download_succeeded(report)

        report.destination.close.assert_called_once_with()
        super_download_succeeded.assert_called_once_with(report)
        _process_manifest.assert_called_once_with(NUMPY_MANIFEST, conduit)
        self.assertEqual(step.parent.parent._packages_to_download, [{'a': 1}, {'b': 2}, {'c': 3}])

    def test__process_manifest_associates_existing_versions(self):
        """
        Ensure that _process_manifest() associates packages that we already have in Pulp, rather
        than scheduling them to be downloaded.
        """
        conduit = mock.MagicMock()

        class FakeUnit(object):
            def __init__(self, version):
                self.unit_key = {'version': version}

        versions = ['1.8.0', '1.8.1', '1.8.2', '1.9.0', '1.9.1']
        conduit.get_units.return_value = []
        conduit.search_all_units.return_value = [FakeUnit(v) for v in versions]

        packages_to_dl = sync.DownloadMetadataStep._process_manifest(NUMPY_MANIFEST, conduit)

        # There should have been no packages to download, since they were all already in Pulp.
        self.assertEqual(packages_to_dl, [])
        # Make sure the correct call to search_all_units was made
        search = criteria.Criteria(filters={'name': 'numpy'}, fields=['name', 'version'])
        # Because the Criteria object is stupid, we'll have the fake the id being the same as the
        # one that was actually used
        search._id = conduit.search_all_units.mock_calls[0][2]['criteria']._id
        search.id = conduit.search_all_units.mock_calls[0][2]['criteria'].id
        conduit.search_all_units.assert_called_once_with(constants.PACKAGE_TYPE_ID, criteria=search)
        # The repo should have been searched for available versions as well
        search = criteria.UnitAssociationCriteria(unit_filters={'name': 'numpy'},
                                                  unit_fields=['name', 'version'])
        # Again, because the Criteria object is stupid, we'll have the fake the id being the same as
        # the one that was actually used
        search._id = conduit.get_units.mock_calls[0][2]['criteria']._id
        search.id = conduit.get_units.mock_calls[0][2]['criteria'].id
        conduit.get_units.assert_called_once_with(criteria=search)
        # All of the versions should have been added to the repo
        self.assertEqual(conduit.associate_existing.call_count, 1)
        self.assertEqual(conduit.associate_existing.mock_calls[0][1][0], constants.PACKAGE_TYPE_ID)
        self.assertEqual(
            set([u['version'] for u in conduit.associate_existing.mock_calls[0][1][1]]),
            set(versions))
        self.assertEqual(
            set([u['name'] for u in conduit.associate_existing.mock_calls[0][1][1]]),
            set(['numpy']))
        self.assertEqual(
            len([u['version'] for u in conduit.associate_existing.mock_calls[0][1][1]]), 5)

    def test__process_manifest_downloads_missing_versions(self):
        """
        Ensure that _process_manifest() downloads versions that we are missing in Pulp. This test
        also ensures that we do not download bdist or wheel archives, and that their presence in the
        metadata does not cause any issues for the importer by using a manifest that does contain
        those types of archives. Support for those archive types may be added at a later date.
        """
        conduit = mock.MagicMock()
        conduit.get_units.return_value = []
        conduit.search_all_units.return_value = []

        packages_to_dl = sync.DownloadMetadataStep._process_manifest(NUMPY_MANIFEST, conduit)

        # It should have marked all tarball packages for download
        expected_packages_to_dl = [
            {'name': 'numpy', 'version': '1.8.0',
             'url': 'https://pypi.python.org/packages/source/n/numpy/numpy-1.8.0.tar.gz',
             'checksum': '2a4b0423a758706d592abb6721ec8dcd'},
            {'name': 'numpy', 'version': '1.8.1',
             'url': 'https://pypi.python.org/packages/source/n/numpy/numpy-1.8.1.tar.gz',
             'checksum': 'be95babe263bfa3428363d6db5b64678'},
            {'name': 'numpy', 'version': '1.8.2',
             'url': 'https://pypi.python.org/packages/source/n/numpy/numpy-1.8.2.tar.gz',
             'checksum': 'cdd1a0d14419d8a8253400d8ca8cba42'},
            {'name': 'numpy', 'version': '1.9.0',
             'url': 'https://pypi.python.org/packages/source/n/numpy/numpy-1.9.0.tar.gz',
             'checksum': '510cee1c6a131e0a9eb759aa2cc62609'},
            {'name': 'numpy', 'version': '1.9.1',
             'url': 'https://pypi.python.org/packages/source/n/numpy/numpy-1.9.1.tar.gz',
             'checksum': '78842b73560ec378142665e712ae4ad9'}]
        # The packages_to_dl list is not sorted in an easily predictable way. Since the order is not
        # meaningful, let's sort it by version to make the assertion easier.
        packages_to_dl = sorted(packages_to_dl, key=lambda k: k['version'])
        self.assertEqual(packages_to_dl, expected_packages_to_dl)
        # Make sure the correct call to search_all_units was made
        search = criteria.Criteria(filters={'name': 'numpy'}, fields=['name', 'version'])
        # Because the Criteria object is stupid, we'll have the fake the id being the same as the
        # one that was actually used
        search._id = conduit.search_all_units.mock_calls[0][2]['criteria']._id
        search.id = conduit.search_all_units.mock_calls[0][2]['criteria'].id
        conduit.search_all_units.assert_called_once_with(constants.PACKAGE_TYPE_ID, criteria=search)
        # The repo should have been searched for available versions as well
        search = criteria.UnitAssociationCriteria(unit_filters={'name': 'numpy'},
                                                  unit_fields=['name', 'version'])
        # Again, because the Criteria object is stupid, we'll have the fake the id being the same as
        # the one that was actually used
        search._id = conduit.get_units.mock_calls[0][2]['criteria']._id
        search.id = conduit.get_units.mock_calls[0][2]['criteria'].id
        conduit.get_units.assert_called_once_with(criteria=search)
        # Since there were no existing versions, no calls should have been made to associate
        # existing
        self.assertEqual(conduit.associate_existing.call_count, 0)

    def test__process_manifest_mixed_case(self):
        """
        Test _process_manifest() when there are both packages that just need to be associated, and
        packages that need to be downloaded.
        """
        conduit = mock.MagicMock()

        class FakeUnit(object):
            def __init__(self, version):
                self.unit_key = {'version': version}

        # Let's fake 1.8.0, 1.8.1, and 1.9.0 as all being in Pulp, but also 1.9.0 not being in the
        # repo that is being sync'd. This should cause Pulp to download 1.8.2 and 1.9.1, and it
        # should add an assocation for the existing 1.9.0 to the repo.
        versions = ['1.8.0', '1.8.1', '1.9.0']
        conduit.get_units.return_value = [FakeUnit(v) for v in ['1.8.0', '1.8.1']]
        conduit.search_all_units.return_value = [FakeUnit(v) for v in versions]

        packages_to_dl = sync.DownloadMetadataStep._process_manifest(NUMPY_MANIFEST, conduit)

        # 1.8.2 and 1.9.1 should have been marked for download
        expected_packages_to_dl = [
            {'name': 'numpy', 'version': '1.8.2',
             'url': 'https://pypi.python.org/packages/source/n/numpy/numpy-1.8.2.tar.gz',
             'checksum': 'cdd1a0d14419d8a8253400d8ca8cba42'},
            {'name': 'numpy', 'version': '1.9.1',
             'url': 'https://pypi.python.org/packages/source/n/numpy/numpy-1.9.1.tar.gz',
             'checksum': '78842b73560ec378142665e712ae4ad9'}]
        # The packages_to_dl list is not sorted in an easily predictable way. Since the order is not
        # meaningful, let's sort it by version to make the assertion easier.
        packages_to_dl = sorted(packages_to_dl, key=lambda k: k['version'])
        self.assertEqual(packages_to_dl, expected_packages_to_dl)
        # Make sure the correct call to search_all_units was made
        search = criteria.Criteria(filters={'name': 'numpy'}, fields=['name', 'version'])
        # Because the Criteria object is stupid, we'll have the fake the id being the same as the
        # one that was actually used
        search._id = conduit.search_all_units.mock_calls[0][2]['criteria']._id
        search.id = conduit.search_all_units.mock_calls[0][2]['criteria'].id
        conduit.search_all_units.assert_called_once_with(constants.PACKAGE_TYPE_ID, criteria=search)
        # The repo should have been searched for available versions as well
        search = criteria.UnitAssociationCriteria(unit_filters={'name': 'numpy'},
                                                  unit_fields=['name', 'version'])
        # Again, because the Criteria object is stupid, we'll have the fake the id being the same as
        # the one that was actually used
        search._id = conduit.get_units.mock_calls[0][2]['criteria']._id
        search.id = conduit.get_units.mock_calls[0][2]['criteria'].id
        conduit.get_units.assert_called_once_with(criteria=search)
        # 1.9.0 should have been added to the repo
        conduit.associate_existing.assert_called_once_with(constants.PACKAGE_TYPE_ID,
                                                           [{'name': 'numpy', 'version': '1.9.0'}])

    def test__process_manifest_nothing_to_do(self):
        """
        Test the _process_manifest() method when there is nothing to do. It should return an empty
        list, and make no associations.
        """
        conduit = mock.MagicMock()

        class FakeUnit(object):
            def __init__(self, version):
                self.unit_key = {'version': version}

        # Let's fake all the versions already being in Pulp and also in the repo. There should be
        # nothing to download, and no associations to make.
        versions = ['1.8.0', '1.8.1', '1.8.2', '1.9.0', '1.9.1']
        conduit.get_units.return_value = [FakeUnit(v) for v in versions]
        conduit.search_all_units.return_value = [FakeUnit(v) for v in versions]

        packages_to_dl = sync.DownloadMetadataStep._process_manifest(NUMPY_MANIFEST, conduit)

        self.assertEqual(packages_to_dl, [])
        # Make sure the correct call to search_all_units was made
        search = criteria.Criteria(filters={'name': 'numpy'}, fields=['name', 'version'])
        # Because the Criteria object is stupid, we'll have the fake the id being the same as the
        # one that was actually used
        search._id = conduit.search_all_units.mock_calls[0][2]['criteria']._id
        search.id = conduit.search_all_units.mock_calls[0][2]['criteria'].id
        conduit.search_all_units.assert_called_once_with(constants.PACKAGE_TYPE_ID, criteria=search)
        # The repo should have been searched for available versions as well
        search = criteria.UnitAssociationCriteria(unit_filters={'name': 'numpy'},
                                                  unit_fields=['name', 'version'])
        # Again, because the Criteria object is stupid, we'll have the fake the id being the same as
        # the one that was actually used
        search._id = conduit.get_units.mock_calls[0][2]['criteria']._id
        search.id = conduit.get_units.mock_calls[0][2]['criteria'].id
        conduit.get_units.assert_called_once_with(criteria=search)
        # No associations should have been made
        self.assertEqual(conduit.associate_existing.call_count, 0)


class TestDownloadPackagesStep(unittest.TestCase):
    """
    This class tests the DownloadPackagesStep class.
    """
    @mock.patch('pulp_python.plugins.importers.sync.models.Package.checksum')
    @mock.patch('pulp_python.plugins.importers.sync.models.Package.save_unit')
    @mock.patch('pulp_python.plugins.importers.sync.DownloadPackagesStep.download_failed')
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.DownloadStep.download_succeeded')
    @mock.patch('pulp_python.plugins.importers.sync.shutil.copy')
    def test_download_succeeded_checksum_bad(self, copy, super_download_succeeded,
                                             download_failed, save_unit, checksum):
        """
        Test the download_succeeded() method when the checksum of the downloaded package is
        incorrect.
        """
        report = mock.MagicMock()
        report.data = {'checksum': 'expected checksum'}
        conduit = mock.MagicMock()
        step = sync.DownloadPackagesStep('sync_step_download_packages', conduit=conduit)
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
        # copy and save_unit should not have been called since the download failed
        self.assertEqual(copy.call_count, 0)
        self.assertEqual(save_unit.call_count, 0)

    @mock.patch('pulp_python.plugins.importers.sync.models.Package.checksum')
    @mock.patch('pulp_python.plugins.importers.sync.models.Package.from_archive')
    @mock.patch('pulp_python.plugins.importers.sync.DownloadPackagesStep.download_failed')
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.DownloadStep.download_succeeded')
    @mock.patch('pulp_python.plugins.importers.sync.shutil.copy')
    def test_download_succeeded_checksum_good(self, copy, super_download_succeeded, download_failed,
                                              from_archive, checksum):
        """
        Test the download_succeeded() method when the checksum of the downloaded package is correct.
        """
        report = mock.MagicMock()
        report.data = {'checksum': 'good checksum'}
        conduit = mock.MagicMock()
        step = sync.DownloadPackagesStep('sync_step_download_packages', conduit=conduit)
        checksum.return_value = 'good checksum'

        step.download_succeeded(report)

        # Download failed should not have been called
        self.assertEqual(download_failed.call_count, 0)
        # Make sure the checksum was calculated with the correct data
        checksum.assert_called_once_with(report.destination, 'md5')
        # The from_archive method should have been given the destination
        from_archive.assert_called_once_with(report.destination)
        # The Package's init_unit should have been handed the conduit
        package = from_archive.return_value
        package.init_unit.assert_called_once_with(conduit)
        # The unit should have been copied to the storage path
        copy.assert_called_once_with(report.destination, package.storage_path)
        # The unit should have been saved to the DB
        package.save_unit.assert_called_once_with(conduit)
        # The superclass success method should have been called.
        super_download_succeeded.assert_called_once_with(report)


class TestGetMetadataStep(unittest.TestCase):
    """
    This class contains tests for the GetMetadataStep class.
    """
    @mock.patch('pulp_python.plugins.importers.sync.DownloadMetadataStep.__init__',
                side_effect=sync.DownloadMetadataStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.GetMetadataStep.add_child',
                side_effect=sync.GetMetadataStep.add_child, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.GetMetadataStep.generate_download_requests',
                autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.PluginStep.__init__',
                side_effect=sync.publish_step.PluginStep.__init__, autospec=True)
    def test___init__(self, super___init__, generate_download_requests, add_child,
                      download___init__):
        """
        Assert that __init__() properly initializes the object.
        """
        repo = mock.MagicMock()
        conduit = mock.MagicMock()
        config = mock.MagicMock()
        working_dir = '/some/dir'

        step = sync.GetMetadataStep(repo, conduit, config, working_dir)

        # The superclass's __init__ gets called through super(), and also when the
        # DownloadMetadataStep is constructed, so there are two calls. We'll assert the second call
        # through the more specific download___init__ mock.
        self.assertEqual(super___init__.call_count, 2)
        self.assertEqual(
            super___init__.mock_calls[0][1],
            (step, 'sync_step_metadata', repo, conduit, config, working_dir,
             constants.IMPORTER_TYPE_ID))
        # Now let's check the download___init__ mock.
        download_step = super___init__.mock_calls[1][1][0]
        self.assertEqual(download___init__.call_count, 1)
        self.assertEqual(
            download___init__.mock_calls[0][1],
            (download_step, 'sync_step_download_metadata',))
        downloads = generate_download_requests.return_value
        self.assertEqual(
            download___init__.mock_calls[0][2],
            {'downloads': downloads, 'repo': repo, 'conduit': conduit, 'config': config,
             'working_dir': working_dir, 'description': _('Downloading Python metadata.')})
        self.assertEqual(step.description, _('Downloading and processing metadata.'))
        add_child.assert_called_once_with(step, download_step)

    def test_generate_download_requests(self):
        """
        Assert that generate_download_requests returns the proper objects.
        """
        repo = mock.MagicMock()
        conduit = mock.MagicMock()
        config = mock.MagicMock()
        working_dir = '/some/dir'
        step = sync.GetMetadataStep(repo, conduit, config, working_dir)
        step.parent = mock.MagicMock()
        step.parent._feed_url = 'http://example.com'
        step.parent._package_names = ['numpy', 'scipy']

        requests = step.generate_download_requests()

        self.assertTrue(isinstance(requests, types.GeneratorType))
        # For the remainder of our tests, it will be more useful if requests is a list
        requests = list(requests)
        self.assertEqual(len(requests), 2)
        request_urls = [r.url for r in requests]
        self.assertEqual(
            request_urls,
            ['http://example.com/pypi/numpy/json/', 'http://example.com/pypi/scipy/json/'])
        # A StringIO should have been used for the destination, and the data should be an empty dict
        for r in requests:
            self.assertEqual(type(r.destination), type(StringIO()))
            self.assertEqual(r.data, {})


class TestSyncStep(unittest.TestCase):
    """
    This class contains tests for the SyncStep class.
    """
    @mock.patch('pulp_python.plugins.importers.sync.DownloadPackagesStep.__init__',
                side_effect=sync.DownloadPackagesStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.GetMetadataStep.__init__',
                side_effect=sync.GetMetadataStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.PluginStep.__init__',
                side_effect=sync.publish_step.PluginStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.SyncStep.generate_download_requests',
                autospec=True)
    def test___init___no_packages(self, generate_download_requests, super___init__,
                                  get_metadata___init__, download_packages___init__):
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
        self.assertEqual(step._package_names, [])
        # _packages_to_download should have been initialized to the empty list
        self.assertEqual(step._packages_to_download, [])
        # Two child steps should have been added
        self.assertEqual(len(step.children), 2)
        self.assertEqual(type(step.children[0]), sync.GetMetadataStep)
        self.assertEqual(type(step.children[1]), sync.DownloadPackagesStep)
        # Make sure the steps were initialized properly
        get_metadata___init__.assert_called_once_with(step.children[0], repo, conduit, config,
                                                      working_dir)
        downloads = generate_download_requests.return_value
        download_packages___init__.assert_called_once_with(
            step.children[1], 'sync_step_download_packages', downloads=downloads, repo=repo,
            config=config, conduit=conduit, working_dir=working_dir,
            description=_('Downloading and processing Python packages.'))

    @mock.patch('pulp_python.plugins.importers.sync.DownloadPackagesStep.__init__',
                side_effect=sync.DownloadPackagesStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.GetMetadataStep.__init__',
                side_effect=sync.GetMetadataStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.PluginStep.__init__',
                side_effect=sync.publish_step.PluginStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.SyncStep.generate_download_requests',
                autospec=True)
    def test___init___one_package(self, generate_download_requests, super___init__,
                                  get_metadata___init__, download_packages___init__):
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
        self.assertEqual(step._package_names, ['numpy'])
        # _packages_to_download should have been initialized to the empty list
        self.assertEqual(step._packages_to_download, [])
        # Two child steps should have been added
        self.assertEqual(len(step.children), 2)
        self.assertEqual(type(step.children[0]), sync.GetMetadataStep)
        self.assertEqual(type(step.children[1]), sync.DownloadPackagesStep)
        # Make sure the steps were initialized properly
        get_metadata___init__.assert_called_once_with(step.children[0], repo, conduit, config,
                                                      working_dir)
        downloads = generate_download_requests.return_value
        download_packages___init__.assert_called_once_with(
            step.children[1], 'sync_step_download_packages', downloads=downloads, repo=repo,
            config=config, conduit=conduit, working_dir=working_dir,
            description=_('Downloading and processing Python packages.'))

    @mock.patch('pulp_python.plugins.importers.sync.DownloadPackagesStep.__init__',
                side_effect=sync.DownloadPackagesStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.GetMetadataStep.__init__',
                side_effect=sync.GetMetadataStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.publish_step.PluginStep.__init__',
                side_effect=sync.publish_step.PluginStep.__init__, autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.SyncStep.generate_download_requests',
                autospec=True)
    def test___init___three_packages(self, generate_download_requests, super___init__,
                                     get_metadata___init__, download_packages___init__):
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
        self.assertEqual(step._package_names, ['numpy', 'scipy', 'django'])
        # _packages_to_download should have been initialized to the empty list
        self.assertEqual(step._packages_to_download, [])
        # Two child steps should have been added
        self.assertEqual(len(step.children), 2)
        self.assertEqual(type(step.children[0]), sync.GetMetadataStep)
        self.assertEqual(type(step.children[1]), sync.DownloadPackagesStep)
        # Make sure the steps were initialized properly
        get_metadata___init__.assert_called_once_with(step.children[0], repo, conduit, config,
                                                      working_dir)
        downloads = generate_download_requests.return_value
        download_packages___init__.assert_called_once_with(
            step.children[1], 'sync_step_download_packages', downloads=downloads, repo=repo,
            config=config, conduit=conduit, working_dir=working_dir,
            description=_('Downloading and processing Python packages.'))

    def test_generate_download_requests(self):
        """
        Ensure correct operation from generate_download_requests().
        """
        repo = mock.MagicMock()
        conduit = mock.MagicMock()
        config = mock.MagicMock()
        working_dir = '/some/dir'
        step = sync.SyncStep(repo, conduit, config, working_dir)
        step._packages_to_download = [{'url': 'http://example.com/cool.tar.gz'},
                                      {'url': 'http://example.com/beats.tar.gz'}]

        requests = step.generate_download_requests()

        self.assertTrue(isinstance(requests, types.GeneratorType))
        # For the remainder of our tests, it will be more useful if requests is a list
        requests = list(requests)
        self.assertEqual(len(requests), 2)
        request_urls = [r.url for r in requests]
        self.assertEqual(
            request_urls,
            ['http://example.com/cool.tar.gz', 'http://example.com/beats.tar.gz'])
        # The destinations should both have been paths
        request_destinations = [r.destination for r in requests]
        expected_destinations = [
            os.path.join(working_dir, '%s.tar.gz' % f) for f in ['cool', 'beats']]
        self.assertEqual(request_destinations, expected_destinations)
        requests_data = [r.data for r in requests]
        self.assertEqual(requests_data, step._packages_to_download)

    @mock.patch('pulp_python.plugins.importers.sync.SyncStep._build_final_report',
                autospec=True)
    @mock.patch('pulp_python.plugins.importers.sync.SyncStep.process_lifecycle',
                autospec=True)
    def test_sync(self, process_lifecycle, _build_final_report):
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
