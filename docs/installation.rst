User Setup
==========

All workflow examples use the Pulp CLI. Install and setup from PyPI:

.. code-block:: bash

    pip install pulp-cli[pygments] # For color output
    pulp config create -e
    pulp status # Check that CLI can talk to Pulp

If you configured the ``admin`` user with a different password, adjust the configuration
accordingly. If you prefer to specify the username and password with each request, please see
``Pulp CLI`` documentation on how to do that.


Install ``pulpcore``
--------------------

Follow the `installation
instructions <https://docs.pulpproject.org/pulpcore/installation/index.html>`__
provided with pulpcore.

Install plugin
--------------

This document assumes that you have
`installed pulpcore <https://docs.pulpproject.org/pulpcore/installation/index.html>`_
into a the virtual environment ``pulpvenv``.

Users should install from **either** PyPI or source.

From Source
***********

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   cd pulp_python
   pip install -e .
   django-admin runserver 24817

Make and Run Migrations
-----------------------

.. code-block:: bash

   pulpcore-manager makemigrations python
   pulpcore-manager migrate python

Run Services
------------

.. code-block:: bash

   pulpcore-manager runserver
   gunicorn pulpcore.content:server --bind 'localhost:24816' --worker-class 'aiohttp.GunicornWebWorker' -w 2
   sudo systemctl restart pulpcore-resource-manager
   sudo systemctl restart pulpcore-worker@1
   sudo systemctl restart pulpcore-worker@2
