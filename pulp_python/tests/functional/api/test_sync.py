import pytest

from pulp_python.tests.functional.constants import (
    PYTHON_XS_PACKAGE_COUNT,
    PYTHON_PRERELEASE_TEST_SPECIFIER,
    PYTHON_WITH_PRERELEASE_COUNT,
    PYTHON_WITHOUT_PRERELEASE_COUNT,
    PYTHON_XS_PROJECT_SPECIFIER,
    PYTHON_MD_PROJECT_SPECIFIER,
    PYTHON_MD_PACKAGE_COUNT,
    PYTHON_SM_PROJECT_SPECIFIER,
    PYTHON_SM_PACKAGE_COUNT,
    PYTHON_UNAVAILABLE_PACKAGE_COUNT,
    PYTHON_UNAVAILABLE_PROJECT_SPECIFIER,
    PYTHON_LG_PROJECT_SPECIFIER,
    PYTHON_LG_PACKAGE_COUNT,
    PYTHON_LG_FIXTURE_COUNTS,
    DJANGO_LATEST_3,
    SCIPY_COUNTS,
)


@pytest.mark.parallel
def test_sync(
    python_bindings, python_repo, python_remote_factory, python_content_summary, monitor_task
):
    """Sync repositories with the python plugin."""
    remote = python_remote_factory()

    # Sync the repository.
    sync_data = dict(remote=remote.pulp_href)
    response = python_bindings.RepositoriesPythonApi.sync(python_repo.pulp_href, sync_data)
    task = monitor_task(response.task)
    repo = python_bindings.RepositoriesPythonApi.read(python_repo.pulp_href)

    assert task.created_resources[0] == repo.latest_version_href
    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.added["python.python"]["count"] == PYTHON_XS_PACKAGE_COUNT
    assert summary.present["python.python"]["count"] == PYTHON_XS_PACKAGE_COUNT

    # Sync the repository again.
    latest_version_href = repo.latest_version_href
    response = python_bindings.RepositoriesPythonApi.sync(repo.pulp_href, sync_data)
    task = monitor_task(response.task)
    repo = python_bindings.RepositoriesPythonApi.read(repo.pulp_href)

    assert latest_version_href == repo.latest_version_href
    assert len(task.created_resources) == 0


@pytest.mark.parallel
def test_sync_prereleases(python_repo_with_sync, python_remote_factory, python_content_summary):
    """Test syncing with prereleases filter."""
    remote = python_remote_factory(includes=PYTHON_PRERELEASE_TEST_SPECIFIER, prereleases=False)
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_WITHOUT_PRERELEASE_COUNT

    # Now sync with prereleases=True
    remote = python_remote_factory(includes=PYTHON_PRERELEASE_TEST_SPECIFIER, prereleases=True)
    repo = python_repo_with_sync(remote, repository=repo)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_WITH_PRERELEASE_COUNT
    diff_count = PYTHON_WITH_PRERELEASE_COUNT - PYTHON_WITHOUT_PRERELEASE_COUNT
    assert summary.added["python.python"]["count"] == diff_count

    # Sync w/ mirror=True & prereleases=False to ensure units are removed
    remote = python_remote_factory(includes=PYTHON_PRERELEASE_TEST_SPECIFIER, prereleases=False)
    repo = python_repo_with_sync(remote, mirror=True, repository=repo)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_WITHOUT_PRERELEASE_COUNT
    assert summary.removed["python.python"]["count"] == diff_count


@pytest.mark.parallel
def test_sync_includes_excludes(
    python_repo_with_sync, python_remote_factory, python_content_summary
):
    """Test behavior of the includes and excludes fields on the Remote during sync."""
    remote = python_remote_factory(includes=PYTHON_XS_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_XS_PACKAGE_COUNT

    # Test w/ large superset includes
    remote = python_remote_factory(includes=PYTHON_MD_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote, repository=repo)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_MD_PACKAGE_COUNT

    # Test w/ exclude subset
    remote = python_remote_factory(
        includes=PYTHON_MD_PROJECT_SPECIFIER, excludes=PYTHON_SM_PROJECT_SPECIFIER
    )
    repo = python_repo_with_sync(remote, repository=repo, mirror=True)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    diff_count = PYTHON_MD_PACKAGE_COUNT - PYTHON_SM_PACKAGE_COUNT
    assert summary.present["python.python"]["count"] == diff_count
    assert summary.removed["python.python"]["count"] == PYTHON_SM_PACKAGE_COUNT

    # Test w/ even smaller exclude subset
    remote = python_remote_factory(
        includes=PYTHON_MD_PROJECT_SPECIFIER, excludes=PYTHON_XS_PROJECT_SPECIFIER
    )
    repo = python_repo_with_sync(remote, repository=repo, mirror=True)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    diff_count = PYTHON_MD_PACKAGE_COUNT - PYTHON_XS_PACKAGE_COUNT
    assert summary.present["python.python"]["count"] == diff_count


@pytest.mark.parallel
def test_sync_unavailable_projects(
    python_repo_with_sync, python_remote_factory, python_content_summary
):
    """
    Test syncing with projects that aren't on the upstream remote.

    Tests that sync doesn't fail if the Remote contains projects (includes or excludes) for which
    metadata does not exist on the upstream remote.
    """
    remote = python_remote_factory(includes=PYTHON_UNAVAILABLE_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_UNAVAILABLE_PACKAGE_COUNT

    remote = python_remote_factory(
        includes=PYTHON_MD_PROJECT_SPECIFIER, excludes=PYTHON_UNAVAILABLE_PROJECT_SPECIFIER
    )
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    diff_count = PYTHON_MD_PACKAGE_COUNT - PYTHON_UNAVAILABLE_PACKAGE_COUNT
    assert summary.present["python.python"]["count"] == diff_count


@pytest.mark.parallel
def test_sync_latest_kept(python_repo_with_sync, python_remote_factory, python_content_summary):
    """
    Test checks that latest X packages are synced when latest kept is
    specified

    This feature uses Bandersnatch's latest_kept filter which doesn't work well
    with the other filters like pre-releases and allow/blocklist. Whether to
    count the behavior as a bug or feature is hard to tell.
    """
    # Tests latest_kept on syncing one package w/ prereleases
    remote = python_remote_factory(
        includes=["Django"],
        keep_latest_packages=3,
        prereleases=True,
    )
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == DJANGO_LATEST_3

    # Tests latest_kept on syncing multiple packages w/ prereleases
    remote = python_remote_factory(
        includes=PYTHON_LG_PROJECT_SPECIFIER,
        keep_latest_packages=3,
        prereleases=True,
    )
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_LG_FIXTURE_COUNTS["latest_3"]


@pytest.mark.parallel
def test_sync_package_type(python_repo_with_sync, python_remote_factory, python_content_summary):
    """Tests that check only specified package types can be synced."""
    # Checks that only sdist content is synced
    remote = python_remote_factory(
        includes=PYTHON_LG_PROJECT_SPECIFIER,
        package_types=["sdist"],
        prereleases=True,
    )
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_LG_FIXTURE_COUNTS["sdist"]

    # Checks that only bdist_wheel content is synced
    remote = python_remote_factory(
        includes=PYTHON_LG_PROJECT_SPECIFIER,
        package_types=["bdist_wheel"],
        prereleases=True,
    )
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_LG_FIXTURE_COUNTS["bdist_wheel"]

    # Checks that specifying sdist and bdist_wheel gets all packages
    remote = python_remote_factory(
        includes=PYTHON_LG_PROJECT_SPECIFIER,
        package_types=["sdist", "bdist_wheel"],
        prereleases=True,
    )
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == PYTHON_LG_PACKAGE_COUNT


@pytest.mark.parallel
def test_sync_platform_exclude(
        python_repo_with_sync, python_remote_factory, python_content_summary
):
    """
    Tests for platform specific packages not being synced when specified

    Only our scipy packages have platform specific versions
    23 release files:
    4 macos releases
    8 windows releases
    10 linux releases
    1 any platform release
    """
    # Tests that no windows packages are synced
    remote = python_remote_factory(includes=["scipy"], exclude_platforms=["windows"],
                                   prereleases=True, )
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    diff_count = SCIPY_COUNTS["total"] - SCIPY_COUNTS["windows"]
    assert summary.present["python.python"]["count"] == diff_count

    # Tests that no macos packages are synced
    remote = python_remote_factory(includes=["scipy"], exclude_platforms=["macos"],
                                   prereleases=True, )
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    diff_count = SCIPY_COUNTS["total"] - SCIPY_COUNTS["macos"]
    assert summary.present["python.python"]["count"] == diff_count

    # Tests that no linux packages are synced
    remote = python_remote_factory(includes=["scipy"], exclude_platforms=["linux"],
                                   prereleases=True, )
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    diff_count = SCIPY_COUNTS["total"] - SCIPY_COUNTS["linux"]
    assert summary.present["python.python"]["count"] == diff_count

    # Tests that no package specified for a platform is synced
    remote = python_remote_factory(
        includes=["scipy"],
        exclude_platforms=["windows", "macos", "linux", "freebsd"],
        prereleases=True,
    )
    repo = python_repo_with_sync(remote)

    summary = python_content_summary(repository_version=repo.latest_version_href)
    assert summary.present["python.python"]["count"] == SCIPY_COUNTS["no_os"]


@pytest.mark.parallel
def test_proxy_sync(
    python_bindings,
    python_repo_with_sync,
    python_remote_factory,
    http_proxy,
):
    """Test syncing with a proxy."""
    remote = python_remote_factory(proxy_url=http_proxy.proxy_url)
    repo = python_repo_with_sync(remote)
    assert repo.latest_version_href[-2] == "1"

    content = python_bindings.ContentPackagesApi.list(repository_version=repo.latest_version_href)
    assert content.count == 2


@pytest.mark.parallel
def test_proxy_auth_sync(
    python_bindings,
    python_repo_with_sync,
    python_remote_factory,
    http_proxy_with_auth,
):
    """Test syncing with a proxy with auth."""
    remote = python_remote_factory(
        proxy_url=http_proxy_with_auth.proxy_url,
        proxy_username=http_proxy_with_auth.username,
        proxy_password=http_proxy_with_auth.password,
    )
    repo = python_repo_with_sync(remote)
    assert repo.latest_version_href[-2] == "1"

    content = python_bindings.ContentPackagesApi.list(repository_version=repo.latest_version_href)
    assert content.count == 2
