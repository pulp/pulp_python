.. _uploading-content:

Upload and Manage Content
=========================
Content can be added to a repository not only by synchronizing from a remote source but also by uploading the files directly into Pulp.

Create a repository
-------------------

If you don't already have a repository, create one.

.. literalinclude:: ../_scripts/repo.sh
    :language: bash

Repository GET response::

    {
        "description": null,
        "latest_version_href": "/pulp/api/v3/repositories/python/python/931109d3-db86-4933-bf1d-45b4d4216d5d/versions/0/",
        "name": "foo",
        "pulp_created": "2020-05-28T20:15:08.644358Z",
        "pulp_href": "/pulp/api/v3/repositories/python/python/931109d3-db86-4933-bf1d-45b4d4216d5d/",
        "versions_href": "/pulp/api/v3/repositories/python/python/931109d3-db86-4933-bf1d-45b4d4216d5d/versions/"
    }



Upload a file to Pulp
---------------------

Each artifact in Pulp represents a file. They can be created during sync or created manually by uploading a file.

.. literalinclude:: ../_scripts/artifact.sh
    :language: bash

Artifact GET response::

    {
        "file": "artifact/04/cfd8bb4f843e35d51bfdef2035109bdea831b55a57c3e6a154d14be116398c",
        "md5": "2dac570a33d88ca224be86759be59376",
        "pulp_created": "2020-05-28T20:21:23.441981Z",
        "pulp_href": "/pulp/api/v3/artifacts/f87a20b0-d5b9-4a07-9282-bf7f9e5eb37f/",
        "sha1": "bf039b185ef1f308e7d0bc5322be10061ca4f695",
        "sha224": "01c8a673b13875cb12deb0e9fb2fddf3579583d7837b4458a78dd83c",
        "sha256": "04cfd8bb4f843e35d51bfdef2035109bdea831b55a57c3e6a154d14be116398c",
        "sha384": "4c22ded8001904b4fedb3fa974c883479fb32d630ceb48d7455bfd390166afd73cfda5b4c9c0c8d3a19bb67966ae13d0",
        "sha512": "4d11d6a67ec6aa3eb25df2416b6d48f1c6c04d5e745b12d7dbc89aacfc8bcb439c5ccff56324ce8493099e4e2f79a414d2513758782efcaef84b3d8cf00ea45f",
        "size": 19097
    }


Create content from an artifact
-------------------------------

Now that Pulp has the package, its time to make it into a unit of content.

.. literalinclude:: ../_scripts/package.sh
   :language: bash

Content GET response::

    {
    "artifact": "/pulp/api/v3/artifacts/f87a20b0-d5b9-4a07-9282-bf7f9e5eb37f/",
    "author": "Austin Macdonald",
    "author_email": "asmacdo@gmail.com",
    "classifiers": [],
    "description": "too long to read",
    "download_url": "",
    "filename": "shelf-reader-0.1.tar.gz",
    "home_page": "https://github.com/asmacdo/shelf-reader",
    "keywords": "",
    "license": "GNU GENERAL PUBLIC LICENSE Version 2, June 1991",
    "maintainer": "",
    "maintainer_email": "",
    "metadata_version": "1.1",
    "name": "shelf-reader",
    "obsoletes_dist": "[]",
    "packagetype": "sdist",
    "platform": "",
    "project_url": "",
    "provides_dist": "[]",
    "pulp_created": "2020-05-28T20:49:12.156807Z",
    "pulp_href": "/pulp/api/v3/content/python/packages/2ac13c48-0f45-4811-80d2-5dcbb7821ce1/",
    "requires_dist": "[]",
    "requires_external": "[]",
    "requires_python": "",
    "summary": "Make sure your collections are in call number order.",
    "supported_platform": "",
    "version": "0.1"
    }


Add content to a repository
---------------------------

Once there is a content unit, it can be added and removed from repositories using add_content_units or remove_content_units respectively.

.. literalinclude:: ../_scripts/add_content_repo.sh
   :language: bash

Repository Version GET response (after task complete)::

    {
        "base_version": null,
        "content_summary": {
            "added": {
                "python.python": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/python/packages/?repository_version_added=/pulp/api/v3/repositories/python/python/931109d3-db86-4933-bf1d-45b4d4216d5d/versions/1/"
                }
            },
            "present": {
                "python.python": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/python/packages/?repository_version=/pulp/api/v3/repositories/python/python/931109d3-db86-4933-bf1d-45b4d4216d5d/versions/1/"
                }
            },
            "removed": {}
        },
        "number": 1,
        "pulp_created": "2020-05-28T21:04:54.403979Z",
        "pulp_href": "/pulp/api/v3/repositories/python/python/931109d3-db86-4933-bf1d-45b4d4216d5d/versions/1/"
    }