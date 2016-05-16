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
    @mock.patch('pulp.server.controllers.repository.get_unit_model_querysets', spec_set=True)
    @mock.patch('pulp.server.controllers.repository.associate_single_unit', spec_set=True)
    def test_import_units_units_none(self, mock_associate, mock_get):
        """
        Assert correct behavior when units == None.
        """
        python_importer = importer.PythonImporter()
        dest_repo = mock.MagicMock()
        source_repo = mock.MagicMock()
        units = ['unit_a', 'unit_b', 'unit_3']
        mock_get.return_value = [units]

        imported_units = python_importer.import_units(source_repo, dest_repo, mock.MagicMock(),
                                                      mock.MagicMock(), units=None)

        mock_get.assert_called_once_with(source_repo.repo_obj.repo_id, models.Package)
        # Assert that the units were associated correctly
        associate_unit_call_args = [c[1] for c in mock_associate.mock_calls]
        self.assertEqual(associate_unit_call_args, [(dest_repo.repo_obj, u) for u in units])
        # Assert that the units were returned
        self.assertEqual(imported_units, units)

    @mock.patch('pulp.server.controllers.repository.associate_single_unit', spec_set=True)
    def test_import_units_units_not_none(self, mock_associate):
        """
        Assert correct behavior when units != None.
        """
        python_importer = importer.PythonImporter()
        dest_repo = mock.MagicMock()
        units = ['unit_a', 'unit_b', 'unit_3']

        imported_units = python_importer.import_units(mock.MagicMock(), dest_repo, mock.MagicMock(),
                                                      mock.MagicMock(), units=units)

        # Assert that the units were associated correctly
        associate_unit_call_args = [c[1] for c in mock_associate.mock_calls]
        self.assertEqual(associate_unit_call_args, [(dest_repo.repo_obj, u) for u in units])
        # Assert that the units were returned
        self.assertEqual(imported_units, units)

    def test_metadata(self):
        """
        Test the metadata class method's return value.
        """
        metadata = importer.PythonImporter.metadata()

        expected_value = {
            'id': constants.IMPORTER_TYPE_ID, 'display_name': _('Python Importer'),
            'types': [constants.PACKAGE_TYPE_ID]}
        self.assertEqual(metadata, expected_value)

    @mock.patch('pulp_python.plugins.importers.importer.shutil.rmtree')
    @mock.patch('pulp_python.plugins.importers.importer.sync.SyncStep.__init__')
    @mock.patch('pulp_python.plugins.importers.importer.sync.SyncStep.sync')
    @mock.patch('pulp_python.plugins.importers.importer.tempfile.mkdtemp')
    def test_sync_repo_failure(self, mkdtemp, sync, __init__, rmtree):
        """
        Test the sync_repo() method when the sync fails.
        """
        config = mock.MagicMock()
        python_importer = importer.PythonImporter()
        repo = mock.MagicMock()
        sync_conduit = mock.MagicMock()
        # Fake the sync raising some bogus error
        sync.side_effect = IOError('I/O error, lol!')
        __init__.return_value = None

        try:
            python_importer.sync_repo(repo, sync_conduit, config)
        except IOError as e:
            # Make sure the error was passed on as it should have been
            self.assertEqual(str(e), 'I/O error, lol!')

        # A temporary working dir should have been created in the repo's working dir
        mkdtemp.assert_called_once_with(dir=repo.working_dir)
        # No matter what happens, it's important that we cleaned up the temporary dir
        rmtree.assert_called_once_with(mkdtemp.return_value, ignore_errors=True)
        # Make sure the SyncStep was initialized correctly
        __init__.assert_called_once_with(repo=repo, conduit=sync_conduit, config=config,
                                         working_dir=mkdtemp.return_value)
        # Make sure all the right args were passed on to sync()
        sync.assert_called_once_with()

    @mock.patch('pulp_python.plugins.importers.importer.shutil.rmtree')
    @mock.patch('pulp_python.plugins.importers.importer.sync.SyncStep.__init__')
    @mock.patch('pulp_python.plugins.importers.importer.sync.SyncStep.sync')
    @mock.patch('pulp_python.plugins.importers.importer.tempfile.mkdtemp')
    def test_sync_repo_success(self, mkdtemp, sync, __init__, rmtree):
        """
        Test the sync_repo() method when the sync is successful.
        """
        config = mock.MagicMock()
        python_importer = importer.PythonImporter()
        repo = mock.MagicMock()
        sync_conduit = mock.MagicMock()
        sync_report = mock.MagicMock()
        sync.return_value = sync_report
        __init__.return_value = None

        return_value = python_importer.sync_repo(repo, sync_conduit, config)

        # A temporary working dir should have been created in the repo's working dir
        mkdtemp.assert_called_once_with(dir=repo.working_dir)
        # No matter what happens, it's important that we cleaned up the temporary dir
        rmtree.assert_called_once_with(mkdtemp.return_value, ignore_errors=True)
        # Make sure the SyncStep was initialized correctly
        __init__.assert_called_once_with(repo=repo, conduit=sync_conduit, config=config,
                                         working_dir=mkdtemp.return_value)
        # Make sure all the right args were passed on to sync()
        sync.assert_called_once_with()
        # And, of course, assert that the sync report was returned
        self.assertEqual(return_value, sync_report)

    def test_validate_config(self):
        """
        There is no config, so we'll just assert that validation passes.
        """
        python_importer = importer.PythonImporter()

        return_value = python_importer.validate_config(mock.MagicMock(), {})

        expected_value = (True, '')
        self.assertEqual(return_value, expected_value)


class TestUploadUnit(unittest.TestCase):
    """
    Assert correct operation of upload_unit().
    """
    def setUp(self):
        super(TestUploadUnit, self).setUp()
        self.repo = mock.MagicMock()
        self.type_id = constants.PACKAGE_TYPE_ID
        self.unit_key = {}
        self.metadata = {}
        self.file_path = '/some/path/1234'
        self.conduit = mock.MagicMock()
        self.config = {}

'''
TODO (asmacdo) upload units!
    @mock.patch('pulp.server.controllers.repository.rebuild_content_unit_counts', spec_set=True)
    @mock.patch('pulp.server.controllers.repository.associate_single_unit', spec_set=True)
    @mock.patch('pulp_python.plugins.models.Package.from_archive')
    def test_upload_unit(self, from_archive, mock_associate, mock_rebuild):
        """
        Assert upload_unit() works correctly and reports a success.
        """
        package = from_archive.return_value
        python_importer = importer.PythonImporter()
        report = python_importer.upload_unit(self.repo, self.type_id, self.unit_key, self.metadata,
                                             self.file_path, self.conduit, self.config)
        from_archive.assert_called_once_with(self.file_path)
        package.save_and_import_content.assert_called_once_with(self.file_path)
        mock_associate.assert_called_once_with(self.repo.repo_obj, package)
        self.assertTrue(report['success_flag'])

    @mock.patch('pulp_python.plugins.models.Package.from_archive')
    def test_upload_unit_failure(self, from_archive):
        """
        Assert that upload_unit() reports failure.
        """
        expected_msg = 'upload failure message'
        from_archive.side_effect = Exception(expected_msg)
        python_importer = importer.PythonImporter()
        report = python_importer.upload_unit(self.repo, self.type_id, self.unit_key, self.metadata,
                                             self.file_path, self.conduit, self.config)
        self.assertFalse(report['success_flag'])
        self.assertEqual(report['summary'], expected_msg)
'''
