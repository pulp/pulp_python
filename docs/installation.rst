User Setup
==========

Install pulp-python
-------------------

This document assumes that you have
`installed pulpcore <https://docs.pulpproject.org/en/3.0/nightly/installation/instructions.html>`_
into a the virtual environment ``pulpvenv``.

Users should install from **either** PyPI or source.

From PyPI
*********

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   pip install pulp-python

From Source
***********

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   git clone https://github.com/pulp/pulp_python.git
   cd pulp_python
   pip install -e .

Make and Run Migrations
-----------------------

.. code-block:: bash

   pulp-manager makemigrations python
   pulp-manager migrate python

Run Services
------------

.. code-block:: bash

   pulp-manager runserver
   gunicorn pulpcore.content:server --bind 'localhost:24816' --worker-class 'aiohttp.GunicornWebWorker' -w 2
   sudo systemctl restart pulp-resource-manager
   sudo systemctl restart pulp-worker@1
   sudo systemctl restart pulp-worker@2
