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


