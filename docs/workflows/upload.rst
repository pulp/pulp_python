Upload Content
==============

One-shot upload a file to Pulp
------------------------------

Each artifact in Pulp represents a file. They can be created during sync or created manually by uploading a file via
one-shot upload. One-shot upload takes a file you specify, creates an artifact, and creates content from that artifact.
The python plugin will inspect the file and populate its metadata.

.. literalinclude:: ../_scripts/upload.sh
   :language: bash

Content GET Response::

    {
        "_artifact": null,
        "pulp_created": "2019-07-25T13:57:55.178993Z",
        "pulp_href": "/pulp/api/v3/content/python/packages/6172ff0f-3e11-4b5f-8460-bd6a72616747/",
        "_type": "python.python",
        "author": "",
        "author_email": "",
        "classifiers": [],
        "description": "",
        "download_url": "",
        "filename": "shelf_reader-0.1-py2-none-any.whl",
        "home_page": "",
        "keywords": "",
        "license": "",
        "maintainer": "",
        "maintainer_email": "",
        "metadata_version": "",
        "name": "[]",
        "obsoletes_dist": "[]",
        "packagetype": "bdist_wheel",
        "platform": "",
        "project_url": "",
        "provides_dist": "[]",
        "requires_dist": "[]",
        "requires_external": "[]",
        "requires_python": "",
        "summary": "",
        "supported_platform": "",
        "version": "0.1"
    }

Reference: `Python Content Usage <../restapi.html#tag/content>`_

Add content to a repository during one-shot upload
--------------------------------------------------

One-shot upload can also optionally add the content being created to a repository you specify.

.. literalinclude:: ../_scripts/upload_with_repo.sh
   :language: bash

Repository GET Response::

    {
        "pulp_created": "2019-07-25T14:03:48.378437Z",
        "pulp_href": "/pulp/api/v3/repositories/135f468f-0c61-4337-9f37-0cd911244bec/versions/1/",
        "base_version": null,
        "content_summary": {
            "added": {
                "python.python": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/python/packages/?repository_version_added=/pulp/api/v3/repositories/135f468f-0c61-4337-9f37-0cd911244bec/versions/1/"
                }
            },
            "present": {
                "python.python": {
                    "count": 1,
                    "href": "/pulp/api/v3/content/python/packages/?repository_version=/pulp/api/v3/repositories/135f468f-0c61-4337-9f37-0cd911244bec/versions/1/"
                }
            },
            "removed": {}
        },
        "number": 1
    }


Reference: `Python Repository Usage <../restapi.html#tag/repositories>`_

For other ways to add content to a repository, see :ref:`add-remove`
