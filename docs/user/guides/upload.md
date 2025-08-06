# Upload and Manage Content

Content can be added to a repository not only by synchronizing from a remote source but also by uploading the files directly into Pulp.

## Create a repository

If you don't already have a repository, create one.

=== "Run"

    ```bash
    # Start by creating a new repository named "foo":
    pulp python repository create --name foo
    ```

=== "Output"

    ```
    {
      "pulp_href": "/pulp/api/v3/repositories/python/python/0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20/",
      "prn": "prn:python.pythonrepository:0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20",
      "pulp_created": "2025-05-10T12:30:34.358509Z",
      "pulp_last_updated": "2025-05-10T12:30:34.373703Z",
      "versions_href": "/pulp/api/v3/repositories/python/python/0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20/versions/",
      "pulp_labels": {},
      "latest_version_href": "/pulp/api/v3/repositories/python/python/0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20/versions/0/",
      "name": "foo",
      "description": null,
      "retain_repo_versions": null,
      "remote": null,
      "autopublish": false
    }
    ```

## Upload a file to Pulp

Each artifact in Pulp represents a file. They can be created during sync or created manually by uploading a file.

=== "Run"

    ```bash
    # Get a Python package or choose your own
    curl -O https://fixtures.pulpproject.org/python-pypi/packages/shelf-reader-0.1.tar.gz
    PKG="shelf-reader-0.1.tar.gz"
    
    # Upload it to Pulp
    pulp python content upload --relative-path "$PKG" --file "$PKG"
    ```

=== "Output"

    ```
    {
      "pulp_href": "/pulp/api/v3/content/python/packages/0196ba2d-6453-75f9-949c-55b3cd435909/",
      "prn": "prn:python.pythonpackagecontent:0196ba2d-6453-75f9-949c-55b3cd435909",
      "pulp_created": "2025-05-10T12:30:59.157306Z",
      "pulp_last_updated": "2025-05-10T12:30:59.157328Z",
      "pulp_labels": {},
      "artifact": "/pulp/api/v3/artifacts/0196ba2d-637f-7fd4-bce7-7e557ad82bc9/",
      "filename": "shelf-reader-0.1.tar.gz",
      "packagetype": "sdist",
      "name": "shelf-reader",
      "version": "0.1",
      "sha256": "04cfd8bb4f843e35d51bfdef2035109bdea831b55a57c3e6a154d14be116398c",
      "metadata_version": "1.1",
      "summary": "Make sure your collections are in call number order.",
      "description": "too long to read",
      "description_content_type": "",
      "keywords": "",
      "home_page": "https://github.com/asmacdo/shelf-reader",
      "download_url": "",
      "author": "Austin Macdonald",
      "author_email": "asmacdo@gmail.com",
      "maintainer": "",
      "maintainer_email": "",
      "license": "GNU GENERAL PUBLIC LICENSE Version 2, June 1991",
      "requires_python": "",
      "project_url": "",
      "project_urls": "{}",
      "platform": "",
      "supported_platform": "",
      "requires_dist": "[]",
      "provides_dist": "[]",
      "obsoletes_dist": "[]",
      "requires_external": "[]",
      "classifiers": "[]"
    }
    ```

## Add content to a repository

Once there is a content unit, it can be added to a repository using the `add` command.
This command requires both the `filename` and `sha256` to ensure that a specific file can be identified,
as Pulp may contain different content units with the same name.

=== "Run"

    ```bash
    # Matches shelf-reader-0.1.tar.gz
    SHA256="04cfd8bb4f843e35d51bfdef2035109bdea831b55a57c3e6a154d14be116398c"

    # Add the created PythonPackage content to the repository
    pulp python repository content add --repository foo --filename "$PKG" --sha256 "$SHA256"
    
    # After the task is complete, it gives us a new repository version
    pulp python repository version show --repository foo
    ```

=== "Output"

    ```
    {
      "pulp_href": "/pulp/api/v3/repositories/python/python/0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20/versions/1/",
      "prn": "prn:core.repositoryversion:0196ba2d-b1bc-7ac2-ac2a-dc8300104a8c",
      "pulp_created": "2025-05-10T12:31:18.972944Z",
      "pulp_last_updated": "2025-05-10T12:31:19.051457Z",
      "number": 1,
      "repository": "/pulp/api/v3/repositories/python/python/0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20/",
      "base_version": "/pulp/api/v3/repositories/python/python/0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20/versions/0/",
      "content_summary": {
        "added": {
          "python.python": {
            "count": 1,
            "href": "/pulp/api/v3/content/python/packages/?repository_version_added=/pulp/api/v3/repositories/python/python/0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20/versions/1/"
          }
        },
        "removed": {},
        "present": {
          "python.python": {
            "count": 1,
            "href": "/pulp/api/v3/content/python/packages/?repository_version=/pulp/api/v3/repositories/python/python/0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20/versions/1/"
          }
        }
      }
    }
    ```

## Remove content from a repository

A content unit can be removed from a repository using the `remove` command.
This command requires the same options as the `add` command.

=== "Run"

    ```bash
    # Remove the PythonPackage content from the repository
    pulp python repository content remove --repository foo --filename "$PKG" --sha256 "$SHA256"
    
    # After the task is complete, it gives us a new repository version
    pulp python repository version show --repository foo
    ```

=== "Output"

    ```
    {
      "pulp_href": "/pulp/api/v3/repositories/python/python/0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20/versions/2/",
      "prn": "prn:core.repositoryversion:01987e28-c79b-7033-9d5b-8a07cddcc24c",
      "pulp_created": "2025-08-06T06:54:18.526088Z",
      "pulp_last_updated": "2025-08-06T06:54:18.565594Z",
      "number": 2,
      "repository": "/pulp/api/v3/repositories/python/python/0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20/",
      "base_version": "/pulp/api/v3/repositories/python/python/0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20/versions/1/",
      "content_summary": {
        "added": {},
        "removed": {
          "python.python": {
            "count": 1,
            "href": "/pulp/api/v3/content/python/packages/?repository_version_removed=/pulp/api/v3/repositories/python/python/0196ba2d-0374-77ef-a4e0-1b5ba5b1ed20/versions/2/"
          }
        },
        "present": {}
      }
    }
    ```
