import pytest
import requests
import subprocess

from pulp_python.tests.functional.constants import (
    PYPI_URL,
    PYTHON_XS_FIXTURE_CHECKSUMS,
    PYTHON_SM_PROJECT_SPECIFIER,
    PYTHON_SM_FIXTURE_RELEASES,
)

from pypi_simple import ProjectPage
from packaging.version import parse
from urllib.parse import urljoin, urlsplit
from random import sample


def test_pull_through_install(
    python_bindings, python_remote_factory, python_distribution_factory, delete_orphans_pre
):
    """Tests that a pull-through distro can be installed from."""
    remote = python_remote_factory(url=PYPI_URL, includes=[])
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
    remote = python_remote_factory(url=PYPI_URL, includes=["shelf-reader"])
    distro = python_distribution_factory(remote=remote.pulp_href)

    url = f"{distro.base_url}simple/shelf-reader/"
    project_page = ProjectPage.from_response(requests.get(url), "shelf-reader")

    assert len(project_page.packages) == 2
    for package in project_page.packages:
        assert package.filename in PYTHON_XS_FIXTURE_CHECKSUMS
        relative_path = f"{distro.base_path}/{package.filename}?redirect="
        assert urljoin(pulp_content_url, relative_path) in package.url
        assert PYTHON_XS_FIXTURE_CHECKSUMS[package.filename] == package.digests["sha256"]


@pytest.mark.parallel
def test_pull_through_filter(python_remote_factory, python_distribution_factory):
    """Tests that pull-through respects the includes/excludes filter on the remote."""
    remote = python_remote_factory(url=PYPI_URL, includes=["shelf-reader"])
    distro = python_distribution_factory(remote=remote.pulp_href)

    r = requests.get(f"{distro.base_url}simple/pulpcore/")
    assert r.status_code == 404
    assert r.json() == {"detail": "pulpcore does not exist."}

    r = requests.get(f"{distro.base_url}simple/shelf-reader/")
    assert r.status_code == 200

    # Test complex include specifiers
    remote = python_remote_factory(includes=PYTHON_SM_PROJECT_SPECIFIER)
    distro = python_distribution_factory(remote=remote.pulp_href)
    for package, releases in PYTHON_SM_FIXTURE_RELEASES.items():
        url = f"{distro.base_url}simple/{package}/"
        project_page = ProjectPage.from_response(requests.get(url), package)
        packages = {p.filename for p in project_page.packages if not parse(p.version).is_prerelease}
        assert packages == set(releases)

    # Test exclude logic
    remote = python_remote_factory(includes=[], excludes=["django"])
    distro = python_distribution_factory(remote=remote.pulp_href)

    r = requests.get(f"{distro.base_url}simple/django/")
    assert r.status_code == 404
    assert r.json() == {"detail": "django does not exist."}

    r = requests.get(f"{distro.base_url}simple/pulpcore/")
    assert r.status_code == 502
    assert r.text == f"Failed to fetch pulpcore from {remote.url}."

    r = requests.get(f"{distro.base_url}simple/shelf-reader/")
    assert r.status_code == 200


@pytest.mark.parallel
def test_pull_through_with_repo(
    python_repo_factory,
    python_remote_factory,
    python_distribution_factory,
    python_bindings,
    pulpcore_bindings,
    monitor_task,
    has_pulp_plugin,
):
    """Tests that content is saved to repository."""
    remote = python_remote_factory(includes=[])
    repo = python_repo_factory()
    distro = python_distribution_factory(repository=repo.pulp_href, remote=remote.pulp_href)

    # Perform a download of aiohttp to ensure it's saved to the repo
    url = urljoin(distro.base_url, "simple/aiohttp/")
    project_page = ProjectPage.from_response(requests.get(url), "aiohttp")
    for package in sample(project_page.packages, 3):
        assert "?redirect=" in package.url
        r = requests.get(package.url)
        assert r.status_code == 200

    if has_pulp_plugin("core", max="3.73"):
        pytest.skip("Pull-through repository save added in 3.74")

    tasks = pulpcore_bindings.TasksApi.list(reserved_resources=repo.prn)
    assert tasks.count == 3

    for task in tasks.results:
        monitor_task(task.pulp_href)

    repo = python_bindings.RepositoriesPythonApi.read(repo.pulp_href)
    assert repo.latest_version_href[-2] == "3"
    content = python_bindings.ContentPackagesApi.list(repository_version=repo.latest_version_href)
    assert content.count == 3

    # Check that getting content that is already present doesn't trigger a task
    r = requests.get(package.url)
    assert r.status_code == 200
    tasks = pulpcore_bindings.TasksApi.list(reserved_resources=repo.prn)
    assert tasks.count == 3
