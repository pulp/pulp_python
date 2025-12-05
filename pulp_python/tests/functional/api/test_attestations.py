import pytest
import json
import requests
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urljoin

from pypi_simple import PyPISimple

from pulpcore.tests.functional.utils import PulpTaskError


@pytest.fixture(scope="session")
def twine_package():
    """Returns the twine package."""
    filename = "twine-6.2.0.tar.gz"
    with PyPISimple() as client:
        page = client.get_project_page("twine")
        for package in page.packages:
            if package.filename == filename:
                return package

    raise ValueError("Twine package not found")


def get_attestations(provenance_url):
    """Get the attestations from the provenance url."""
    r = requests.get(provenance_url)
    assert r.status_code == 200
    prov = r.json()
    return prov["attestation_bundles"][0]["attestations"]


@pytest.mark.parallel
def test_crd_provenance(python_bindings, twine_package, python_content_factory, monitor_task):
    """
    Test creating and reading a provenance.
    """
    content = python_content_factory(relative_path=twine_package.filename, url=twine_package.url)

    provenance = python_bindings.ContentProvenanceApi.create(
        package=content.pulp_href,
        file_url=twine_package.provenance_url,
    )
    task = monitor_task(provenance.task)
    provenance = python_bindings.ContentProvenanceApi.read(task.created_resources[-1])
    assert provenance.package == content.pulp_href
    r = requests.get(twine_package.provenance_url)
    assert r.status_code == 200
    assert r.json() == provenance.provenance


@pytest.mark.parallel
def test_verify_provenance(python_bindings, twine_package, python_content_factory, monitor_task):
    """
    Test verifying a provenance.
    """
    wrong_content = python_content_factory(
        relative_path=twine_package.filename, url=twine_package.url
    )
    prov_url = twine_package.provenance_url.replace(
        "twine-6.2.0.tar.gz", "twine-6.2.0-py3-none-any.whl"
    )
    provenance = python_bindings.ContentProvenanceApi.create(
        package=wrong_content.pulp_href,
        file_url=prov_url,
    )
    with pytest.raises(PulpTaskError) as e:
        monitor_task(provenance.task)
    assert e.value.task.state == "failed"
    assert "twine-6.2.0-py3-none-any.whl != twine-6.2.0.tar.gz" in e.value.task.error["description"]

    # Test creating a provenance without verifying
    provenance = python_bindings.ContentProvenanceApi.create(
        package=wrong_content.pulp_href,
        file_url=twine_package.provenance_url,
        verify=False,
    )
    task = monitor_task(provenance.task)
    provenance = python_bindings.ContentProvenanceApi.read(task.created_resources[-1])
    assert provenance.package == wrong_content.pulp_href


@pytest.mark.parallel
def test_integrity_api(
    python_bindings,
    python_repo,
    python_distribution_factory,
    twine_package,
    python_content_factory,
    monitor_task,
):
    """
    Test the integrity API.
    """
    content = python_content_factory(
        relative_path=twine_package.filename,
        repository=python_repo.pulp_href,
        url=twine_package.url,
    )
    provenance = python_bindings.ContentProvenanceApi.create(
        package=content.pulp_href,
        file_url=twine_package.provenance_url,
        repository=python_repo.pulp_href,
    )
    task = monitor_task(provenance.task)
    provenance = python_bindings.ContentProvenanceApi.read(task.created_resources[-1])

    distro = python_distribution_factory(repository=python_repo.pulp_href)
    url = f"{distro.base_url}integrity/twine/6.2.0/{twine_package.filename}/provenance/"
    r = requests.get(url)
    assert r.status_code == 200
    assert r.json() == provenance.provenance


@pytest.mark.parallel
def test_attestation_upload(python_bindings, twine_package, monitor_task):
    """Check that attestations can be uploaded along with a package."""
    attestations = get_attestations(twine_package.provenance_url)
    body = {
        "relative_path": twine_package.filename,
        "file_url": twine_package.url,
        "attestations": json.dumps(attestations),
    }
    task = python_bindings.ContentPackagesApi.create(**body).task
    response = monitor_task(task)

    assert len(response.created_resources) == 2
    prov = python_bindings.ContentProvenanceApi.read(response.created_resources[1])
    assert prov.package == response.created_resources[0]
    att_bundle = prov.provenance["attestation_bundles"][0]
    assert att_bundle["attestations"] == attestations
    assert att_bundle["publisher"]["kind"] == "Pulp User"


@pytest.mark.parallel
def test_attestation_sync_upload(python_bindings, twine_package, download_python_file):
    """Check that attestations can be uploaded along with a package."""
    attestations = get_attestations(twine_package.provenance_url)
    body = {
        "file": download_python_file(twine_package.filename, twine_package.url),
        "attestations": json.dumps(attestations),
    }
    content = python_bindings.ContentPackagesApi.upload(**body)

    assert content.provenance is not None
    provs = python_bindings.ContentProvenanceApi.list(prn__in=[content.provenance])
    assert len(provs.results) == 1
    prov = provs.results[0]
    assert prov.package == content.pulp_href
    att_bundle = prov.provenance["attestation_bundles"][0]
    assert att_bundle["attestations"] == attestations
    assert att_bundle["publisher"]["kind"] == "Pulp User"


def test_attestation_twine_upload(
    pulpcore_bindings,
    python_content_summary,
    python_empty_repo_distro,
    python_package_dist_directory,
    monitor_task,
):
    """Tests that packages with attestations can be properly uploaded through Twine."""
    repo, distro = python_empty_repo_distro()
    url = urljoin(distro.base_url, "legacy/")
    dist_dir, _, _ = python_package_dist_directory

    # Copy attestation files from test assets to dist_dir
    assets_dir = Path(__file__).parent.parent / "assets"
    attestation_files = [
        "shelf-reader-0.1.tar.gz.publish.attestation",
        "shelf_reader-0.1-py2-none-any.whl.publish.attestation",
    ]
    for attestation_file in attestation_files:
        src = assets_dir / attestation_file
        dst = dist_dir / attestation_file
        shutil.copy2(src, dst)

    username, password = "admin", "password"
    subprocess.run(
        (
            "twine",
            "upload",
            "--attestations",
            "--repository-url",
            url,
            dist_dir / "*",
            "-u",
            username,
            "-p",
            password,
        ),
        capture_output=True,
        check=True,
    )
    tasks = pulpcore_bindings.TasksApi.list(reserved_resources=repo.pulp_href).results
    for task in reversed(tasks):
        t = monitor_task(task.pulp_href)
        repo_ver_href = t.created_resources[0]

    assert repo_ver_href.endswith("versions/2/")
    summary = python_content_summary(repository_version=repo_ver_href)
    assert summary.present["python.python"]["count"] == 2
    assert summary.present["python.provenance"]["count"] == 2


@pytest.mark.parallel
def test_bad_attestation_upload(python_bindings, twine_package, monitor_task):
    """Check that bad attestations are rejected."""
    attestations = get_attestations(twine_package.provenance_url)
    attestation = attestations[0]
    attestation["version"] = 2  # Only version 1 is supported
    body = {
        "relative_path": twine_package.filename,
        "file_url": twine_package.url,
        "attestations": json.dumps(attestations),
    }
    with pytest.raises(python_bindings.ApiException) as e:
        python_bindings.ContentPackagesApi.create(**body)
    assert e.value.status == 400
    assert "Invalid attestations" in e.value.body

    attestation["version"] = 1
    del attestation["envelope"]
    body["attestations"] = json.dumps(attestations)
    with pytest.raises(python_bindings.ApiException) as e:
        python_bindings.ContentPackagesApi.create(**body)
    assert e.value.status == 400
    assert "Invalid attestations" in e.value.body

    # Upload valid but wrong attestation
    prov_url = twine_package.provenance_url.replace(
        "twine-6.2.0.tar.gz", "twine-6.2.0-py3-none-any.whl"
    )
    attestations = get_attestations(prov_url)
    body["attestations"] = json.dumps(attestations)
    task = python_bindings.ContentPackagesApi.create(**body).task
    with pytest.raises(PulpTaskError) as e:
        monitor_task(task)
    assert e.value.task.state == "failed"
    assert "Attestations failed verification" in e.value.task.error["description"]
