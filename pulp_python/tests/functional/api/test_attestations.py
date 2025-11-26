import pytest
import requests

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
