"""
This migration removes `home_page`, `platform`, 'author_email`, `description` and `license` from
the units_python_package collection. Additionally, it renames `_filename` to `filename`.
"""
from pulp.server.db import connection


def migrate(*args, **kwargs):
    """
    Perform the migration as described in this module's docblock.
    """
    db = connection.get_database()
    collection = db['units_python_package']

    collection.update({}, {"$unset": {"home_page": True}}, multi=True)
    collection.update({}, {"$unset": {"platform": True}}, multi=True)
    collection.update({}, {"$unset": {"license": True}}, multi=True)
    collection.update({}, {"$unset": {"_metadata_file": True}}, multi=True)
    collection.update({}, {"$unset": {"description": True}}, multi=True)
    collection.update({}, {"$unset": {"author_email": True}}, multi=True)

    collection.update({}, {"$rename": {"_filename": "filename"}}, multi=True)
