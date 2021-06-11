pulp-python Plugin
==================

The `python`` plugin extends `pulpcore <https://pypi.org/project/pulpcore/>`__ to support
hosting python packages. This plugin is a part of the `Pulp Project
<http://www.pulpproject.org>`_, and assumes some familiarity with the `pulpcore documentation
<https://docs.pulpproject.org/pulpcore/>`_.

If you are just getting started, we recommend getting to know the :doc:`basic
workflows<workflows/index>`.

The REST API documentation for ``pulp_python`` is available `here <restapi.html>`_.

Features
--------

* :ref:`Create local mirrors of PyPI <sync-workflow>` that you have full control over
* :ref:`Upload your own Python packages <uploading-content>`
* :ref:`Perform pip install <host>` from your Pulp Python repositories
* :ref:`Download packages on-demand <create-remote>` to reduce disk usage
* Every operation creates a restorable snapshot with :ref:`Versioned Repositories <versioned-repo-created>`
* Curate your Python repositories with allowed and disallowed packages
* Host content either `locally or on S3 <https://docs.pulpproject.org/installation/storage.html>`_
* De-duplication of all saved content

Tech Preview
------------

Some additional features are being supplied as a tech preview.  There is a possibility that
backwards incompatible changes will be introduced for these particular features.  For a list of
features currently being supplied as tech previews only, see the :doc:`tech preview page
<tech-preview>`.

How to use these docs
=====================

The documentation here should be considered the **primary documentation for managing Python related content.**
All relevent workflows are covered here, with references to some pulpcore supplemental docs.
Users may also find pulpcore’s conceptual docs useful.

This documentation falls into two main categories:

    1. :ref:`workflows-index` shows the **major features** of the Python plugin, with links to reference docs.
    2. The `REST API Docs <restapi.html>`_ are automatically generated and provide more detailed information for each
       minor feature, including all fields and options.

Table of Contents
-----------------

.. toctree::
   :maxdepth: 1

   installation
   workflows/index
   changes
   contributing
   restapi/index
   tech-preview


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

