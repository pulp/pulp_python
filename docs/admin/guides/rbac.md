# Role Base Access Control in Pulp Python

Role based access control in Pulp Python is configured using access policies for the following `viewset_names`:

* `content/python/packages`
* `distributions/python/pypi`
* `publications/python/pypi`
* `remotes/python/python`
* `repositories/python/python`
* `repositories/python/python/versions`
* `pypi/root`
* `pypi/simple`
* `pypi/pypi`
* `pypi/legacy`

This document will focus on describing the default access policies for the PyPI specific APIs and how they may be
customized. The access policies for the Pulp APIs follow the same scheme as the Pulp File plugin which can be read 
about here: [Pulp File RBAC](site:pulp_file/docs/admin/guides/rbac/). Use the Pulp 
CLI to follow along with the examples here.

!!! note 
    This feature is currently in tech preview and is subject to change in future releases.

## Default Index Behavior

By default, the read APIs of the index are accessible to any user, authenticated or not, while the upload APIs 
require permission to modify the backing repository. 

```json
"statements": [
    {
        "action": ["list", "retrieve"],
        "principal": "*",
        "effect": "allow",
    },
    {
        "action": ["create"],
        "principal": "authenticated",
        "effect": "allow",
        "condition": "index_has_repo_perm:python.modify_pythonrepository",
    },
],
```

The `root` and `pypi` endpoints are solely read APIs while the `legacy` endpoint is solely an upload API. The 
`simple` endpoint is both a read and upload API and thus has two actions in its access policy. The defaults on 
these endpoints match the default behavior found on public repositories like PyPI and ensure the maximum compatibility 
with Python tooling.

Also by default, the download links for the Python packages in the index are accessible by anyone. If you wish to 
protect who can download Python content then do so by adding a content guard to your distribution.

```bash
pulp python distribution update --name foo --content-guard $CONTENT_GUARD_HREF_OR_NAME
```

Example pulp-cli workflow to add RBAC-based access to download from the index:

```bash
pulp content-guard rbac create --name foo-guard
pulp content-guard rbac assign --name foo-guard --user user1 --user user2 --group group1 --group group2
CG_HREF=$(pulp content-guard rbac list --name foo-guard | jq -r ".[0].pulp_href")
pulp python distribution update --name foo --content-guard $CG_HREF
```

Links for using basic auth with various python package tools to pass the 
new RBACContentGuard:
- [pip](https://pip.pypa.io/en/stable/topics/authentication/)
- [poetry](https://python-poetry.org/docs/repositories/#private-repository-example)
- [pipenv](https://pipenv.pypa.io/en/latest/credentials.html)
- [pdm](https://pdm-project.org/en/latest/usage/config/#store-credentials-with-the-index)

!!! warning
    The PyPI access policies do not support `creation_hooks` or `queryset_scoping`.

## Index Specific Access Conditions

Pulp Python comes with two specific access condition methods that can be used in the PyPI access policies.

### `index_has_repo_perm`

This access condition checks if the user has the supplied permission on the index's backing repository. If the index
has no repository this will return `True`. If no permission is specified for the method then it will use 
`python.view_pythonrepository` as its default. This is the default condition that is used for the upload APIs with
the modify python repository permission.

### `index_has_perm`

This access condition checks if the user has the supplied permission on the index (distribution) itself. If no 
permission is specified for the method then it will use `python.view_pythondistribution` as its default.

!!! note 
    Both access condition methods are compatible with the Pulp Domains feature.