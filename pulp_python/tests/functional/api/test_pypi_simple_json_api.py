from urllib.parse import urljoin

import pytest
import requests

from pulp_python.tests.functional.constants import PYTHON_SM_PROJECT_SPECIFIER

API_VERSION = "1.0"
PYPI_SERIAL_CONSTANT = 1000000000

PYPI_TEXT_HTML = "text/html"
PYPI_SIMPLE_V1_HTML = "application/vnd.pypi.simple.v1+html"
PYPI_SIMPLE_V1_JSON = "application/vnd.pypi.simple.v1+json"


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


@pytest.mark.parallel
def test_simple_json_detail_api(
    python_remote_factory, python_repo_with_sync, python_distribution_factory
):
    remote = python_remote_factory(includes=PYTHON_SM_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)
    distro = python_distribution_factory(repository=repo)

    url = f'{urljoin(distro.base_url, "simple/")}aiohttp'
    headers = {"Accept": PYPI_SIMPLE_V1_JSON}

    response = requests.get(url, headers=headers)
    assert response.headers["Content-Type"] == PYPI_SIMPLE_V1_JSON
    assert response.headers["X-PyPI-Last-Serial"] == str(PYPI_SERIAL_CONSTANT)

    data = response.json()
    assert data["meta"] == {"api-version": API_VERSION, "_last-serial": PYPI_SERIAL_CONSTANT}
    assert data["name"] == "aiohttp"
    assert data["files"]
    for file in data["files"]:
        for i in [
            "filename",
            "url",
            "hashes",
            "data-dist-info-metadata",
            "requires_python",
            "yanked",
        ]:
            assert i in file


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
