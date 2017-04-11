Python Type
===========

The Python plugins come with a database type for Python packages. This type's id is
``python_package``, and it has the following attributes:

Unit Key
--------

The Python type's unit key is the filename of the package. In versions before 2.0, the unit key was
the name and version, which did not allow for multiple package types of a single release.

Other Attributes
----------------

The Python package type has these additional attributes, all of which are determined automatically
by the package metadata.

+--------------+-------------------------------------------------------+
| Name         | Description                                           |
+==============+=======================================================+
| author       | The author's name                                     |
+--------------+-------------------------------------------------------+
| name         | Project/package name                                  |
+--------------+-------------------------------------------------------+
| packagetype  | Format of the python package, ex sdist or bdist_wheel |
+--------------+-------------------------------------------------------+
| summary      | A brief summary                                       |
+--------------+-------------------------------------------------------+
| platform     | The platforms that the package is intended to work in |
+--------------+-------------------------------------------------------+
| version      | Version number of the package distribution            |
+--------------+-------------------------------------------------------+
