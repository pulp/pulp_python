# Publish and Host Your Python Content

This section assumes that you have a repository with content in it. To do this, see the
[sync](site:pulp_python/docs/user/guides/sync/) or [upload](site:pulp_python/docs/user/guides/upload/) documentation.

## Create a Publication (manually)

Kick off a publish task by creating a new publication. The publish task will generate all the
metadata that `pip` needs to install packages (although it will need to be hosted through a
Distribution before it is consumable).

=== "Run"

    ```bash
    # Create a new publication specifying the repository_version.
    # Alternatively, you can specify just the repository, and Pulp will assume the latest version.
    pulp python publication create --repository foo --version 1
    
    # Publications can only be referenced through their pulp_href
    PUBLICATION_HREF=$(pulp python publication list | jq -r .[0].pulp_href)
    ```

=== "Output"

    ```
    {
      "pulp_href": "/pulp/api/v3/publications/python/pypi/0196ba31-cd04-7aba-a7b4-71a98a976745/",
      "prn": "prn:python.pythonpublication:0196ba31-cd04-7aba-a7b4-71a98a976745",
      "pulp_created": "2025-05-10T12:35:48.103758Z",
      "pulp_last_updated": "2025-05-10T12:35:48.205361Z",
      "repository_version": "/pulp/api/v3/repositories/python/python/0196ba30-e15e-71ea-9867-33aeceb5a87e/versions/1/",
      "repository": "/pulp/api/v3/repositories/python/python/0196ba30-e15e-71ea-9867-33aeceb5a87e/",
      "distributions": []
    }
    ```

## Host a Publication (Create a Distribution)

To host a publication, (which makes it consumable by `pip`), users create a distribution which
will serve the associated publication at `${BASE_ADDR}/pypi/${DIST_BASE_PATH}/`.

=== "Run"

    ```bash
    # Distributions are created asynchronously. Create one, and specify the publication that will
    # be served at the base path specified.
    pulp python distribution create --name foo --base-path foo --publication "$PUBLICATION_HREF"
    ```

=== "Output"

    ```
    {
      "pulp_href": "/pulp/api/v3/distributions/python/pypi/0196ba32-0be6-7f85-bbb3-cf561a4e2d88/",
      "prn": "prn:python.pythondistribution:0196ba32-0be6-7f85-bbb3-cf561a4e2d88",
      "pulp_created": "2025-05-10T12:36:04.200189Z",
      "pulp_last_updated": "2025-05-10T12:36:04.200232Z",
      "base_path": "foo",
      "base_url": "http://localhost:5001/pypi/foo/",
      "content_guard": null,
      "no_content_change_since": "2025-05-10T12:36:04.200232Z",
      "hidden": false,
      "pulp_labels": {},
      "name": "foo",
      "repository": null,
      "publication": "/pulp/api/v3/publications/python/pypi/0196ba31-cd04-7aba-a7b4-71a98a976745/",
      "allow_uploads": true,
      "remote": null
    }
    ```

## Automate Publication and Distribution

With a little more initial setup, you can have publications and distributions for your repositories
updated automatically when new repository versions are created.

```bash
# This configures the repository to produce new publications when a new version is created
pulp python repository update --name foo --autopublish
# This configures the distribution to track the latest repository version for a given repository
pulp python distribution update --name foo --repository foo
```

!!! warning
    Support for automatic publication and distribution is provided as a tech preview in Pulp 3.
    Functionality may not work or may be incomplete. Also, backwards compatibility when upgrading
    is not guaranteed.

## Enable Pull-Through Caching

Only packages present in your repository will be available from your index, but adding a remote source to
your distribution will enable the pull-through cache feature. This feature allows you to install any package
from the remote source and have Pulp store that package as orphaned content.

```bash
# Add remote to distribution to enable pull-through caching
pulp python distribution update --name foo --remote bar
```

!!! note
    Pull-through caching will respect the includes/excludes filters on the supplied remote.

!!! warning
    Support for pull-through caching is provided as a tech preview in Pulp 3.
    Functionality may not work or may be incomplete. Also, backwards compatibility when upgrading
    is not guaranteed.

## Use the newly created distribution

The metadata and packages can now be retrieved from the distribution:

```bash
http "${BASE_ADDR}/pypi/foo/simple/"
http "${BASE_ADDR}/pypi/foo/simple/shelf-reader/"
```

!!! note
    When domains are enabled, it is necessary to include the domain name within the URL, like so:
    `${BASE_ADDR}/pypi/${DOMAIN_NAME}/foo/simple/`

The content is also pip installable:

```bash
pip install --trusted-host localhost -i "${BASE_ADDR}/pypi/foo/simple/" shelf-reader
```

If you don't want to specify the distribution path every time, you can modify your `pip.conf` file:

=== "Run"

    ```bash
    cat pip.conf
    ```

=== "Output"

    ```
    [global]
    index-url = http://localhost:24817/pypi/foo/simple/
    ```

The above configuration informs `pip` to install from `pulp`:

```bash
pip install --trusted-host localhost shelf-reader
```

See the [pip docs](https://pip.pypa.io/en/stable/topics/configuration) for more details.
