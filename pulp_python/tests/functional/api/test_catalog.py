"""Catalog API tests."""

import io
import tarfile
import uuid
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
        assert set(item) == {"version", "license_expression"}
        assert item["version"]


def _write_sdist(directory, name, version):
    """Write a minimal sdist whose PKG-INFO Name/Version pkginfo can read."""
    pkg_dir = f"{name}-{version}"
    filename = f"{pkg_dir}.tar.gz"
    path = directory / filename
    pkg_info = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode()
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


@pytest.mark.parallel
def test_package_list_grouping_and_pagination(bindings_cfg, sm_repo):
    """Package index is one row per name, and count is distinct packages not files."""
    data = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/", limit=1)
    assert data["count"] == 3
    assert len(data["results"]) == 1
    _assert_package_row(data["results"][0])

    page2 = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/", limit=1, offset=1)
    assert page2["count"] == 3
    assert page2["results"][0]["name_normalized"] != data["results"][0]["name_normalized"]

    all_rows = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/", limit=100)["results"]
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
    data = python_bindings.RepositoriesPythonPackagesApi.list(repo.pulp_href)
    assert data.count == 0
    assert data.results == []


@pytest.mark.parallel
def test_packages_repository_version(bindings_cfg, sm_repo, python_repo_factory):
    """repository_version selects a snapshot; omitted uses the latest complete version."""
    latest_href = sm_repo.latest_version_href
    v0_href = f"{sm_repo.pulp_href}versions/0/"

    default_pkgs = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/")
    explicit_pkgs = _api_get(
        bindings_cfg, f"{sm_repo.pulp_href}packages/", repository_version=latest_href
    )
    assert default_pkgs["count"] == explicit_pkgs["count"] == 3

    version = _api_get(bindings_cfg, latest_href)
    prn_pkgs = _api_get(
        bindings_cfg, f"{sm_repo.pulp_href}packages/", repository_version=version["prn"]
    )
    assert prn_pkgs["count"] == 3
    assert version["prn"].startswith("prn:core.repositoryversion:")

    v0_pkgs = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/", repository_version=v0_href)
    assert v0_pkgs["count"] == 0
    assert v0_pkgs["results"] == []

    other = python_repo_factory()
    url = urljoin(bindings_cfg.host + "/", f"{sm_repo.pulp_href}packages/".lstrip("/"))
    response = requests.get(
        url,
        params={"repository_version": other.latest_version_href},
        auth=(bindings_cfg.username, bindings_cfg.password),
    )
    assert response.status_code == 400, response.text


@pytest.mark.parallel
def test_package_list_one_entry_per_stored_version(
    bindings_cfg, python_bindings, python_repo_with_sync
):
    """A wheel and an sdist of the same version are one version string."""
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
    historical = _api_get(
        bindings_cfg, f"{repo.pulp_href}packages/", repository_version=original_version
    )["results"][0]
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
def test_package_list_filters_and_ordering(bindings_cfg, sm_repo):
    """Name filters and ordering apply to packages within the selected snapshot."""
    path = f"{sm_repo.pulp_href}packages/"
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
@pytest.mark.parametrize("selector", ["invalid", "repository", "missing", "wrong_type_prn"])
def test_package_list_invalid_version(bindings_cfg, python_repo_factory, selector):
    """Malformed, missing, and non-version resources return a validation error."""
    repo = python_repo_factory()
    selectors = {
        "invalid": "/not-a-pulp-resource/",
        "repository": repo.pulp_href,
        "missing": f"{repo.pulp_href}versions/999/",
        "wrong_type_prn": repo.prn,
    }
    response = requests.get(
        urljoin(bindings_cfg.host, f"{repo.pulp_href}packages/"),
        params={"repository_version": selectors[selector]},
        auth=(bindings_cfg.username, bindings_cfg.password),
    )
    assert response.status_code == 400, response.text
    assert "repository_version" in response.json()


@pytest.mark.parallel
def test_package_list_permissions(bindings_cfg, python_repo_factory, gen_user):
    """Catalog access requires view permission on the parent repository."""
    repo = python_repo_factory()
    other = python_repo_factory()
    user = gen_user()
    viewer = gen_user(object_roles=[("python.pythonrepository_viewer", repo.pulp_href)])
    model_viewer = gen_user(model_roles=["python.pythonrepository_viewer"])
    for actor, repository, status in (
        (user, repo, 403),
        (viewer, repo, 200),
        (viewer, other, 403),
        (model_viewer, other, 200),
    ):
        response = requests.get(
            urljoin(bindings_cfg.host, f"{repository.pulp_href}packages/"),
            auth=(actor.username, actor.password),
        )
        assert response.status_code == status, response.text

    response = requests.post(
        urljoin(bindings_cfg.host, f"{repo.pulp_href}packages/"),
        json={},
        auth=(bindings_cfg.username, bindings_cfg.password),
    )
    assert response.status_code == 405, response.text

    response = requests.get(
        urljoin(bindings_cfg.host, f"{repo.pulp_href}packages/"),
        auth=("", ""),
    )
    assert response.status_code == 401, response.text
