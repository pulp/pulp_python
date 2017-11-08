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

Install ``pulpcore``
--------------------

Follow the `installation
instructions <https://docs.pulpproject.org/en/3.0/nightly/installation/instructions.html>`__
provided with pulpcore.

Install ``pulp-python`` from source
---------------------------------

1)  sudo -u pulp -i
2)  source ~/pulpvenv/bin/activate
3)  git clone https://github.com/pulp/pulp\_python.git
4)  cd pulp\_python
5)  python setup.py develop
6)  pulp-manager makemigrations pulp\_python
7)  pulp-manager migrate pulp\_python
8)  django-admin runserver
9)  sudo systemctl restart pulp\_worker@1
10) sudo systemctl restart pulp\_worker@2

Install ``pulp-python`` From PyPI
-------------------------------

1) sudo -u pulp -i
2) source ~/pulpvenv/bin/activate
3) pip install pulp-python
4) pulp-manager makemigrations pulp\_python
5) pulp-manager migrate pulp\_python
6) django-admin runserver
7) sudo systemctl restart pulp\_worker@1
8) sudo systemctl restart pulp\_worker@2


Create a repository ``foo``
---------------------------

``$ http POST http://localhost:8000/api/v3/repositories/ name=foo``

Add an Importer to repository ``foo``
-------------------------------------

Add important details about your Importer and provide examples.

``$ http POST http://localhost:8000/api/v3/repositories/foo/importers/python/ some=params``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/repositories/foo/importers/python/bar/",
        ...
    }

Add a Publisher to repository ``foo``
-------------------------------------

``$ http POST http://localhost:8000/api/v3/repositories/foo/publishers/python/ name=bar``

.. code:: json

    {
        "_href": "http://localhost:8000/api/v3/repositories/foo/publishers/python/bar/",
        ...
    }

Add a Distribution to Publisher ``bar``
---------------------------------------

``$ http POST http://localhost:8000/api/v3/repositories/foo/publishers/python/bar/distributions/ some=params``

Sync repository ``foo`` using Importer ``bar``
----------------------------------------------

Use ``python`` Importer:

``http POST http://localhost:8000/api/v3/repositories/foo/importers/python/bar/sync/``

Add content to repository ``foo``
---------------------------------

``$ http POST http://localhost:8000/api/v3/repositorycontents/ repository='http://localhost:8000/api/v3/repositories/foo/' content='http://localhost:8000/api/v3/content/python/a9578a5f-c59f-4920-9497-8d1699c112ff/'``

Create a Publication using Publisher ``bar``
--------------------------------------------

Dispatch the Publish task

``$ http POST http://localhost:8000/api/v3/repositories/foo/publishers/python/bar/publish/``

.. code:: json

    [
        {
            "_href": "http://localhost:8000/api/v3/tasks/fd4cbecd-6c6a-4197-9cbe-4e45b0516309/",
            "task_id": "fd4cbecd-6c6a-4197-9cbe-4e45b0516309"
        }
    ]

Check status of a task
----------------------

``$ http GET http://localhost:8000/api/v3/tasks/82e64412-47f8-4dd4-aa55-9de89a6c549b/``

Download ``foo.tar.gz`` from Pulp
---------------------------------

``$ http GET http://localhost:8000/content/foo/foo.tar.gz``
