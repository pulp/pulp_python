Installation
============

Prerequisites
-------------

These instructions assume that you have a working Pulp installation first. If you have not yet
installed Pulp, please follow the Pulp :ref:`installation <platform:server_installation>`
instructions, and then return to this document.

The command line examples included here are written for systems that use yum as their package
manager, and systemd as their init system. Please season to taste if your system is different.

Server
------

Consider stopping httpd. If you need it to keep running other web apps, or if
you need Pulp to continue serving static content, it is usually sufficient to
disable access to Pulp's REST API. That will be left as an exercise for the reader.
Otherwise, just stop the ``httpd`` service::

  $ sudo systemctl stop httpd

Next, install the ``pulp-python-plugins`` package::

  $ sudo yum install pulp-python-plugins

Then run ``pulp-manage-db`` to initialize the new types in Pulp's database. You must run this
command as the same user that the web server uses when it runs Pulp::

  $ sudo -u apache pulp-manage-db

Finally, restart ``httpd``::

  $ sudo systemctl restart httpd

Admin Client
------------

Simply install the ``pulp-python-admin-extensions`` package::

  $ sudo yum install pulp-python-admin-extensions
