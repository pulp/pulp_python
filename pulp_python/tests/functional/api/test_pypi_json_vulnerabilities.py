from urllib.parse import urljoin, urlsplit

import pytest
import requests

from pulp_python.tests.functional.constants import (
    PYPI_URL,
    VULNERABILITY_REPORT_TEST_PACKAGE_NAME,
    VULNERABILITY_REPORT_TEST_PACKAGES,
)

WAREHOUSE_VULN_KEYS = {
    "id",
    "source",
    "link",
    "aliases",
    "details",
    "summary",
    "fixed_in",
    "withdrawn",
}


def _index_url(distro, bindings_cfg):
    """Build the index URL using the same origin the API client uses."""
    path = urlsplit(distro.base_url).path
    if not path.endswith("/"):
        path += "/"
    return bindings_cfg.host.rstrip("/") + path


def _wait_for_child_tasks(pulpcore_bindings, monitor_task, parent_task):
    parent = pulpcore_bindings.TasksApi.read(parent_task.pulp_href)
    children = parent.child_tasks or []
    assert children, "expected a follow-up vulnerability scan task"
    for child in children:
        href = child if isinstance(child, str) else child.pulp_href
        monitor_task(href)


def _assert_warehouse_vulnerabilities(package):
    vulns = package["vulnerabilities"]
    assert vulns
    ids = [vuln["id"] for vuln in vulns]
    assert len(ids) == len(set(ids))
    for vuln in vulns:
        assert WAREHOUSE_VULN_KEYS <= vuln.keys()
        assert vuln["source"] == "osv"
        assert vuln["id"]
        assert vuln["link"] == f"https://osv.dev/vulnerability/{vuln['id']}"
        assert isinstance(vuln["aliases"], list)
        assert isinstance(vuln["fixed_in"], list)


@pytest.mark.parallel
def test_pypi_json_vulnerabilities_from_manual_scan(
    bindings_cfg,
    pulpcore_bindings,
    python_bindings,
    python_remote_factory,
    python_repo,
    python_repo_factory,
    python_distribution_factory,
    monitor_task,
):
    """A remote without vulnerabilities does not scan; a later scan fills the JSON API."""
    remote = python_remote_factory(url=PYPI_URL, includes=VULNERABILITY_REPORT_TEST_PACKAGES)
    sync_task = monitor_task(
        python_bindings.RepositoriesPythonApi.sync(
            python_repo.pulp_href, dict(remote=remote.pulp_href)
        ).task
    )
    assert not sync_task.child_tasks

    repo = python_bindings.RepositoriesPythonApi.read(python_repo.pulp_href)
    distro = python_distribution_factory(repository=repo)
    name = VULNERABILITY_REPORT_TEST_PACKAGE_NAME.lower()
    index = _index_url(distro, bindings_cfg)
    version_url = urljoin(index, f"pypi/{name}/5.2.1/json")
    project_url = urljoin(index, f"pypi/{name}/json")

    scan_task = python_bindings.RepositoriesPythonVersionsApi.scan(repo.latest_version_href)
    monitor_task(scan_task.task)

    project = requests.get(project_url).json()
    version = requests.get(version_url).json()
    _assert_warehouse_vulnerabilities(project)
    _assert_warehouse_vulnerabilities(version)
    assert [v["id"] for v in project["vulnerabilities"]] == [
        v["id"] for v in version["vulnerabilities"]
    ]

    packages = python_bindings.ContentPackagesApi.list(
        name=VULNERABILITY_REPORT_TEST_PACKAGE_NAME,
        repository_version=repo.latest_version_href,
    )
    assert packages.count >= 2
    hrefs = []
    for content in packages.results:
        assert content.vuln_report is not None
        report = pulpcore_bindings.VulnReportApi.read(content.vuln_report)
        assert report.vulns
        assert "affected" in report.vulns[0]
        hrefs.append(content.pulp_href)

    other = python_repo_factory()
    monitor_task(
        python_bindings.RepositoriesPythonApi.modify(
            other.pulp_href, {"add_content_units": hrefs}
        ).task
    )
    other = python_bindings.RepositoriesPythonApi.read(other.pulp_href)
    other_distro = python_distribution_factory(repository=other)
    other_json = requests.get(
        urljoin(_index_url(other_distro, bindings_cfg), f"pypi/{name}/json")
    ).json()
    assert other_json["vulnerabilities"] == []


@pytest.mark.parallel
def test_sync_dispatches_vulnerability_scan(
    bindings_cfg,
    pulpcore_bindings,
    python_bindings,
    python_remote_factory,
    python_repo,
    python_distribution_factory,
    monitor_task,
):
    """A remote with vulnerabilities=True scans the new repository version after sync."""
    remote = python_remote_factory(
        url=PYPI_URL,
        includes=VULNERABILITY_REPORT_TEST_PACKAGES,
        vulnerabilities=True,
    )
    sync_task = monitor_task(
        python_bindings.RepositoriesPythonApi.sync(
            python_repo.pulp_href, dict(remote=remote.pulp_href)
        ).task
    )
    _wait_for_child_tasks(pulpcore_bindings, monitor_task, sync_task)

    repo = python_bindings.RepositoriesPythonApi.read(python_repo.pulp_href)
    distro = python_distribution_factory(repository=repo)
    name = VULNERABILITY_REPORT_TEST_PACKAGE_NAME.lower()
    package = requests.get(urljoin(_index_url(distro, bindings_cfg), f"pypi/{name}/json")).json()
    _assert_warehouse_vulnerabilities(package)


@pytest.mark.parallel
def test_uploaded_package_json_vulnerabilities_empty_until_scan(
    bindings_cfg,
    python_bindings,
    python_content_factory,
    python_repo_factory,
    python_distribution_factory,
    monitor_task,
):
    """Uploaded packages have an empty vulnerabilities list until a scan runs."""
    repo = python_repo_factory()
    python_content_factory(repository=repo)
    distro = python_distribution_factory(repository=repo)
    url = urljoin(_index_url(distro, bindings_cfg), "pypi/shelf-reader/json")

    package = requests.get(url).json()
    assert package["vulnerabilities"] == []

    repo = python_bindings.RepositoriesPythonApi.read(repo.pulp_href)
    monitor_task(python_bindings.RepositoriesPythonVersionsApi.scan(repo.latest_version_href).task)
    package = requests.get(url).json()
    assert isinstance(package["vulnerabilities"], list)
