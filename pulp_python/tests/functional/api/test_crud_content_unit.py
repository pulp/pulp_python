import pytest

from urllib.parse import urljoin
from pypi_simple import PyPISimple

from pulpcore.tests.functional.utils import PulpTaskError
from pulp_python.tests.functional.constants import (
    PYTHON_FIXTURES_URL,
    PYTHON_PACKAGE_DATA,
    PYTHON_EGG_FILENAME,
    PYTHON_EGG_URL,
    PYTHON_SM_FIXTURE_CHECKSUMS,
)


def test_content_crud(
    python_bindings, pulpcore_bindings, python_repo_factory, download_python_file, monitor_task
):
    """Test CRUD python content unit."""
    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)
    python_file = download_python_file(PYTHON_EGG_FILENAME, PYTHON_EGG_URL)

    artifact = pulpcore_bindings.ArtifactsApi.create(python_file)

    # Test create
    content_body = {"relative_path": PYTHON_EGG_FILENAME, "artifact": artifact.pulp_href}
    response = python_bindings.ContentPackagesApi.create(**content_body)
    task = monitor_task(response.task)
    content = python_bindings.ContentPackagesApi.read(task.created_resources[0])
    for k, v in PYTHON_PACKAGE_DATA.items():
        assert getattr(content, k) == v

    # Test read
    result = python_bindings.ContentPackagesApi.list(filename=content.filename)
    assert result.count == 1
    assert result.results[0] == content

    # Test partial update
    with pytest.raises(AttributeError) as e:
        python_bindings.ContentPackagesApi.partial_update(content.pulp_href, {"filename": "te"})
    assert "object has no attribute 'partial_update'" in e.value.args[0]

    # Test delete
    with pytest.raises(AttributeError) as e:
        python_bindings.ContentPackagesApi.delete(content.pulp_href)
    assert "object has no attribute 'delete'" in e.value.args[0]

    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)

    # Test create w/ file
    content_body = {"relative_path": PYTHON_EGG_FILENAME, "file": python_file}
    response = python_bindings.ContentPackagesApi.create(**content_body)
    task = monitor_task(response.task)
    content = python_bindings.ContentPackagesApi.read(task.created_resources[0])
    for k, v in PYTHON_PACKAGE_DATA.items():
        assert getattr(content, k) == v

    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)

    # Test create w/ file & repository
    repo = python_repo_factory()
    response = python_bindings.ContentPackagesApi.create(repository=repo.pulp_href, **content_body)
    task = monitor_task(response.task)
    assert len(task.created_resources) == 2
    content_search = python_bindings.ContentPackagesApi.list(
        repository_version_added=task.created_resources[0]
    )
    content = python_bindings.ContentPackagesApi.read(content_search.results[0].pulp_href)
    for k, v in PYTHON_PACKAGE_DATA.items():
        assert getattr(content, k) == v

    # Test duplicate upload
    content_body = {"relative_path": PYTHON_EGG_FILENAME, "file": python_file}
    response = python_bindings.ContentPackagesApi.create(**content_body)
    task = monitor_task(response.task)
    assert task.created_resources[0] == content.pulp_href

    # Test upload same filename w/ different artifact
    second_python_url = urljoin(urljoin(PYTHON_FIXTURES_URL, "packages/"), "aiohttp-3.3.0.tar.gz")
    second_python_file = download_python_file("aiohttp-3.3.0.tar.gz", second_python_url)
    content_body = {"relative_path": PYTHON_EGG_FILENAME, "file": second_python_file}
    response = python_bindings.ContentPackagesApi.create(**content_body)
    task = monitor_task(response.task)
    content2 = python_bindings.ContentPackagesApi.read(task.created_resources[0])
    assert content2.pulp_href != content.pulp_href

    # Test upload same filename w/ different artifacts in same repo
    # repo already has EGG_FILENAME w/ EGG_ARTIFACT, not upload EGG_FILENAME w/ AIO_ARTIFACT
    # and see that repo will only have the second content unit inside after upload
    response = python_bindings.ContentPackagesApi.create(repository=repo.pulp_href, **content_body)
    task = monitor_task(response.task)
    assert len(task.created_resources) == 2
    assert content2.pulp_href in task.created_resources
    repo_ver2 = task.created_resources[0]
    content_list = python_bindings.ContentPackagesApi.list(repository_version=repo_ver2)
    assert content_list.count == 1
    assert content_list.results[0].pulp_href == content2.pulp_href

    # Test upload w/ mismatched sha256
    # If we don't perform orphan cleanup here, the upload will fail with a different error :hmm:
    monitor_task(python_bindings.RepositoriesPythonApi.delete(repo.pulp_href).task)
    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)
    mismatch_sha256 = PYTHON_SM_FIXTURE_CHECKSUMS["aiohttp-3.3.0.tar.gz"]
    content_body = {
        "relative_path": PYTHON_EGG_FILENAME, "file": python_file, "sha256": mismatch_sha256
    }
    with pytest.raises(PulpTaskError) as e:
        response = python_bindings.ContentPackagesApi.create(**content_body)
        monitor_task(response.task)
    msg = "The uploaded artifact's sha256 checksum does not match the one provided"
    assert msg in e.value.task.error["description"]


def test_content_create_new_metadata(
    delete_orphans_pre, download_python_file, monitor_task, python_bindings
):
    """
    Test the creation of python content unit with newly added core metadata (provides_extras,
    dynamic, license_expression, license_file).
    """
    python_egg_filename = "setuptools-80.9.0.tar.gz"
    python_egg_url = urljoin(urljoin(PYTHON_FIXTURES_URL, "packages/"), python_egg_filename)
    python_file = download_python_file(python_egg_filename, python_egg_url)

    body = {"relative_path": python_egg_filename, "file": python_file}
    response = python_bindings.ContentPackagesApi.create(**body)
    task = monitor_task(response.task)
    content = python_bindings.ContentPackagesApi.read(task.created_resources[0])

    python_package_data = {
        "filename": "setuptools-80.9.0.tar.gz",
        "provides_extras":
            '["test", "doc", "ssl", "certs", "core", "check", "cover", "enabler", "type"]',
        "dynamic": '["license-file"]',
        "license_expression": "MIT",
        "license_file": '["LICENSE"]',
    }
    for k, v in python_package_data.items():
        assert getattr(content, k) == v


@pytest.mark.parallel
def test_upload_metadata_23_spec(python_content_factory):
    """Test that packages using metadata spec 2.3 can be uploaded to pulp."""
    filename = "urllib3-2.2.2-py3-none-any.whl"
    with PyPISimple() as client:
        page = client.get_project_page("urllib3")
        for package in page.packages:
            if package.filename == filename:
                content = python_content_factory(filename, url=package.url)
                assert content.metadata_version == "2.3"
                break


@pytest.mark.parallel
def test_upload_requires_python(python_content_factory):
    filename = "pip-24.3.1-py3-none-any.whl"
    with PyPISimple() as client:
        page = client.get_project_page("pip")
        for package in page.packages:
            if package.filename == filename:
                content = python_content_factory(filename, url=package.url)
                assert content.requires_python == ">=3.8"
                break


@pytest.mark.parallel
def test_upload_metadata_24_spec(python_content_factory):
    """Test that packages using metadata spec 2.4 can be uploaded to pulp."""
    filename = "setuptools-80.9.0.tar.gz"
    with PyPISimple() as client:
        page = client.get_project_page("setuptools")
        for package in page.packages:
            if package.filename == filename:
                content = python_content_factory(filename, url=package.url)
                assert content.metadata_version == "2.4"
                assert content.license_expression == "MIT"
                assert content.license_file == '["LICENSE"]'
                break
