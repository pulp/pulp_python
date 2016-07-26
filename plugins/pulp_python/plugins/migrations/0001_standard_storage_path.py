import logging

from pulp.plugins.migration.standard_storage_path import Migration, Plan
from pulp.server.db import connection


_logger = logging.getLogger(__name__)


def migrate(*args, **kwargs):
    """
    Migrate content units to use the standard storage path introduced in pulp 2.8.
    """
    msg = '* NOTE: This migration may take a long time depending on the size of your Pulp content *'
    stars = '*' * len(msg)

    _logger.info(stars)
    _logger.info(msg)
    _logger.info(stars)

    migration = Migration()
    migration.add(Package())
    migration()


class Package(Plan):
    """
    The migration plan for python package units.
    """

    def __init__(self):
        """
        Call super with collection and fields.
        """
        collection = connection.get_collection('units_python_package')
        super(Package, self).__init__(collection, ('name', 'version'))
        self.fields.add('_filename')

    def _new_path(self, unit):
        """
        Units created by 2.8.0 don't include the filename.  This was a regression
        that is being corrected by this additional logic.  If the storage path
        does not end with the filename stored in the unit, it is appended.

        :param unit: The unit being migrated.
        :type  unit: pulp.plugins.migration.standard_storage_path.Unit
        :return: The new path.
        :rtype: str
        """
        filename = unit.document['_filename']
        path = unit.document['_storage_path']
        if not path.endswith(filename):
            unit.document['_storage_path'] = filename
        new_path = super(Package, self)._new_path(unit)
        return new_path
