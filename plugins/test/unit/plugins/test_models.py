"""
This modules contains tests for pulp_python.plugins.models.
"""
from gettext import gettext as _
import hashlib
import re
import tarfile
import unittest

import mock

from pulp_python.common import constants
from pulp_python.plugins import models


# The BAD_MANIFEST is missing the Version field.
BAD_MANIFEST = """Metadata-Version: 1.1
Name: nectar
Summary: Performance tuned network download client library
Home-page: https://github.com/pulp/nectar
Author: Pulp Team
Author-email: pulp-list@redhat.com
License: GPLv2
Description: UNKNOWN
Platform: UNKNOWN
Classifier: Intended Audience :: Developers
Classifier: Intended Audience :: Information Technology
Classifier: License :: OSI Approved :: GNU General Public License v2 (GPLv2)
Classifier: Operating System :: POSIX
Classifier: Programming Language :: Python :: 2.6
Classifier: Programming Language :: Python :: 2.7
Classifier: Topic :: Software Development :: Libraries :: Python Modules"""

GOOD_MANIFEST = """Metadata-Version: 1.1
Name: nectar
Version: 1.3.1
Summary: Performance tuned network download client library
Home-page: https://github.com/pulp/nectar
Author: Pulp Team
Author-email: pulp-list@redhat.com
License: GPLv2
Description: UNKNOWN
Platform: UNKNOWN
Classifier: Intended Audience :: Developers
Classifier: Intended Audience :: Information Technology
Classifier: License :: OSI Approved :: GNU General Public License v2 (GPLv2)
Classifier: Operating System :: POSIX
Classifier: Programming Language :: Python :: 2.6
Classifier: Programming Language :: Python :: 2.7
Classifier: Topic :: Software Development :: Libraries :: Python Modules"""


class TestPackage(unittest.TestCase):
    """
    This class contains tests for the Package class.
    """
    def test_class_attributes(self):
        """
        Assert correct class attributes.
        """
        self.assertEqual(models.Package.TYPE, constants.PACKAGE_TYPE_ID)
        self.assertEqual(
            models.Package._ATTRS, ('name', 'version', 'summary', 'home_page', 'author',
                                    'author_email', 'license', 'description', 'platform',
                                    '_filename', '_checksum', '_checksum_type', '_metadata_file'))

    @mock.patch('pulp_python.plugins.models.Package.checksum', return_value='sum')
    @mock.patch('pulp_python.plugins.models.Package._compression_type', return_value='.gz')
    @mock.patch('pulp_python.plugins.models.tarfile.open')
    def test_from_archive_closely_named_metadata(self, tarfile_open, _compression_type, checksum):
        """
        Test from_archive() with files named very similarly to PKG-INFO to test the regex. This also
        coincidentally tests behavior when the archive is missing metadata.
        """
        tarfile_open.return_value = mock.MagicMock(spec=tarfile.TarFile)

        class TarInfo(object):
            """
            This class fakes being a TarInfo. It just needs a name.
            """
            def __init__(self, name):
                self.name = name

        members = [TarInfo(name) for name in ['aPKG-INFO', 'PKG-INFO.txt', '/path/to/PKG-INFO.txt'
                                              '/path/to/aPKG-INFO']]
        tarfile_open.return_value.getmembers.return_value = members
        path = '/some/path.tar.gz'

        try:
            models.Package.from_archive(path)
            self.fail('The above call should have raised a ValueError!')
        except ValueError as e:
            self.assertTrue(
                _('The archive at %s does not contain a PKG-INFO file.') % path in str(e))

        tarfile_open.assert_called_once_with(path)
        _compression_type.assert_called_once_with(path)
        tarfile_open.return_value.close.assert_called_once_with()

    @mock.patch('pulp_python.plugins.models.Package.checksum', return_value='sum')
    @mock.patch('pulp_python.plugins.models.Package._compression_type', return_value='.gz')
    @mock.patch('pulp_python.plugins.models.tarfile.open')
    def test_from_archive_multiple_metadatas(self, tarfile_open, _compression_type, checksum):
        """
        Test from_archive() with multiple PKG-INFO files.
        """
        tarfile_open.return_value = mock.MagicMock(spec=tarfile.TarFile)

        class TarInfo(object):
            """
            This class fakes being a TarInfo. It just needs a name.
            """
            def __init__(self, name):
                self.name = name

        members = [TarInfo(name) for name in ['package-1.2.3/some/stuff/PKG-INFO',
                                              'package-1.2.3',
                                              'package-1.2.3/PKG-INFO',
                                              'package-1.2.3/other/stuff/PKG-INFO']]
        mock_manifest_file = mock.MagicMock(spec=file)
        mock_manifest_file.read.return_value = GOOD_MANIFEST
        tarfile_open.return_value.extractfile.return_value = mock_manifest_file
        tarfile_open.return_value.getmembers.return_value = members
        path = '/some/path.tar.gz'

        package = models.Package.from_archive(path)

        self.assertEqual(package._metadata_file, 'package-1.2.3/PKG-INFO')

        tarfile_open.assert_called_once_with(path)
        _compression_type.assert_called_once_with(path)
        tarfile_open.return_value.close.assert_called_once_with()

    @mock.patch('pulp_python.plugins.models.Package.checksum', return_value='sum')
    @mock.patch('pulp_python.plugins.models.Package._compression_type', return_value='.gz')
    @mock.patch('pulp_python.plugins.models.tarfile.open')
    def test_from_archive_empty_metadata(self, tarfile_open, _compression_type, checksum):
        """
        Test from_archive() when the PKG-INFO file is empty.
        """
        tarfile_open.return_value = mock.MagicMock(spec=tarfile.TarFile)

        class TarInfo(object):
            """
            This class fakes being a TarInfo. It just needs a name.
            """
            def __init__(self, name):
                self.name = name

        members = [TarInfo(name) for name in ['package-1.2.3', 'package-1.2.3/PKG-INFO']]
        tarfile_open.return_value.getmembers.return_value = members
        mock_manifest_file = mock.MagicMock(spec=file)
        mock_manifest_file.read.return_value = ''
        tarfile_open.return_value.extractfile.return_value = mock_manifest_file
        path = '/some/path.tar.gz'

        try:
            models.Package.from_archive(path)
            self.fail('The above call should have raised a ValueError!')
        except ValueError as e:
            self.assertTrue('The PKG-INFO file is missing required attributes.' in str(e))

        tarfile_open.assert_called_once_with(path)
        _compression_type.assert_called_once_with(path)
        tarfile_open.return_value.extractfile.assert_called_once_with(members[-1])
        tarfile_open.return_value.close.assert_called_once_with()

    def test_from_archive_file_not_found(self):
        """
        Test from_archive() when the given path does not exist.
        """
        dne = '/some/path/that/doesnt/exist'

        self.assertRaises(IOError, models.Package.from_archive, dne)

    @mock.patch('pulp_python.plugins.models.Package.checksum', return_value='sum')
    @mock.patch('pulp_python.plugins.models.Package._compression_type', return_value='.gz')
    @mock.patch('pulp_python.plugins.models.tarfile.open')
    def test_from_archive_good_metadata(self, tarfile_open, _compression_type, checksum):
        """
        Test from_archive() with good metadata, with PKG-INFO at the typical location as would be
        done by setup.py sdist.
        """
        tarfile_open.return_value = mock.MagicMock(spec=tarfile.TarFile)

        class TarInfo(object):
            """
            This class fakes being a TarInfo. It just needs a name.
            """
            def __init__(self, name):
                self.name = name

        members = [
            TarInfo(name) for name in ['nectar-1.3.1', 'nectar-1.3.1/nectar',
                                       'nectar-1.3.1/nectar/config.py',
                                       'nectar-1.3.1/nectar/downloaders',
                                       'nectar-1.3.1/nectar/downloaders/threaded.py',
                                       'nectar-1.3.1/nectar/downloaders/base.py',
                                       'nectar-1.3.1/nectar/downloaders/__init__.py',
                                       'nectar-1.3.1/nectar/downloaders/local.py',
                                       'nectar-1.3.1/nectar/__init__.py',
                                       'nectar-1.3.1/nectar/exceptions.py',
                                       'nectar-1.3.1/nectar/listener.py',
                                       'nectar-1.3.1/nectar/report.py',
                                       'nectar-1.3.1/nectar/request.py', 'nectar-1.3.1/PKG-INFO']]
        tarfile_open.return_value.getmembers.return_value = members
        mock_manifest_file = mock.MagicMock(spec=file)
        mock_manifest_file.read.return_value = GOOD_MANIFEST
        tarfile_open.return_value.extractfile.return_value = mock_manifest_file
        path = '/some/path.tar.gz'

        package = models.Package.from_archive(path)

        self.assertEqual(package.name, 'nectar')
        self.assertEqual(package.version, '1.3.1')
        self.assertEqual(package.summary, 'Performance tuned network download client library')
        self.assertEqual(package.home_page, 'https://github.com/pulp/nectar')
        self.assertEqual(package.author, 'Pulp Team')
        self.assertEqual(package.author_email, 'pulp-list@redhat.com')
        self.assertEqual(package.license, 'GPLv2')
        self.assertEqual(package.description, 'UNKNOWN')
        self.assertEqual(package.platform, 'UNKNOWN')
        self.assertEqual(package._filename, 'nectar-1.3.1.tar.gz')
        self.assertEqual(package._checksum, 'sum')
        self.assertEqual(package._checksum_type, 'sha512')
        self.assertEqual(package._unit, None)
        checksum.assert_called_once_with(path)
        tarfile_open.assert_called_once_with(path)
        _compression_type.assert_called_once_with(path)
        tarfile_open.return_value.extractfile.assert_called_once_with(members[-1])
        tarfile_open.return_value.close.assert_called_once_with()

    @mock.patch('pulp_python.plugins.models.Package.checksum', return_value='sum')
    @mock.patch('pulp_python.plugins.models.Package._compression_type', return_value='.gz')
    @mock.patch('pulp_python.plugins.models.tarfile.open')
    def test_from_archive_dos_metadata(self, tarfile_open, _compression_type, checksum):
        """
        Test from_archive() with good metadata that has DOS line endings, with
        PKG-INFO at the typical location as would be done by setup.py sdist.
        """
        tarfile_open.return_value = mock.MagicMock(spec=tarfile.TarFile)

        class TarInfo(object):
            """
            This class fakes being a TarInfo. It just needs a name.
            """
            def __init__(self, name):
                self.name = name

        members = [
            TarInfo(name) for name in ['nectar-1.3.1', 'nectar-1.3.1/nectar',
                                       'nectar-1.3.1/nectar/config.py',
                                       'nectar-1.3.1/nectar/downloaders',
                                       'nectar-1.3.1/nectar/downloaders/threaded.py',
                                       'nectar-1.3.1/nectar/downloaders/base.py',
                                       'nectar-1.3.1/nectar/downloaders/__init__.py',
                                       'nectar-1.3.1/nectar/downloaders/local.py',
                                       'nectar-1.3.1/nectar/__init__.py',
                                       'nectar-1.3.1/nectar/exceptions.py',
                                       'nectar-1.3.1/nectar/listener.py',
                                       'nectar-1.3.1/nectar/report.py',
                                       'nectar-1.3.1/nectar/request.py', 'nectar-1.3.1/PKG-INFO']]
        tarfile_open.return_value.getmembers.return_value = members
        mock_manifest_file = mock.MagicMock(spec=file)
        mock_manifest_file.read.return_value = re.sub(r'\n', '\r\n', GOOD_MANIFEST)
        tarfile_open.return_value.extractfile.return_value = mock_manifest_file
        path = '/some/path.tar.gz'

        package = models.Package.from_archive(path)

        self.assertEqual(package.name, 'nectar')
        self.assertEqual(package.version, '1.3.1')
        self.assertEqual(package.summary, 'Performance tuned network download client library')
        self.assertEqual(package.home_page, 'https://github.com/pulp/nectar')
        self.assertEqual(package.author, 'Pulp Team')
        self.assertEqual(package.author_email, 'pulp-list@redhat.com')
        self.assertEqual(package.license, 'GPLv2')
        self.assertEqual(package.description, 'UNKNOWN')
        self.assertEqual(package.platform, 'UNKNOWN')
        self.assertEqual(package._filename, 'nectar-1.3.1.tar.gz')
        self.assertEqual(package._checksum, 'sum')
        self.assertEqual(package._checksum_type, 'sha512')
        self.assertEqual(package._unit, None)
        checksum.assert_called_once_with(path)
        tarfile_open.assert_called_once_with(path)
        _compression_type.assert_called_once_with(path)
        tarfile_open.return_value.extractfile.assert_called_once_with(members[-1])
        tarfile_open.return_value.close.assert_called_once_with()

    @mock.patch('pulp_python.plugins.models.Package.checksum', return_value='sum')
    @mock.patch('pulp_python.plugins.models.Package._compression_type', return_value='.gz')
    @mock.patch('pulp_python.plugins.models.tarfile.open')
    def test_from_archive_metadata_at_absolute_root(self, tarfile_open, _compression_type,
                                                    checksum):
        """
        Test from_archive() with good metadata when the PKG-INFO file is at /.
        """
        tarfile_open.return_value = mock.MagicMock(spec=tarfile.TarFile)

        class TarInfo(object):
            """
            This class fakes being a TarInfo. It just needs a name.
            """
            def __init__(self, name):
                self.name = name

        members = [
            TarInfo(name) for name in ['/PKG-INFO', 'nectar-1.3.1', 'nectar-1.3.1/nectar',
                                       'nectar-1.3.1/nectar/config.py',
                                       'nectar-1.3.1/nectar/downloaders',
                                       'nectar-1.3.1/nectar/downloaders/threaded.py',
                                       'nectar-1.3.1/nectar/downloaders/base.py',
                                       'nectar-1.3.1/nectar/downloaders/__init__.py',
                                       'nectar-1.3.1/nectar/downloaders/local.py',
                                       'nectar-1.3.1/nectar/__init__.py',
                                       'nectar-1.3.1/nectar/exceptions.py',
                                       'nectar-1.3.1/nectar/listener.py',
                                       'nectar-1.3.1/nectar/report.py',
                                       'nectar-1.3.1/nectar/request.py']]
        tarfile_open.return_value.getmembers.return_value = members
        mock_manifest_file = mock.MagicMock(spec=file)
        mock_manifest_file.read.return_value = GOOD_MANIFEST
        tarfile_open.return_value.extractfile.return_value = mock_manifest_file
        path = '/some/path.tar.gz'

        package = models.Package.from_archive(path)

        self.assertEqual(package.name, 'nectar')
        self.assertEqual(package.version, '1.3.1')
        self.assertEqual(package.summary, 'Performance tuned network download client library')
        self.assertEqual(package.home_page, 'https://github.com/pulp/nectar')
        self.assertEqual(package.author, 'Pulp Team')
        self.assertEqual(package.author_email, 'pulp-list@redhat.com')
        self.assertEqual(package.license, 'GPLv2')
        self.assertEqual(package.description, 'UNKNOWN')
        self.assertEqual(package.platform, 'UNKNOWN')
        self.assertEqual(package._filename, 'nectar-1.3.1.tar.gz')
        self.assertEqual(package._checksum, 'sum')
        self.assertEqual(package._checksum_type, 'sha512')
        self.assertEqual(package._unit, None)
        checksum.assert_called_once_with(path)
        tarfile_open.assert_called_once_with(path)
        _compression_type.assert_called_once_with(path)
        tarfile_open.return_value.extractfile.assert_called_once_with(members[0])
        tarfile_open.return_value.close.assert_called_once_with()

    @mock.patch('pulp_python.plugins.models.Package.checksum', return_value='sum')
    @mock.patch('pulp_python.plugins.models.Package._compression_type', return_value='.gz')
    @mock.patch('pulp_python.plugins.models.tarfile.open')
    def test_from_archive_metadata_at_root(self, tarfile_open, _compression_type, checksum):
        """
        Test from_archive() when the PKG-INFO file is at the root of the archive.
        """
        tarfile_open.return_value = mock.MagicMock(spec=tarfile.TarFile)

        class TarInfo(object):
            """
            This class fakes being a TarInfo. It just needs a name.
            """
            def __init__(self, name):
                self.name = name

        members = [
            TarInfo(name) for name in ['nectar-1.3.1', 'nectar-1.3.1/nectar',
                                       'nectar-1.3.1/nectar/config.py',
                                       'nectar-1.3.1/nectar/downloaders',
                                       'nectar-1.3.1/nectar/downloaders/threaded.py',
                                       'nectar-1.3.1/nectar/downloaders/base.py',
                                       'nectar-1.3.1/nectar/downloaders/__init__.py',
                                       'nectar-1.3.1/nectar/downloaders/local.py',
                                       'nectar-1.3.1/nectar/__init__.py',
                                       'nectar-1.3.1/nectar/exceptions.py',
                                       'nectar-1.3.1/nectar/listener.py',
                                       'nectar-1.3.1/nectar/report.py',
                                       'nectar-1.3.1/nectar/request.py', 'PKG-INFO']]
        tarfile_open.return_value.getmembers.return_value = members
        mock_manifest_file = mock.MagicMock(spec=file)
        mock_manifest_file.read.return_value = GOOD_MANIFEST
        tarfile_open.return_value.extractfile.return_value = mock_manifest_file
        path = '/some/path.tar.gz'

        package = models.Package.from_archive(path)

        self.assertEqual(package.name, 'nectar')
        self.assertEqual(package.version, '1.3.1')
        self.assertEqual(package.summary, 'Performance tuned network download client library')
        self.assertEqual(package.home_page, 'https://github.com/pulp/nectar')
        self.assertEqual(package.author, 'Pulp Team')
        self.assertEqual(package.author_email, 'pulp-list@redhat.com')
        self.assertEqual(package.license, 'GPLv2')
        self.assertEqual(package.description, 'UNKNOWN')
        self.assertEqual(package.platform, 'UNKNOWN')
        self.assertEqual(package._filename, 'nectar-1.3.1.tar.gz')
        self.assertEqual(package._checksum, 'sum')
        self.assertEqual(package._checksum_type, 'sha512')
        self.assertEqual(package._unit, None)
        checksum.assert_called_once_with(path)
        tarfile_open.assert_called_once_with(path)
        _compression_type.assert_called_once_with(path)
        tarfile_open.return_value.extractfile.assert_called_once_with(members[-1])
        tarfile_open.return_value.close.assert_called_once_with()

    @mock.patch('pulp_python.plugins.models.Package.checksum', return_value='sum')
    @mock.patch('pulp_python.plugins.models.Package._compression_type', return_value='.gz')
    @mock.patch('pulp_python.plugins.models.tarfile.open')
    def test_from_archive_missing_required_metadata(self, tarfile_open, _compression_type,
                                                    checksum):
        """
        Test from_archive() when the PKG-INFO file is missing required fields.
        """
        tarfile_open.return_value = mock.MagicMock(spec=tarfile.TarFile)

        class TarInfo(object):
            """
            This class fakes being a TarInfo. It just needs a name.
            """
            def __init__(self, name):
                self.name = name

        members = [
            TarInfo(name) for name in ['nectar-1.3.1', 'nectar-1.3.1/nectar',
                                       'nectar-1.3.1/nectar/config.py',
                                       'nectar-1.3.1/nectar/downloaders',
                                       'nectar-1.3.1/nectar/downloaders/threaded.py',
                                       'nectar-1.3.1/nectar/downloaders/base.py',
                                       'nectar-1.3.1/nectar/downloaders/__init__.py',
                                       'nectar-1.3.1/nectar/downloaders/local.py',
                                       'nectar-1.3.1/nectar/__init__.py',
                                       'nectar-1.3.1/nectar/exceptions.py',
                                       'nectar-1.3.1/nectar/listener.py',
                                       'nectar-1.3.1/nectar/report.py',
                                       'nectar-1.3.1/nectar/request.py', 'nectar-1.3.1/PKG-INFO']]
        tarfile_open.return_value.getmembers.return_value = members
        mock_manifest_file = mock.MagicMock(spec=file)
        mock_manifest_file.read.return_value = BAD_MANIFEST
        tarfile_open.return_value.extractfile.return_value = mock_manifest_file
        path = '/some/path.tar.gz'
        try:
            models.Package.from_archive(path)
            self.fail('The above call should have raised a ValueError!')
        except ValueError as e:
            self.assertTrue(_('The PKG-INFO file is missing required attributes.') in str(e))

        tarfile_open.assert_called_once_with(path)
        _compression_type.assert_called_once_with(path)
        tarfile_open.return_value.extractfile.assert_called_once_with(members[-1])
        tarfile_open.return_value.close.assert_called_once_with()

    def test_init_unit(self):
        """
        Test the init_unit() method.
        """
        pulp_unit = mock.MagicMock()
        conduit = mock.MagicMock()
        conduit.init_unit.return_value = pulp_unit
        name = 'nectar'
        version = '1.3.1'
        summary = 'a summary'
        home_page = 'http://github.com/pulp/nectar'
        author = 'The Pulp Team'
        author_email = 'pulp-list@redhat.com'
        license = 'GPLv2'
        description = 'a description'
        platform = 'Linux'
        _filename = 'nectar-1.3.1.tar.gz'
        _checksum = 'some_sum'
        _checksum_type = 'some-type'
        _metadata_file = 'nectar-1.3.1/PKG-INFO'
        pp = models.Package(name, version, summary, home_page, author, author_email, license,
                            description, platform, _filename, _checksum, _checksum_type,
                            _metadata_file)

        pp.init_unit(conduit)

        conduit.init_unit.assert_called_once_with(
            models.Package.TYPE, {'name': name, 'version': version},
            {'summary': summary, 'home_page': home_page, 'author': author,
             'author_email': author_email, 'license': license, 'description': description,
             'platform': platform, '_filename': _filename, '_checksum': _checksum,
             '_checksum_type': _checksum_type, '_metadata_file': _metadata_file},
            _filename)
        self.assertEqual(pp._unit, pulp_unit)

    def test_save_unit(self):
        """
        Test the save_unit() method.
        """
        conduit = mock.MagicMock()
        pp = models.Package(
            'name', 'version', 'summary', 'home_page', 'author', 'author_email', 'license',
            'description', 'platform', '_filename', '_checksum', '_checksum_type',
            '_metadata_file')
        pp._unit = mock.MagicMock()

        pp.save_unit(conduit)

        conduit.save_unit.assert_called_once_with(pp._unit)

    def test_storage_path(self):
        """
        Test the storage_path property.
        """
        pp = models.Package(
            'name', 'version', 'summary', 'home_page', 'author', 'author_email', 'license',
            'description', 'platform', '_filename', '_checksum', '_checksum_type',
            '_metadata_file')
        pp._unit = mock.MagicMock()
        path = '/some/path.tar.gz'
        pp._unit.storage_path.return_value = path

        sp = pp.storage_path()

        self.assertEqual(sp, path)

    @mock.patch('__builtin__.open')
    def test_checksum_default_sum(self, mock_open):
        """
        Assert that the checksum method works correctly with the default sum.
        """
        file_chunks = ['Hello', ' World!', '']

        def mock_read(size):
            """
            A fake file read() that will return "Hello", " World!" and "" when called three times.
            """
            self.assertEqual(size, 32 * 1024 * 1024)
            return file_chunks.pop(0)

        mock_open.return_value.__enter__.return_value.read.side_effect = mock_read
        path = '/some/path'

        checksum = models.Package.checksum(path)

        mock_open.assert_called_once_with(path)
        hasher = hashlib.sha512()
        hasher.update('Hello World!')
        self.assertEqual(checksum, hasher.hexdigest())

    @mock.patch('__builtin__.open')
    def test_checksum_md5(self, mock_open):
        """
        Assert that the checksum method works correctly with md5.
        """
        file_chunks = ['Hello', ' World!', '']

        def mock_read(size):
            """
            A fake file read() that will return "Hello", " World!" and "" when called three times.
            """
            self.assertEqual(size, 32 * 1024 * 1024)
            return file_chunks.pop(0)

        mock_open.return_value.__enter__.return_value.read.side_effect = mock_read
        path = '/some/path'

        checksum = models.Package.checksum(path, 'md5')

        mock_open.assert_called_once_with(path)
        hasher = hashlib.md5()
        hasher.update('Hello World!')
        self.assertEqual(checksum, hasher.hexdigest())

    @mock.patch('pulp_python.plugins.models.open', create=True)
    def test__compression_type_empty_file(self, mock_open):
        """
        Test that _compression_type() correctly handles empty files.
        """
        mock_file = mock.MagicMock(spec=file)
        mock_file.__enter__.return_value.read.return_value = ''
        mock_open.return_value = mock_file
        path = '/some/path/to/hello_world'

        compression_type = models.Package._compression_type(path)

        # Since "" isn't a magic string, the empty string should have been returned.
        self.assertEqual(compression_type, '')
        mock_open.assert_called_once_with(path)

    @mock.patch('pulp_python.plugins.models.open', create=True)
    def test__compression_type_handle_other(self, mock_open):
        """
        Test that _compression_type() correctly handles other files.
        """
        mock_file = mock.MagicMock(spec=file)
        mock_file.__enter__.return_value.read.return_value = 'Hello World!'
        mock_open.return_value = mock_file
        path = '/some/path/to/hello_world'

        compression_type = models.Package._compression_type(path)

        # Since "Hello World!" isn't a magic string, the empty string should have been returned.
        self.assertEqual(compression_type, '')
        mock_open.assert_called_once_with(path)

    @mock.patch('pulp_python.plugins.models.open', create=True)
    def test__compression_type_match_bz2(self, mock_open):
        """
        Test that _compression_type() correctly matches bz2 files.
        """
        mock_file = mock.MagicMock(spec=file)
        mock_file.__enter__.return_value.read.return_value = '\x42\x5a\x68Hello World!'
        mock_open.return_value = mock_file
        path = '/some/path/to/hello_world.bz2'

        compression_type = models.Package._compression_type(path)

        self.assertEqual(compression_type, '.bz2')
        mock_open.assert_called_once_with(path)

    @mock.patch('pulp_python.plugins.models.open', create=True)
    def test__compression_type_match_gz(self, mock_open):
        """
        Test that _compression_type() correctly matches gz files.
        """
        mock_file = mock.MagicMock(spec=file)
        mock_file.__enter__.return_value.read.return_value = '\x1f\x8b\x08Hello World!'
        mock_open.return_value = mock_file
        path = '/some/path/to/hello_world.gz'

        compression_type = models.Package._compression_type(path)

        self.assertEqual(compression_type, '.gz')
        mock_open.assert_called_once_with(path)

    @mock.patch('pulp_python.plugins.models.open', create=True)
    def test__compression_type_match_zip(self, mock_open):
        """
        Test that _compression_type() correctly matches zip files.
        """
        mock_file = mock.MagicMock(spec=file)
        mock_file.__enter__.return_value.read.return_value = '\x50\x4b\x03\x04Hello World!'
        mock_open.return_value = mock_file
        path = '/some/path/to/hello_world.zip'

        compression_type = models.Package._compression_type(path)

        self.assertEqual(compression_type, '.zip')
        mock_open.assert_called_once_with(path)

    def test__metadata_label(self):
        """
        Test various manipulations of possible metadata attributes with the _metadata_label()
        method.
        """
        expected_value_map = {'name': 'Name', 'author_email': 'Author-email', 'a': 'A'}

        for key, value in expected_value_map.items():
            self.assertEqual(models.Package._metadata_label(key), value)

    def test___init__(self):
        """
        Assert correct behavior with the __init__() method.
        """
        name = 'nectar'
        version = '1.3.1'
        summary = 'a summary'
        home_page = 'http://github.com/pulp/nectar'
        author = 'The Pulp Team'
        author_email = 'pulp-list@redhat.com'
        license = 'GPLv2'
        description = 'a description'
        platform = 'Linux'
        _filename = 'nectar-1.3.1.tar.gz'
        _checksum = 'abcde'
        _checksum_type = 'some_type'
        _metadata_file = 'nectar-1.3.1/PKG-INFO'

        pp = models.Package(name, version, summary, home_page, author, author_email, license,
                            description, platform, _filename, _checksum, _checksum_type,
                            _metadata_file)

        self.assertEqual(pp.name, name)
        self.assertEqual(pp.version, version)
        self.assertEqual(pp.summary, summary)
        self.assertEqual(pp.home_page, home_page)
        self.assertEqual(pp.author, author)
        self.assertEqual(pp.author_email, author_email)
        self.assertEqual(pp.license, license)
        self.assertEqual(pp.description, description)
        self.assertEqual(pp.platform, platform)
        self.assertEqual(pp._filename, _filename)
        self.assertEqual(pp._checksum, _checksum)
        self.assertEqual(pp._checksum_type, _checksum_type)
        self.assertEqual(pp._metadata_file, _metadata_file)
        self.assertEqual(pp._unit, None)

    def test___repr__(self):
        """
        Assert correct behavior with the __repr__() method.
        """
        name = 'nectar'
        version = '1.3.1'
        summary = 'a summary'
        home_page = 'http://github.com/pulp/nectar'
        author = 'The Pulp Team'
        author_email = 'pulp-list@redhat.com'
        license = 'GPLv2'
        description = 'a description'
        platform = 'Linux'
        _filename = 'nectar-1.3.1.tar.gz'
        _checksum = 'abcde'
        _checksum_type = 'some_type'
        _metadata_file = 'nectar-1.3.1/PKG-INFO'

        pp = models.Package(name, version, summary, home_page, author, author_email, license,
                            description, platform, _filename, _checksum, _checksum_type,
                            _metadata_file)

        self.assertEqual(repr(pp), 'Python Package: nectar-1.3.1')
