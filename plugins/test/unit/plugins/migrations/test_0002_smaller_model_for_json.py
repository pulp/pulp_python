"""
This module contains tests for pulp.server.db.migrations.0002_smaller_model_for_json.py
"""
import unittest

import mock

from pulp.server.db.migrate.models import _import_all_the_way

PATH_TO_MODULE = 'pulp_python.plugins.migrations.0002_smaller_model_for_json'
migration = _import_all_the_way(PATH_TO_MODULE)


@mock.patch.object(migration.connection, 'get_database')
class TestMigrate(unittest.TestCase):
    """
    Test the migrate() function.
    """
    @mock.patch.object(migration, "set_packagetype")
    @mock.patch.object(migration, "update_fields")
    def test_calls(self, mock_set_pkg_type, mock_update_fields, mock_get_database):
        collection = mock_get_database.return_value['archived_calls']
        migration.migrate()
        mock_set_pkg_type.assert_called_once_with(collection)
        mock_update_fields.assert_called_once_with(collection)
        collection.drop_indexes.assert_called_once_with()


class TestUpdateFields(unittest.TestCase):
    """
    Test that unnecessary fields are removed and `_filename` is renamed.
    """

    @mock.patch.object(migration.connection, 'get_database')
    def test_repos_collection_id_renamed(self, mock_get_database):
        mock_get_database.return_value.collection_names.return_value = []
        collection = mock_get_database.return_value['archived_calls']
        migration.update_fields(collection)
        collection.update.assert_has_calls([
            mock.call({}, {"$unset": {"home_page": True}}, multi=True),
            mock.call({}, {"$unset": {"platform": True}}, multi=True),
            mock.call({}, {"$unset": {"license": True}}, multi=True),
            mock.call({}, {"$unset": {"_metadata_file": True}}, multi=True),
            mock.call({}, {"$unset": {"description": True}}, multi=True),
            mock.call({}, {"$unset": {"author_email": True}}, multi=True),
            mock.call({}, {"$rename": {"_filename": "filename"}}, multi=True)
        ])


class TestSetPackagetype(unittest.TestCase):
    """
    Test that packagetype is set.
    """

    @mock.patch.object(migration.connection, 'get_database')
    def test_packages_set_calls(self, mock_get_database):
        """
        Ensure update is called with the correct parameters.
        """
        mock_get_database.return_value.collection_names.return_value = []
        collection = mock_get_database.return_value['archived_calls']
        migration.set_packagetype(collection)
        search_params = {
            "$and": [
                {
                    "$or": [
                        {"filename": {"$regex": "tar.gz$"}},
                        {"filename": {"$regex": "tar.bz2$"}},
                        {"filename": {"$regex": "zip$"}},
                    ]
                },
                {"packagetype": {"$exists": 0}}
            ]
        }
        set_command = {"$set": {"packagetype": "sdist"}}

        collection.update.assert_called_once_with(search_params, set_command, multi=True)
