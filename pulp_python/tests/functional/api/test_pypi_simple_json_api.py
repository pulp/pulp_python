from urllib.parse import urljoin

import pytest
import requests

from pulp_python.tests.functional.constants import (
    PYTHON_EGG_FILENAME,
    PYTHON_EGG_URL,
    PYTHON_SM_PROJECT_SPECIFIER,
    PYTHON_WHEEL_FILENAME,
    PYTHON_WHEEL_URL,
)

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


def test_simple_json_detail_api(
    delete_orphans_pre,
    monitor_task,
    python_bindings,
    python_content_factory,
    python_distribution_factory,
    python_repo_factory,
):
    content_1 = python_content_factory(PYTHON_WHEEL_FILENAME, url=PYTHON_WHEEL_URL)
    content_2 = python_content_factory(PYTHON_EGG_FILENAME, url=PYTHON_EGG_URL)
    body = {"add_content_units": [content_1.pulp_href, content_2.pulp_href]}

    repo = python_repo_factory()
    monitor_task(python_bindings.RepositoriesPythonApi.modify(repo.pulp_href, body).task)
    distro = python_distribution_factory(repository=repo)

    url = f'{urljoin(distro.base_url, "simple/")}shelf-reader'
    headers = {"Accept": PYPI_SIMPLE_V1_JSON}

    response = requests.get(url, headers=headers)
    assert response.headers["Content-Type"] == PYPI_SIMPLE_V1_JSON
    assert response.headers["X-PyPI-Last-Serial"] == str(PYPI_SERIAL_CONSTANT)

    data = response.json()
    assert data["meta"] == {"api-version": API_VERSION, "_last-serial": PYPI_SERIAL_CONSTANT}
    assert data["name"] == "shelf-reader"
    assert data["files"]

    # Check data of a wheel
    file_whl = next(
        (i for i in data["files"] if i["filename"] == "shelf_reader-0.1-py2-none-any.whl"), None
    )
    assert file_whl is not None, "wheel file not found"
    assert file_whl["url"]
    assert file_whl["hashes"] == {
        "sha256": "2eceb1643c10c5e4a65970baf63bde43b79cbdac7de81dae853ce47ab05197e9"
    }
    assert file_whl["requires-python"] is None
    assert file_whl["data-dist-info-metadata"] == {
        "sha256": "ed333f0db05d77e933a157b7225b403ada9a2f93318d77b41b662eba78bac350"
    }

    # Check data of a tarball
    file_tar = next((i for i in data["files"] if i["filename"] == "shelf-reader-0.1.tar.gz"), None)
    assert file_tar is not None, "tar file not found"
    assert file_tar["url"]
    assert file_tar["hashes"] == {
        "sha256": "04cfd8bb4f843e35d51bfdef2035109bdea831b55a57c3e6a154d14be116398c"
    }
    assert file_tar["requires-python"] is None
    assert file_tar["data-dist-info-metadata"] is False


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
