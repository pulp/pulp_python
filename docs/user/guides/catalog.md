# Browse the package catalog

The package catalog returns one row per normalized package name. Use the
repository URL to read its latest complete repository version, or a repository
version URL to read a specific complete version. `${REPO_PK}` is the repository UUID.

## List packages

```bash
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/packages/?limit=10"
```

To read a specific repository version, set `${VERSION_NUMBER}` to its number:

```bash
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/versions/${VERSION_NUMBER}/packages/?limit=10"
```

`count` is the number of distinct packages, not files. `summary`, `description`,
`author`, `author_email`, and `license` come from the highest package version in
PEP 440 order. Metadata comes from an sdist of that version when available.
Otherwise, it comes from that version's newest file.

`versions` has one entry per stored version string, in descending PEP 440 order.
A wheel and an sdist of the same version share one entry. Different version
strings, such as `1.0.0` and `1.0.0+test.1`, produce separate entries.

Each version's `last_updated` is the latest `pulp_created` timestamp among its
files in the selected repository version. This records when Pulp created the
content, not the upstream release date.

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
        {"version": "0.1", "last_updated": "2026-11-11T12:00:00Z"}
      ]
    }
  ]
}
```

Results are ordered by `name_normalized`. Use `limit` and `offset` to page
through the catalog. Use a repository version URL to keep every page on the
same repository version. Missing or incomplete repository versions return HTTP 404.

Filter names with `name_normalized`, `name_normalized__icontains`, or
`name_normalized__istartswith`. Use `ordering=-name_normalized` to list names
in descending order.
