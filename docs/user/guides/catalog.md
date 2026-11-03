# Browse the package catalog

The package list returns **one row per package name**. It defaults to the
repository's latest complete version. Pass `repository_version` (HREF or PRN)
to read an older snapshot. `{pulp_id}` is the repository UUID.

## List packages

```bash
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/packages/?limit=10"
```

`count` is the number of distinct packages, not files. Each row is one package
name. `summary`, `description`, `author`, `author_email`, and `license` come
from the newest version. `versions` has one entry per stored version string,
newest first, with that version's `license_expression`. A wheel and an sdist
of the same version are one entry. A rebuild such as `1.0.0+test.1` stays its
own entry because the stored version differs.

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "name": "shelf-reader",
      "name_normalized": "shelf-reader",
      "summary": "A small example package",
      "description": "",
      "author": "",
      "author_email": "",
      "license": "",
      "versions": [
        {"version": "0.1", "license_expression": ""}
      ]
    }
  ]
}
```

Results are ordered by `name_normalized`. Within a package, versions are newest
first. Page with `limit` and `offset` to read the whole catalog. Pass
`repository_version` when the export must stay on one snapshot.
