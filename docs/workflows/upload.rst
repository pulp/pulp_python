Upload and Manage Content
=========================

Create a repository
-------------------

If you don't already have a repository, create one::

    $ http POST $BASE_ADDR/pulp/api/v3/repositories/ name=foo

Response::

    {
        "_href": "/pulp/api/v3/repositories/1/",
        ...
    }

Create a variable for convenience::

    $ export REPO_HREF=$(http $BASE_ADDR/pulp/api/v3/repositories/ | jq -r '.results[] | select(.name == "foo") | ._href')


Upload a file to Pulp
---------------------

Each artifact in Pulp represents a file. They can be created during sync or created manually by uploading a file::

    $ export ARTIFACT_HREF=$(http --form POST $BASE_ADDR/pulp/api/v3/artifacts/ file@./shelf_reader-0.1-py2-none-any.whl | jq -r '._href')

Response::

    {
        "_href": "/pulp/api/v3/artifacts/1/",
        ...
    }


Create content from an artifact
-------------------------------

Now that Pulp has the wheel, its time to make it into a unit of content. The python plugin will
inspect the file and populate its metadata::

    $ http POST $BASE_ADDR/pulp/api/v3/content/python/packages/ _artifact=$ARTIFACT_HREF filename=shelf_reader-0.1-py2-none-any.whl

Response::

    {
        "_href": "/pulp/api/v3/content/python/packages/1/",
        "_artifact": "/pulp/api/v3/artifacts/1/",
        "digest": "b5bb9d8014a0f9b1d61e21e796d78dccdf1352f23cd32812f4850b878ae4944c",
        "filename": "shelf_reader-0.1-py2-none-any.whl",
        "type": "python"
    }

Create a variable for convenience::

    $ export CONTENT_HREF=$(http $BASE_ADDR/pulp/api/v3/content/python/packages/ | jq -r '.results[] | select(.filename == "shelf_reader-0.1-py2-none-any.whl") | ._href')

Add content to a repository
---------------------------

Once there is a content unit, it can be added and removed and from to repositories::

$ http POST $BASE_ADDR$REPO_HREF'versions/' add_content_units:="[\"$CONTENT_HREF\"]"
