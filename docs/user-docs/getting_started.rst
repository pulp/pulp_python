Getting Started
===============

If you have not yet installed the Python plugins on your Pulp installation, please follow our
:doc:`../admin-docs/installation`. This document will assume you have the environment installed and
ready to go. We will perform some simple tasks here to get you started by showing you how to create
a repository, upload Python packages into it, publish it, and then use pip to install packages from
it.

Create a Repository
-------------------

We will start by making a Python repository::

   $ pulp-admin python repo create --repo-id my_own_pypi

List Repositories
-----------------

You can list existing Python repositories::

   $ pulp-admin python repo list
   +----------------------------------------------------------------------+
                             Python Repositories
   +----------------------------------------------------------------------+

   Id:                  my_own_pypi
   Display Name:        my_own_pypi
   Description:         None
   Content Unit Counts:

Upload a Python Package
-----------------------

Now that we have a Python repository, we can upload a Python source package to it. Pulp accepts
source distributions and wheels, which are uploaded in the same way. Let's clone the
pulp_python plugins package and build a source package suitable for uploading to Pulp::

   $ cd /tmp
   $ git clone https://github.com/pulp/pulp_python.git --branch 0.0-dev
   $ cd pulp_python/plugins
   $ ./setup.py sdist
   <output snipped>
   $ ls dist/
   pulp_python_plugins-0.0.0.tar.gz

That tarball in the ``dist/`` folder is the package that Pulp expects with its upload command. Let's
upload it to Pulp now::

   $ pulp-admin python repo upload --repo-id my_own_pypi -f dist/pulp_python_plugins-0.0.0.tar.gz

And now we can see that there is one Python package in our repository::

   $ pulp-admin python repo list
   +----------------------------------------------------------------------+
                            Python Repositories
   +----------------------------------------------------------------------+

   Id:                  my_own_pypi
   Display Name:        my_own_pypi
   Description:         None
   Content Unit Counts:
     Python Package: 1


Query Packages in a Repository
------------------------------

You can also query the packages in a repository::

   $ pulp-admin python repo packages --repo-id my_own_pypi --match name=pulp-python-plugins
   Name:         pulp-python-plugins
   Version:      0.0.0
   Author:       Pulp Team
   Author Email: pulp-list@redhat.com
   Description:  UNKNOWN
   Home Page:    http://www.pulpproject.org
   License:      GPLv2+
   Platform:     UNKNOWN
   Summary:      plugins for python support in pulp


Publish a Python Repository
---------------------------

The next thing we might want to do once our repository has some content in it is to publish it so
that clients can install the package from Pulp::

   $ pulp-admin python repo publish run --repo-id my_own_pypi

Your data is now available at its web publish location: `http://<host>/pulp/python/web/<repo_id>/`.

Install a Package From a Pulp Hosted Python Repository
------------------------------------------------------

We can now use pip to install from your repository. As with PyPI, the pip access point is the
repository web location plus "simple/". We will now install our package on another machine using pip::

   $ pip install -i http://pulp.example.com/pulp/python/web/my_own_pypi/simple/ pulp-python-plugins
   Downloading/unpacking pulp-python-plugins
     Downloading pulp-python-plugins-0.0.0.tar.gz
     Running setup.py egg_info for package pulp-python-plugins

   Installing collected packages: pulp-python-plugins
     Running setup.py install for pulp-python-plugins

   Successfully installed pulp-python-plugins
   Cleaning up...


Remove Python Packages From a Pulp Python Repository
----------------------------------------------------

Occasionally, we may want to remove uploaded packages from the repository::

   $ pulp-admin python repo remove --repo-id my_own_pypi --str-eq="name=pulp-python-plugins"
   This command may be exited via ctrl+c without affecting the request.


   [\]
   Running...

   Units Removed:
     pulp-python-plugins-0.0.0

Note that this only removes the association of given packages with the repository. Uploaded packages
still exist on the server. Python packages which are not associated with any repositories can be
removed from the server using `pulp-admin orphan remove --type python_package` command.

.. _sync_from_pypi:

Synchronize Packages from PyPI
------------------------------

It is possible to synchronize packages from the Python Package Index. In order to do this, you must
specify the feed URL as well as a comma separated list of package names you wish to sync. Pulp will
sync all releases of all package types.::

   $ pulp-admin python repo create --repo-id pypi --feed https://pypi.python.org/ --package-names numpy,scipy
   Repository [pypi] successfully created

   $ pulp-admin python repo sync run --repo-id pypi
   +----------------------------------------------------------------------+
                       Synchronizing Repository [pypi]
   +----------------------------------------------------------------------+

   This command may be exited via ctrl+c without affecting the request.

   Downloading Python metadata.
   [==================================================] 100%
   2 of 2 items
   ... completed

   Downloading and processing Python packages.
   [==================================================] 100%
   718 of 718 items
   ... completed


   Task Succeeded

   Publishing Python Metadata.
   [-]
   ... completed

   Publishing Python Content.
   [-]
   ... completed

   Making files available via web.
   [-]
   ... completed


   Task Succeeded


Synchronize Packages from another Pulp
--------------------------------------

Version 2.0+ publishes include metadata for each project. This allows separate instances of Pulp
to sync from each other. After a publish is complete, the web publish location can be
used as a feed for a second Pulp. Here is an example.::

   $ pulp-admin python repo create --repo-id sync_from_other_pulp --feed http://<host>/pulp/python/web/<repo_id>/ --package-names numpy,scipy

   $ pulp-admin python repo sync run --repo-id sync_from_other_pulp

The pulp_python RPM distribution automatically adds index.json as a DirectoryIndex in pulp_python.conf. If you're not running the pulp_python RPM distribution, you will need to ensure this setting is present before remote Pulp instances will be able to sync your repository.

Version 2.0+ of the pulp_python plugin is required on both Pulp servers for synchronization to work. Syncronizing python content between pulp_python 1.x and 2.x is not supported.
