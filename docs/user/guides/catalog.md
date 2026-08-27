# Browse the package catalog

Pulp CLI commands for these endpoints are generated from the OpenAPI spec in a separate package; until that is updated, use HTTP.

The content list (`/pulp/api/v3/content/python/packages/`) returns **one row per distribution file** (wheel, sdist, …). For catalog UIs and automation that need **one row per package name**, plus repository metrics, use the repository package index.

These endpoints default to the **latest complete repository version**. `{pulp_id}` is the repository UUID. Pass `repository_version` (HREF or PRN) to read a specific version of that repository.

## List packages

```bash
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/packages/?limit=10"
```

Pagination `count` is the number of **distinct packages** (`name_normalized`), not files.

Each row includes both a simple version list and per-version metadata:

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

`set(versions)` is always the same as `set(latest_releases[].version)`. Both lists are newest-first using PEP 440 version order (`1.10` before `1.9` before `1.2`). There is one `latest_releases` entry per **logical version** (after stripping a trailing rebuild suffix `\.[a-zA-Z]+-[^.]+$`), not per wheel or sdist. A rebuild is the last dot-segment that is letters, a dash, then the rest of that segment (for example `5.3.17.rhlw-00001-n0001` → `5.3.17`). Public and predisclosure files of the same `name_normalized` and logical version collapse to that one row.

`version` is that base. `release` is the stripped suffix without the leading dot (`rhlw-00001` or `rhlw-00001-n0001`) of the newest unit (`pulp_created`) in that group, otherwise empty.

`created_at` is when that logical version entered the repository: `RepositoryContent.pulp_created` of the selected newest rebuild, falling back to the content unit's `pulp_created`.

`last_updated` is when the **package** was last updated in this repository version: the latest `RepositoryContent.pulp_created` among **all** Python package units for that `name_normalized` (any rebuild), falling back to the content unit's `pulp_created`. A rebuild of an older version uploaded yesterday updates `last_updated` even if a newer version number already exists.

### Ordering

Default order is `name`. Pass `ordering` to change it:

```bash
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/packages/" \
  ordering==name
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/packages/" \
  ordering==-last_updated
```

Allowed fields: `name`, `name_normalized`, `last_updated`. Prefix with `-` for descending. `last_updated` uses `name` then `name_normalized` as a stable pagination tiebreaker. Unknown fields return 400.

### Name search

```bash
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/packages/" \
  name_normalized__istartswith==shelf
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/packages/" \
  name_normalized__icontains==http
```

`name_normalized__istartswith` and `name_normalized__icontains` are case-insensitive: the value is lowercased and matched with `LIKE` against already-canonical `name_normalized`. Each requires **at least 3 characters** (shorter values return 400). `name__istartswith` is still `ILIKE` on the original package name and has no minimum length. Name search belongs on this index, not on the flat content list.

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

Counts use Python package content units in that repository version (not filtered by `packagetype`):

| Field | Identity |
|-------|----------|
| `package_count` | distinct `name_normalized` |
| `version_count` | distinct `(name_normalized, base_version)` after rebuild-suffix strip |
| `build_count` | distinct `(name_normalized, full version)` |

Until rebuild suffixes exist, `version_count` equals `build_count`.

## List versions of a package

Use the existing content API. Pass `packagetype=sdist` for one representative file per PEP version (retry with `packagetype=bdist_wheel` if a release is wheel-only).

`collapse_builds=true` keeps one unit per logical version (`name_normalized` + `base_version`), the one with the latest `pulp_created`. Do not nest rebuilds on this list. Clients can drain Pulp `next` if the page is full.

```bash
http GET "${BASE_ADDR}/pulp/api/v3/content/python/packages/" \
  name==shelf-reader \
  packagetype==sdist \
  collapse_builds==true \
  repository_version=="${LATEST_VERSION_HREF}"
```

Every content row includes `base_version` (stripped version; equal to `version` when there is no suffix).

## Get one version

Omit `collapse_builds`. Filter with `name`, `version`, and `packagetype=sdist`:

```bash
http GET "${BASE_ADDR}/pulp/api/v3/content/python/packages/" \
  name==shelf-reader \
  version==0.1 \
  packagetype==sdist
```
