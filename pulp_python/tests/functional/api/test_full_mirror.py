import pytest
import requests
import subprocess

from pulp_python.tests.functional.constants import (
    PYPI_URL,
    PYTHON_XS_FIXTURE_CHECKSUMS,
)

from pypi_simple import parse_repo_project_response
from urllib.parse import urljoin, urlsplit


def test_pull_through_install(
    python_bindings, python_remote_factory, python_distribution_factory, delete_orphans_pre
):
    """Tests that a pull-through distro can be installed from."""
    remote = python_remote_factory(url=PYPI_URL)
    distro = python_distribution_factory(remote=remote.pulp_href)
    PACKAGE = "pulpcore-releases"

    # Check if already installed
    stdout = subprocess.run(("pip", "list"), capture_output=True).stdout.decode("utf-8")
    if stdout.find(PACKAGE) != -1:
        subprocess.run(("pip", "uninstall", PACKAGE, "-y"))

    # Perform pull-through install
    host = urlsplit(distro.base_url).hostname
    url = f"{distro.base_url}simple/"
    cmd = ("pip", "install", "--trusted-host", host, "-i", url, PACKAGE)
    subprocess.run(cmd, check=True)

    stdout = subprocess.run(("pip", "list"), capture_output=True).stdout.decode("utf-8")
    assert stdout.find(PACKAGE) != -1
    subprocess.run(("pip", "uninstall", PACKAGE, "-y"))
    content = python_bindings.ContentPackagesApi.list(name=PACKAGE)
    assert content.count == 1


@pytest.mark.parallel
def test_pull_through_simple(python_remote_factory, python_distribution_factory, pulp_content_url):
    """Tests that the simple page is properly modified when requesting a pull-through."""
    remote = python_remote_factory(url=PYPI_URL)
    distro = python_distribution_factory(remote=remote.pulp_href)

    url = f"{distro.base_url}simple/shelf-reader/"
    project_page = parse_repo_project_response("shelf-reader", requests.get(url))

    assert len(project_page.packages) == 2
    for package in project_page.packages:
        assert package.filename in PYTHON_XS_FIXTURE_CHECKSUMS
        relative_path = f"{distro.base_path}/{package.filename}?redirect="
        assert urljoin(pulp_content_url, relative_path) in package.url
        digests = package.get_digests()
        assert PYTHON_XS_FIXTURE_CHECKSUMS[package.filename] == digests["sha256"]


@pytest.mark.parallel
def test_pull_through_with_repo(
    python_repo_with_sync, python_remote_factory, python_distribution_factory
):
    """Tests that if content is already in repository, pull-through isn't used."""
    remote = python_remote_factory()
    repo = python_repo_with_sync(remote)
    distro = python_distribution_factory(repository=repo.pulp_href, remote=remote.pulp_href)

    url = urljoin(distro.base_url, "simple/shelf-reader/")
    project_page = parse_repo_project_response("shelf-reader", requests.get(url))

    assert len(project_page.packages) == 2
    for package in project_page.packages:
        assert package.filename in PYTHON_XS_FIXTURE_CHECKSUMS
        assert "?redirect=" not in package.url
