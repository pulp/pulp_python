from urllib.parse import urljoin

import pytest
import requests

from pulp_python.tests.functional.constants import PYTHON_SM_PROJECT_SPECIFIER


@pytest.mark.parallel
def test_simple_json_api(python_remote_factory, python_repo_with_sync, python_distribution_factory):
    remote = python_remote_factory(includes=PYTHON_SM_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)
    distro = python_distribution_factory(repository=repo)

    index_url = urljoin(distro.base_url, "simple/")
    detail_url = f"{index_url}aiohttp"
    headers = {"Accept": "application/vnd.pypi.simple.v1+json"}

    response_index = requests.get(index_url, headers=headers)
    data_index = response_index.json()
    assert data_index["meta"] == {"api-version": "1.4", "_last-serial": 1000000000}
    assert data_index["projects"]
    for project in data_index["projects"]:
        for i in ["_last-serial", "name"]:
            assert project[i]
    assert response_index.headers["Content-Type"] == "application/vnd.pypi.simple.v1+json"
    assert response_index.headers["X-PyPI-Last-Serial"] == "1000000000"

    response_detail = requests.get(detail_url, headers=headers)
    data_detail = response_detail.json()
    assert data_detail["meta"] == {"api-version": "1.4", "_last-serial": 1000000000}
    assert data_detail["name"] == "aiohttp"
    assert data_detail["files"]
    for file in data_detail["files"]:
        for i in ["filename", "url", "hashes"]:
            assert file[i]
    assert response_detail.headers["Content-Type"] == "application/vnd.pypi.simple.v1+json"
    assert response_detail.headers["X-PyPI-Last-Serial"] == "1000000000"


@pytest.mark.parametrize(
    "header, result",
    [
        ("text/html", "text/html"),
        ("application/vnd.pypi.simple.v1+html", "application/vnd.pypi.simple.v1+html"),
        ("application/vnd.pypi.simple.v1+json", "application/vnd.pypi.simple.v1+json"),
        # Follows defined ordering (html, pypi html, pypi json)
        (
            "application/vnd.pypi.simple.v1+json, application/vnd.pypi.simple.v1+html",
            "application/vnd.pypi.simple.v1+html",
        ),
        # Everything else should be html
        ("", "text/html"),
        ("application/json", "text/html"),
        ("sth/else", "text/html"),
    ],
)
def test_simple_json_api_headers(
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
