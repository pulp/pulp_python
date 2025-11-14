import pytest
import requests

from pypi_simple import PyPISimple

from pulpcore.tests.functional.utils import PulpTaskError
from pulp_python.tests.functional.constants import TWINE_READABLE_PROVENANCE


@pytest.mark.parallel
def test_crd_provenance(python_bindings, python_content_factory, monitor_task, bindings_cfg):
    """
    Test creating and reading a provenance.
    """
    filename = "twine-6.2.0-py3-none-any.whl"
    with PyPISimple() as client:
        page = client.get_project_page("twine")
        for package in page.packages:
            if package.filename == filename:
                content = python_content_factory(filename, url=package.url)
                break
    provenance = python_bindings.ContentProvenanceApi.create(
        package=content.pulp_href,
        file_url=package.provenance_url,
    )
    task = monitor_task(provenance.task)
    provenance = python_bindings.ContentProvenanceApi.read(task.created_resources[0])
    assert provenance.package == content.pulp_href
    r = requests.get(package.provenance_url)
    assert r.status_code == 200
    assert r.json() == provenance.provenance

    url = f"{bindings_cfg.host}{provenance.pulp_href}?minimal=true"
    r = requests.get(url, auth=(bindings_cfg.username, bindings_cfg.password))
    assert r.status_code == 200
    assert r.json() == TWINE_READABLE_PROVENANCE


@pytest.mark.parallel
def test_verify_provenance(python_bindings, python_content_factory, monitor_task):
    """
    Test verifying a provenance.
    """
    filename = "twine-6.2.0.tar.gz"
    with PyPISimple() as client:
        page = client.get_project_page("twine")
        for package in page.packages:
            if package.filename == filename:
                break
    wrong_content = python_content_factory()  # shelf-reader-0.1.tar.gz
    provenance = python_bindings.ContentProvenanceApi.create(
        package=wrong_content.pulp_href,
        file_url=package.provenance_url,
    )
    with pytest.raises(PulpTaskError) as e:
        monitor_task(provenance.task)
    assert e.value.task.state == "failed"
    assert "twine-6.2.0.tar.gz != shelf-reader-0.1.tar.gz" in e.value.task.error["description"]

    # Test creating a provenance without verifying
    provenance = python_bindings.ContentProvenanceApi.create(
        package=wrong_content.pulp_href,
        file_url=package.provenance_url,
        verify=False,
    )
    task = monitor_task(provenance.task)
    provenance = python_bindings.ContentProvenanceApi.read(task.created_resources[0])
    assert provenance.package == wrong_content.pulp_href
