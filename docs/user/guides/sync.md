# Synchronize a Repository

Users can populate their repositories with content from an external source like PyPI by syncing
their repository.

## Create a Repository

=== "Run"

    ```bash
    # Start by creating a new repository named "foo":
    pulp python repository create --name foo
    ```

=== "Output"

    ```
    {
      "pulp_href": "/pulp/api/v3/repositories/python/python/0196ba2a-f353-736a-854c-2d415389a509/",
      "prn": "prn:python.pythonrepository:0196ba2a-f353-736a-854c-2d415389a509",
      "pulp_created": "2025-05-10T12:28:19.156941Z",
      "pulp_last_updated": "2025-05-10T12:28:19.169190Z",
      "versions_href": "/pulp/api/v3/repositories/python/python/0196ba2a-f353-736a-854c-2d415389a509/versions/",
      "pulp_labels": {},
      "latest_version_href": "/pulp/api/v3/repositories/python/python/0196ba2a-f353-736a-854c-2d415389a509/versions/0/",
      "name": "foo",
      "description": null,
      "retain_repo_versions": null,
      "remote": null,
      "autopublish": false
    }
    ```

Reference: [Python Repository Usage](site:pulp_python/restapi/#tag/Repositories:-Python)

## Create a Remote

Creating a remote object informs Pulp about an external content source. In this case, we will be
using a fixture, but Python remotes can be anything that implements the PyPI API. This can be PyPI
itself, a fixture, or even an instance of Pulp 2.

=== "Run"

    ```bash
    # Create a remote that syncs some versions of shelf-reader into your repository.
    pulp python remote create --name bar --url https://pypi.org/ --includes '["shelf-reader"]'
    ```

=== "Output"

    ```
    {
      "pulp_href": "/pulp/api/v3/remotes/python/python/0196ba2b-1461-7d0d-99f6-5f75610abf71/",
      "prn": "prn:python.pythonremote:0196ba2b-1461-7d0d-99f6-5f75610abf71",
      "pulp_created": "2025-05-10T12:28:27.617672Z",
      "pulp_last_updated": "2025-05-10T12:28:27.617697Z",
      "name": "bar",
      "url": "https://pypi.org/",
      "ca_cert": null,
      "client_cert": null,
      "tls_validation": true,
      "proxy_url": null,
      "pulp_labels": {},
      "download_concurrency": null,
      "max_retries": null,
      "policy": "on_demand",
      "total_timeout": null,
      "connect_timeout": null,
      "sock_connect_timeout": null,
      "sock_read_timeout": null,
      "headers": null,
      "rate_limit": null,
      "hidden_fields": [
        {
          "name": "client_key",
          "is_set": false
        },
        {
          "name": "proxy_username",
          "is_set": false
        },
        {
          "name": "proxy_password",
          "is_set": false
        },
        {
          "name": "username",
          "is_set": false
        },
        {
          "name": "password",
          "is_set": false
        }
      ],
      "includes": [
        "shelf-reader"
      ],
      "excludes": [],
      "prereleases": true,
      "package_types": [],
      "keep_latest_packages": 0,
      "exclude_platforms": []
    }
    ```

Reference: [Python Remote Usage](site:pulp_python/restapi/#tag/Remotes:-Python)

## A More Complex Remote

If only the name of a project is specified, every distribution of every version of that project
will be synced. You can use the version specifier field to ensure only distributions you care
about will be synced:

```bash
pulp python remote create \
    --name 'complex-remote' \
    --url 'https://pypi.org/' \
    --includes '[
        "django~=2.0,!=2.0.1",
        "pip-tools>=1.12,<=2.0",
        "scipy",
        "shelf-reader"
    ]'
```

You can also use version specifiers to "exclude" certain versions of a project, like so:

```bash
pulp python remote create \
    --name 'complex-remote' \
    --url 'https://pypi.org/' \
    --includes '[
        "django",
        "scipy"
    ]' \
    --excludes '[
        "django~=1.0",
        "scipy"
    ]'
```

You can also filter packages by their type, platform and amount synced through the "package_types",
"exclude_platforms", and "keep_latest_packages" fields respectively, like so:

```bash
# Sync only sdist and bdist_wheel package types, exclude any packages built
# for windows and keep the five latest versions
pulp python remote create \
    --name 'complex-filters' \
    --url 'https://pypi.org/' \
    --includes '["django"]' \
    --package-types '["sdist", "bdist_wheel"]' \
    --exclude-platforms '["windows"]' \
    --keep-latest-packages 5 
```

Reference: [Python Remote Usage](site:pulp_python/restapi/#tag/Remotes:-Python)

### Creating a remote to sync all of PyPI

A remote can be set up to sync all of PyPI by not specifying any included packages, like so:

```bash
pulp python remote create \
    --name 'PyPI-mirror' \
    --url 'https://pypi.org/' \
    --excludes '[
        "django~=1.0",
        "scipy"
    ]'
```

By not setting the "includes" field Pulp will ask PyPI for all of its available packages to sync, minus the ones from
the excludes field. Default Python remotes are created with syncing policy "on_demand" because the most common
Python remotes involve syncing with PyPI which requires terabytes of disk space. This can be changed by
modifying the "policy" field.

Syncing all of PyPI can take a long time depending on your network and disk speeds. Check out
[pull-through caching](site:pulp_python/docs/user/guides/publish/#enable-pull-through-caching) 
to learn about another way to mirror PyPI.

## Sync repository foo with remote

Use the remote object to kick off a synchronize task by specifying the repository to
sync with. You are telling pulp to fetch content from the remote and add to the repository.

=== "Run"

    ```bash
    # Using the Remote we just created, we kick off a sync task
    pulp python repository sync --name foo --remote bar
    
    # The sync command will by default wait for the sync to complete
    # Use Ctrl+c or the -b option to send the task to the background
    
    # Show the latest version when sync is done
    pulp python repository version show --repository foo
    ```

=== "Output"

    ```
    {
      "pulp_href": "/pulp/api/v3/repositories/python/python/0196ba2a-f353-736a-854c-2d415389a509/versions/1/",
      "prn": "prn:core.repositoryversion:0196ba2b-655c-7745-b10f-bdde15a941c6",
      "pulp_created": "2025-05-10T12:28:48.349938Z",
      "pulp_last_updated": "2025-05-10T12:28:49.031497Z",
      "number": 1,
      "repository": "/pulp/api/v3/repositories/python/python/0196ba2a-f353-736a-854c-2d415389a509/",
      "base_version": null,
      "content_summary": {
        "added": {
          "python.python": {
            "count": 2,
            "href": "/pulp/api/v3/content/python/packages/?repository_version_added=/pulp/api/v3/repositories/python/python/0196ba2a-f353-736a-854c-2d415389a509/versions/1/"
          }
        },
        "removed": {},
        "present": {
          "python.python": {
            "count": 2,
            "href": "/pulp/api/v3/content/python/packages/?repository_version=/pulp/api/v3/repositories/python/python/0196ba2a-f353-736a-854c-2d415389a509/versions/1/"
          }
        }
      }
    }
    ```

Reference: [Python Sync Usage](site:pulp_python/restapi/#tag/Repositories:-Python/operation/repositories_python_python_sync)
