# Browse the package catalog

The content list (`/pulp/api/v3/content/python/packages/`) returns **one row per distribution file** (wheel, sdist, …). For catalog UIs and automation that need **one row per package name**, plus repository metrics, use the repository package index.

These endpoints read the **latest complete repository version**. `{pulp_id}` is the repository UUID, not a repository version.

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

`set(versions)` is always the same as `set(latest_releases[].version)`. There is one `latest_releases` entry per **logical version** (after stripping a trailing rebuild suffix `\.[a-zA-Z]+-\d+$`), not per wheel or sdist.

`created_at` is when that logical version entered the repository: the earliest `RepositoryContent.pulp_created` among its files, falling back to the content unit's `pulp_created`. `release` is empty until Python rebuilds are stored.

### Prefix search

```bash
http GET "${BASE_ADDR}/pulp/api/v3/repositories/python/python/${REPO_PK}/packages/" \
  name_normalized__istartswith==shelf
```

`name_normalized__istartswith` and `name__istartswith` are case-insensitive (`ILIKE`). Prefix search belongs on this index, not on the flat content list.

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

Counts use Python package content units in the latest repository version (not filtered by `packagetype`):

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
  name_normalized==shelf-reader \
  packagetype==sdist \
  collapse_builds==true \
  repository_version=="${LATEST_VERSION_HREF}"
```

Every content row includes `base_version` (stripped version; equal to `version` when there is no suffix).

## Get one version

Omit `collapse_builds`. Filter with `name` / `name_normalized`, `version`, and `packagetype=sdist`:

```bash
http GET "${BASE_ADDR}/pulp/api/v3/content/python/packages/" \
  name_normalized==shelf-reader \
  version==0.1 \
  packagetype==sdist
```
