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
   git clone https://github.com/pulp/pulp\_python.git
   cd pulp\_python
   git checkout 3.0-dev
   python setup.py develop

Make and Run Migrations
-----------------------

.. code-block:: bash

   pulp-manager makemigrations pulp\_python
   pulp-manager migrate pulp\_python

Run Services
------------

.. code-block:: bash

   pulp-manager runserver
   sudo systemctl restart pulp\_resource\_manager
   sudo systemctl restart pulp\_worker@1
   sudo systemctl restart pulp\_worker@2
