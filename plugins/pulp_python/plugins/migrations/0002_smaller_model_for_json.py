"""
This migration removes `home_page`, `platform`, 'author_email`, `description` and `license` from
the units_python_package collection, it renames `_filename` to `filename`, and it populates the
new required field, `packagetype`.
"""
from pulp.server.db import connection


def migrate(*args, **kwargs):
    """
    Perform the migration as described in this module's docblock.
    """
    db = connection.get_database()
    collection = db['units_python_package']
    set_packagetype(collection)
    update_fields(collection)
    collection.drop_indexes()


def update_fields(collection):
    """
    Updates field names and removes unecessary fields.

    :param collection: collection to update
    :type  collection: pymongo.collection.Collection
    """
    collection.update({}, {"$unset": {"home_page": True}}, multi=True)
    collection.update({}, {"$unset": {"platform": True}}, multi=True)
    collection.update({}, {"$unset": {"license": True}}, multi=True)
    collection.update({}, {"$unset": {"_metadata_file": True}}, multi=True)
    collection.update({}, {"$unset": {"description": True}}, multi=True)
    collection.update({}, {"$unset": {"author_email": True}}, multi=True)

    collection.update({}, {"$rename": {"_filename": "filename"}}, multi=True)


def set_packagetype(collection):
    """
    This sets the new `packagetype` field. This migration should only operate on sdists
    because they were the only supported type before this migration.

    :param collection: collection to update
    :type  collection: pymongo.collection.Collection
    """
    tarball = {"filename": {"$regex": "tar.gz$"}}
    bzip = {"filename": {"$regex": "tar.bz2$"}}
    zipfile = {"filename": {"$regex": "zip$"}}

    sdist_filetype = {"$or": [tarball, bzip, zipfile]}
    no_packagetype = {"packagetype": {"$exists": 0}}
    set_sdist = {"$set": {"packagetype": "sdist"}}

    collection.update({"$and": [sdist_filetype, no_packagetype]}, set_sdist, multi=True)
