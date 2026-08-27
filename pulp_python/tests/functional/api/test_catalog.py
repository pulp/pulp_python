"""Catalog API tests.

Generated client methods are unavailable until `oci-env generate-client` is rerun.
"""

import io
import tarfile
import uuid
from datetime import datetime
from urllib.parse import urljoin

import pytest
import requests

from pulp_python.tests.functional.constants import PYTHON_SM_PROJECT_SPECIFIER


def _parse_dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


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
    assert pkg["last_updated"]
    assert pkg["versions"] == [rel["version"] for rel in pkg["latest_releases"]]
    for rel in pkg["latest_releases"]:
        assert "release" in rel
        assert rel["created_at"]


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
    assert {pkg["name_normalized"] for pkg in all_rows} == {"aiohttp", "celery", "django"}
    django = next(pkg for pkg in all_rows if pkg["name_normalized"] == "django")
    assert django["versions"] == ["1.10.4", "1.10.3", "1.10.2", "1.10.1"]
    # Dual-field contract: one latest_releases entry per logical version, not per wheel/sdist.
    assert len(django["latest_releases"]) == 4
    for rel in django["latest_releases"]:
        assert rel["release"] == ""


@pytest.mark.parallel
def test_package_list_istartswith(bindings_cfg, sm_repo):
    """Name prefix and substring search is case-insensitive on the package index."""
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

    data = _api_get(
        bindings_cfg, f"{sm_repo.pulp_href}packages/", name_normalized__icontains="http"
    )
    assert data["count"] == 1
    assert data["results"][0]["name_normalized"] == "aiohttp"

    data = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/", name_normalized__icontains="JAN")
    assert data["count"] == 1
    assert data["results"][0]["name_normalized"] == "django"

    data = _api_get(
        bindings_cfg, f"{sm_repo.pulp_href}packages/", name_normalized__icontains="shelf"
    )
    assert data["count"] == 0


@pytest.mark.parallel
def test_package_list_name_normalized_search_min_length(bindings_cfg, sm_repo):
    """name_normalized prefix/substring shorter than 3 characters is rejected."""
    url = urljoin(bindings_cfg.host + "/", f"{sm_repo.pulp_href}packages/".lstrip("/"))
    auth = (bindings_cfg.username, bindings_cfg.password)
    for param, value in (
        ("name_normalized__istartswith", "dj"),
        ("name_normalized__icontains", "ht"),
    ):
        response = requests.get(url, params={param: value}, auth=auth)
        assert response.status_code == 400, response.text
        assert param in response.json()


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
def test_packages_and_metrics_repository_version(bindings_cfg, sm_repo, python_repo_factory):
    """repository_version selects a snapshot; omitted uses the latest complete version."""
    latest_href = sm_repo.latest_version_href
    v0_href = f"{sm_repo.pulp_href}versions/0/"

    default_pkgs = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/")
    explicit_pkgs = _api_get(
        bindings_cfg, f"{sm_repo.pulp_href}packages/", repository_version=latest_href
    )
    assert default_pkgs["count"] == explicit_pkgs["count"] == 3

    v0_pkgs = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/", repository_version=v0_href)
    assert v0_pkgs["count"] == 0
    assert v0_pkgs["results"] == []

    default_metrics = _api_get(bindings_cfg, f"{sm_repo.pulp_href}metrics/")
    explicit_metrics = _api_get(
        bindings_cfg, f"{sm_repo.pulp_href}metrics/", repository_version=latest_href
    )
    assert default_metrics == explicit_metrics
    v0_metrics = _api_get(bindings_cfg, f"{sm_repo.pulp_href}metrics/", repository_version=v0_href)
    assert v0_metrics == {"package_count": 0, "version_count": 0, "build_count": 0}

    other = python_repo_factory()
    url = urljoin(bindings_cfg.host + "/", f"{sm_repo.pulp_href}packages/".lstrip("/"))
    response = requests.get(
        url,
        params={"repository_version": other.latest_version_href},
        auth=(bindings_cfg.username, bindings_cfg.password),
    )
    assert response.status_code == 400, response.text


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
        name="shelf-reader",
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
    assert row["latest_releases"][0]["release"] == ""


@pytest.mark.parallel
def test_package_list_ordering_name(bindings_cfg, sm_repo):
    """Default order is name; -name reverses it."""
    default = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/")["results"]
    names = [pkg["name"] for pkg in default]
    assert len(names) == 3
    explicit = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/", ordering="name")["results"]
    assert [pkg["name"] for pkg in explicit] == names

    reversed_rows = _api_get(bindings_cfg, f"{sm_repo.pulp_href}packages/", ordering="-name")[
        "results"
    ]
    assert [pkg["name"] for pkg in reversed_rows] == list(reversed(names))


@pytest.mark.parallel
def test_package_list_version_order(
    bindings_cfg, python_bindings, python_content_factory, python_repo_factory, tmp_path
):
    """versions and latest_releases are newest-first by PEP 440, not lexicographically."""
    repo = python_repo_factory()
    name = f"ordered-{uuid.uuid4().hex[:8]}"
    for version in ("1.10", "1.9", "1.2"):
        repo = _add_sdist(python_content_factory, python_bindings, tmp_path, repo, name, version)
    data = _api_get(bindings_cfg, f"{repo.pulp_href}packages/")
    assert data["count"] == 1
    pkg = data["results"][0]
    _assert_package_row(pkg)
    assert pkg["versions"] == ["1.10", "1.9", "1.2"]


@pytest.mark.parallel
def test_package_list_ordering_last_updated(
    bindings_cfg, python_bindings, python_content_factory, python_repo_factory, tmp_path
):
    """last_updated is newest membership of any rebuild and is a sort key."""
    repo = python_repo_factory()
    suffix = uuid.uuid4().hex[:8]
    later_name = f"zzz-later-{suffix}"
    earlier_name = f"aaa-earlier-{suffix}"

    repo = _add_sdist(python_content_factory, python_bindings, tmp_path, repo, later_name, "2.0.0")
    first = _api_get(bindings_cfg, f"{repo.pulp_href}packages/")["results"][0]
    first_updated = _parse_dt(first["last_updated"])
    assert first["name_normalized"] == later_name
    assert first["last_updated"] == first["latest_releases"][0]["created_at"]

    repo = _add_sdist(
        python_content_factory, python_bindings, tmp_path, repo, earlier_name, "1.0.0"
    )
    rows = _api_get(bindings_cfg, f"{repo.pulp_href}packages/")["results"]
    by_name = {pkg["name_normalized"]: pkg for pkg in rows}
    older = by_name[later_name]
    newer = by_name[earlier_name]
    assert _parse_dt(older["last_updated"]) == first_updated
    assert _parse_dt(newer["last_updated"]) > first_updated

    default_names = [pkg["name_normalized"] for pkg in rows]
    assert default_names == [earlier_name, later_name]

    by_updated = _api_get(
        bindings_cfg, f"{repo.pulp_href}packages/", ordering="-last_updated", limit=100
    )["results"]
    assert [pkg["name_normalized"] for pkg in by_updated] == [earlier_name, later_name]

    repo = _add_sdist(
        python_content_factory,
        python_bindings,
        tmp_path,
        repo,
        later_name,
        "1.0.0.rhlw-00003",
    )
    after_rebuild = _api_get(
        bindings_cfg, f"{repo.pulp_href}packages/", ordering="-last_updated", limit=100
    )["results"]
    assert [pkg["name_normalized"] for pkg in after_rebuild] == [later_name, earlier_name]
    zzz = after_rebuild[0]
    assert _parse_dt(zzz["last_updated"]) > _parse_dt(newer["last_updated"])
    assert set(zzz["versions"]) == {"2.0.0", "1.0.0"}
    assert zzz["versions"][0] == "2.0.0"
    rebuild_rel = next(rel for rel in zzz["latest_releases"] if rel["version"] == "1.0.0")
    assert rebuild_rel["release"] == "rhlw-00003"
    assert zzz["last_updated"] == rebuild_rel["created_at"]
    public_rel = next(rel for rel in zzz["latest_releases"] if rel["version"] == "2.0.0")
    assert public_rel["release"] == ""


@pytest.mark.parallel
def test_public_and_predisclosure_collapse_to_logical_version(
    bindings_cfg, python_bindings, python_content_factory, python_repo_factory, tmp_path
):
    """Public and predisclosure rebuilds of the same name share one logical version."""
    repo = python_repo_factory()
    name = f"rebuild-{uuid.uuid4().hex[:8]}"
    repo = _add_sdist(python_content_factory, python_bindings, tmp_path, repo, name, "5.3.17")
    repo = _add_sdist(
        python_content_factory,
        python_bindings,
        tmp_path,
        repo,
        name,
        "5.3.17.rhlw-00001-n0001",
    )

    pkgs = _api_get(bindings_cfg, f"{repo.pulp_href}packages/")
    assert pkgs["count"] == 1
    pkg = pkgs["results"][0]
    _assert_package_row(pkg)
    assert pkg["versions"] == ["5.3.17"]
    assert len(pkg["latest_releases"]) == 1
    assert pkg["latest_releases"][0]["version"] == "5.3.17"
    assert pkg["latest_releases"][0]["release"] == "rhlw-00001-n0001"

    metrics = _api_get(bindings_cfg, f"{repo.pulp_href}metrics/")
    assert metrics == {"package_count": 1, "version_count": 1, "build_count": 2}

    path = _content_packages_path(repo.pulp_href)
    repo_version = repo.latest_version_href
    expanded = _api_get(
        bindings_cfg,
        path,
        name=name,
        packagetype="sdist",
        repository_version=repo_version,
        collapse_builds="false",
        limit=100,
    )
    collapsed = _api_get(
        bindings_cfg,
        path,
        name=name,
        packagetype="sdist",
        repository_version=repo_version,
        collapse_builds="true",
        limit=100,
    )
    assert expanded["count"] == 2
    assert {item["base_version"] for item in expanded["results"]} == {"5.3.17"}
    assert collapsed["count"] == 1
    kept = collapsed["results"][0]
    assert kept["base_version"] == "5.3.17"
    assert kept["version"] == "5.3.17.rhlw-00001-n0001"


@pytest.mark.parallel
def test_package_list_ordering_invalid(bindings_cfg, sm_repo):
    url = urljoin(bindings_cfg.host + "/", f"{sm_repo.pulp_href}packages/".lstrip("/"))
    response = requests.get(
        url,
        params={"ordering": "group_id"},
        auth=(bindings_cfg.username, bindings_cfg.password),
    )
    assert response.status_code == 400, response.text
