from urllib.parse import urljoin

import pytest
import requests

from pulp_python.tests.functional.constants import (
    PYPI_SERIAL_CONSTANT,
    PYTHON_SM_FIXTURE_CHECKSUMS,
    PYTHON_SM_FIXTURE_RELEASES,
    PYTHON_SM_PROJECT_SPECIFIER,
    TWINE_EGG_FILENAME,
    TWINE_EGG_REQUIRES_PYTHON,
    TWINE_EGG_SHA256,
    TWINE_EGG_SIZE,
    TWINE_EGG_URL,
    TWINE_FIXTURE_CHECKSUMS,
    TWINE_FIXTURE_METADATA_SHA256,
    TWINE_FIXTURE_REQUIRES_PYTHON,
    TWINE_WHEEL_FILENAME,
    TWINE_WHEEL_METADATA_SHA256,
    TWINE_WHEEL_REQUIRES_PYTHON,
    TWINE_WHEEL_SHA256,
    TWINE_WHEEL_SIZE,
    TWINE_WHEEL_URL,
)
from pulp_python.tests.functional.utils import ensure_simple

API_VERSION = "1.1"

PYPI_TEXT_HTML = "text/html"
PYPI_SIMPLE_V1_HTML = "application/vnd.pypi.simple.v1+html"
PYPI_SIMPLE_V1_JSON = "application/vnd.pypi.simple.v1+json"


@pytest.mark.parallel
def test_simple_html_index_api(
    python_remote_factory, python_repo_with_sync, python_distribution_factory
):
    remote = python_remote_factory(includes=PYTHON_SM_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)
    distro = python_distribution_factory(repository=repo)

    url = urljoin(distro.base_url, "simple/")
    headers = {"Accept": PYPI_SIMPLE_V1_HTML}

    response = requests.get(url, headers=headers)
    assert response.headers["Content-Type"] == PYPI_SIMPLE_V1_HTML
    assert response.headers["X-PyPI-Last-Serial"] == str(PYPI_SERIAL_CONSTANT)

    proper, msgs = ensure_simple(
        url, PYTHON_SM_FIXTURE_RELEASES, sha_digests=PYTHON_SM_FIXTURE_CHECKSUMS
    )
    assert proper, f"Simple API validation failed: {msgs}"


def test_simple_html_detail_api(
    delete_orphans_pre,
    monitor_task,
    python_bindings,
    python_content_factory,
    python_distribution_factory,
    python_repo_factory,
):
    content_1 = python_content_factory(TWINE_WHEEL_FILENAME, url=TWINE_WHEEL_URL)
    content_2 = python_content_factory(TWINE_EGG_FILENAME, url=TWINE_EGG_URL)
    body = {"add_content_units": [content_1.pulp_href, content_2.pulp_href]}

    repo = python_repo_factory()
    monitor_task(python_bindings.RepositoriesPythonApi.modify(repo.pulp_href, body).task)
    distro = python_distribution_factory(repository=repo)

    url = f'{urljoin(distro.base_url, "simple/")}twine'
    headers = {"Accept": PYPI_SIMPLE_V1_HTML}

    response = requests.get(url, headers=headers)
    assert response.headers["Content-Type"] == PYPI_SIMPLE_V1_HTML
    assert response.headers["X-PyPI-Last-Serial"] == str(PYPI_SERIAL_CONSTANT)

    proper, msgs = ensure_simple(
        urljoin(distro.base_url, "simple/"),
        {"twine": [TWINE_WHEEL_FILENAME, TWINE_EGG_FILENAME]},
        sha_digests=TWINE_FIXTURE_CHECKSUMS,
        metadata_sha_digests=TWINE_FIXTURE_METADATA_SHA256,
        requires_python=TWINE_FIXTURE_REQUIRES_PYTHON,
    )
    assert proper, f"Simple API validation failed: {msgs}"


@pytest.mark.parallel
def test_simple_json_index_api(
    python_remote_factory, python_repo_with_sync, python_distribution_factory
):
    remote = python_remote_factory(includes=PYTHON_SM_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)
    distro = python_distribution_factory(repository=repo)

    url = urljoin(distro.base_url, "simple/")
    headers = {"Accept": PYPI_SIMPLE_V1_JSON}

    response = requests.get(url, headers=headers)
    assert response.headers["Content-Type"] == PYPI_SIMPLE_V1_JSON
    assert response.headers["X-PyPI-Last-Serial"] == str(PYPI_SERIAL_CONSTANT)

    data = response.json()
    assert data["meta"] == {"api-version": API_VERSION, "_last-serial": PYPI_SERIAL_CONSTANT}
    assert data["projects"]
    for project in data["projects"]:
        for i in ["_last-serial", "name"]:
            assert i in project


def test_simple_json_detail_api(
    delete_orphans_pre,
    monitor_task,
    python_bindings,
    python_content_factory,
    python_distribution_factory,
    python_repo_factory,
):
    content_1 = python_content_factory(TWINE_WHEEL_FILENAME, url=TWINE_WHEEL_URL)
    content_2 = python_content_factory(TWINE_EGG_FILENAME, url=TWINE_EGG_URL)
    body = {"add_content_units": [content_1.pulp_href, content_2.pulp_href]}

    repo = python_repo_factory()
    monitor_task(python_bindings.RepositoriesPythonApi.modify(repo.pulp_href, body).task)
    distro = python_distribution_factory(repository=repo)

    url = f'{urljoin(distro.base_url, "simple/")}twine'
    headers = {"Accept": PYPI_SIMPLE_V1_JSON}

    response = requests.get(url, headers=headers)
    assert response.headers["Content-Type"] == PYPI_SIMPLE_V1_JSON
    assert response.headers["X-PyPI-Last-Serial"] == str(PYPI_SERIAL_CONSTANT)

    data = response.json()
    assert data["meta"] == {"api-version": API_VERSION, "_last-serial": PYPI_SERIAL_CONSTANT}
    assert data["name"] == "twine"
    assert data["files"]
    assert data["versions"] == ["5.1.0"]

    # Check data of a wheel
    file_whl = next((i for i in data["files"] if i["filename"] == TWINE_WHEEL_FILENAME), None)
    assert file_whl is not None, "wheel file not found"
    assert file_whl["url"]
    assert file_whl["hashes"] == {"sha256": TWINE_WHEEL_SHA256}
    assert file_whl["requires-python"] == TWINE_WHEEL_REQUIRES_PYTHON
    assert file_whl["data-dist-info-metadata"] == {"sha256": TWINE_WHEEL_METADATA_SHA256}
    assert file_whl["core-metadata"] == {"sha256": TWINE_WHEEL_METADATA_SHA256}
    assert file_whl["size"] == TWINE_WHEEL_SIZE
    assert file_whl["upload-time"] is not None
    assert file_whl["provenance"] is None

    # Check data of a tarball
    file_tar = next((i for i in data["files"] if i["filename"] == TWINE_EGG_FILENAME), None)
    assert file_tar is not None, "tar file not found"
    assert file_tar["url"]
    assert file_tar["hashes"] == {"sha256": TWINE_EGG_SHA256}
    assert file_tar["requires-python"] == TWINE_EGG_REQUIRES_PYTHON
    assert file_tar["data-dist-info-metadata"] is False
    assert file_tar["core-metadata"] is False
    assert file_tar["size"] == TWINE_EGG_SIZE
    assert file_tar["upload-time"] is not None
    assert file_tar["provenance"] is None


@pytest.mark.parallel
@pytest.mark.parametrize(
    "header, result",
    [
        (PYPI_TEXT_HTML, PYPI_TEXT_HTML),
        (PYPI_SIMPLE_V1_HTML, PYPI_SIMPLE_V1_HTML),
        (PYPI_SIMPLE_V1_JSON, PYPI_SIMPLE_V1_JSON),
        # Follows defined ordering (html, pypi html, pypi json)
        (f"{PYPI_SIMPLE_V1_JSON}, {PYPI_SIMPLE_V1_HTML}", PYPI_SIMPLE_V1_HTML),
        # Everything else should be html
        ("", PYPI_TEXT_HTML),
        ("application/json", PYPI_TEXT_HTML),
        ("sth/else", PYPI_TEXT_HTML),
    ],
)
def test_simple_api_content_headers(
    python_remote_factory, python_repo_with_sync, python_distribution_factory, header, result
):
    remote = python_remote_factory(includes=PYTHON_SM_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)
    distro = python_distribution_factory(repository=repo)

    index_url = urljoin(distro.base_url, "simple/")
    detail_url = f"{index_url}aiohttp"

    for url in [index_url, detail_url]:
        response = requests.get(url, headers={"Accept": header})
        assert response.status_code == 200
        assert result in response.headers["Content-Type"]
