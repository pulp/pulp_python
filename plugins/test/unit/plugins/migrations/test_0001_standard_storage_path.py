import os

from unittest import TestCase

from mock import Mock, patch

from pulp.server.db.migrate.models import _import_all_the_way


PATH_TO_MODULE = 'pulp_python.plugins.migrations.0001_standard_storage_path'

migration = _import_all_the_way(PATH_TO_MODULE)


class TestMigrate(TestCase):
    """
    Test migration 0001.
    """

    @patch(PATH_TO_MODULE + '.Migration')
    @patch(PATH_TO_MODULE + '.connection.get_collection', Mock())
    def test_migrate(self, _migration):
        plans = []
        _migration.return_value.add.side_effect = plans.append

        # test
        migration.migrate()

        # validation
        self.assertTrue(isinstance(plans[0], migration.Package))
        self.assertEqual(1, len(plans))
        _migration.return_value.assert_called_once_with()


class TestPackage(TestCase):

    @patch(PATH_TO_MODULE + '.connection.get_collection')
    def test_init(self, get_collection):
        fields = set()
        fields.add('_filename')
        plan = migration.Package()
        self.assertEqual(plan.collection, get_collection.return_value)
        self.assertEqual(plan.key_fields, ('name', 'version'))
        self.assertEqual(plan.fields, fields)

    @patch(PATH_TO_MODULE + '.Plan._new_path')
    @patch(PATH_TO_MODULE + '.connection.get_collection', Mock())
    def test_new_path(self, new_path):
        filename = 'pulp.tar.gz'
        unit = Mock(
            document={
                '_storage_path': 'something',
                '_filename': filename
            })

        def _new_path(u):
            return os.path.join('1234', u.document['_storage_path'])

        new_path.side_effect = _new_path

        # test
        plan = migration.Package()
        path = plan._new_path(unit)

        # validation
        self.assertEqual(path, os.path.join('1234', filename))
