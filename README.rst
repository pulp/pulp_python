``pulp_python`` Plugin
=======================

This is the ``pulp_python`` Plugin for `Pulp Project
3.0+ <https://pypi.python.org/pypi/pulpcore/>`__. A Pulp plugin to support hosting your own
pip compatible Python packages.

For more information, please see http://www.pulpproject.org.

All REST API examples bellow use `httpie <https://httpie.org/doc>`__ to perform the requests.
The ``httpie`` commands below assume that the user executing the commands has a ``.netrc`` file
in the home directory. The ``.netrc`` should have the following configuration:

.. code-block::

    machine localhost
    login admin
    password admin

If you configured the ``admin`` user with a different password, adjust the configuration
accordingly. If you prefer to specify the username and password with each request, please see
``httpie`` documentation on how to do that.

This documentation makes use of the `jq library <https://stedolan.github.io/jq/>`_
to parse the json received from requests, in order to get the unique urls generated
when objects are created. To follow this documentation as-is please install the jq
library with:

``$ sudo dnf install jq``

Install ``pulpcore``
--------------------

Follow the `installation
instructions <https://docs.pulpproject.org/en/3.0/nightly/installation/instructions.html>`__
provided with pulpcore.

Install ``pulp-python`` from source
-----------------------------------

1)  sudo -u pulp -i
2)  source ~/pulpvenv/bin/activate
3)  git clone https://github.com/pulp/pulp\_python.git
4)  cd pulp\_python
5)  git checkout 3.0-dev
6)  python setup.py develop
7)  pulp-manager makemigrations pulp\_python
8)  pulp-manager migrate pulp\_python
9)  django-admin runserver
10) sudo systemctl restart pulp\_resource\_manager
11) sudo systemctl restart pulp\_worker@1
12) sudo systemctl restart pulp\_worker@2


Install ``pulp-python`` From PyPI
---------------------------------

1) sudo -u pulp -i
2) source ~/pulpvenv/bin/activate
3) pip install pulp-python
4) pulp-manager makemigrations pulp\_python
5) pulp-manager migrate pulp\_python
6) django-admin runserver
7) sudo systemctl restart pulp\_resource\_manager
8) sudo systemctl restart pulp\_worker@1
9) sudo systemctl restart pulp\_worker@2


Create a repository ``foo``
---------------------------

``$ http POST http://localhost:8000/api/v3/repositories/ name=foo``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/repositories/e81221c3-9c7a-4681-a435-aa74020753f2/",
        ...
    }

``$ export REPO_HREF=$(http :8000/api/v3/repositories/ | jq -r '.results[] | select(.name == "foo") | ._href')``

Add an Importer to repository ``foo``
-------------------------------------

``$ http POST http://localhost:8000/api/v3/importers/python/ name='bar' download_policy='immediate' sync_mode='additive' repository=$REPO_HREF feed_url='https://repos.fedorapeople.org/repos/pulp/pulp/fixtures/python-pypi/' projects='["shelf-reader"]'``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/repositories/foo/importers/python/3750748b-781f-48df-9734-df014b2a11b4/",
        ...
    }

``$ export IMPORTER_HREF=$(http :8000/api/v3/importers/python/ | jq -r '.results[] | select(.name == "bar") | ._href')``


Sync repository ``foo`` using Importer ``bar``
----------------------------------------------

Use ``python`` Importer:

``$ http POST $IMPORTER_HREF'sync/' repository=$REPO_HREF``

Look at the new Repository Version created
------------------------------------------

``$ http POST $REPO_HREF'versions/'``

.. code:: json
    [
      {
            "_href": "http://localhost:8000/api/v3/repositories/e81221c3-9c7a-4681-a435-aa74020753f2/versions/1/",
            "_content_href": "http://localhost:8000/api/v3/repositories/e81221c3-9c7a-4681-a435-aa74020753f2/versions/1/content/",
            "_added_href": "http://localhost:8000/api/v3/repositories/e81221c3-9c7a-4681-a435-aa74020753f2/versions/1/added/",
            "_removed_href": "http://localhost.dev:8000/api/v3/repositories/e81221c3-9c7a-4681-a435-aa74020753f2/versions/1/removed/",
            "number": 1,
            "created": "2018-01-03T19:15:17.974275Z",
            "content_summary": {}
        }

    ]


Upload ``shelf_reader-0.1-py2-none-any.whl`` to Pulp
----------------------------------------------------

Create an Artifact by uploading the wheel to Pulp.

``$ http --form POST http://localhost:8000/api/v3/artifacts/ file@./shelf_reader-0.1-py2-none-any.whl``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/artifacts/7d39e3f6-535a-4b6e-81e9-c83aa56aa19e/",
        ...
    }

Create ``python`` content from an Artifact
-------------------------------------------

Create a file with the json bellow and save it as content.json.

.. code:: json

    {
        "filename": "shelf_reader-0.1-py2-none-any.whl",
        "packagetype": "bdist_wheel",
        "name": "shelf-reader",
        "version": "0.1",
        "metadata_version": null,
        "summary": "Make sure your collections are in call number order.",
        "description": "Shelf Reader is a tool for libraries that retrieves call numbers of items \nfrom their barcode and determines if they are in the correct order.",
        "keywords": "",
        "home_page": "https://github.com/asmacdo/shelf-reader",
        "download_url": "UNKNOWN",
        "author": "Austin Macdonald",
        "author_email": "asmacdo@gmail.com",
        "maintainer": null,
        "maintainer_email": null,
        "license": "GNU GENERAL PUBLIC LICENSE Version 2",
        "requires_python": null,
        "project_url": null,
        "platform": "UNKNOWN",
        "supported_platform": null,
        "requires_dist": "[]",
        "provides_dist": "[]",
        "obsoletes_dist": "[]",
        "requires_external": "[]",
        "classifiers": [],
        "artifacts": {"shelf_reader-0.1-py2-none-any.whl":"http://localhost:8000/api/v3/artifacts/7d39e3f6-535a-4b6e-81e9-c83aa56aa19e/"}
    }

``$ http POST http://localhost:8000/api/v3/content/python/ < content.json``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/content/python/a9578a5f-c59f-4920-9497-8d1699c112ff/",
        "artifacts": {
            "shelf_reader-0.1-py2-none-any.whl": "http://localhost:8000/api/v3/artifacts/7d39e3f6-535a-4b6e-81e9-c83aa56aa19e/"
        },
        "digest": "b5bb9d8014a0f9b1d61e21e796d78dccdf1352f23cd32812f4850b878ae4944c",
        "notes": {},
        "path": "shelf_reader-0.1-py2-none-any.whl",
        "type": "python"
    }

``$ export CONTENT_HREF=$(http :8000/api/v3/content/python/ | jq -r '.results[] | select(.path == "shelf_reader-0.1-py2-none-any.whl") | ._href')``

Add content to repository ``foo``
---------------------------------

Currently there is no endpoint to manually associate content to a repository. This functionality
will be added before pulp3 beta is released.

Add a Publisher to repository ``foo``
-------------------------------------

``$ http POST http://localhost:8000/api/v3/repositories/foo/publishers/python/ name=bar``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/repositories/foo/publishers/python/bar/",
        ...
    }

``$ export PUBLISHER_HREF=$(http :8000/api/v3/publishers/python/ | jq -r '.results[] | select(.name == "bar") | ._href')``

Create a Publication for Publisher ``bar``
------------------------------------------

``$ http POST http://localhost:8000/api/v3/publications/ publisher=$PUBLISHER_HREF``

.. code:: json

    [
        {
            "_href": "http://localhost:8000/api/v3/tasks/fd4cbecd-6c6a-4197-9cbe-4e45b0516309/",
            "task_id": "fd4cbecd-6c6a-4197-9cbe-4e45b0516309"
        }
    ]

``$ export PUBLICATION_HREF=$(http :8000/api/v3/publications/ | jq -r --arg PUBLISHER_HREF "$PUBLISHER_HREF" '.results[] | select(.publisher==$PUBLISHER_HREF) | ._href')``

Add a Distribution to Publisher ``bar``
---------------------------------------

``$ http POST http://localhost:8000/api/v3/distributions/ name='baz' base_path='foo' auto_updated=true http=true https=true publisher=$PUBLISHER_HREF publication=$PUBLICATION_HREF``


.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/distributions/9b29f1b2-6726-40a2-988a-273d3f009a41/",
       ...
    }


Check status of a task
----------------------

``$ http GET http://localhost:8000/api/v3/tasks/82e64412-47f8-4dd4-aa55-9de89a6c549b/``

Download ``shelf_reader-0.1-py2-none-any.whl`` from Pulp
--------------------------------------------------------


``$ http GET http://localhost:8000/content/foo/shelf_reader-0.1-py2-none-any.whl``
