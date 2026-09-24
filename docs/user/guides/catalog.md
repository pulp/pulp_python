# Browse the package catalog

The content API lists **one row per file** (wheel, sdist, and so on). Use the repository
package catalog when you want **one row per package name**, for example in a UI that
shows Django once with its versions underneath.

Both catalog endpoints default to the repository's latest complete version. Pass
`repository_version` (HREF or PRN) to read an older snapshot. `{pulp_id}` is the
repository UUID.

## List packages

```bash
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/packages/?limit=10"
```

`count` is the number of distinct packages, not files. Each row looks like:

```json
{
  "name": "shelf-reader",
  "name_normalized": "shelf-reader",
  "last_updated": "2026-08-10T10:45:08.099362Z",
  "versions": ["0.1"],
  "latest_releases": [
    {
      "version": "0.1",
      "release": "",
      "created_at": "2026-08-10T10:45:08.099362Z"
    }
  ]
}
```

- `versions` is the list of version numbers, newest first (PEP 440, so `1.10` before `1.9`).
- `latest_releases` is the same versions with extra metadata. `release` is filled when
  that version has a rebuild (for example `5.3.17+test.1` is shown as version
  `5.3.17` with `release` `test.1`); otherwise it is empty.
- `created_at` is when that version was added to the repository.
- `last_updated` is when **any** file for the package last changed in this repository
  version, including a rebuild of an older version.

### Ordering

Default order is `name`. Allowed fields: `name`, `name_normalized`, `last_updated`.
Prefix with `-` for descending.

```bash
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/packages/" \
  ordering==-last_updated
```

### Name search

```bash
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/packages/" \
  name_normalized__istartswith==shelf
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/packages/" \
  name_normalized__icontains==http
```

`name_normalized__istartswith` and `name_normalized__icontains` match the PEP 503
normalized name and require at least 3 characters. `name__istartswith` matches the
original project name and has no minimum length.

## Repository metrics

```bash
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/metrics/"
```

```json
{
  "package_count": 3,
  "version_count": 9,
  "build_count": 9
}
```

| Field | Meaning |
|-------|---------|
| `package_count` | Distinct packages |
| `version_count` | Distinct packages × versions (rebuilds of the same version count as one) |
| `build_count` | Distinct packages × stored version strings (each rebuild counted) |

Until a repository contains rebuilds, `version_count` equals `build_count`.

## List files for a package

Use the content API. `packagetype=sdist` returns one sdist per version (retry with
`packagetype=bdist_wheel` if a release is wheel-only). `collapse_builds=true` keeps
the newest rebuild per version so you do not have to page through every rebuild.

```bash
http GET "${BASE_ADDR}/pulp/api/v3/content/python/packages/" \
  name==shelf-reader \
  packagetype==sdist \
  collapse_builds==true \
  repository_version=="${LATEST_VERSION_HREF}"
```

Each content row includes `base_version`: the version without a PEP 440 local
version (equal to `version` when there is none).

To fetch a single version, omit `collapse_builds` and filter by `name`, `version`,
and `packagetype`:

```bash
http GET "${BASE_ADDR}/pulp/api/v3/content/python/packages/" \
  name==shelf-reader \
  version==0.1 \
  packagetype==sdist
```
