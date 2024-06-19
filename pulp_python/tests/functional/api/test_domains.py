import pytest
import uuid
import json
import subprocess

from pulpcore.app import settings

from pulp_python.tests.functional.constants import PYTHON_URL, PYTHON_EGG_FILENAME
from urllib.parse import urlsplit


pytestmark = pytest.mark.skipif(not settings.DOMAIN_ENABLED, reason="Domain not enabled")


@pytest.mark.parallel
def test_domain_object_creation(
    domain_factory,
    python_bindings,
    python_repo_factory,
    python_remote_factory,
    python_distribution_factory,
):
    """Test basic object creation in a separate domain."""
    domain = domain_factory()
    domain_name = domain.name

    repo = python_repo_factory(pulp_domain=domain_name)
    assert f"{domain_name}/api/v3/" in repo.pulp_href

    repos = python_bindings.RepositoriesPythonApi.list(pulp_domain=domain_name)
    assert repos.count == 1
    assert repo.pulp_href == repos.results[0].pulp_href

    # Check that distribution's base_url reflects second domain's name
    distro = python_distribution_factory(repository=repo.pulp_href, pulp_domain=domain_name)
    assert distro.repository == repo.pulp_href
    assert domain_name in distro.base_url

    # Will list repos on default domain
    default_repos = python_bindings.RepositoriesPythonApi.list(name=repo.name)
    assert default_repos.count == 0

    # Try to create an object w/ cross domain relations
    default_remote = python_remote_factory(policy="immediate")
    with pytest.raises(python_bindings.ApiException) as e:
        repo_body = {"name": str(uuid.uuid4()), "remote": default_remote.pulp_href}
        python_bindings.RepositoriesPythonApi.create(repo_body, pulp_domain=domain.name)
    assert e.value.status == 400
    assert json.loads(e.value.body) == {
        "non_field_errors": [f"Objects must all be apart of the {domain_name} domain."]
    }

    with pytest.raises(python_bindings.ApiException) as e:
        sync_body = {"remote": default_remote.pulp_href}
        python_bindings.RepositoriesPythonApi.sync(repo.pulp_href, sync_body)
    assert e.value.status == 400
    assert json.loads(e.value.body) == {
        "non_field_errors": [f"Objects must all be apart of the {domain_name} domain."]
    }

    with pytest.raises(python_bindings.ApiException) as e:
        publish_body = {"repository": repo.pulp_href}
        python_bindings.PublicationsPypiApi.create(publish_body)
    assert e.value.status == 400
    assert json.loads(e.value.body) == {
        "non_field_errors": ["Objects must all be apart of the default domain."]
    }

    with pytest.raises(python_bindings.ApiException) as e:
        distro_body = {
            "name": str(uuid.uuid4()), "base_path": str(uuid.uuid4()), "repository": repo.pulp_href
        }
        python_bindings.DistributionsPypiApi.create(distro_body)
    assert e.value.status == 400
    assert json.loads(e.value.body) == {
        "non_field_errors": ["Objects must all be apart of the default domain."]
    }


@pytest.fixture
def python_file(tmp_path, http_get):
    filename = tmp_path / PYTHON_EGG_FILENAME
    with open(filename, mode="wb") as f:
        f.write(http_get(PYTHON_URL))
    yield filename


@pytest.mark.parallel
def test_domain_content_upload(
    domain_factory,
    pulpcore_bindings,
    python_bindings,
    python_file,
    monitor_task,
):
    """Test uploading of file content with domains."""
    domain = domain_factory()

    content_body = {"relative_path": PYTHON_EGG_FILENAME, "file": python_file}
    task = python_bindings.ContentPackagesApi.create(**content_body).task
    response = monitor_task(task)
    default_content = python_bindings.ContentPackagesApi.read(response.created_resources[0])
    default_artifact_href = default_content.artifact

    # Try to create content in second domain with default domain's artifact
    with pytest.raises(python_bindings.ApiException) as e:
        content_body = {"relative_path": PYTHON_EGG_FILENAME, "artifact": default_artifact_href}
        python_bindings.ContentPackagesApi.create(**content_body, pulp_domain=domain.name)
    assert e.value.status == 400
    assert json.loads(e.value.body) == {
        "non_field_errors": [f"Objects must all be apart of the {domain.name} domain."]
    }

    # Now create the same content in the second domain
    content_body = {"relative_path": PYTHON_EGG_FILENAME, "file": python_file}
    task2 = python_bindings.ContentPackagesApi.create(**content_body, pulp_domain=domain.name).task
    response = monitor_task(task2)
    domain_content = python_bindings.ContentPackagesApi.read(response.created_resources[0])
    domain_artifact_href = domain_content.artifact

    assert default_content.pulp_href != domain_content.pulp_href
    assert default_artifact_href != domain_artifact_href
    assert default_content.sha256 == domain_content.sha256
    assert default_content.filename == domain_content.filename

    domain_contents = python_bindings.ContentPackagesApi.list(pulp_domain=domain.name)
    assert domain_contents.count == 1

    # Content needs to be deleted for the domain to be deleted
    body = {"orphan_protection_time": 0}
    task = pulpcore_bindings.OrphansCleanupApi.cleanup(body, pulp_domain=domain.name).task
    monitor_task(task)

    domain_contents = python_bindings.ContentPackagesApi.list(pulp_domain=domain.name)
    assert domain_contents.count == 0


@pytest.mark.parallel
def test_domain_content_replication(
    domain_factory,
    bindings_cfg,
    pulp_settings,
    pulpcore_bindings,
    python_bindings,
    python_file,
    python_repo_factory,
    python_publication_factory,
    python_distribution_factory,
    monitor_task,
    monitor_task_group,
    gen_object_with_cleanup,
    add_to_cleanup,
):
    """Test replication feature through the usage of domains."""
    # Set up source domain to replicate from
    source_domain = domain_factory()
    repo = python_repo_factory(pulp_domain=source_domain.name)
    body = {"relative_path": PYTHON_EGG_FILENAME, "file": python_file, "repository": repo.pulp_href}
    monitor_task(
        python_bindings.ContentPackagesApi.create(pulp_domain=source_domain.name, **body).task
    )
    pub = python_publication_factory(repository=repo, pulp_domain=source_domain.name)
    python_distribution_factory(publication=pub.pulp_href, pulp_domain=source_domain.name)

    # Create the replica domain
    replica_domain = domain_factory()
    upstream_pulp_body = {
        "name": str(uuid.uuid4()),
        "base_url": bindings_cfg.host,
        "api_root": pulp_settings.API_ROOT,
        "domain": source_domain.name,
        "username": bindings_cfg.username,
        "password": bindings_cfg.password,
    }
    upstream_pulp = gen_object_with_cleanup(
        pulpcore_bindings.UpstreamPulpsApi, upstream_pulp_body, pulp_domain=replica_domain.name
    )
    # Run the replicate task and assert that all tasks successfully complete.
    response = pulpcore_bindings.UpstreamPulpsApi.replicate(upstream_pulp.pulp_href)
    monitor_task_group(response.task_group)

    counts = {}
    for api_client in (
        python_bindings.ContentPackagesApi,
        python_bindings.RepositoriesPythonApi,
        python_bindings.RemotesPythonApi,
        python_bindings.PublicationsPypiApi,
        python_bindings.DistributionsPypiApi,
    ):
        result = api_client.list(pulp_domain=replica_domain.name)
        counts[api_client] = result.count
        for item in result.results:
            add_to_cleanup(api_client, item.pulp_href)

    assert all(1 == x for x in counts.values()), f"Replica had more than 1 object {counts}"


@pytest.fixture
def shelf_reader_cleanup():
    """Take care of uninstalling shelf-reader before/after the test."""
    cmd = ("pip", "uninstall", "shelf-reader", "-y")
    subprocess.run(cmd)
    yield
    subprocess.run(cmd)


@pytest.mark.parallel
def test_domain_pypi_apis(
    domain_factory,
    pulpcore_bindings,
    monitor_task,
    python_file,
    python_repo_factory,
    python_distribution_factory,
    pulp_admin_user,
    http_get,
    shelf_reader_cleanup,
):
    """Test the PyPI apis with upload & download through python tooling (twine/pip)."""
    domain = domain_factory()
    repo = python_repo_factory(pulp_domain=domain.name)
    distro = python_distribution_factory(repository=repo.pulp_href, pulp_domain=domain.name)

    response = json.loads(http_get(distro.base_url))
    assert response["projects"] == response["releases"] == response["files"] == 0

    # Test upload
    subprocess.run(
        (
            "twine",
            "upload",
            "--repository-url",
            distro.base_url + "simple/",
            python_file,
            "-u",
            pulp_admin_user.username,
            "-p",
            pulp_admin_user.password,
        ),
        capture_output=True,
        check=True,
    )
    results = pulpcore_bindings.TasksApi.list(
        reserved_resources=repo.pulp_href, pulp_domain=domain.name
    )
    monitor_task(results.results[0].pulp_href)
    response = json.loads(http_get(distro.base_url))
    assert response["projects"] == response["releases"] == response["files"] == 1

    # Test download
    subprocess.run(
        (
            "pip",
            "install",
            "--no-deps",
            "--trusted-host",
            urlsplit(distro.base_url).hostname,
            "-i",
            distro.base_url + "simple/",
            "shelf-reader",
        ),
        capture_output=True,
        check=True,
    )
