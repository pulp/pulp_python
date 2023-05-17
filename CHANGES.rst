=========
Changelog
=========

..
    You should *NOT* be adding new change log entries to this file, this
    file is managed by towncrier. You *may* edit previous change logs to
    fix problems like typo corrections or such.
    To add a new change log entry, please see
    https://docs.pulpproject.org/en/3.0/nightly/contributing/git.html#changelog-update

    WARNING: Don't drop the next directive!

.. towncrier release notes start

3.10.0 (2023-05-17)
===================


Features
--------

- Added compatibility for pulpcore 3.25, pulpcore support is now >=3.25,<3.40.
  `#605 <https://github.com/pulp/pulp_python/issues/605>`__


----


3.9.0 (2023-03-17)
==================


Features
--------

- Added version filter to package list endpoint.
  `#577 <https://github.com/pulp/pulp_python/issues/577>`__
- Allow duplicate uploads to return existing packages instead of erring.
  `#590 <https://github.com/pulp/pulp_python/issues/590>`__


Bugfixes
--------

- Fixed pull-through caching ignoring remote proxy settings.
  `#553 <https://github.com/pulp/pulp_python/issues/553>`__
- Changed includes and excludes openapi schema to report as array of strings instead of object.
  `#576 <https://github.com/pulp/pulp_python/issues/576>`__
- Fixed syncing ignoring remote proxy.
  `#581 <https://github.com/pulp/pulp_python/issues/581>`__
- Fixed duplicate operationID for generated PyPI simple endpoints schema.
  `#594 <https://github.com/pulp/pulp_python/issues/594>`__


----


3.8.0 (2022-12-19)
==================


Bugfixes
--------

- Fixed syncing failing when using bandersnatch 5.3.0
  `#554 <https://github.com/pulp/pulp_python/issues/554>`__
- Prevent .netrc file from being read on syncs.
  `#566 <https://github.com/pulp/pulp_python/issues/566>`__
- Fix 500 error when pip installing using object storage.
  `#572 <https://github.com/pulp/pulp_python/issues/572>`__


Improved Documentation
----------------------

- Documented ``pulp_python`` specific settings.
  `#571 <https://github.com/pulp/pulp_python/issues/571>`__


----


3.7.3 (2022-10-06)
==================


Bugfixes
--------

- Prevent .netrc file from being read on syncs.
  `#566 <https://github.com/pulp/pulp_python/issues/566>`__


----


3.7.2 (2022-08-04)
==================


Bugfixes
--------

- Fixed syncing failing when using bandersnatch 5.3.0
  `#554 <https://github.com/pulp/pulp_python/issues/554>`__


----


3.7.1 (2022-06-29)
==================


No significant changes.


----


3.7.0 (2022-06-22)
==================


Features
--------

- Added ability to fully sync repositories that don't support the PyPI XMLRPC endpoints. Full Pulp-to-Pulp syncing is now available.
  `#462 <https://github.com/pulp/pulp_python/issues/462>`__


Bugfixes
--------

- Ensured temporary package uploads are written to worker's directory instead of /tmp.
  `#505 <https://github.com/pulp/pulp_python/issues/505>`__


Misc
----

- `#503 <https://github.com/pulp/pulp_python/issues/503>`__


----


3.6.1 (2022-08-19)
==================


Bugfixes
--------

- Fixed syncing failing when using bandersnatch 5.3.0
  `#554 <https://github.com/pulp/pulp_python/issues/554>`__


----


3.6.0 (2021-12-15)
==================


Features
--------

- ``pulp_python`` now supports pull-through caching. Add a remote to a distribution to enable this feature.
  `#381 <https://github.com/pulp/pulp_python/issues/381>`_
- Enable Azure support
  `#458 <https://github.com/pulp/pulp_python/issues/458>`_


Bugfixes
--------

- Fixed proxy url not being passed during sync
  `#433 <https://github.com/pulp/pulp_python/issues/433>`_
- Changed the use of ``dispatch`` to match the signature from pulpcore>=3.15.
  `#443 <https://github.com/pulp/pulp_python/issues/443>`_
- Fixed package name normalization issue preventing installing packages with "." or "_" in their names.
  `#467 <https://github.com/pulp/pulp_python/issues/467>`_


----


3.5.2 (2021-10-05)
==================


Bugfixes
--------

- Fixed proxy url not being passed during sync
  (backported from #445)
  `#436 <https://github.com/pulp/pulp_python/issues/436>`_
- Changed the use of ``dispatch`` to match the signature from pulpcore>=3.15.
  (backported from #443)
  `#446 <https://github.com/pulp/pulp_python/issues/446>`_


----


3.5.1 (2021-09-10)
==================


Bugfixes
--------

- Fixed proxy url not being passed during sync
  (backported from #433)
  `#436 <https://github.com/pulp/pulp_python/issues/436>`_


----


3.5.0 (2021-08-30)
==================


Features
--------

- Python package content can now be filtered by their sha256
  `#404 <https://github.com/pulp/pulp_python/issues/404>`_
- Added new setting ``PYPI_API_HOSTNAME`` that is used to form a distribution's ``base_url``. Defaults to the machine's FQDN.
  `#412 <https://github.com/pulp/pulp_python/issues/412>`_
- Enabled reclaim disk feature provided by pulpcore 3.15+.
  `#425 <https://github.com/pulp/pulp_python/issues/425>`_


Bugfixes
--------

- Fixed twine upload failing when using remote storage backends
  `#400 <https://github.com/pulp/pulp_python/issues/400>`_
- Fixed improper metadata serving when using publications with S3 storage
  `#413 <https://github.com/pulp/pulp_python/issues/413>`_


Deprecations and Removals
-------------------------

- Dropped support for Python < 3.8.
  `#402 <https://github.com/pulp/pulp_python/issues/402>`_


Misc
----

- `#408 <https://github.com/pulp/pulp_python/issues/408>`_, `#427 <https://github.com/pulp/pulp_python/issues/427>`_


----


3.4.1 (2021-08-24)
==================


Features
--------

- Python package content can now be filtered by their sha256
  (backported from #404)
  `#419 <https://github.com/pulp/pulp_python/issues/419>`_


Bugfixes
--------

- Fixed improper metadata serving when using publications with S3 storage
  (backported from #413)
  `#418 <https://github.com/pulp/pulp_python/issues/418>`_
- Fixed twine upload failing when using remote storage backends
  (backported from #400)
  `#420 <https://github.com/pulp/pulp_python/issues/420>`_


----


3.4.0 (2021-06-17)

Features
--------

- Added ``twine`` (and other similar Python tools) package upload support
  `#342 <https://github.com/pulp/pulp_python/issues/342>`_
- PyPI endpoints are now available at ``/pypi/{base_path}/``
  `#376 <https://github.com/pulp/pulp_python/issues/376>`_
- Changed the global uniqueness constraint for ``PythonPackageContent`` to its sha256 digest
  `#380 <https://github.com/pulp/pulp_python/issues/380>`_


Bugfixes
--------

- Added missing fields to PyPI live JSON API to be compliant with core metadata version 2.1
  `#352 <https://github.com/pulp/pulp_python/issues/352>`_
- Fixed sync to use default concurrency (10) when download_concurrency was not specified
  `#391 <https://github.com/pulp/pulp_python/issues/391>`_


----


3.3.0 (2021-05-27)
==================


Features
--------

- Add support for automatic publishing and distributing.
  `#365 <https://github.com/pulp/pulp_python/issues/365>`_


Bugfixes
--------

- Fixed publications publishing more content than was in the repository
  `#362 <https://github.com/pulp/pulp_python/issues/362>`_


Improved Documentation
----------------------

- Update syntax in doc for cli repository content add command
  `#368 <https://github.com/pulp/pulp_python/issues/368>`_


Misc
----

- `#347 <https://github.com/pulp/pulp_python/issues/347>`_, `#360 <https://github.com/pulp/pulp_python/issues/360>`_, `#371 <https://github.com/pulp/pulp_python/issues/371>`_


----


3.2.0 (2021-04-14)
==================


Features
--------

- Added new sync filter `keep_latest_packages` to specify how many latest versions of packages to sync
  `#339 <https://github.com/pulp/pulp_python/issues/339>`_
- Added new sync filters `package_types` and `exclude_platforms` to specify package types to sync
  `#341 <https://github.com/pulp/pulp_python/issues/341>`_


Misc
----

- `#354 <https://github.com/pulp/pulp_python/issues/354>`_


----


3.1.0 (2021-03-12)
==================


Features
--------

- Python content can now be filtered by requires_python
  `#3629 <https://pulp.plan.io/issues/3629>`_


Improved Documentation
----------------------

- Updated workflows to use Pulp CLI commands
  `#8364 <https://pulp.plan.io/issues/8364>`_


----


3.0.0 (2021-01-12)
==================


Bugfixes
--------

- Remote proxy settings are now passed to Bandersnatch while syncing
  `#7864 <https://pulp.plan.io/issues/7864>`_


Improved Documentation
----------------------

- Added bullet list of Python Plugin features and a tech preview page for new experimental features
  `#7628 <https://pulp.plan.io/issues/7628>`_


----


3.0.0b12 (2020-11-05)
=====================


Features
--------

- Pulp Python can now fully mirror all packages from PyPi
  `#985 <https://pulp.plan.io/issues/985>`_
- Implemented PyPi's json API at content endpoint '/pypi/{package-name}/json'.  Pulp can now perform basic syncing on other Pulp Python instances.
  `#2886 <https://pulp.plan.io/issues/2886>`_
- Pulp Python now uses Bandersnatch to perform syncing and filtering of package metadata
  `#6930 <https://pulp.plan.io/issues/6930>`_


Bugfixes
--------

- Sync now includes python package's classifiers in the content unit
  `#3627 <https://pulp.plan.io/issues/3627>`_
- Policy can now be specified when creating a remote from a Bandersnatch config
  `#7331 <https://pulp.plan.io/issues/7331>`_
- Includes/excludes/prereleases fields are now properly set in a remote from Bandersnatch config
  `#7392 <https://pulp.plan.io/issues/7392>`_


Improved Documentation
----------------------

- Fixed makemigrations commands in the install docs
  `#5386 <https://pulp.plan.io/issues/5386>`_


Misc
----

- `#6875 <https://pulp.plan.io/issues/6875>`_, `#7401 <https://pulp.plan.io/issues/7401>`_


----


3.0.0b11 (2020-08-18)
=====================


Compatibility update for pulpcore 3.6


----


3.0.0b10 (2020-08-05)
=====================


Features
--------

- Added a new endpoint to remotes "/from_bandersnatch" that allows for Python remote creation from a Bandersnatch config file.
  `#6929 <https://pulp.plan.io/issues/6929>`_


Bugfixes
--------

- Including requirements.txt on MANIFEST.in
  `#6891 <https://pulp.plan.io/issues/6891>`_
- Updating API to not return publications that aren't complete.
  `#6987 <https://pulp.plan.io/issues/6987>`_
- Fixed an issue that prevented 'on_demand' content from being published.
  `#7128 <https://pulp.plan.io/issues/7128>`_


Improved Documentation
----------------------

- Change the commands for publication and distribution on the publish workflow to use their respective scripts already defined in _scripts.
  `#6877 <https://pulp.plan.io/issues/6877>`_
- Updated sync.sh, publication.sh and distribution.sh in docs/_scripts to reference wait_until_task_finished function from base.sh
  `#6918 <https://pulp.plan.io/issues/6918>`_


----


3.0.0b9 (2020-06-01)
====================


Features
--------

- Add upload functionality to the python contents endpoints.
  `#5464 <https://pulp.plan.io/issues/5464>`_


Bugfixes
--------

- Fixed the 500 error returned by the OpenAPI schema endpoint.
  `#5452 <https://pulp.plan.io/issues/5452>`_


Improved Documentation
----------------------

- Change the prefix of Pulp services from pulp-* to pulpcore-*
  `#4554 <https://pulp.plan.io/issues/4554>`_
- Added "python/python/" to fix two commands in repo.sh, fixed export command in sync.sh
  `#6790 <https://pulp.plan.io/issues/6790>`_
- ﻿Added "index.html" to the relative_path field for both project_metadata and index_metadata. Added a "/" to fix the link in the simple_index_template.
  `#6792 <https://pulp.plan.io/issues/6792>`_
- Updated the workflow documentation for upload.html.  Fixed the workflow commands and added more details to the instructions.
  `#6854 <https://pulp.plan.io/issues/6854>`_


Deprecations and Removals
-------------------------

- Change `_id`, `_created`, `_last_updated`, `_href` to `pulp_id`, `pulp_created`, `pulp_last_updated`, `pulp_href`
  `#5457 <https://pulp.plan.io/issues/5457>`_
- Remove "_" from `_versions_href`, `_latest_version_href`
  `#5548 <https://pulp.plan.io/issues/5548>`_
- Removing base field: `_type` .
  `#5550 <https://pulp.plan.io/issues/5550>`_
- Sync is no longer available at the {remote_href}/sync/ repository={repo_href} endpoint. Instead, use POST {repo_href}/sync/ remote={remote_href}.

  Creating / listing / editing / deleting python repositories is now performed on /pulp/api/v3/python/python/ instead of /pulp/api/v3/repositories/. Only python content can be present in a python repository, and only a python repository can hold python content.
  `#5625 <https://pulp.plan.io/issues/5625>`_


Misc
----

- `#remotetests <https://pulp.plan.io/issues/remotetests>`_, `#4681 <https://pulp.plan.io/issues/4681>`_, `#4682 <https://pulp.plan.io/issues/4682>`_, `#5304 <https://pulp.plan.io/issues/5304>`_, `#5471 <https://pulp.plan.io/issues/5471>`_, `#5580 <https://pulp.plan.io/issues/5580>`_, `#5701 <https://pulp.plan.io/issues/5701>`_


----


3.0.0b8 (2019-09-16)
====================


Misc
----

- `#4681 <https://pulp.plan.io/issues/4681>`_


----


3.0.0b7 (2019-08-01)
====================


Features
--------

- Users can upload a file to create content and optionally add to a repo in one step known as
  one-shot upload
  `#4396 <https://pulp.plan.io/issues/4396>`_
- Override the Remote's serializer to allow policy='on_demand' and policy='streamed'.
  `#4990 <https://pulp.plan.io/issues/4990>`_


Improved Documentation
----------------------

- Switch to using `towncrier <https://github.com/hawkowl/towncrier>`_ for better release notes.
  `#4875 <https://pulp.plan.io/issues/4875>`_


----


