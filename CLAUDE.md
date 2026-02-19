# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

`pulp_python` is a Pulp plugin that enables self-hosted, PyPI-compatible Python package repositories. It is a Django application that integrates with [pulpcore](https://github.com/pulp/pulpcore) via the Pulp plugin API. Key capabilities: sync from PyPI, upload packages, serve via pip, pull-through caching, versioned repos, PEP 740 attestations.

## Development Commands

### Linting
```bash
# Code formatting check
black --check --diff .

# Style/docstring linting
flake8

# Run both via CI scripts
.ci/scripts/extra_linting.sh
.ci/scripts/check_pulpcore_imports.sh
```

**Style rules** (`.flake8`): max line length 100, black-compatible, docstrings required on public methods (with several D-codes ignored — see `.flake8`).

### Testing

Tests require a running Pulp instance. Functional tests use pytest fixtures from `pulp_python/pytest_plugin.py` and connect to a live API.

```bash
# Run all tests
pytest pulp_python/tests/

# Run only unit tests (no Pulp instance needed)
pytest pulp_python/tests/unit/

# Run a single functional test file
pytest pulp_python/tests/functional/api/test_sync.py

# Run a single test by name
pytest pulp_python/tests/functional/api/test_sync.py::test_name
```

### Building
```bash
# Build the Python distribution wheel
python -m build

# Install in development mode
pip install -e .
```

### Changelog Entries

New changelog fragments go in `CHANGES/` using towncrier format. See `pyproject.toml` `[tool.towncrier]` for configuration.

## Architecture

### Plugin Structure

This follows the standard Pulp plugin pattern. The plugin registers itself via the entry point `pulpcore.plugin` → `pulp_python.app.PulpPythonPluginAppConfig`.

All application code lives in `pulp_python/app/`:

| File/Dir | Purpose |
|---|---|
| `models.py` | Django models for all content types and repository objects |
| `serializers.py` | DRF serializers with validation and metadata extraction |
| `viewsets.py` | DRF viewsets implementing the REST API |
| `urls.py` | URL routing — PyPI API endpoints |
| `utils.py` | Metadata extraction, PyPI template rendering, canonicalization |
| `provenance.py` | PEP 740 attestation/provenance validation logic |
| `tasks/` | Celery async tasks (sync, publish, upload, repair, vulnerability) |
| `pypi/` | PyPI-specific views (Simple API, Legacy upload, Metadata, Provenance) |
| `settings.py` | Django settings additions |
| `migrations/` | Database migrations |

### Core Models

- **`PythonPackageContent`** — the main content type; stores all Python package metadata (PEP 440/core-metadata fields) plus release info (filename, sha256, size). Unique per `(sha256, _pulp_domain)`.
- **`PackageProvenance`** — PEP 740 provenance objects linked to a `PythonPackageContent`.
- **`PythonRepository`** — Repository; supports `autopublish`, `PULL_THROUGH_SUPPORTED = True`. Calls `tasks.publish()` on new versions if `autopublish` is set.
- **`PythonRemote`** — Remote with package filtering (`includes`, `excludes`, `package_types`, `keep_latest_packages`, `exclude_platforms`, `prereleases`, `provenance`).
- **`PythonPublication`** — Publication for generated PyPI Simple API index files.
- **`PythonDistribution`** — Distribution serving content via `content_handler()` which generates JSON API responses and handles Simple API serving from remote storage.
- **`NormalizeName`** — A custom Django `Transform` that normalizes package names per PEP 426 (regex replace `., _, -` → `-`, lowercased). Used as `name__normalize=value` in queries.

### PyPI API Endpoints (`urls.py`)

```
pypi/<domain>/<path>/legacy/          → UploadView (twine/pip upload)
pypi/<domain>/<path>/integrity/...    → ProvenanceView (PEP 740)
pypi/<domain>/<path>/pypi/<meta>/     → MetadataView (JSON API)
pypi/<domain>/<path>/simple/...       → SimpleView (pip simple index)
```

### Async Tasks (`tasks/`)

- **`sync.py`** — Syncs packages from a remote (PyPI or compatible). Uses `bandersnatch` and `pypi-simple`.
- **`publish.py`** — Creates a `PythonPublication` with Simple API index files.
- **`upload.py`** — Handles package uploads (`upload` for single, `upload_group` for multi-upload).
- **`repair.py`** — Re-downloads missing artifacts.
- **`vulnerability_report.py`** — Fetches vulnerability data for repository content.

### Test Fixtures (`pytest_plugin.py`)

The pytest plugin defines session-scoped and function-scoped fixtures for all major objects: `python_repo_factory`, `python_remote_factory`, `python_distribution_factory`, `python_publication_factory`, `python_content_factory`, `python_repo_with_sync`. Functional tests depend on a running Pulp instance configured via environment.

### Key Conventions

- The plugin is domain-compatible (`domain_compatible = True`). All content models have a `_pulp_domain` FK.
- Package name lookups always use the `NormalizeName` transform: `name__normalize=canonicalize_name(name)`.
- Content deduplication is enforced in `PythonRepository.finalize_new_version()` via pulpcore's `remove_duplicates()`.
- Access policies use `AutoAddObjPermsMixin` and role-based permissions defined in each model's `Meta.permissions`.
- Changelog entries use towncrier; fragment files belong in `CHANGES/`.
