# coding=utf-8
"""Tests that publish python plugin repositories."""
import random
import unittest
from random import choice

from pulp_smash import config
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_content,
    get_versions,
    modify_repo,
    gen_distribution,
)
from pulp_smash.utils import http_get
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
from pulp_python.tests.functional.utils import gen_python_client, gen_python_remote
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_python import (
    PublicationsPypiApi,
    RepositoriesPythonApi,
    RepositorySyncURL,
    RemotesPythonApi,
    PythonPythonPublication,
    DistributionsPypiApi,
)
from pulpcore.client.pulp_python.exceptions import ApiException
from lxml import html


class PublishAnyRepoVersionTestCase(unittest.TestCase):
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
        cfg = config.get_config()
        client = gen_python_client()
        repo_api = RepositoriesPythonApi(client)
        remote_api = RemotesPythonApi(client)
        publications = PublicationsPypiApi(client)

        body = gen_python_remote()
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        repository_sync_data = RepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        # Step 1
        repo = repo_api.read(repo.pulp_href)
        for python_content in get_content(repo.to_dict())[PYTHON_CONTENT_NAME]:
            modify_repo(cfg, repo.to_dict(), add_units=[python_content])
        version_hrefs = tuple(ver["pulp_href"] for ver in get_versions(repo.to_dict()))
        non_latest = choice(version_hrefs[:-1])

        # Step 2
        publish_data = PythonPythonPublication(repository=repo.pulp_href)
        publish_response = publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        self.addCleanup(publications.delete, publication_href)
        publication = publications.read(publication_href)

        # Step 3
        self.assertEqual(publication.repository_version, version_hrefs[-1])

        # Step 4
        publish_data.repository = None
        publish_data.repository_version = non_latest
        publish_response = publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        publication = publications.read(publication_href)

        # Step 5
        self.assertEqual(publication.repository_version, non_latest)

        # Step 6
        with self.assertRaises(ApiException):
            body = {"repository": repo.pulp_href, "repository_version": non_latest}
            publications.create(body)


class PublishDifferentPolicyContent(unittest.TestCase):
    """Test whether a 'on_demand', 'immediate', or 'streamed' synced repository can be published.

    This test targets the following issues:

    * `Pulp #7128 <https://pulp.plan.io/issues/7128>`_
    """

    @classmethod
    def setUpClass(cls):
        """Sets up APIs used by tests."""
        client = gen_python_client()
        cls.repo_api = RepositoriesPythonApi(client)
        cls.remote_api = RemotesPythonApi(client)
        cls.pub_api = PublicationsPypiApi(client)

    def test_on_demand(self):
        """Test whether a particular repository version can be published.

        1. Create a repository
        2. Create a remote with on_demand sync policy
        3. Sync
        4. Publish repository
        """
        repo, _, pub = create_workflow(self.repo_api, self.pub_api, remote_api=self.remote_api,
                                       body={"policy": "on_demand"}, cleanup=self.addCleanup)

        self.assertEqual(pub.repository_version, repo.latest_version_href)

    def test_immediate(self):
        """Test if immediate synced content can be published."""
        repo, _, pub = create_workflow(self.repo_api, self.pub_api, remote_api=self.remote_api,
                                       body={"policy": "immediate"}, cleanup=self.addCleanup)

        self.assertEqual(pub.repository_version, repo.latest_version_href)

    def test_streamed(self):
        """Test if streamed synced content can be published."""
        repo, _, pub = create_workflow(self.repo_api, self.pub_api, remote_api=self.remote_api,
                                       body={"policy": "streamed"}, cleanup=self.addCleanup)

        self.assertEqual(pub.repository_version, repo.latest_version_href)

    def test_mixed(self):
        """Test if repository with mixed synced content can be published."""
        # Sync on demand content
        body = {"includes": PYTHON_SM_PROJECT_SPECIFIER}
        repo, _, pub = create_workflow(self.repo_api, self.pub_api, remote_api=self.remote_api,
                                       body=body, cleanup=self.addCleanup)

        self.assertEqual(pub.repository_version, repo.latest_version_href)
        # Add immediate content
        body = {"policy": "immediate"}
        remote = create_remote(self.remote_api, body=body, cleanup=self.addCleanup)
        repository_sync_data = RepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = self.repo_api.read(repo.pulp_href)
        pub = create_publication(self.pub_api, repo, cleanup=self.addCleanup)

        self.assertEqual(pub.repository_version, repo.latest_version_href)


class ListPublications(unittest.TestCase):
    """
    This tests that publications can be listed.

    This also tests that associated distributions show up when listing a publication.

    # TODO Make test RBAC specific when RBAC is implemented
    """

    @classmethod
    def setUpClass(cls):
        """Setup apis for all tests."""
        client = gen_python_client()
        cls.repo_api = RepositoriesPythonApi(client)
        cls.pub_api = PublicationsPypiApi(client)
        cls.dis_api = DistributionsPypiApi(client)

    def test_multiple_list(self):
        """Test listing multiple publications."""
        _, publication = create_workflow(self.repo_api, self.pub_api, cleanup=self.addCleanup)
        _, publication2 = create_workflow(self.repo_api, self.pub_api, cleanup=self.addCleanup)

        publications = self.pub_api.list()
        self.assertEqual(publications.results, [publication2, publication])

    def test_none_list(self):
        """Test listing publications when empty."""
        publications = self.pub_api.list()
        self.assertEqual(publications.count, 0)

    def test_publication_distribution(self):
        """Test that a publication properly lists it's connected distributions."""
        repo, pub, distro = create_workflow(self.repo_api, self.pub_api,
                                            distro_api=self.dis_api, cleanup=self.addCleanup)
        distro2 = create_distribution(self.dis_api, pub, cleanup=self.addCleanup)

        publication = self.pub_api.read(pub.pulp_href)
        self.assertEqual(publication.distributions, [distro.pulp_href, distro2.pulp_href])


class DeletePublications(unittest.TestCase):
    """
    These tests are dedicated to making sure that deleting works correctly.

    Deleted publications should be removed from associated distributions
    Deleted repositories should remove publications
    """

    @classmethod
    def setUpClass(cls):
        """Setup apis for all tests."""
        client = gen_python_client()
        cls.repo_api = RepositoriesPythonApi(client)
        cls.pub_api = PublicationsPypiApi(client)
        cls.dis_api = DistributionsPypiApi(client)

    def test_basic_delete(self):
        """Checks that deleting decreases publication count."""
        publications = self.pub_api.list()
        current_length = publications.count
        repo, publication = create_workflow(self.repo_api, self.pub_api)
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        publications = self.pub_api.list()
        self.assertEqual(publications.count, 1 + current_length)

        self.pub_api.delete(publication.pulp_href)
        publications = self.pub_api.list()
        self.assertEqual(publications.count, current_length)

    def test_distro_removed_on_delete(self):
        """Test that distributions no longer point to a publication after deleted."""
        repo, publication, distro = create_workflow(
            self.repo_api, self.pub_api, distro_api=self.dis_api
        )
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        self.addCleanup(self.dis_api.delete, distro.pulp_href)

        self.assertEqual(distro.publication, publication.pulp_href)

        self.pub_api.delete(publication.pulp_href)
        distro = self.dis_api.read(distro.pulp_href)

        self.assertEqual(distro.publication, None)

    def test_repository_delete(self):
        """Tests that deleting the repository of a publication deletes the publication."""
        repo, publication = create_workflow(self.repo_api, self.pub_api)

        monitor_task(self.repo_api.delete(repo.pulp_href).task)
        with self.assertRaises(ApiException):
            self.pub_api.read(publication.pulp_href)


class PublishedCorrectContent(unittest.TestCase):
    """
    These tests ensure that publications only serve content currently in the repository version.

    This test targets the following issues:

    * `Pulp #362 <https://github.com/pulp/pulp_python/issues/362>`_
    """

    @staticmethod
    def ensure_simple(base_path, packages, sha_digests=None):
        """
        Tests that the simple api at `base_path` matches the packages supplied.

        `packages`: dictionary of form {package_name: [release_filenames]}

        First check `/simple/index.html` has each package name, no more, no less
        Second check `/simple/package_name/index.html` for each package exists
        Third check each package's index has all their releases listed, no more, no less

        Returns tuple (`proper`: bool, `error_msg`: str)

        *Technically, if there was a bug, other packages' indexes could be posted, but not present
        in the simple index and thus be accessible from the distribution, but if one can't see it
        how would one know that it's there?*
        """
        def explore_links(page_url, page_name, links_found):
            legit_found_links = []
            page = html.fromstring(http_get(page_url))
            page_links = page.xpath("/html/body/a")
            for link in page_links:
                if link.text in links_found:
                    if links_found[link.text]:
                        msgs += f"\nDuplicate {page_name} name {link.text}"  # noqa: F823
                    links_found[link.text] = True
                    if link.get("href"):
                        legit_found_links.append(link.get("href"))
                    else:
                        msgs += f"\nFound {page_name} link without href {link.text}"  # noqa: F823
                else:
                    msgs += f"\nFound extra {page_name} link {link.text}"  # noqa: F823
            return legit_found_links

        packages_found = {name: False for name in packages.keys()}
        releases_found = {name: False for releases in packages.values() for name in releases}
        msgs = ""
        simple_url = urljoin(PULP_CONTENT_BASE_URL, f"{base_path}/simple/")
        found_release_links = explore_links(simple_url, "simple", packages_found)
        dl_links = []
        for release_link in found_release_links:
            dl_links += explore_links(urljoin(simple_url, release_link), "release", releases_found)
        for dl_link in dl_links:
            package_link, _, sha = dl_link.partition("#sha256=")
            if len(sha) != 64:
                msgs += f"\nRelease download link has bad sha256 {dl_link}"
            if sha_digests:
                package = package_link.split("/")[-1]
                if sha_digests[package] != sha:
                    msgs += f"\nRelease has bad sha256 attached to it {package}"
        msgs += "".join(map(lambda x: f"\nSimple link not found for {x}",
                            [name for name, val in packages_found.items() if not val]))
        msgs += "".join(map(lambda x: f"\nReleases link not found for {x}",
                            [name for name, val in releases_found.items() if not val]))
        return len(msgs) == 0, msgs

    @classmethod
    def setUpClass(cls):
        """Sets up the apis for the tests."""
        client = gen_python_client()
        cls.repo_api = RepositoriesPythonApi(client)
        cls.rem_api = RemotesPythonApi(client)
        cls.pub_api = PublicationsPypiApi(client)
        cls.dis_api = DistributionsPypiApi(client)
        cls.releases = [PYTHON_EGG_FILENAME, PYTHON_WHEEL_FILENAME]

    def test_all_content_published(self):
        """Publishes SM Project and ensures correctness of simple api."""
        body = {"includes": PYTHON_SM_PROJECT_SPECIFIER}
        _, _, _, distro = create_workflow(self.repo_api, self.pub_api, self.rem_api,
                                          body, self.dis_api, self.addCleanup)

        proper, msgs = self.ensure_simple(distro.base_path, PYTHON_SM_FIXTURE_RELEASES,
                                          sha_digests=PYTHON_SM_FIXTURE_CHECKSUMS)
        self.assertTrue(proper, msg=msgs)

    def test_removed_content_not_published(self):
        """Ensure content removed from a repository doesn't get published again."""
        repo, _, _, distro = create_workflow(self.repo_api, self.pub_api, remote_api=self.rem_api,
                                             distro_api=self.dis_api, cleanup=self.addCleanup)

        proper, msgs = self.ensure_simple(distro.base_path, {"shelf-reader": self.releases})
        self.assertTrue(proper, msg=msgs)

        cfg = config.get_config()
        removed_content = random.choice(get_content(repo.to_dict())[PYTHON_CONTENT_NAME])
        modify_repo(cfg, repo.to_dict(), remove_units=[removed_content])

        publication = create_publication(self.pub_api, repo, cleanup=self.addCleanup)
        distro = create_distribution(self.dis_api, publication, cleanup=self.addCleanup)

        if removed_content["filename"] == PYTHON_WHEEL_FILENAME:
            remaining_release = [PYTHON_EGG_FILENAME]
        else:
            remaining_release = [PYTHON_WHEEL_FILENAME]
        proper, msgs = self.ensure_simple(distro.base_path, {"shelf-reader": remaining_release})

        self.assertTrue(proper, msg=msgs)

    def test_new_content_is_published(self):
        """Ensures added content is published with a new publication."""
        body = {"package_types": ["sdist"]}
        repo, _, _, distro = create_workflow(self.repo_api, self.pub_api, self.rem_api,
                                             body, self.dis_api, self.addCleanup)

        proper, m = self.ensure_simple(distro.base_path, {"shelf-reader": [PYTHON_EGG_FILENAME]})
        self.assertTrue(proper, msg=m)

        remote = create_remote(self.rem_api, cleanup=self.addCleanup)
        repository_sync_data = RepositorySyncURL(remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)

        publication = create_publication(self.pub_api, repo, cleanup=self.addCleanup)
        distro = create_distribution(self.dis_api, publication, cleanup=self.addCleanup)

        proper, msgs = self.ensure_simple(distro.base_path, {"shelf-reader": self.releases})
        self.assertTrue(proper, msg=msgs)


def create_repository(repo_api, cleanup=None):
    """Creates a new python repository."""
    repo = repo_api.create(gen_repo())
    if cleanup:
        cleanup(repo_api.delete, repo.pulp_href)
    return repo


def create_remote(remote_api, body={}, cleanup=None):
    """Creates a new python remote."""
    remote = remote_api.create(gen_python_remote(**body))
    if cleanup:
        cleanup(remote_api.delete, remote.pulp_href)
    return remote


def create_publication(pub_api, repository, cleanup=None):
    """Creates a new python publication."""
    publish_data = PythonPythonPublication(repository=repository.pulp_href)
    publish_response = pub_api.create(publish_data)
    publication = pub_api.read(monitor_task(publish_response.task).created_resources[0])
    if cleanup:
        cleanup(pub_api.delete, publication.pulp_href)
    return publication


def create_distribution(dis_api, publication, cleanup=None):
    """Creates a new python distribution."""
    dis_body = gen_distribution(publication=publication.pulp_href)
    distro_response = dis_api.create(dis_body)
    distro = dis_api.read(monitor_task(distro_response.task).created_resources[0])
    if cleanup:
        cleanup(dis_api.delete, distro.pulp_href)
    return distro


def create_workflow(repo_api, pub_api, remote_api=None, body={}, distro_api=None, cleanup=None):
    """Creates repository, publication, and potentially remote and distribution if specified."""
    created_objects = []
    repo = create_repository(repo_api, cleanup=cleanup)
    created_objects.append(repo)
    if remote_api:
        remote = create_remote(remote_api, body=body, cleanup=cleanup)
        repository_sync_data = RepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = repo_api.read(repo.pulp_href)
        created_objects[0] = repo
        created_objects.append(remote)
    publication = create_publication(pub_api, repo, cleanup=cleanup)
    created_objects.append(publication)
    if distro_api:
        distro = create_distribution(distro_api, publication, cleanup=cleanup)
        created_objects.append(distro)
    return created_objects
