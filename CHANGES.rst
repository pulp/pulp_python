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


