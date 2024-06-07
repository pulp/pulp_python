import pytest
import random
from urllib.parse import urljoin

from pulp_python.tests.functional.constants import (
    PYTHON_SM_PROJECT_SPECIFIER,
    PYTHON_SM_FIXTURE_RELEASES,
    PYTHON_SM_FIXTURE_CHECKSUMS,
    PYTHON_EGG_FILENAME,
    PYTHON_WHEEL_FILENAME,
)
from pulp_python.tests.functional.utils import ensure_simple


@pytest.fixture
def python_publication_workflow(
    python_repo_with_sync, python_remote_factory, python_publication_factory
):
    """Create repo, remote, sync & then publish."""
    def _publish_workflow(repository=None, remote=None, **remote_body):
        if not remote:
            remote = python_remote_factory(**remote_body)
        repository = python_repo_with_sync(remote, repository=repository)
        publication = python_publication_factory(repository=repository)
        return repository, remote, publication

    yield _publish_workflow


@pytest.mark.parametrize("policy", ["immediate", "on_demand", "streamed"])
def test_publications_sync_policy(policy, python_publication_workflow, delete_orphans_pre):
    """Test whether a 'on_demand', 'immediate', or 'streamed' synced repository can be published."""
    repo, _, pub = python_publication_workflow(policy=policy)

    assert pub.repository_version, repo.latest_version_href


def test_mixed(python_publication_workflow, delete_orphans_pre):
    """Test if repository with mixed synced content can be published."""
    # Sync on demand content
    repo, _, pub = python_publication_workflow(
        policy="on_demand", includes=PYTHON_SM_PROJECT_SPECIFIER
    )
    # Sync immediate content
    _, _, pub2 = python_publication_workflow(repository=repo, policy="immediate")

    assert pub.repository_version == f"{repo.versions_href}1/"
    assert pub2.repository_version == f"{repo.versions_href}2/"


@pytest.mark.parallel
def test_all_content_published(python_publication_workflow, python_distribution_factory):
    """Publishes SM Project and ensures correctness of simple api."""
    _, _, pub = python_publication_workflow(includes=PYTHON_SM_PROJECT_SPECIFIER)
    distro = python_distribution_factory(publication=pub)

    url = urljoin(distro.base_url, "simple/")
    proper, msgs = ensure_simple(url, PYTHON_SM_FIXTURE_RELEASES,
                                 sha_digests=PYTHON_SM_FIXTURE_CHECKSUMS)
    assert proper is True, msgs


@pytest.mark.parallel
def test_removed_content_not_published(
    python_bindings, python_publication_workflow, python_distribution_factory, monitor_task
):
    """Ensure content removed from a repository doesn't get published again."""
    repo, _, pub = python_publication_workflow()
    distro = python_distribution_factory(publication=pub)

    url = urljoin(distro.base_url, "simple/")
    releases = [PYTHON_EGG_FILENAME, PYTHON_WHEEL_FILENAME]
    proper, msgs = ensure_simple(url, {"shelf-reader": releases})
    assert proper is True, msgs

    contents = python_bindings.ContentPackagesApi.list(repository_version=repo.latest_version_href)
    removed_content = random.choice(contents.results)
    body = {"remove_content_units": [removed_content.pulp_href]}
    monitor_task(python_bindings.RepositoriesPythonApi.modify(repo.pulp_href, body).task)
    repo, _, pub2 = python_publication_workflow(repository=repo)
    distro2 = python_distribution_factory(publication=pub2)

    if removed_content.filename == PYTHON_WHEEL_FILENAME:
        remaining_release = [PYTHON_EGG_FILENAME]
    else:
        remaining_release = [PYTHON_WHEEL_FILENAME]
    url = urljoin(distro2.base_url, "simple/")
    proper, msgs = ensure_simple(url, {"shelf-reader": remaining_release})

    assert proper is True, msgs


@pytest.mark.parallel
def test_new_content_is_published(python_publication_workflow, python_distribution_factory):
    """Ensures added content is published with a new publication."""
    repo, _, pub = python_publication_workflow(package_types=["sdist"])
    distro = python_distribution_factory(publication=pub)

    url = urljoin(distro.base_url, "simple/")
    proper, msgs = ensure_simple(url, {"shelf-reader": [PYTHON_EGG_FILENAME]})
    assert proper is True, msgs

    repo, _, pub = python_publication_workflow()
    distro = python_distribution_factory(publication=pub)

    releases = [PYTHON_EGG_FILENAME, PYTHON_WHEEL_FILENAME]
    url = urljoin(distro.base_url, "simple/")
    proper, msgs = ensure_simple(url, {"shelf-reader": releases})
    assert proper is True, msgs
