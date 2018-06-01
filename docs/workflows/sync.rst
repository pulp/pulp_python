Synchronize a Repository
========================

Users can populate their repositories with content from an external source like PyPI by syncing
their repository.

Create a Repository
-------------------

Start by creating a new repository named "foo"::

    $ http POST $BASE_ADDR/pulp/api/v3/repositories/ name=foo

Response::

    {
        "_href": "http://localhost:8000/pulp/api/v3/repositories/e81221c3-9c7a-4681-a435-aa74020753f2/",
        ...
    }

If you want to copy/paste your way through the guide, create an environment variable for the repository URI::

    $ export REPO_HREF=$(http $BASE_ADDR/pulp/api/v3/repositories/ | jq -r '.results[] | select(.name == "foo") | ._href')


Create a Remote
---------------

Creating a remote object informs Pulp about an external content source. In this case, we will be
using a fixture, but Python remotes can be anything that implements the PyPI API. This can be PyPI
itself, a fixture, or even an instance of Pulp 2.

You can use any Python remote to sync content into any repository::

    $ http POST $BASE_ADDR/pulp/api/v3/remotes/python/ \
        name='bar' \
        url='https://pypi.org/' \
        projects:='[{"name": "django", "version_specifier":"~=2.0"}]'




Response::

    {
        "_href": "http://localhost:8000/pulp/api/v3/repositories/foo/remotes/python/3750748b-781f-48df-9734-df014b2a11b4/",
        ...
    }

Again, you can create an environment variable for convenience::

    $ export REMOTE_HREF=$(http $BASE_ADDR/pulp/api/v3/remotes/python/ | jq -r '.results[] | select(.name == "bar") | ._href')


A More Complex Remote
---------------------
If only the name of a project is specified, every distribution of every version of that project
will be synced. You can use the version_specifier and digest fields on a project to ensure
only distributions you care about will be synced::

    $ http POST $BASE_ADDR/pulp/api/v3/remotes/python/ \
        name='complex-remote' \
        url='https://pypi.org/' \
        projects:='[
            { "name": "django",
              "version_specifier": "~=2.0,!=2.0.1",
              "digests":[
                    {"type": "sha256",
                     "digest": "3d9916515599f757043c690ae2b5ea28666afa09779636351da505396cbb2f19"}
              ]
            },
            {"name": "pip-tools",
             "version_specifier": ">=1.12,<=2.0"},
            {"name": "scipy",
             "digests":[
                {"type": "md5",
                "digest": "044af71389ac2ad3d3ece24d0baf4c07"},
                {"type": "sha256",
                "digest": "18b572502ce0b17e3b4bfe50dcaea414a98290358a2fa080c36066ba0651ec14"}]
            },
            {"name": "shelf-reader"}
        ]'


Sync repository foo with remote
-------------------------------

Use the remote object to kick off a synchronize task by specifying the repository to
sync with. You are telling pulp to fetch content from the remote and add to the repository::

    $ http POST $REMOTE_HREF'sync/' repository=$REPO_HREF

Response::

    {
        "_href": "http://localhost:8000/pulp/api/v3/tasks/3896447a-2799-4818-a3e5-df8552aeb903/",
        "task_id": "3896447a-2799-4818-a3e5-df8552aeb903"
    }

You can follow the progress of the task with a GET request to the task href. Notice that when the
synchroinze task completes, it creates a new version, which is specified in ``created_resources``::

    $  http $BASE_ADDR/pulp/api/v3/tasks/3896447a-2799-4818-a3e5-df8552aeb903/

Response::

    {
        "_href": "http://localhost:8000/pulp/api/v3/tasks/3896447a-2799-4818-a3e5-df8552aeb903/",
        "created": "2018-05-01T17:17:46.558997Z",
        "created_resources": [
            "http://localhost:8000/pulp/api/v3/repositories/593e2fa9-af64-4d4b-aa7b-7078c96f2443/versions/6/"
        ],
        "error": null,
        "finished_at": "2018-05-01T17:17:47.149123Z",
        "non_fatal_errors": [],
        "parent": null,
        "progress_reports": [
            {
                "done": 0,
                "message": "Add Content",
                "state": "completed",
                "suffix": "",
                "task": "http://localhost:8000/pulp/api/v3/tasks/3896447a-2799-4818-a3e5-df8552aeb903/",
                "total": 0
            },
            {
                "done": 0,
                "message": "Remove Content",
                "state": "completed",
                "suffix": "",
                "task": "http://localhost:8000/pulp/api/v3/tasks/3896447a-2799-4818-a3e5-df8552aeb903/",
                "total": 0
            }
        ],
        "spawned_tasks": [],
        "started_at": "2018-05-01T17:17:46.644801Z",
        "state": "completed",
        "worker": "http://localhost:8000/pulp/api/v3/workers/eaffe1be-111a-421d-a127-0b8fa7077cf7/"
    }
