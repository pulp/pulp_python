.. _workflows-index:

Workflows
=========

If you have not yet installed the `python` plugin on your Pulp installation, please follow our
:doc:`../installation`. These documents will assume you have the environment installed and
ready to go.

The example workflows here use the Pulp CLI. Get and setup the Pulp CLI from PyPI with the following
commands. For more information about setting up the Pulp CLI please read the `installation and configuration
doc page <https://github.com/pulp/pulp-cli/blob/develop/docs/install.md>`_.

.. code-block:: bash

    pip install pulp-cli[pygments] # For colored output
    pulp config create -e

If you configured the ``admin`` user with a different password, adjust the configuration
accordingly. If you prefer to specify the username and password with each request, please see
Pulp CLI documentation on how to do that.


.. toctree::
   :maxdepth: 2

   sync
   upload
   publish
