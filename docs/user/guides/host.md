# Host Your Python Content

This section assumes that you have a repository with content in it. To do this, see the
[sync](site:pulp_python/docs/user/guides/sync/) or [upload](site:pulp_python/docs/user/guides/upload/) documentation.

## Make a Python Index (Create a Distribution)

To host your Python content as a PyPI compatible index, (which makes it consumable by `pip`), users create a distribution which will serve the content in the repository at `${BASE_ADDR}/pypi/${DIST_BASE_PATH}/`.

=== "Run"

    ```bash
    # Distributions are created asynchronously. Create one, and specify the repository that will
    # be served at the base path specified.
    pulp python distribution create --name foo --base-path foo --repository foo
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
      "repository": "/pulp/api/v3/repositories/python/python/019cf738-6951-7b25-b26f-182683dc32f2/",
      "repository_version": null,
      "publication": null,
      "allow_uploads": true,
      "remote": null
    }
    ```

Setting the distribution's `repository` field will auto-serve the latest version of that repository. If you wish to only serve content from a specific version you can use the `repository_version` field.

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

!!! warning
    Chaining pull-through indices, having a pull-through point to another pull-through, does not
    work.

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


## Migrating off Publications

Ever since the release of `pulp-python` 3.4, publications have no longer been required to serve content to Python compatible tooling. Publications became deprecated in version 3.27, but it is recommended to move off of them even on early versions as many new features like pull-through caching, simple JSON, attestations, were not built to work with publications. To move off publications follow these three steps:

1. Switch any distribution serving a publication to a repository or repository-version
2. Set `autopublish=False` for all repositories
3. Delete all python publications

!!! warning
    Publications may be removed in a future `pulp-python` version.

!!! note
    To maintain backwards compatibility, `/pypi/` endpoints will always try to use a publication if there is one available for the repository. We recommend deleting every publication for a repository if you wish to use the newer features.
