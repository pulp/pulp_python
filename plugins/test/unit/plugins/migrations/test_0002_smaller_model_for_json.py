"""
This module contains tests for pulp.server.db.migrations.0002_smaller_model_for_json.py
"""
import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way

PATH_TO_MODULE = 'pulp_python.plugins.migrations.0002_smaller_model_for_json'
migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(unittest.TestCase):
    """
    Test the migrate() function.
    """

    @mock.patch.object(migration.connection, 'get_database')
    def test_repos_collection_id_renamed(self, mock_get_database):
        mock_get_database.return_value.collection_names.return_value = []
        collection = mock_get_database.return_value['archived_calls']
        migration.migrate()
        collection.update.assert_has_calls([
            mock.call({}, {"$unset": {"home_page": True}}, multi=True),
            mock.call({}, {"$unset": {"platform": True}}, multi=True),
            mock.call({}, {"$unset": {"license": True}}, multi=True),
            mock.call({}, {"$unset": {"_metadata_file": True}}, multi=True),
            mock.call({}, {"$unset": {"description": True}}, multi=True),
            mock.call({}, {"$unset": {"author_email": True}}, multi=True),
            mock.call({}, {"$rename": {"_filename": "filename"}}, multi=True)
        ])
