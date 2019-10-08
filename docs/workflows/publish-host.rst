Publish and Host
================

This section assumes that you have a repository with content in it. To do this, see the
:doc:`sync` or :doc:`upload` documentation.

Create a new Publication
------------------------

Kick off a publish task by creating a new Publication. The publish task will generate all the
metadata that ``pip`` needs to install packages (newly created Publications are not consumable
yet).

.. literalinclude:: ../_scripts/publication.sh
   :language: bash

Publication GET Response::

    {
        "pulp_created": "2019-04-29T15:58:04.939836Z",
        "_distributions": [],
        "pulp_href": "/pulp/api/v3/publications/python/pypi/4cc1ddbb-64ff-4795-894a-09d5ca372774/",
        "publisher": null,
        "repository": "http://localhost:24817/pulp/api/v3/repositories/%3CRepository:%20foo%3E/",
        "repository_version": "/pulp/api/v3/repositories/1b2b0af1-5588-4b4b-b2f6-cdd3a3e1cd36/versions/1/"
    }

Reference: `Python Publication Usage <../restapi.html#tag/publications>`_

Create a Distribution (Host a Publication)
------------------------------------------

To host a publication, (which makes it consumable by ``pip``), users create a distribution which
will serve the associated publication at ``$CONTENT_HOST/pulp/content/<distribution.base_path>`` as
demonstrated in :ref:`using distributions<using-distributions>`.

.. literalinclude:: ../_scripts/distribution.sh
   :language: bash

Distribution GET Response::

  {
      "pulp_created": "2019-05-13T12:39:48.698103Z",
      "pulp_href": "/pulp/api/v3/distributions/python/pypi/682d64c3-fee1-411c-a3af-3f74cab56c5e/",
      "base_path": "foo",
      "base_url": "localhost:24816/pulp/content/foo",
      "content_guard": null,
      "name": "baz",
      "publication": "/pulp/api/v3/publications/python/pypi/23f4c6fb-204b-45b6-8826-f61d4d38748d/",
      "remote": null
  }

Reference: `Python Distribution Usage <../restapi.html#tag/distributions>`_

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
