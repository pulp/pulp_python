Upload and Manage Content
=========================

Create a repository
-------------------

If you don't already have a repository, create one::

    $ http POST $BASE_ADDR/pulp/api/v3/repositories/ name=foo

Response::

    {
        "_href": "http://localhost:8000/pulp/api/v3/repositories/e81221c3-9c7a-4681-a435-aa74020753f2/",
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
        "_href": "http://localhost:8000/pulp/api/v3/artifacts/7d39e3f6-535a-4b6e-81e9-c83aa56aa19e/",
        ...
    }


Create content from an artifact
-------------------------------

Now that Pulp has the wheel, its time to make it into a unit of content. The python plugin will
inspect the file and populate its metadata::

    $ http POST $BASE_ADDR/pulp/api/v3/content/python/packages/ artifact=$ARTIFACT_HREF filename=shelf_reader-0.1-py2-none-any.whl

Response::

    {
        "_href": "http://localhost:8000/pulp/api/v3/content/python/packages/a9578a5f-c59f-4920-9497-8d1699c112ff/",
        "artifact": "http://localhost:8000/pulp/api/v3/artifacts/7d39e3f6-535a-4b6e-81e9-c83aa56aa19e/",
        "digest": "b5bb9d8014a0f9b1d61e21e796d78dccdf1352f23cd32812f4850b878ae4944c",
        "filename": "shelf_reader-0.1-py2-none-any.whl",
        "type": "python"
    }

Create a variable for convenience::

    $ export CONTENT_HREF=$(http $BASE_ADDR/pulp/api/v3/content/python/packages/ | jq -r '.results[] | select(.filename == "shelf_reader-0.1-py2-none-any.whl") | ._href')

Add content to a repository
---------------------------

Once there is a content unit, it can be added and removed and from to repositories::

$ http POST $REPO_HREF'versions/' add_content_units:="[\"$CONTENT_HREF\"]"
