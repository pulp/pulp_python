import pytest

import requests
from urllib.parse import urljoin
from pypi_simple import ProjectPage


@pytest.mark.parallel
def test_cru_project_metadata(python_bindings, python_repo_factory, monitor_task):
    """Test creating/reading/updating project metadata."""
    repo = python_repo_factory()
    body = {
        "project_name": "test-project",
    }
    result = python_bindings.RepositoriesPythonApi.update_project(repo.pulp_href, body)
    task = monitor_task(result.task)
    metadata1 = python_bindings.ContentProjectMetadataApi.read(task.created_resources[-1])
    assert metadata1.project_name == body["project_name"]
    assert metadata1.tracks == []
    assert metadata1.alternate_locations == []
    assert metadata1.sha256 is not None

    # Update metadata
    body["alternate_locations"] = ["https://pypi.org/simple/test-project/"]
    result = python_bindings.RepositoriesPythonApi.update_project(repo.pulp_href, body)
    task = monitor_task(result.task)
    metadata2 = python_bindings.ContentProjectMetadataApi.read(task.created_resources[-1])
    assert metadata2.project_name == body["project_name"]
    assert metadata2.tracks == []
    assert metadata2.alternate_locations == ["https://pypi.org/simple/test-project/"]
    assert metadata2.sha256 is not None
    assert metadata1.sha256 != metadata2.sha256

    # Test that update is a PATCH operation
    del body["alternate_locations"]
    body["tracks"] = ["https://pypi.org/simple/test-project/"]
    result = python_bindings.RepositoriesPythonApi.update_project(repo.pulp_href, body)
    task = monitor_task(result.task)
    metadata3 = python_bindings.ContentProjectMetadataApi.read(task.created_resources[-1])
    assert metadata3.project_name == body["project_name"]
    assert metadata3.tracks == ["https://pypi.org/simple/test-project/"]
    assert metadata3.alternate_locations == metadata2.alternate_locations
    assert metadata3.sha256 is not None
    assert metadata2.sha256 != metadata3.sha256

    # Test that update is idempotent
    body["alternate_locations"] = ["https://pypi.org/simple/test-project/"]
    result = python_bindings.RepositoriesPythonApi.update_project(repo.pulp_href, body)
    task = monitor_task(result.task)
    metadata4 = python_bindings.ContentProjectMetadataApi.read(task.created_resources[-1])
    assert metadata4.pulp_href == metadata3.pulp_href

    # Test name normalization
    body["project_name"] = "Test_Project"
    result = python_bindings.RepositoriesPythonApi.update_project(repo.pulp_href, body)
    task = monitor_task(result.task)
    metadata5 = python_bindings.ContentProjectMetadataApi.read(task.created_resources[-1])
    assert metadata5.project_name == "test-project"
    assert metadata5.pulp_href == metadata4.pulp_href

    # Test that there is only one project metadata for the repository
    repo = python_bindings.RepositoriesPythonApi.read(repo.pulp_href)
    assert repo.latest_version_href[-2] == "3"
    repo_version = python_bindings.RepositoriesPythonVersionsApi.read(repo.latest_version_href)
    assert repo_version.content_summary.present["python.project_metadata"]["count"] == 1


@pytest.mark.parallel
def test_project_metadata_simple(
    python_bindings, python_repo_with_sync, python_distribution_factory, monitor_task
):
    """Test project metadata is served by the simple API."""
    repo = python_repo_with_sync()
    distro = python_distribution_factory(repository=repo)

    tracks = ["https://pypi.org/simple/shelf-reader/"]
    alternate_locations = [
        "https://pypi.org/simple/shelf-reader/",
        "https://fixtures.pulpproject.org/python-pypi/simple/shelf-reader/",
    ]
    body = {
        "project_name": "shelf-reader",
        "tracks": tracks,
        "alternate_locations": alternate_locations,
    }
    result = python_bindings.RepositoriesPythonApi.update_project(repo.pulp_href, body)
    task = monitor_task(result.task)
    metadata = python_bindings.ContentProjectMetadataApi.read(task.created_resources[-1])
    assert metadata.project_name == "shelf-reader"
    assert metadata.tracks == tracks
    assert metadata.alternate_locations == alternate_locations

    # Test that the project metadata is served by the simple API
    url = urljoin(distro.base_url, "simple/shelf-reader/")
    response = requests.get(url)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/html"
    page = ProjectPage.from_response(response, "shelf-reader")
    assert page.tracks == tracks
    assert page.alternate_locations == alternate_locations

    # Test that the project metadata is served by the simple API in JSON format
    response = requests.get(url, headers={"Accept": "application/vnd.pypi.simple.v1+json"})
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/vnd.pypi.simple.v1+json"
    data = response.json()
    assert data["tracks"] == tracks
    assert data["alternate-locations"] == alternate_locations


@pytest.mark.parallel
def test_project_metadata_pull_through(
    python_bindings,
    python_repo_factory,
    python_remote_factory,
    python_distribution_factory,
    monitor_task,
):
    """Test project metadata is served by the pull-through API."""
    repo = python_repo_factory()
    distro = python_distribution_factory(repository=repo)
    body = {
        "project_name": "shelf-reader",
        "tracks": ["https://pypi.org/simple/shelf-reader/"],
        "alternate_locations": ["https://pypi.org/simple/shelf-reader/"],
    }
    result = python_bindings.RepositoriesPythonApi.update_project(repo.pulp_href, body)
    task = monitor_task(result.task)
    metadata = python_bindings.ContentProjectMetadataApi.read(task.created_resources[-1])

    repo2 = python_repo_factory()
    remote = python_remote_factory(url=distro.base_url, includes=[])
    distro2 = python_distribution_factory(repository=repo2, remote=remote.pulp_href)

    response = requests.get(urljoin(distro2.base_url, "simple/shelf-reader/"))
    assert response.status_code == 200
    page = ProjectPage.from_response(response, "shelf-reader")
    assert page.tracks == ["https://pypi.org/simple/shelf-reader/"]
    assert page.alternate_locations == ["https://pypi.org/simple/shelf-reader/"]

    # Test that you can override project metadata from pull-through with local repo metadata
    body = {
        "project_name": "shelf-reader",
        "tracks": [],
        "alternate_locations": ["http://test.org/simple/shelf-reader/"],
    }
    # This only adds the metadata, the repository is still empty of packages
    result = python_bindings.RepositoriesPythonApi.update_project(repo2.pulp_href, body)
    task = monitor_task(result.task)
    metadata2 = python_bindings.ContentProjectMetadataApi.read(task.created_resources[-1])
    assert metadata.sha256 != metadata2.sha256

    response = requests.get(urljoin(distro2.base_url, "simple/shelf-reader/"))
    assert response.status_code == 200
    page = ProjectPage.from_response(response, "shelf-reader")
    assert page.tracks == []
    assert page.alternate_locations == ["http://test.org/simple/shelf-reader/"]
