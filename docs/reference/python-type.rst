Python Type
===========

The Python plugins come with a database type for Python packages. This type's id is
``python_package``, and it has the following attributes:

Unit Key
--------

The Python type's unit key is an ordered list of the following attributes:

+---------+----------------------------+
| Name    | Description                |
+=========+============================+
| name    | The name of the package    |
+---------+----------------------------+
| version | The version of the package |
+---------+----------------------------+

Other Attributes
----------------

The Python package type has these additional attributes that are all taken from the package's
PKG-INFO file:

+--------------+-------------------------------------------------------+
| Name         | Description                                           |
+==============+=======================================================+
| summary      | A brief summary                                       |
+--------------+-------------------------------------------------------+
| home_page    | The package's home page URL                           |
+--------------+-------------------------------------------------------+
| author       | The author's name                                     |
+--------------+-------------------------------------------------------+
| author_email | The author's e-mail address                           |
+--------------+-------------------------------------------------------+
| license      | The package's licence type                            |
+--------------+-------------------------------------------------------+
| description  | A long description of the package                     |
+--------------+-------------------------------------------------------+
| platform     | The platforms that the package is intended to work in |
+--------------+-------------------------------------------------------+
