# Set up your own PyPI

This section guides you through the quickest way to set up `pulp_python` to act as your very own
private `PyPI`.

## Create a Repository

Repositories are the base objects `Pulp` uses to store and organize its content. They are automatically
versioned when content is added or deleted and allow for easy rollbacks to previous versions.

=== "Run"

    ```bash
    # Start by creating a new repository named "foo":
    pulp python repository create --name foo
    ```

=== "Output"

    ```
    {
      "pulp_href": "/pulp/api/v3/repositories/python/python/0196ba29-52b9-7cf4-b12e-f3247f0eb3dc/",
      "prn": "prn:python.pythonrepository:0196ba29-52b9-7cf4-b12e-f3247f0eb3dc",
      "pulp_created": "2025-05-10T12:26:32.506906Z",
      "pulp_last_updated": "2025-05-10T12:26:32.517333Z",
      "versions_href": "/pulp/api/v3/repositories/python/python/0196ba29-52b9-7cf4-b12e-f3247f0eb3dc/versions/",
      "pulp_labels": {},
      "latest_version_href": "/pulp/api/v3/repositories/python/python/0196ba29-52b9-7cf4-b12e-f3247f0eb3dc/versions/0/",
      "name": "foo",
      "description": null,
      "retain_repo_versions": null,
      "remote": null,
      "autopublish": false
    }
    ```

## Create a Distribution

Distributions serve the content stored in repositories so that it can be used by tools like `pip`.

=== "Run"

    ```bash
    pulp python distribution create --name my-pypi --base-path my-pypi --repository foo
    ```

=== "Output"

    ```
    {
      "pulp_href": "/pulp/api/v3/distributions/python/pypi/0196ba29-8f95-776b-a782-78d7838f3f9f/",
      "prn": "prn:python.pythondistribution:0196ba29-8f95-776b-a782-78d7838f3f9f",
      "pulp_created": "2025-05-10T12:26:48.086775Z",
      "pulp_last_updated": "2025-05-10T12:26:48.086806Z",
      "base_path": "my-pypi",
      "base_url": "http://localhost:5001/pypi/my-pypi/",
      "content_guard": null,
      "no_content_change_since": null,
      "hidden": false,
      "pulp_labels": {},
      "name": "my-pypi",
      "repository": "/pulp/api/v3/repositories/python/python/0196ba29-52b9-7cf4-b12e-f3247f0eb3dc/",
      "publication": null,
      "allow_uploads": true,
      "remote": null
    }
    ```

## Upload and Install Packages

Packages can now be uploaded to the index using your favorite Python tool. The index url will be available
at `${BASE_ADDR}/pypi/${DIST_BASE_PATH}/simple/`.

```bash
BASE_ADDR="http://localhost:5001"
PLUGIN_SOURCE="shelf-reader"
git clone https://github.com/asmacdo/shelf-reader.git
# Build custom package
python -m build "$PLUGIN_SOURCE"
# Upload built package distributions to my-pypi
twine upload --repository-url "${BASE_ADDR}/pypi/my-pypi/simple/" -u admin -p password "${PLUGIN_SOURCE}/dist/"*
```

Packages can then be installed using your favorite Python tool:

```bash
pip install --trusted-host localhost -i "${BASE_ADDR}/pypi/my-pypi/simple/" "$PLUGIN_SOURCE"
```

Now you have a fully operational Python package index. Check out the other workflows to see more features of
`pulp_python`.
