Synchronize a Repository
========================

Users can populate their repositories with content from an external source like PyPI by syncing
their repository.

Create a Repository
-------------------

.. literalinclude:: ../_scripts/repo.sh
   :language: bash

Repository GET Response::

    {
        "pulp_created": "2019-04-29T15:57:59.763712Z",
        "pulp_href": "/pulp/api/v3/repositories/1b2b0af1-5588-4b4b-b2f6-cdd3a3e1cd36/",
        "latest_version_href": null,
        "versions_href": "/pulp/api/v3/repositories/1b2b0af1-5588-4b4b-b2f6-cdd3a3e1cd36/versions/",
        "description": "",
        "name": "foo"
    }

Reference (pulpcore): `Repository API Usage
<https://docs.pulpproject.org/en/3.0/nightly/restapi.html#tag/repositories>`_


Create a Remote
---------------

Creating a remote object informs Pulp about an external content source. In this case, we will be
using a fixture, but Python remotes can be anything that implements the PyPI API. This can be PyPI
itself, a fixture, or even an instance of Pulp 2.

.. literalinclude:: ../_scripts/remote.sh
   :language: bash

Remote GET Response::

    {
        "ca_cert": null,
        "client_cert": null,
        "client_key": null,
        "download_concurrency": 10,
        "excludes": [],
        "includes": [
            "shelf-reader"
        ],
        "name": "bar",
        "password": null,
        "policy": "on_demand",
        "prereleases": false,
        "proxy_url": null,
        "pulp_created": "2020-10-15T22:08:07.943369Z",
        "pulp_href": "/pulp/api/v3/remotes/python/python/bbcfa980-ea53-425c-b03b-17c9c2867bba/",
        "pulp_last_updated": "2020-10-15T22:08:07.943404Z",
        "tls_validation": true,
        "url": "https://pypi.org/",
        "username": null
    }

Reference: `Python Remote Usage <../restapi.html#tag/remotes>`_

A More Complex Remote
---------------------

If only the name of a project is specified, every distribution of every version of that project
will be synced. You can use the version_specifier field to ensure only distributions you care
about will be synced::

    $ http POST $BASE_ADDR/pulp/api/v3/remotes/python/python/ \
        name='complex-remote' \
        url='https://pypi.org/' \
        includes:='[
            "django~=2.0,!=2.0.1",
            "pip-tools>=1.12,<=2.0",
            "scipy",
            "shelf-reader"
        ]'

You can also use version specifiers to "exclude" certain versions of a project, like so::

    $ http POST $BASE_ADDR/pulp/api/v3/remotes/python/python/ \
        name='complex-remote' \
        url='https://pypi.org/' \
        includes:='[
            "django",
            "scipy"
        ]' \
        excludes:='[
            "django~=1.0",
            "scipy"
        ]'

Reference: `Python Remote Usage <../restapi.html#tag/remotes>`_

Creating a remote to sync all of PyPi
_____________________________________

A remote can be setup to sync all of PyPi by not specifying any included packages like so::

    $ http POST $BASE_ADDR/pulp/api/v3/remotes/python/python/ \
        name='PyPi-mirror' \
        url='https://pypi.org/' \
        excludes:='[
            "django~=1.0",
            "scipy"
        ]'

By not setting the "includes" field Pulp will ask PyPi for all of its available packages to sync, minus the ones from
the excludes field. Default Python remotes are created with syncing policy "on_demand" because the most common
Python remotes involve syncing with PyPi which requires terabytes of disk space. This can be changed by
modifying the "policy" field.

Sync repository foo with remote
-------------------------------

Use the remote object to kick off a synchronize task by specifying the repository to
sync with. You are telling pulp to fetch content from the remote and add to the repository.

.. literalinclude:: ../_scripts/sync.sh
   :language: bash

Repository Version GET Response (when complete)::

    {
        "pulp_created": "2019-04-29T15:58:02.579318Z",
        "pulp_href": "/pulp/api/v3/repositories/1b2b0af1-5588-4b4b-b2f6-cdd3a3e1cd36/versions/1/",
        "base_version": null,
        "content_summary": {
            "added": {
                "python.python": {
                    "count": 2,
                    "href": "/pulp/api/v3/content/python/packages/?repository_version_added=/pulp/api/v3/repositories/1b2b0af1-5588-4b4b-b2f6-cdd3a3e1cd36/versions/1/"
                }
            },
            "present": {
                "python.python": {
                    "count": 2,
                    "href": "/pulp/api/v3/content/python/packages/?repository_version=/pulp/api/v3/repositories/1b2b0af1-5588-4b4b-b2f6-cdd3a3e1cd36/versions/1/"
                }
            },
            "removed": {}
        },
        "number": 1
    }



Reference: `Python Sync Usage <../restapi.html#operation/remotes_python_python_sync>`_

Reference (pulpcore): `Repository Version Creation API Usage
<https://docs.pulpproject.org/en/3.0/nightly/restapi.html#operation/repositories_versions_list>`_
