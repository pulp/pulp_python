from urllib.parse import urljoin

import pytest
import requests

from pulp_python.tests.functional.constants import PYTHON_SM_PROJECT_SPECIFIER


def _api_get(bindings_cfg, path, **params):
    url = urljoin(bindings_cfg.host + "/", path.lstrip("/"))
    response = requests.get(url, params=params, auth=(bindings_cfg.username, bindings_cfg.password))
    assert response.status_code == 200, response.text
    return response.json()


def _content_packages_path(repo_href):
    marker = "/api/v3/"
    idx = repo_href.find(marker)
    assert idx != -1, repo_href
    return f"{repo_href[: idx + len(marker)]}content/python/packages/"


def _assert_package_row(pkg):
    assert pkg["name"]
    assert pkg["name_normalized"]
    assert set(pkg["versions"]) == {rel["version"] for rel in pkg["latest_releases"]}
    for rel in pkg["latest_releases"]:
        assert rel["release"] == ""
        assert rel["created_at"]


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
    assert {pkg["name_normalized"] for pkg in all_rows} == {"aiohttp", "celery", "django"}
    django = next(pkg for pkg in all_rows if pkg["name_normalized"] == "django")
    assert set(django["versions"]) == {"1.10.1", "1.10.2", "1.10.3", "1.10.4"}
    # Dual-field contract: one latest_releases entry per logical version, not per wheel/sdist.
    assert len(django["latest_releases"]) == 4


@pytest.mark.parallel
def test_package_list_istartswith(bindings_cfg, sm_repo):
    """Prefix search is case-insensitive on the package index."""
    data = _api_get(
        bindings_cfg, f"{sm_repo.pulp_href}packages/", name_normalized__istartswith="djan"
    )
    assert data["count"] == 1
    assert data["results"][0]["name_normalized"] == "django"

    data = _api_get(
        bindings_cfg, f"{sm_repo.pulp_href}packages/", name_normalized__istartswith="DJAN"
    )
    assert data["count"] == 1
    assert data["results"][0]["name_normalized"] == "django"

    data = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/", name__istartswith="Cel")
    assert data["count"] == 1
    assert data["results"][0]["name_normalized"] == "celery"

    data = _api_get(
        bindings_cfg, f"{sm_repo.pulp_href}packages/", name_normalized__istartswith="shelf"
    )
    assert data["count"] == 0


@pytest.mark.parallel
def test_package_list_empty_repository(bindings_cfg, python_repo_factory):
    repo = python_repo_factory()
    data = _api_get(bindings_cfg, f"{repo.pulp_href}packages/")
    assert data["count"] == 0
    assert data["results"] == []


@pytest.mark.parallel
def test_repository_metrics(bindings_cfg, sm_repo, python_repo_factory):
    """Metrics count distinct packages / logical versions / builds, not files."""
    data = _api_get(bindings_cfg, f"{sm_repo.pulp_href}metrics/")
    assert data["package_count"] == 3
    # aiohttp 3 + celery 2 + Django 4; no rebuild suffixes in fixtures.
    assert data["version_count"] == 9
    assert data["build_count"] == 9
    assert data["version_count"] == data["build_count"]

    empty = _api_get(bindings_cfg, f"{python_repo_factory().pulp_href}metrics/")
    assert empty == {"package_count": 0, "version_count": 0, "build_count": 0}


@pytest.mark.parallel
def test_collapse_builds_and_base_version(bindings_cfg, sm_repo):
    """collapse_builds keeps one unit per logical version; base_version is always present."""
    path = _content_packages_path(sm_repo.pulp_href)
    repo_version = sm_repo.latest_version_href

    expanded = _api_get(
        bindings_cfg,
        path,
        name="Django",
        repository_version=repo_version,
        collapse_builds="false",
        limit=100,
    )
    collapsed = _api_get(
        bindings_cfg,
        path,
        name="Django",
        repository_version=repo_version,
        collapse_builds="true",
        limit=100,
    )
    # Wheel + sdist per Django version collapse when packagetype is omitted.
    assert expanded["count"] == 8
    assert collapsed["count"] == 4
    assert {item["base_version"] for item in collapsed["results"]} == {
        "1.10.1",
        "1.10.2",
        "1.10.3",
        "1.10.4",
    }
    for item in expanded["results"] + collapsed["results"]:
        assert item["base_version"] == item["version"]

    sdist_false = _api_get(
        bindings_cfg,
        path,
        name="Django",
        packagetype="sdist",
        repository_version=repo_version,
        collapse_builds="false",
        limit=100,
    )
    sdist_true = _api_get(
        bindings_cfg,
        path,
        name="Django",
        packagetype="sdist",
        repository_version=repo_version,
        collapse_builds="true",
        limit=100,
    )
    assert sdist_false["count"] == 4
    assert sdist_true["count"] == 4
    assert {item["version"] for item in sdist_true["results"]} == {
        "1.10.1",
        "1.10.2",
        "1.10.3",
        "1.10.4",
    }


@pytest.mark.parallel
def test_package_get_base_version_without_collapse(bindings_cfg, python_repo_with_sync):
    """PackageGet uses the content list without collapse_builds; base_version is still present."""
    repo = python_repo_with_sync()
    path = _content_packages_path(repo.pulp_href)
    data = _api_get(
        bindings_cfg,
        path,
        name_normalized="shelf-reader",
        version="0.1",
        packagetype="sdist",
    )
    assert data["count"] == 1
    item = data["results"][0]
    assert item["version"] == "0.1"
    assert item["base_version"] == "0.1"
    assert "collapse_builds" not in item

    pkgs = _api_get(bindings_cfg, f"{repo.pulp_href}packages/")
    assert pkgs["count"] == 1
    row = pkgs["results"][0]
    _assert_package_row(row)
    assert row["name_normalized"] == "shelf-reader"
    assert row["versions"] == ["0.1"]
    assert len(row["latest_releases"]) == 1
