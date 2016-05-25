"""
This module contains tests for the pulp_python.extensions.admin.upload module.
"""
import unittest

import mock

from pulp_python.common import constants
from pulp_python.extensions.admin import upload


@mock.patch('pulp.client.upload.manager.UploadManager.init_with_defaults', mock.MagicMock())
class TestUploadPackageCommand(unittest.TestCase):
    """
    This class contains tests for the UploadPackageCommand class.
    """
    def test_determine_type_id(self):
        """
        Assert that determine_type_id() returns the correct type.
        """
        command = upload.UploadPackageCommand(mock.MagicMock())

        type_id = command.determine_type_id('some_file_name', some='kwargs')

        self.assertEqual(type_id, constants.PACKAGE_TYPE_ID)

    def test_generate_unit_key(self):
        """
        Assert that generate_unit_key() returns the filename.
        """
        command = upload.UploadPackageCommand(mock.MagicMock())

        key = command.generate_unit_key('some', 'args', and_some='kwargs')

        self.assertEqual(key, {'filename': 'some'})

    def test_generate_unit_key_with_path(self):
        """
        Assert that generate_unit_key() returns the filename, even when it is passed a path.
        """
        command = upload.UploadPackageCommand(mock.MagicMock())

        key = command.generate_unit_key('path/mock_file', 'args', and_some='kwargs')

        self.assertEqual(key, {'filename': 'mock_file'})
