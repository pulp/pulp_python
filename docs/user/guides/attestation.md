# Attestation Hosting (PEP 740)

Pulp Python has support for uploading attestations as originally specified in [PEP 740](https://peps.python.org/pep-0740/).
Attestations are stored in Pulp as Provenance Content that can be added/synced/removed from python
repositories. The provenance objects will be available through the Simple API and served by the 
[Integrity API matching PyPI's implementation](https://docs.pypi.org/api/integrity/).

## Uploading Attestations

Attestations can be uploaded to Pulp with its package as a JSON list under the field `attestations`.

```bash
pulp python content create \
  --relative-path twine-6.2.0.tar.gz \
  --file twine-6.2.0.tar.gz \
  --repository $REPO_PRN \
  --attestation @twine-6.2.0.tar.gz.publish.attestation
# --attestation can be specified multiple times to attach many attestations with a package
```

The uploaded attestations can be found in the created Provenance object attached to the content in
the task report. 

```json
// Task output abbreviated
{
    "pulp_href": "/pulp/api/v3/tasks/019af033-c8e8-7a02-a583-0fac5e39e54b/",
    "state": "completed",
    "name": "pulpcore.app.tasks.base.general_create",
    "created_resources": [
        "/pulp/api/v3/content/python/provenance/019aeb59-34bb-7ae4-ab95-4f8a62199be9/",
        "/pulp/api/v3/content/python/packages/019aeb59-34b1-7c73-a746-aea2cc3fbd85/"
    ],
    "result": {
        "prn": "prn:python.pythonpackagecontent:019aeb59-34b1-7c73-a746-aea2cc3fbd85",
        "name": "twine",
        "sha256": "418ebf08ccda9a8caaebe414433b0ba5e25eb5e4a927667122fbe8f829f985d8",,
        "version": "6.2.0",
        "artifact": "/pulp/api/v3/artifacts/019aeb59-33c3-7877-9787-22c34eb6c15b/",
        "filename": "twine-6.2.0.tar.gz",
        "pulp_href": "/pulp/api/v3/content/python/packages/019aeb59-34b1-7c73-a746-aea2cc3fbd85/",
        // PRN of newly created Provenance object
        "provenance": "prn:python.packageprovenance:019aeb59-34bb-7ae4-ab95-4f8a62199be9",
    }
}
```

You can also use twine to upload your packages. Twine will find the attestations in files ending with
`.attestation` and attach them to the same filename during the upload. Pulp will then add the new 
package and provenance object to the backing repository of the distribution.

```bash
pulp python distribution create --name foo --base-path foo --repository foo
pypi-attestations sign dist/twine-6.2.0.tar.gz dist/twine-6.2.0-py3-none-any.whl
twine upload --repository-url $PULP_API/pypi/foo/simple/ --attestations dist/*
```

## Interacting with Provenance Content

Provenance content can be directly uploaded to Pulp through its content endpoint.

```bash
pulp python content -t provenance create \
  --file twine.provenance \
  --package $TWINE_PRN \
  --repository $REPO_PRN
# you can also specify a package through its sha256
```

Provenance objects are artifactless content, their data is stored in a json field and are unique by
their sha256 digest. In a repository a provenance object is unique by their associated package, i.e
a package can only have one provenance in the repository at a time. Provenance objects can't be 
modified after upload as content is immutable, but a new one can be uploaded to replace the existing
one. Since provenance objects are content they can be added, removed, and synced into repositories.
To sync provenance objects from an upstream repository set the `provenance` field on the remote.

```bash
pulp python remote update --name foo --provenance
pulp python repository sync --repository foo --remote foo
```

## Downloading Provenance objects

A package's provenance objects are exposed through its Simple page and downloaded from the Integrity
API. The attestations can then be verified using tools like `sigstore` or `pypi-attestations`.

```bash
http $PULP_API/pypi/foo/simple/twine/ "Accept:application/vnd.pypi.simple.v1+json" | jq -r ".files[].provenance"

http $PULP_API/pypi/foo/integrity/twine/6.2.0/twine-6.2.0.tar.gz/
```
