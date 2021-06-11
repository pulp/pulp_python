Tech previews
=============

The following features are currently being released as part of a tech preview

* New endpoint “pulp/api/v3/remotes/python/python/from_bandersnatch/” that allows for Python remote creation from a
  Bandersnatch config file.
* PyPI’s json API at content endpoint ‘/pypi/{package-name}/json’. Allows for basic Pulp-to-Pulp syncing.
* Fully mirror Python repositories like PyPI.
* ``Twine`` upload packages to indexes at endpoints '/simple` or '/legacy'.
* Create pull-through caches of remote sources.
