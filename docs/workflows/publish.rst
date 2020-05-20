Publish and Host
================

This section assumes that you have a repository with content in it. To do this, see the
:doc:`sync` or :doc:`upload` documentation.

Create a Publication
--------------------

Kick off a publish task by creating a new publication. The publish task will generate all the
metadata that ``pip`` needs to install packages (although it will need to be hosted through a
Distribution before it is consumable).::

$ http POST $BASE_ADDR/pulp/api/v3/publications/python/python/ name=bar

Response::

    {
        "pulp_href": "http://localhost:24817/pulp/api/v3/publications/python/python/bar/",
        ...
    }


Host a Publication (Create a Distribution)
--------------------------------------------

To host a publication, (which makes it consumable by ``pip``), users create a distribution which
will serve the associated publication at ``/pulp/content/<distribution.base_path>``::

$ http POST $BASE_ADDR/pulp/api/v3/distributions/python/python/ name='baz' base_path='foo' publication=$BASE_ADDR/publications/5fcb3a98-1bd1-445f-af94-801a1d563b9f/

Response::

    {
        "pulp_href": "http://localhost:24817/pulp/api/v3/distributions/2ac41454-931c-41c7-89eb-a9d11e19b02a/",
       ...
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
