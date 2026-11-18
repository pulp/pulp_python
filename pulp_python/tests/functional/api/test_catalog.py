"""Catalog API tests."""

import io
import tarfile
from urllib.parse import urljoin

import pytest
import requests

from pulp_python.tests.functional.constants import PYTHON_SM_PROJECT_SPECIFIER


@pytest.fixture(params=["repository", "version"])
def catalog(request, python_bindings):
    """Call either catalog action through its generated client."""
    version = request.param == "version"
    api = (
        python_bindings.RepositoriesPythonVersionsApi
        if version
        else python_bindings.RepositoriesPythonApi
    )

    def packages(repo, **params):
        href = repo.latest_version_href if version else repo.pulp_href
        return api.packages(href, **params)

    return packages


def test_package_list_schema(pulp_openapi_schema_pk_path_set):
    """Both actions expose package filters without a repository-version filter."""
    operations = [
        methods["get"]
        for path, methods in pulp_openapi_schema_pk_path_set["paths"].items()
        if "/repositories/python/python/" in path and path.endswith("/packages/")
    ]
    assert len(operations) == 2
    for operation in operations:
        params = {item["name"] for item in operation["parameters"] if item["in"] == "query"}
        assert {"name_normalized", "ordering", "limit", "offset"} <= params
        assert "repository_version" not in params


@pytest.mark.parallel
def test_package_list(python_repo_with_sync, python_remote_factory, catalog):
    """Group and page package names, with name filtering and ordering."""
    repo = python_repo_with_sync(python_remote_factory(includes=PYTHON_SM_PROJECT_SPECIFIER))
    first = catalog(repo, limit=2)
    second = catalog(repo, limit=2, offset=2)
    assert first.count == second.count == 3
    assert [pkg.name_normalized for pkg in first.results + second.results] == [
        "aiohttp",
        "celery",
        "django",
    ]
    django = second.results[0]
    assert [item.version for item in django.versions] == ["1.10.4", "1.10.3", "1.10.2", "1.10.1"]
    assert set(django.versions[0].to_dict()) == {"version", "last_updated"}
    for params in ({"name_normalized": "django"}, {"name_normalized__istartswith": "DJAN"}):
        filtered = catalog(repo, **params)
        assert filtered.count == 1
        assert filtered.results[0].name_normalized == "django"
    descending = catalog(repo, ordering=["-name_normalized"], limit=2)
    assert [pkg.name_normalized for pkg in descending.results] == ["django", "celery"]


@pytest.mark.parallel
def test_package_list_snapshots(
    bindings_cfg, python_bindings, python_repo_with_sync, python_repo_factory, monitor_task
):
    """Metadata and update times use only files in the requested repository version."""
    repo = python_repo_with_sync()
    repositories = python_bindings.RepositoriesPythonApi
    versions = python_bindings.RepositoriesPythonVersionsApi
    empty = versions.packages(f"{repo.pulp_href}versions/0/")
    assert empty.count == 0
    assert empty.results == []

    files = python_bindings.ContentPackagesApi.list(
        repository_version=repo.latest_version_href
    ).results
    sdist = next(item for item in files if item.packagetype == "sdist")
    newest = max(files, key=lambda item: item.pulp_created)
    remaining = next(item for item in files if item.pulp_href != newest.pulp_href)
    original = repositories.packages(repo.pulp_href)
    assert original.count == 1
    row = original.results[0]
    response = requests.get(
        urljoin(bindings_cfg.host, f"{repo.pulp_href}packages/"),
        auth=(bindings_cfg.username, bindings_cfg.password),
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["versions"][0]["last_updated"].endswith("Z")
    assert row.description == sdist.description
    assert [item.version for item in row.versions] == ["0.1"]
    added = row.versions[0].last_updated
    assert added >= versions.read(repo.latest_version_href).pulp_created

    monitor_task(
        repositories.modify(repo.pulp_href, {"remove_content_units": [newest.pulp_href]}).task
    )
    current = repositories.packages(repo.pulp_href).results[0]
    assert remaining.pulp_created < current.versions[0].last_updated <= added
    assert current.description == remaining.description
    monitor_task(
        repositories.modify(repo.pulp_href, {"add_content_units": [newest.pulp_href]}).task
    )
    readded = repositories.packages(repo.pulp_href).results[0].versions[0].last_updated
    assert readded > added
    other = python_repo_factory()
    monitor_task(
        repositories.modify(other.pulp_href, {"add_content_units": [newest.pulp_href]}).task
    )
    assert repositories.packages(repo.pulp_href).results[0].versions[0].last_updated == readded
    assert versions.packages(repo.latest_version_href).to_dict() == original.to_dict()
    with pytest.raises(python_bindings.ApiException) as exc:
        versions.packages(f"{repo.pulp_href}versions/999/")
    assert exc.value.status == 404


@pytest.mark.parallel
def test_package_list_versions(
    python_content_factory,
    python_repo,
    python_bindings,
    python_distribution_factory,
    monitor_task,
    tmp_path,
):
    """PEP 440 ordering selects metadata and preserves separate rebuild versions."""
    content = {}
    added_after = {}
    for version in ("1.10", "1.9", "1.9+test.1"):
        filename = f"catalog-test-{version}.tar.gz"
        path = tmp_path / filename
        metadata = (
            f"Metadata-Version: 2.4\nName: catalog-test\nVersion: {version}\n\nVersion {version}\n"
        ).encode()
        with tarfile.open(path, "w:gz") as archive:
            info = tarfile.TarInfo(f"catalog-test-{version}/PKG-INFO")
            info.size = len(metadata)
            archive.addfile(info, io.BytesIO(metadata))
        content[version] = python_content_factory(filename, file=str(path), repository=python_repo)
        repo = python_bindings.RepositoriesPythonApi.read(python_repo.pulp_href)
        added_after[version] = python_bindings.RepositoriesPythonVersionsApi.read(
            repo.latest_version_href
        ).pulp_created

    data = python_bindings.RepositoriesPythonApi.packages(python_repo.pulp_href)
    assert data.count == 1
    row = data.results[0]
    assert row.description.strip() == "Version 1.10"
    assert [item.version for item in row.versions] == ["1.10", "1.9+test.1", "1.9"]
    for item in row.versions:
        assert item.last_updated >= added_after[item.version]
        assert item.last_updated > content[item.version].pulp_created
    distro = python_distribution_factory(repository=python_repo)
    monitor_task(
        python_bindings.PypiYankApi.yank(
            path=distro.base_path, yank={"name": "catalog-test", "version": "1.10"}
        ).task
    )
    row = python_bindings.RepositoriesPythonApi.packages(python_repo.pulp_href).results[0]
    assert [item.version for item in row.versions] == ["1.9+test.1", "1.9"]
    assert row.description.strip() == "Version 1.9+test.1"


@pytest.mark.parallel
def test_package_list_yanked(
    python_bindings, python_repo_with_sync, python_distribution_factory, monitor_task, catalog
):
    """Yank markers exclude versions only from repository versions containing them."""
    repo = python_repo_with_sync()
    distro = python_distribution_factory(repository=repo)
    monitor_task(
        python_bindings.PypiYankApi.yank(
            path=distro.base_path, yank={"name": "shelf-reader", "version": "0.1"}
        ).task
    )
    historical = python_bindings.RepositoriesPythonVersionsApi.packages(repo.latest_version_href)
    assert historical.count == 1
    latest = python_bindings.RepositoriesPythonApi.read(repo.pulp_href)
    excluded = catalog(latest)
    assert excluded.count == 0
    assert excluded.results == []


@pytest.mark.parallel
@pytest.mark.parametrize(
    "catalog, denied_status", [("repository", 404), ("version", 403)], indirect=["catalog"]
)
def test_package_list_permissions(
    python_bindings, python_repo, python_repo_factory, gen_user, catalog, denied_status
):
    """Both actions require view permission on the parent repository."""
    other = python_repo_factory()
    viewer = gen_user(object_roles=[("python.pythonrepository_viewer", python_repo.pulp_href)])
    with viewer:
        assert catalog(python_repo).results == []
        with pytest.raises(python_bindings.ApiException) as exc:
            catalog(other)
        assert exc.value.status == denied_status
    with gen_user(model_roles=["python.pythonrepository_viewer"]):
        assert catalog(other).results == []


@pytest.mark.parallel
def test_package_list_domains(
    python_bindings, domain_factory, python_repo_factory, gen_user, pulp_domain_enabled, catalog
):
    """Both actions enforce domain boundaries and accept domain viewer roles."""
    if not pulp_domain_enabled:
        pytest.skip("Domain not enabled")
    domain = domain_factory()
    repo = python_repo_factory(pulp_domain=domain.name)
    with gen_user(domain_roles=[("python.pythonrepository_viewer", domain.pulp_href)]):
        assert catalog(repo).results == []
    repo.pulp_href = repo.pulp_href.replace(f"/{domain.name}/api/", "/default/api/")
    repo.latest_version_href = repo.latest_version_href.replace(
        f"/{domain.name}/api/", "/default/api/"
    )
    with pytest.raises(python_bindings.ApiException) as exc:
        catalog(repo)
    assert exc.value.status == 404
