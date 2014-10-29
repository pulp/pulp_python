"""
Contains tests for pulp_python.plugins.importers.importer.
"""
from gettext import gettext as _
import unittest

import mock

from pulp_python.common import constants
from pulp_python.plugins import models
from pulp_python.plugins.importers import importer


class TestEntryPoint(unittest.TestCase):
    """
    Tests for the entry_point() function.
    """
    def test_return_value(self):
        """
        Assert the correct return value for the entry_point() function.
        """
        return_value = importer.entry_point()

        expected_value = (importer.PythonImporter, {})
        self.assertEqual(return_value, expected_value)


class TestPythonImporter(unittest.TestCase):
    """
    This class contains tests for the PythonImporter class.
    """
    def test_metadata(self):
        """
        Test the metadata class method's return value.
        """
        metadata = importer.PythonImporter.metadata()

        expected_value = {
            'id': constants.IMPORTER_TYPE_ID, 'display_name': _('Python Importer'),
            'types': [constants.PACKAGE_TYPE_ID]}
        self.assertEqual(metadata, expected_value)

    @mock.patch('pulp_python.plugins.models.Package.from_archive')
    @mock.patch('pulp_python.plugins.models.Package.init_unit', autospec=True)
    @mock.patch('pulp_python.plugins.models.Package.save_unit', autospec=True)
    @mock.patch('shutil.move')
    def test_upload_unit(self, move, save_unit, init_unit, from_archive):
        """
        Assert correct operation of upload_unit().
        """
        package = models.Package(
            'name', 'version', 'summary', 'home_page', 'author', 'author_email', 'license',
            'description', 'platform', '_filename', '_checksum', '_checksum_type')
        from_archive.return_value = package
        storage_path = '/some/path/name-version.tar.bz2'

        def init_unit_side_effect(self, conduit):
            class Unit(object):
                def __init__(self, *args, **kwargs):
                    self.storage_path = storage_path
            self._unit = Unit()
        init_unit.side_effect = init_unit_side_effect

        python_importer = importer.PythonImporter()
        repo = mock.MagicMock()
        type_id = constants.PACKAGE_TYPE_ID
        unit_key = {}
        metadata = {}
        file_path = '/some/path/1234'
        conduit = mock.MagicMock()
        config = {}

        report = python_importer.upload_unit(repo, type_id, unit_key, metadata, file_path, conduit,
                                             config)

        self.assertEqual(report, {'success_flag': True, 'summary': {}, 'details': {}})
        from_archive.assert_called_once_with(file_path)
        init_unit.assert_called_once_with(package, conduit)
        save_unit.assert_called_once_with(package, conduit)
        move.assert_called_once_with(file_path, storage_path)

    def test_validate_config(self):
        """
        There is no config, so we'll just assert that validation passes.
        """
        python_importer = importer.PythonImporter()

        return_value = python_importer.validate_config(mock.MagicMock(), {})

        expected_value = (True, '')
        self.assertEqual(return_value, expected_value)
