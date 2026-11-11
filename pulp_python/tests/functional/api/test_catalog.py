"""Catalog API tests."""

import io
import tarfile

import pytest

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
def test_package_list_snapshots(python_bindings, python_repo_with_sync, monitor_task):
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
    assert row.description == sdist.description
    assert [(item.version, item.last_updated) for item in row.versions] == [
        ("0.1", newest.pulp_created)
    ]

    monitor_task(
        repositories.modify(repo.pulp_href, {"remove_content_units": [newest.pulp_href]}).task
    )
    current = repositories.packages(repo.pulp_href).results[0]
    assert current.versions[0].last_updated == remaining.pulp_created
    assert current.description == remaining.description
    assert versions.packages(repo.latest_version_href).to_dict() == original.to_dict()
    with pytest.raises(python_bindings.ApiException) as exc:
        versions.packages(f"{repo.pulp_href}versions/999/")
    assert exc.value.status == 404


@pytest.mark.parallel
def test_package_list_versions(python_content_factory, python_repo, python_bindings, tmp_path):
    """PEP 440 ordering selects metadata and preserves separate rebuild versions."""
    content = {}
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

    data = python_bindings.RepositoriesPythonApi.packages(python_repo.pulp_href)
    assert data.count == 1
    row = data.results[0]
    assert row.description.strip() == "Version 1.10"
    assert [(item.version, item.last_updated) for item in row.versions] == [
        (version, content[version].pulp_created) for version in ("1.10", "1.9+test.1", "1.9")
    ]


@pytest.mark.parallel
def test_package_list_permissions(
    python_bindings, python_repo, python_repo_factory, gen_user, catalog
):
    """Both actions require view permission on the parent repository."""
    other = python_repo_factory()
    viewer = gen_user(object_roles=[("python.pythonrepository_viewer", python_repo.pulp_href)])
    with viewer:
        assert catalog(python_repo).results == []
        with pytest.raises(python_bindings.ApiException) as exc:
            catalog(other)
        assert exc.value.status in (403, 404)
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
