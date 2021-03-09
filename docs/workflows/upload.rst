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
      "pulp_href": "/pulp/api/v3/repositories/python/python/8fbb24ee-dc91-44f4-a6ee-beec60aa542d/",
      "pulp_created": "2021-03-09T04:11:54.347921Z",
      "versions_href": "/pulp/api/v3/repositories/python/python/8fbb24ee-dc91-44f4-a6ee-beec60aa542d/versions/",
      "pulp_labels": {},
      "latest_version_href": "/pulp/api/v3/repositories/python/python/8fbb24ee-dc91-44f4-a6ee-beec60aa542d/versions/0/",
      "name": "foo",
      "description": null,
      "remote": null
    }

Upload a file to Pulp
---------------------

Each artifact in Pulp represents a file. They can be created during sync or created manually by uploading a file.

.. literalinclude:: ../_scripts/artifact.sh
    :language: bash

Content Upload response::

    {
      "pulp_href": "/pulp/api/v3/content/python/packages/f226894b-daa9-4152-9a04-595979ea5f9b/",
      "pulp_created": "2021-03-09T04:47:13.066911Z",
      "artifact": "/pulp/api/v3/artifacts/532b6318-add2-4208-ac1b-d6d37a39a97f/",
      "filename": "shelf-reader-0.1.tar.gz",
      "packagetype": "sdist",
      "name": "shelf-reader",
      "version": "0.1",
      "metadata_version": "1.1",
      "summary": "Make sure your collections are in call number order.",
      "description": "too long to read"
      "keywords": "",
      "home_page": "https://github.com/asmacdo/shelf-reader",
      "download_url": "",
      "author": "Austin Macdonald",
      "author_email": "asmacdo@gmail.com",
      "maintainer": "",
      "maintainer_email": "",
      "license": "GNU GENERAL PUBLIC LICENSE Version 2, June 1991",
      "requires_python": "",
      "project_url": "",
      "platform": "",
      "supported_platform": "",
      "requires_dist": "[]",
      "provides_dist": "[]",
      "obsoletes_dist": "[]",
      "requires_external": "[]",
      "classifiers": "[]"
    }

Add content to a repository
---------------------------

Once there is a content unit, it can be added and removed from repositories using the add and remove commands

.. literalinclude:: ../_scripts/add_content_repo.sh
   :language: bash

Repository Version Show Response (after task complete)::

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
