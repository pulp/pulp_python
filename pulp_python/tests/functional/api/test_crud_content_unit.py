import pytest

from urllib.parse import urljoin

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
    content = python_bindings.ContentPackagesApi.read(task.created_resources[0]).to_dict()
    for k, v in PYTHON_PACKAGE_DATA.items():
        assert content[k] == v

    # Test read
    result = python_bindings.ContentPackagesApi.list(filename=content["filename"])
    assert result.count == 1
    assert result.results[0].to_dict() == content

    # Test partial update
    with pytest.raises(AttributeError) as e:
        python_bindings.ContentPackagesApi.partial_update(content["pulp_href"], {"filename": "te"})
    assert "object has no attribute 'partial_update'" in e.value.args[0]

    # Test delete
    with pytest.raises(AttributeError) as e:
        python_bindings.ContentPackagesApi.delete(content["pulp_href"])
    assert "object has no attribute 'delete'" in e.value.args[0]

    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)

    # Test create w/ file
    content_body = {"relative_path": PYTHON_EGG_FILENAME, "file": python_file}
    response = python_bindings.ContentPackagesApi.create(**content_body)
    task = monitor_task(response.task)
    content = python_bindings.ContentPackagesApi.read(task.created_resources[0]).to_dict()
    for k, v in PYTHON_PACKAGE_DATA.items():
        assert content[k] == v

    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)

    # Test create w/ file & repository
    repo = python_repo_factory()
    response = python_bindings.ContentPackagesApi.create(repository=repo.pulp_href, **content_body)
    task = monitor_task(response.task)
    assert len(task.created_resources) == 2
    content_search = python_bindings.ContentPackagesApi.list(
        repository_version_added=task.created_resources[0]
    )
    content = python_bindings.ContentPackagesApi.read(content_search.results[0].pulp_href).to_dict()
    for k, v in PYTHON_PACKAGE_DATA.items():
        assert content[k] == v

    # Test duplicate upload
    content_body = {"relative_path": PYTHON_EGG_FILENAME, "file": python_file}
    response = python_bindings.ContentPackagesApi.create(**content_body)
    task = monitor_task(response.task)
    assert task.created_resources[0] == content["pulp_href"]

    # Test upload same filename w/ different artifact
    second_python_url = urljoin(urljoin(PYTHON_FIXTURES_URL, "packages/"), "aiohttp-3.3.0.tar.gz")
    second_python_file = download_python_file("aiohttp-3.3.0.tar.gz", second_python_url)
    content_body = {"relative_path": PYTHON_EGG_FILENAME, "file": second_python_file}
    response = python_bindings.ContentPackagesApi.create(**content_body)
    task = monitor_task(response.task)
    content2 = python_bindings.ContentPackagesApi.read(task.created_resources[0]).to_dict()
    assert content2["pulp_href"] != content["pulp_href"]

    # Test upload same filename w/ different artifacts in same repo
    # repo already has EGG_FILENAME w/ EGG_ARTIFACT, not upload EGG_FILENAME w/ AIO_ARTIFACT
    # and see that repo will only have the second content unit inside after upload
    response = python_bindings.ContentPackagesApi.create(repository=repo.pulp_href, **content_body)
    task = monitor_task(response.task)
    assert len(task.created_resources) == 2
    assert content2["pulp_href"] in task.created_resources
    repo_ver2 = task.created_resources[0]
    content_list = python_bindings.ContentPackagesApi.list(repository_version=repo_ver2)
    assert content_list.count == 1
    assert content_list.results[0].pulp_href == content2["pulp_href"]

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
