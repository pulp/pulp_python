"""Catalog API tests."""

import io
import tarfile
import uuid
from datetime import datetime
from urllib.parse import urljoin

import pytest
import requests

from pulp_python.tests.functional.constants import PYTHON_SM_PROJECT_SPECIFIER


def _api_get(bindings_cfg, path, **params):
    url = urljoin(bindings_cfg.host + "/", path.lstrip("/"))
    response = requests.get(url, params=params, auth=(bindings_cfg.username, bindings_cfg.password))
    assert response.status_code == 200, response.text
    return response.json()


_PACKAGE_FIELDS = {
    "name",
    "name_normalized",
    "summary",
    "description",
    "author",
    "author_email",
    "license",
    "versions",
}


def _assert_package_row(pkg):
    assert set(pkg) == _PACKAGE_FIELDS
    assert pkg["name"]
    assert pkg["name_normalized"]
    versions = [item["version"] for item in pkg["versions"]]
    assert versions
    assert len(versions) == len(set(versions))
    for item in pkg["versions"]:
        assert set(item) == {"version", "last_updated"}
        assert item["version"]
        assert datetime.fromisoformat(item["last_updated"]).tzinfo is not None


def _write_sdist(directory, name, version):
    """Write a minimal sdist whose PKG-INFO Name/Version pkginfo can read."""
    pkg_dir = f"{name}-{version}"
    filename = f"{pkg_dir}.tar.gz"
    path = directory / filename
    pkg_info = (
        f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n\n{name} {version} description\n"
    ).encode()
    with tarfile.open(path, "w:gz") as tar:
        info = tarfile.TarInfo(name=f"{pkg_dir}/PKG-INFO")
        info.size = len(pkg_info)
        tar.addfile(info, io.BytesIO(pkg_info))
    return filename, str(path)


def _add_sdist(python_content_factory, python_bindings, tmp_path, repo, name, version):
    filename, path = _write_sdist(tmp_path, name, version)
    python_content_factory(relative_path=filename, file=path, repository=repo)
    return python_bindings.RepositoriesPythonApi.read(repo.pulp_href)


@pytest.fixture
def sm_repo(python_repo_with_sync, python_remote_factory):
    remote = python_remote_factory(includes=PYTHON_SM_PROJECT_SPECIFIER)
    return python_repo_with_sync(remote)


@pytest.fixture(params=[False, True], ids=["repository", "version"])
def catalog_path(request):
    def path(repo):
        resource = repo.latest_version_href if request.param else repo.pulp_href
        return f"{resource}packages/"

    return path


def test_package_list_schema(pulp_openapi_schema_pk_path_set):
    """Both actions document package filters and paginated package responses."""
    schema = pulp_openapi_schema_pk_path_set
    operations = [
        methods["get"]
        for path, methods in schema["paths"].items()
        if "/repositories/python/python/" in path and path.endswith("/packages/")
    ]
    assert len(operations) == 2
    for operation in operations:
        query_params = {item["name"] for item in operation["parameters"] if item["in"] == "query"}
        assert {
            "name_normalized",
            "name_normalized__istartswith",
            "ordering",
            "limit",
            "offset",
        } <= query_params
        assert "repository_version" not in query_params
        response = operation["responses"]["200"]["content"]["application/json"]["schema"]
        component = response["$ref"].rsplit("/", 1)[-1]
        assert "results" in schema["components"]["schemas"][component]["properties"]


@pytest.mark.parallel
def test_package_list_grouping_and_pagination(bindings_cfg, sm_repo, catalog_path):
    """Package index is one row per name, and count is distinct packages not files."""
    path = catalog_path(sm_repo)
    data = _api_get(bindings_cfg, path, limit=1)
    assert data["count"] == 3
    assert len(data["results"]) == 1
    _assert_package_row(data["results"][0])

    page2 = _api_get(bindings_cfg, path, limit=1, offset=1)
    assert page2["count"] == 3
    assert page2["results"][0]["name_normalized"] != data["results"][0]["name_normalized"]

    all_rows = _api_get(bindings_cfg, path, limit=100)["results"]
    names = [pkg["name_normalized"] for pkg in all_rows]
    assert names == sorted(names)
    assert set(names) == {"aiohttp", "celery", "django"}
    django = next(pkg for pkg in all_rows if pkg["name_normalized"] == "django")
    assert {item["version"] for item in django["versions"]} >= {
        "1.10.4",
        "1.10.3",
        "1.10.2",
        "1.10.1",
    }
    assert all("+" not in item["version"] for item in django["versions"])


@pytest.mark.parallel
def test_package_list_empty_repository(python_bindings, python_repo_factory):
    repo = python_repo_factory()
    for api, href in (
        (python_bindings.RepositoriesPythonApi, repo.pulp_href),
        (python_bindings.RepositoriesPythonVersionsApi, repo.latest_version_href),
    ):
        data = api.packages(href)
        assert data.count == 0
        assert data.results == []


@pytest.mark.parallel
def test_packages_repository_version(bindings_cfg, sm_repo, python_repo_factory):
    """Version URLs select snapshots independently of the repository's latest version."""
    latest_href = sm_repo.latest_version_href
    v0_href = f"{sm_repo.pulp_href}versions/0/"

    default_pkgs = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/")
    explicit_pkgs = _api_get(bindings_cfg, f"{latest_href}packages/")
    assert default_pkgs == explicit_pkgs

    v0_pkgs = _api_get(bindings_cfg, f"{v0_href}packages/")
    assert v0_pkgs["count"] == 0
    assert v0_pkgs["results"] == []

    other = python_repo_factory()
    other_pkgs = _api_get(bindings_cfg, f"{other.latest_version_href}packages/")
    assert other_pkgs["results"] == []


@pytest.mark.parallel
def test_package_list_one_entry_per_stored_version(
    bindings_cfg, python_bindings, python_repo_with_sync, monitor_task
):
    """Update times include all files in the selected snapshot."""
    repo = python_repo_with_sync()
    files = python_bindings.ContentPackagesApi.list(repository_version=repo.latest_version_href)
    assert files.count == 2
    assert {item.packagetype for item in files.results} == {"sdist", "bdist_wheel"}

    pkgs = _api_get(bindings_cfg, f"{repo.pulp_href}packages/")
    assert pkgs["count"] == 1
    row = pkgs["results"][0]
    _assert_package_row(row)
    assert row["name_normalized"] == "shelf-reader"
    assert [item["version"] for item in row["versions"]] == ["0.1"]
    assert datetime.fromisoformat(row["versions"][0]["last_updated"]) == max(
        item.pulp_created for item in files.results
    )

    latest_file = max(files.results, key=lambda item: item.pulp_created)
    remaining = next(item for item in files.results if item.pulp_href != latest_file.pulp_href)
    monitor_task(
        python_bindings.RepositoriesPythonApi.modify(
            repo.pulp_href, {"remove_content_units": [latest_file.pulp_href]}
        ).task
    )
    current = _api_get(bindings_cfg, f"{repo.pulp_href}packages/")["results"][0]
    assert datetime.fromisoformat(current["versions"][0]["last_updated"]) == remaining.pulp_created
    historical = _api_get(bindings_cfg, f"{repo.latest_version_href}packages/")["results"][0]
    assert historical == row


@pytest.mark.parallel
def test_package_list_version_order(
    bindings_cfg, python_bindings, python_content_factory, python_repo_factory, tmp_path
):
    """Stored versions are newest-first by PEP 440, not lexicographically."""
    repo = python_repo_factory()
    name = f"ordered-{uuid.uuid4().hex[:8]}"
    for version in ("1.10", "1.9", "1.2"):
        repo = _add_sdist(python_content_factory, python_bindings, tmp_path, repo, name, version)
    data = _api_get(bindings_cfg, f"{repo.pulp_href}packages/")
    assert data["count"] == 1
    pkg = data["results"][0]
    _assert_package_row(pkg)
    assert [item["version"] for item in pkg["versions"]] == ["1.10", "1.9", "1.2"]


@pytest.mark.parallel
def test_package_list_version_metadata(
    python_bindings, python_content_factory, python_repo_factory, tmp_path
):
    """Metadata follows version precedence and remains scoped to the selected snapshot."""
    repo = python_repo_factory()
    name = f"metadata-{uuid.uuid4().hex[:8]}"
    repo = _add_sdist(python_content_factory, python_bindings, tmp_path, repo, name, "2.0")
    historical_href = repo.latest_version_href
    repo = _add_sdist(python_content_factory, python_bindings, tmp_path, repo, name, "1.0")
    files = python_bindings.ContentPackagesApi.list(repository_version=repo.latest_version_href)
    updated = {item.version: item.pulp_created for item in files.results}
    latest = python_bindings.RepositoriesPythonApi.packages(repo.pulp_href).results[0]
    assert latest.description.strip() == f"{name} 2.0 description"
    assert [(item.version, item.last_updated) for item in latest.versions] == [
        ("2.0", updated["2.0"]),
        ("1.0", updated["1.0"]),
    ]
    historical = python_bindings.RepositoriesPythonVersionsApi.packages(historical_href).results[0]
    assert [(item.version, item.last_updated) for item in historical.versions] == [
        ("2.0", updated["2.0"]),
    ]


@pytest.mark.parallel
def test_package_list_keeps_stored_versions(
    bindings_cfg, python_bindings, python_content_factory, python_repo_factory, tmp_path
):
    """A rebuild stays its own file, with the version string stored in Pulp."""
    repo = python_repo_factory()
    suffix = uuid.uuid4().hex[:8]
    name = f"pkg-{suffix}"

    repo = _add_sdist(python_content_factory, python_bindings, tmp_path, repo, name, "2.0.0")
    original_version = repo.latest_version_href
    repo = _add_sdist(python_content_factory, python_bindings, tmp_path, repo, name, "1.0.0+test.3")
    row = _api_get(bindings_cfg, f"{repo.pulp_href}packages/")["results"][0]
    _assert_package_row(row)
    assert [item["version"] for item in row["versions"]] == ["2.0.0", "1.0.0+test.3"]
    historical = _api_get(bindings_cfg, f"{original_version}packages/")["results"][0]
    assert [item["version"] for item in historical["versions"]] == ["2.0.0"]


@pytest.mark.parallel
def test_package_list_keeps_rebuild_version_string(
    bindings_cfg, python_bindings, python_content_factory, python_repo_factory, tmp_path
):
    """A rebuild is a separate entry because its stored version string differs."""
    repo = python_repo_factory()
    name = f"rebuild-{uuid.uuid4().hex[:8]}"
    repo = _add_sdist(python_content_factory, python_bindings, tmp_path, repo, name, "5.3.17")
    repo = _add_sdist(
        python_content_factory,
        python_bindings,
        tmp_path,
        repo,
        name,
        "5.3.17+test.1.n1",
    )

    pkgs = _api_get(bindings_cfg, f"{repo.pulp_href}packages/")
    assert pkgs["count"] == 1
    pkg = pkgs["results"][0]
    _assert_package_row(pkg)
    assert {item["version"] for item in pkg["versions"]} == {"5.3.17", "5.3.17+test.1.n1"}


@pytest.mark.parallel
def test_package_list_filters_and_ordering(bindings_cfg, sm_repo, catalog_path):
    """Name filters and ordering apply to packages within the selected snapshot."""
    path = catalog_path(sm_repo)
    for params in (
        {"name_normalized": "django"},
        {"name_normalized__istartswith": "DJAN"},
        {"name_normalized__icontains": "JANG"},
        {"name_normalized__in": "django,absent"},
    ):
        data = _api_get(bindings_cfg, path, **params)
        assert data["count"] == 1
        assert [row["name_normalized"] for row in data["results"]] == ["django"]
    data = _api_get(bindings_cfg, path, ordering="-name_normalized", limit=2)
    assert data["count"] == 3
    assert [row["name_normalized"] for row in data["results"]] == ["django", "celery"]
    data = _api_get(bindings_cfg, path, ordering="-name_normalized", limit=2, offset=2)
    assert [row["name_normalized"] for row in data["results"]] == ["aiohttp"]


@pytest.mark.parallel
def test_package_list_missing_version(bindings_cfg, python_repo_factory):
    """A missing repository snapshot returns 404."""
    repo = python_repo_factory()
    response = requests.get(
        urljoin(bindings_cfg.host, f"{repo.pulp_href}versions/999/packages/"),
        auth=(bindings_cfg.username, bindings_cfg.password),
    )
    assert response.status_code == 404, response.text


@pytest.mark.parallel
def test_package_list_permissions(bindings_cfg, python_repo_factory, gen_user, catalog_path):
    """Catalog access requires view permission on the parent repository."""
    repo = python_repo_factory()
    other = python_repo_factory()
    user = gen_user()
    viewer = gen_user(object_roles=[("python.pythonrepository_viewer", repo.pulp_href)])
    model_viewer = gen_user(model_roles=["python.pythonrepository_viewer"])
    denied_status = 403 if "/versions/" in catalog_path(repo) else 404
    for actor, repository, status in (
        (user, repo, denied_status),
        (viewer, repo, 200),
        (viewer, other, denied_status),
        (model_viewer, other, 200),
    ):
        response = requests.get(
            urljoin(bindings_cfg.host, catalog_path(repository)),
            auth=(actor.username, actor.password),
        )
        assert response.status_code == status, response.text

    response = requests.post(
        urljoin(bindings_cfg.host, catalog_path(repo)),
        json={},
        auth=(bindings_cfg.username, bindings_cfg.password),
    )
    assert response.status_code == 405, response.text

    response = requests.get(
        urljoin(bindings_cfg.host, catalog_path(repo)),
        auth=("", ""),
    )
    assert response.status_code == 401, response.text
