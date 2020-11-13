.. _host:

Publish and Host
================

This section assumes that you have a repository with content in it. To do this, see the
:doc:`sync` or :doc:`upload` documentation.

Create a Publication
--------------------

Kick off a publish task by creating a new publication. The publish task will generate all the
metadata that ``pip`` needs to install packages (although it will need to be hosted through a
Distribution before it is consumable).

.. literalinclude:: ../_scripts/publication.sh
    :language: bash

Response::

    {
    "distributions": [],
    "pulp_created": "2020-06-02T18:59:50.279427Z",
    "pulp_href": "/pulp/api/v3/publications/python/pypi/da07d7fa-9e13-43d4-925d-2f97bce1b687/",
    "repository": "/pulp/api/v3/repositories/python/python/da7e0e59-214d-44f5-be21-d8c7404e37f1/",
    "repository_version": "/pulp/api/v3/repositories/python/python/da7e0e59-214d-44f5-be21-d8c7404e37f1/versions/0/"
    }



Host a Publication (Create a Distribution)
--------------------------------------------

To host a publication, (which makes it consumable by ``pip``), users create a distribution which
will serve the associated publication at ``/pulp/content/<distribution.base_path>``

.. literalinclude:: ../_scripts/distribution.sh
    :language: bash

Response::

   {
    "base_path": "foo",
    "base_url": "http://pulp3-source-fedora31.localhost.example.com/pulp/content/foo/",
    "content_guard": null,
    "name": "baz",
    "publication": "/pulp/api/v3/publications/python/pypi/da07d7fa-9e13-43d4-925d-2f97bce1b687/",
    "pulp_created": "2020-06-02T19:02:25.999696Z",
    "pulp_href": "/pulp/api/v3/distributions/python/pypi/5be6b6f5-7d83-4143-af22-1c674f58542b/"
    }



.. _using-distributions:

Use the newly created distribution
-----------------------------------

The metadata and packages can now be retrieved from the distribution::

$ http $CONTENT_ADDR/pulp/content/foo/simple/
$ http $CONTENT_ADDR/pulp/content/foo/simple/shelf-reader/

The content is also pip installable::

$ pip install --trusted-host localhost -i $CONTENT_ADDR/pulp/content/foo/simple/ shelf-reader

If you don't want to specify the distribution path every time, you can modify your ``pip.conf``
file. See the `pip docs <https://pip.pypa.io/en/stable/user_guide/#configuration>`_ for more
detail.::

$ cat pip.conf

.. code::

  [global]
  index-url = http://localhost:24816/pulp/content/foo/simple/

The above configuration informs ``pip`` to install from ``pulp``::

$ pip install --trusted-host localhost shelf-reader
