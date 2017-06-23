"""
This modules contains tests for pulp_python.plugins.models.
"""

import hashlib
import unittest

import mock

from pulp_python.plugins import models


def make_package():
    return models.Package(
        name='foo',
        version='1.0.0',
        author='Mr Foo',
        filename='foo-1.0.0.tar.gz',
        packagetype='sdist',
        summary='Foo!',
        md5_digest='md5_123',
        _checksum='abc123',
        _checksum_type='some_type',
    )


class TestPackage(unittest.TestCase):
    """
    This class contains tests for the Package class.
    """

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

    def test_from_json(self):
        """
        Test that the data needed to instantiate a package comes from the right part of the JSON.
        """
        mock_pkg_attrs = {'filename': "m_file", "path": "earl", "packagetype": "mocktype",
                          'md5_digest': 'fleventyfive'}
        mock_release = "1.0.2"
        mock_dist_data = {"author": "me", "name": "test", "summary": "does stuff"}
        package = models.Package.from_json(mock_pkg_attrs, mock_release, mock_dist_data)
        self.assertEqual(package.filename, 'm_file')
        self.assertEqual(package.path, 'earl')
        self.assertEqual(package.packagetype, 'mocktype')
        self.assertEqual(package.md5_digest, 'fleventyfive')
        self.assertEqual(package._checksum_type, 'md5')
        self.assertEqual(package.version, '1.0.2')
        self.assertEqual(package.author, 'me')
        self.assertEqual(package.name, 'test')
        self.assertEqual(package.summary, 'does stuff')

    @mock.patch('pulp_python.plugins.models.Package.checksum')
    @mock.patch('pulp_python.plugins.models.PackageFile')
    def test_from_file(self, m_twine, m_checksum):
        """
        Ensure that before init, metadata from twine is filtered leaving only required fields.
        """
        twine_to_dict = m_twine.from_filename.return_value.metadata_dictionary
        twine_to_dict.return_value = {'name': 'necessary', 'filetype': 'also_necessary',
                                      'extra_field': 'do not include'}
        package = models.Package.from_archive('mock_path')
        self.assertEqual(package.name, 'necessary')
        self.assertFalse(hasattr(package, 'extra_field'))

    def test_checksum_path(self):
        pkg = make_package()
        self.assertEqual(pkg.checksum_path, 'source/f/foo/foo-1.0.0.tar.gz#some_type=abc123')

    def test_package_specific_metadata(self):
        pkg = make_package()
        expected_metadata = {
            'filename': u'foo-1.0.0.tar.gz',
            'packagetype': u'sdist',
            'path': u'source/f/foo/foo-1.0.0.tar.gz',
            'md5_digest': u'md5_123',
            'checksum': u'abc123',
            'checksum_type': u'some_type',
        }
        self.assertEqual(pkg.package_specific_metadata, expected_metadata)

    def test_project_metadata(self):
        pkg = make_package()
        expected_metadata = {
            'name': 'foo',
            'summary': 'Foo!',
            'author': 'Mr Foo',
        }
        self.assertEqual(pkg.project_metadata, expected_metadata)

    def test___repr__(self):
        """
        Assert correct behavior with the __repr__() method.
        """
        pp = make_package()

        self.assertEqual(repr(pp), 'Package(name=foo, version=1.0.0)')
