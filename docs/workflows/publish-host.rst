Publish and Host
================

This section assumes that you have a repository with content in it. To do this, see the
:doc:`sync` or :doc:`upload` documentation.

Create a Publisher
------------------

Publishers contain extra settings for how to publish. You can use a Python publisher on any
repository that contains Python content::

$ http POST $BASE_ADDR/pulp/api/v3/publishers/python/ name=bar

Response::

    {
        "_href": "http://localhost:8000/pulp/api/v3/repositories/foo/publishers/python/bar/",
        ...
    }

Create a variable for convenience.::

$ export PUBLISHER_HREF=$(http $BASE_ADDR/pulp/api/v3/publishers/python/ | jq -r '.results[] | select(.name == "bar") | ._href')


Publish a repository with a publisher
-------------------------------------

Use the remote object to kick off a publish task by specifying the repository version to publish.
Alternatively, you can specify repository, which will publish the latest version.

The result of a publish is a publication, which contains all the information needed for ``pip`` to
use. Publications are not consumable until they are hosted by a distribution::

$ http POST $PUBLISHER_HREF'publish/' repository=$REPO_HREF

Response::

    [
        {
            "_href": "http://localhost:8000/pulp/api/v3/tasks/fd4cbecd-6c6a-4197-9cbe-4e45b0516309/",
            "task_id": "fd4cbecd-6c6a-4197-9cbe-4e45b0516309"
        }
    ]

Create a variable for convenience.::

$ export PUBLICATION_HREF=$(http $BASE_ADDR/pulp/api/v3/publications/ | jq -r --arg PUBLISHER_HREF "$PUBLISHER_HREF" '.results[] | select(.publisher==$PUBLISHER_HREF) | ._href')

Host a Publication (Create a Distribution)
--------------------------------------------

To host a publication, (which makes it consumable by ``pip``), users create a distribution which
will serve the associated publication at ``/pulp/content/<distribution.base_path>`` as demonstrated
in :ref:`using distributions<using-distributions>`::

$ http POST $BASE_ADDR/pulp/api/v3/distributions/ name='baz' base_path='foo' publication=$PUBLICATION_HREF

Response::

    {
        "_href": "http://localhost:8000/pulp/api/v3/distributions/9b29f1b2-6726-40a2-988a-273d3f009a41/",
       ...
    }

.. _using-distributions:

Use the newly created distribution
-----------------------------------

The metadata and packages can now be retrieved from the distribution::

$ http $BASE_ADDR/pulp/content/foo/simple/
$ http $BASE_ADDR/pulp/content/foo/simple/shelf-reader/

The content is also pip installable::

$ pip install --trusted-host localhost -i $BASE_ADDR/pulp/content/foo/simple/ shelf-reader

If you don't want to specify the distribution path every time, you can modify your ``pip.conf``
file. See the `pip docs <https://pip.pypa.io/en/stable/user_guide/#configuration>`_ for more
detail.::

$ cat pip.conf

.. code::

  [global]
  index-url = http://localhost:8000/pulp/content/foo/simple/

The above configuration informs ``pip`` to install from ``pulp``::

$ pip install --trusted-host localhost shelf-reader
