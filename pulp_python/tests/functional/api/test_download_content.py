import pytest

from pulp_python.tests.functional.constants import (
    PYTHON_MD_PROJECT_SPECIFIER,
    PYTHON_LG_PROJECT_SPECIFIER,
    PYTHON_MD_PACKAGE_COUNT,
    PYTHON_LG_PACKAGE_COUNT,
)


@pytest.mark.parallel
def test_basic_pulp_to_pulp_sync(
    python_repo_with_sync,
    python_remote_factory,
    python_content_summary,
    python_publication_factory,
    python_distribution_factory,
    pulp_content_url,
):
    """
    This test checks that the JSON endpoint is setup correctly to allow one Pulp
    instance to perform a basic sync from another Pulp instance
    """
    # Setup
    remote_body = dict(includes=PYTHON_LG_PROJECT_SPECIFIER, prereleases=True)
    remote = python_remote_factory(**remote_body)
    repo = python_repo_with_sync(remote)
    pub = python_publication_factory(repository=repo)
    distro = python_distribution_factory(publication=pub)
    unit_url = f"{pulp_content_url}{distro.base_path}/"

    # Sync using old Pulp content api endpoints
    remote2 = python_remote_factory(url=unit_url, **remote_body)
    repo2 = python_repo_with_sync(remote2)
    summary = python_content_summary(repository_version=repo2.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_LG_PACKAGE_COUNT

    # Sync using new PyPI endpoints
    remote3 = python_remote_factory(url=distro.base_url, **remote_body)
    repo3 = python_repo_with_sync(remote3)
    summary = python_content_summary(repo3.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_LG_PACKAGE_COUNT


@pytest.mark.parallel
def test_full_fixtures_to_pulp_sync(
    python_repo_with_sync, python_remote_factory, python_content_summary
):
    """
    This test checks that Pulp can fully sync another Python Package repository that is not
    PyPI. This reads the repository's simple page if XMLRPC isn't supported.
    """
    # Repository we are syncing from is the fixtures (default url)
    remote = python_remote_factory(includes=[], prereleases=True)
    repo = python_repo_with_sync(remote)
    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_LG_PACKAGE_COUNT


@pytest.mark.parallel
def test_full_pulp_to_pulp_sync(
    python_repo_with_sync,
    python_remote_factory,
    python_publication_factory,
    python_distribution_factory,
    python_content_summary,
):
    """
    This test checks that Pulp can fully sync all packages from another Pulp instance
    without having to specify the includes field.
    """
    remote = python_remote_factory(includes=PYTHON_MD_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)

    # Test using live generated simple pages
    distro = python_distribution_factory(repository=repo)

    remote2 = python_remote_factory(includes=[], url=distro.base_url)
    repo2 = python_repo_with_sync(remote2)
    summary = python_content_summary(repository_version=repo2.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_MD_PACKAGE_COUNT

    # Now test using publication simple pages
    pub = python_publication_factory(repository=repo)
    distro2 = python_distribution_factory(publication=pub)
    remote3 = python_remote_factory(includes=[], url=distro2.base_url)
    repo3 = python_repo_with_sync(remote3)
    summary2 = python_content_summary(repository_version=repo3.latest_version_href)
    assert summary2.present["python.python"]["count"] == PYTHON_MD_PACKAGE_COUNT
