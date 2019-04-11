Project Specifiers
==================

Project Specifiers are how `pulp-python` filters all the Python content on a Remote repository.

Syntax
------

Lists of `ProjectSpecifiers` are passed to `PythonRemotes
<https://pulp-python.readthedocs.io/en/latest/restapi.html#operation/remotes_python_python_create>`_

Each `ProjectSpecifier` is a dictionary, with 2 keys, `name` and `version_specifier`.

`name`:
   the Python Project name, eg "django"
`version_specifier`:
   Accepts standard python versions syntax: >=, <=, ==, ~=, >, <, ! can be used in conjunction with
   other specifiers (i.e.  >1,<=3,!=3.0.2). Note that the specifiers treat pre-released versions as
   < released versions, so 3.0.0a1 < 3.0.0. Not setting the version_specifier will sync all the
   pre-released and released versions. For more information consult `PEP 440
   <https://www.python.org/dev/peps/pep-0440/#version-specifiers>`_ or `Python Packaging specifier
   guidelines <https://packaging.pypa.io/en/latest/specifiers/>`_

**Example usage:**

.. code-block:: bash

   http POST $BASE_ADDR/pulp/api/v3/remotes/python/python/ \
       name='bar' \
       url='https://pypi.org/' \
       includes:='[{"name": "django", "version_specifier":"~=2.0"}]'
