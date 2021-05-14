# coding=utf-8
"""Tests that publish python plugin repositories."""
import random
from random import choice

from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import (
    get_content,
    get_versions,
    modify_repo
)
from urllib.parse import urljoin

from pulp_python.tests.functional.constants import (
    PYTHON_CONTENT_NAME,
    PULP_CONTENT_BASE_URL,
    PYTHON_SM_PROJECT_SPECIFIER,
    PYTHON_SM_FIXTURE_RELEASES,
    PYTHON_SM_FIXTURE_CHECKSUMS,
    PYTHON_EGG_FILENAME,
    PYTHON_WHEEL_FILENAME,
)
from pulp_python.tests.functional.utils import (
    cfg,
    TestCaseUsingBindings,
    TestHelpersMixin,
    ensure_simple,
)
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_python.exceptions import ApiException


class PublishAnyRepoVersionTestCase(TestCaseUsingBindings, TestHelpersMixin):
    """Test whether a particular repository version can be published.

    This test targets the following issues:

    * `Pulp #3324 <https://pulp.plan.io/issues/3324>`_
    * `Pulp Smash #897 <https://github.com/pulp/pulp-smash/issues/897>`_
    """

    def test_all(self):
        """Test whether a particular repository version can be published.

        1. Create a repository with at least 2 repository versions.
        2. Create a publication by supplying the latest ``repository_version``.
        3. Assert that the publication ``repository_version`` attribute points
           to the latest repository version.
        4. Create a publication by supplying the non-latest ``repository_version``.
        5. Assert that the publication ``repository_version`` attribute points
           to the supplied repository version.
        6. Assert that an exception is raised when providing two different
           repository versions to be published at same time.
        """
        remote = self._create_remote()
        repo = self._create_repo_and_sync_with_remote(remote)
        # Step 1
        for python_content in get_content(repo.to_dict())[PYTHON_CONTENT_NAME]:
            modify_repo(cfg, repo.to_dict(), add_units=[python_content])

        version_hrefs = tuple(ver["pulp_href"] for ver in get_versions(repo.to_dict()))
        non_latest = choice(version_hrefs[:-1])

        repo = self.repo_api.read(repo.pulp_href)
        # Step 2, 3
        pub_latest = self._create_publication(repo)
        self.assertEqual(pub_latest.repository_version, version_hrefs[-1])
        # Step 4, 5
        pub_version = self._create_publication(repo, version=non_latest)
        self.assertEqual(pub_version.repository_version, non_latest)

        # Step 6
        with self.assertRaises(ApiException):
            body = {"repository": repo.pulp_href, "repository_version": non_latest}
            self.publications_api.create(body)


class PublishDifferentPolicyContent(TestCaseUsingBindings, TestHelpersMixin):
    """Test whether a 'on_demand', 'immediate', or 'streamed' synced repository can be published.

    This test targets the following issues:

    * `Pulp #7128 <https://pulp.plan.io/issues/7128>`_
    """

    def test_on_demand(self):
        """Test whether a particular repository version can be published.

        1. Create a repository
        2. Create a remote with on_demand sync policy
        3. Sync
        4. Publish repository
        """
        remote = self._create_remote(policy="on_demand")
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)

        self.assertEqual(pub.repository_version, repo.latest_version_href)

    def test_immediate(self):
        """Test if immediate synced content can be published."""
        remote = self._create_remote(policy="immediate")
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)

        self.assertEqual(pub.repository_version, repo.latest_version_href)

    def test_streamed(self):
        """Test if streamed synced content can be published."""
        remote = self._create_remote(policy="streamed")
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)

        self.assertEqual(pub.repository_version, repo.latest_version_href)

    def test_mixed(self):
        """Test if repository with mixed synced content can be published."""
        # Sync on demand content
        remote = self._create_remote(policy="on_demand", includes=PYTHON_SM_PROJECT_SPECIFIER)
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)
        # Sync immediate content
        remote2 = self._create_remote(policy="immediate")
        repo = self._sync_repo(repo, remote=remote2.pulp_href)
        pub2 = self._create_publication(repo)

        self.assertEqual(pub.repository_version, f"{repo.versions_href}1/")
        self.assertEqual(pub2.repository_version, repo.latest_version_href)


class ListPublications(TestCaseUsingBindings, TestHelpersMixin):
    """
    This tests that publications can be listed.

    This also tests that associated distributions show up when listing a publication.

    # TODO Make test RBAC specific when RBAC is implemented
    """

    def test_multiple_list(self):
        """Test listing multiple publications."""
        repo = self._create_repository()
        publication = self._create_publication(repo)
        publication2 = self._create_publication(repo)

        publications = self.publications_api.list()
        self.assertEqual(publications.results, [publication2, publication])

    def test_none_list(self):
        """Test listing publications when empty."""
        publications = self.publications_api.list()
        self.assertEqual(publications.count, 0)

    def test_publication_distribution(self):
        """Test that a publication properly lists it's connected distributions."""
        repo = self._create_repository()
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)
        distro2 = self._create_distribution_from_publication(pub)

        publication = self.publications_api.read(pub.pulp_href)
        self.assertEqual(publication.distributions, [distro.pulp_href, distro2.pulp_href])


class DeletePublications(TestCaseUsingBindings, TestHelpersMixin):
    """
    These tests are dedicated to making sure that deleting works correctly.

    Deleted publications should be removed from associated distributions
    Deleted repositories should remove publications
    """

    def test_basic_delete(self):
        """Checks that deleting decreases publication count."""
        publications = self.publications_api.list()
        current_length = publications.count
        repo = self._create_repository()
        publication = self._create_publication(repo, cleanup=False)

        publications = self.publications_api.list()
        self.assertEqual(publications.count, 1 + current_length)

        self.publications_api.delete(publication.pulp_href)
        publications = self.publications_api.list()
        self.assertEqual(publications.count, current_length)

    def test_distro_removed_on_delete(self):
        """Test that distributions no longer point to a publication after deleted."""
        repo = self._create_repository()
        publication = self._create_publication(repo, cleanup=False)
        distro = self._create_distribution_from_publication(publication)

        self.assertEqual(distro.publication, publication.pulp_href)

        self.publications_api.delete(publication.pulp_href)
        distro = self.distributions_api.read(distro.pulp_href)

        self.assertEqual(distro.publication, None)

    def test_repository_delete(self):
        """Tests that deleting the repository of a publication deletes the publication."""
        repo = self._create_repository(cleanup=False)
        publication = self._create_publication(repo, cleanup=False)

        monitor_task(self.repo_api.delete(repo.pulp_href).task)
        with self.assertRaises(ApiException):
            self.publications_api.read(publication.pulp_href)


class PublishedCorrectContent(TestCaseUsingBindings, TestHelpersMixin):
    """
    These tests ensure that publications only serve content currently in the repository version.

    This test targets the following issues:

    * `Pulp #362 <https://github.com/pulp/pulp_python/issues/362>`_
    """

    @classmethod
    def setUpClass(cls):
        """Sets up the class variables"""
        super().setUpClass()
        cls.releases = [PYTHON_EGG_FILENAME, PYTHON_WHEEL_FILENAME]

    def test_all_content_published(self):
        """Publishes SM Project and ensures correctness of simple api."""
        remote = self._create_remote(includes=PYTHON_SM_PROJECT_SPECIFIER)
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)

        url = urljoin(PULP_CONTENT_BASE_URL, f"{distro.base_path}/simple/")
        proper, msgs = ensure_simple(url, PYTHON_SM_FIXTURE_RELEASES,
                                     sha_digests=PYTHON_SM_FIXTURE_CHECKSUMS)
        self.assertTrue(proper, msg=msgs)

    def test_removed_content_not_published(self):
        """Ensure content removed from a repository doesn't get published again."""
        remote = self._create_remote()
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)

        url = urljoin(PULP_CONTENT_BASE_URL, f"{distro.base_path}/simple/")
        proper, msgs = ensure_simple(url, {"shelf-reader": self.releases})
        self.assertTrue(proper, msg=msgs)

        removed_content = random.choice(get_content(repo.to_dict())[PYTHON_CONTENT_NAME])
        modify_repo(cfg, repo.to_dict(), add_units=[removed_content])
        repo = self.repo_api.read(repo.pulp_href)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)

        if removed_content["filename"] == PYTHON_WHEEL_FILENAME:
            remaining_release = [PYTHON_EGG_FILENAME]
        else:
            remaining_release = [PYTHON_WHEEL_FILENAME]
        url = urljoin(PULP_CONTENT_BASE_URL, f"{distro.base_path}/simple/")
        proper, msgs = ensure_simple(url, {"shelf-reader": remaining_release})

        self.assertTrue(proper, msg=msgs)

    def test_new_content_is_published(self):
        """Ensures added content is published with a new publication."""
        remote = self._create_remote(package_types=["sdist"])
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)

        url = urljoin(PULP_CONTENT_BASE_URL, f"{distro.base_path}/simple/")
        proper, m = ensure_simple(url, {"shelf-reader": [PYTHON_EGG_FILENAME]})
        self.assertTrue(proper, msg=m)

        remote = self._create_remote()
        repo = self._sync_repo(repo, remote=remote.pulp_href)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)

        url = urljoin(PULP_CONTENT_BASE_URL, f"{distro.base_path}/simple/")
        proper, msgs = ensure_simple(url, {"shelf-reader": self.releases})
        self.assertTrue(proper, msg=msgs)
