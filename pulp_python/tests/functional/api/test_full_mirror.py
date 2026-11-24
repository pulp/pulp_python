import subprocess
from hashlib import sha256
from urllib.parse import urljoin, urlsplit

import pytest
import requests
from pypi_simple import ProjectPage

from pulp_python.tests.functional.constants import (
    PYPI_URL,
    PYTHON_XS_FIXTURE_CHECKSUMS,
)


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
    project_page = ProjectPage.from_response(requests.get(url), "shelf-reader")

    assert len(project_page.packages) == 2
    for package in project_page.packages:
        assert package.filename in PYTHON_XS_FIXTURE_CHECKSUMS
        relative_path = f"{distro.base_path}/{package.filename}?pt="
        assert urljoin(pulp_content_url, relative_path) in package.url
        assert PYTHON_XS_FIXTURE_CHECKSUMS[package.filename] == package.digests["sha256"]


@pytest.mark.parallel
def test_pull_through_with_repo(
    python_repo_with_sync, python_remote_factory, python_distribution_factory
):
    """Tests that if content is already in repository, pull-through isn't used."""
    remote = python_remote_factory()
    repo = python_repo_with_sync(remote)
    distro = python_distribution_factory(repository=repo.pulp_href, remote=remote.pulp_href)

    url = urljoin(distro.base_url, "simple/shelf-reader/")
    project_page = ProjectPage.from_response(requests.get(url), "shelf-reader")

    assert len(project_page.packages) == 2
    for package in project_page.packages:
        assert package.filename in PYTHON_XS_FIXTURE_CHECKSUMS
        assert "?pt=" not in package.url


@pytest.mark.parallel
def test_pull_through_rejects_bad_links(python_remote_factory, python_distribution_factory):
    """Test that pull-through only downloads from a valid signed link."""
    remote = python_remote_factory(url=PYPI_URL)
    distro = python_distribution_factory(remote=remote.pulp_href)
    remote2 = python_remote_factory(url=PYPI_URL)
    distro2 = python_distribution_factory(remote=remote2.pulp_href)
    url = f"{distro.base_url}simple/shelf-reader/"

    package1, package2 = ProjectPage.from_response(requests.get(url), "shelf-reader").packages
    token = package1.url.split("?pt=", 1)[1]

    wrong_file_url = package2.url.split("?pt=", 1)[0] + f"?pt={token}"
    assert requests.get(wrong_file_url).status_code == 404

    wrong_remote_url = package1.url.replace(f"/{distro.base_path}/", f"/{distro2.base_path}/")
    assert requests.get(wrong_remote_url).status_code == 404

    unsigned_url = package1.url.split("?pt=", 1)[0]
    assert requests.get(unsigned_url).status_code == 404

    response = requests.get(package1.url)
    assert response.status_code == 200
    assert sha256(response.content).hexdigest() == PYTHON_XS_FIXTURE_CHECKSUMS[package1.filename]
