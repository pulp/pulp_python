3.0.0b6
=======

* See all changes `here <https://github.com/pulp/pulp_python/compare/3.0.0b5...3.0.0b6>`_.

* Adds support for `pulpcore 3.0.0.rc2 <https://docs.pulpproject.org/en/3.0/rc/release-notes/pulpcore/3.0.x.html#rc2>`_.

  Changes urls for distributions and publications

* Adds lazy sync

* Docs replace snippets with testable scripts

3.0.0b5
=======

* Fix relative_path to allow pip install

3.0.0b4
=======

* Adds support for `pulpcore 3.0.0.rc1 <https://docs.pulpproject.org/en/3.0/nightly/release-notes/pulpcore/3.0.x.html#rc1>`_.

* Adds excludes support (aka 'blacklist')

  Renames the "projects" field on the remote to "includes".

  Adds a new "excludes" field to the remote which behaves like "includes", except that any specified
  releasees or digests are not synced, even if an include specifier matches them.

  Also adds a 'prereleases' field to the remote, which toggles whether prerelease versions should be
  synced. This mirrors the 'prereleases' flag that packaging.specifiers.SpecifierSet provides.

* Removes Python 3.5 support
