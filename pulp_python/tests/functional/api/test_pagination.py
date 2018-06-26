import unittest
from random import randint, sample
from threading import Lock, Thread
from urllib.parse import urljoin

from pulp_smash import api, config
from pulp_smash.pulp3.constants import REPO_PATH
from pulp_smash.tests.pulp3.file.utils import set_up_module as setUpModule  # noqa:E722
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_added_content,
    get_auth,
    get_content,
    get_removed_content,
    get_versions,
)

from pulp_python.tests.functional.constants import (
    PYTHON_CONTENT_PATH,
    # FILE_MANY_FEED_COUNT,
    # FILE_MANY_FEED_URL
)
from pulp_python.tests.functional.utils import gen_remote, gen_publisher, populate_pulp


@unittest.skip("test fixtures")
class PaginationTestCase(unittest.TestCase):
    """
    Test pagination.

    This test case assumes that Pulp returns 100 elements in each page of
    results. This is configurable, but the current default set by all known
    Pulp installers.
    """

    @classmethod
    def setUpClass(cls):
        """
        Create class-wide variables.
        """
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.page_handler)
        cls.client.request_kwargs['auth'] = get_auth(cls.cfg)

    def test_repos(self):
        """
        Test pagination for repositories.
        """
        # perform sanity check
        repos = self.client.get(REPO_PATH)
        self.assertEqual(len(repos), 0, repos)

        # Create shared variables.
        repo_hrefs = []  # append() and pop() are thread-safe
        repo_hrefs_lock = Lock()
        number_to_create = randint(100, 101)

        def create_repos():
            """
            Repeatedly create repos and append to ``repos_hrefs``.
            """
            # "It's better to beg for forgiveness than to ask for permission."
            while True:
                repo_href = self.client.post(REPO_PATH, gen_repo())['_href']
                with repo_hrefs_lock:
                    if len(repo_hrefs) < number_to_create:
                        repo_hrefs.append(repo_href)
                    else:
                        self.client.delete(repo_href)
                        break

        def delete_repos():
            """
            Delete the repos listed in ``repos_href``.
            """
            while True:
                try:
                    self.client.delete(repo_hrefs.pop())
                except IndexError:
                    break

        # Create repos, check results, and delete repos.
        create_threads = tuple(Thread(target=create_repos) for _ in range(4))
        delete_threads = tuple(Thread(target=delete_repos) for _ in range(8))
        try:
            for thread in create_threads:
                thread.start()
            for thread in create_threads:
                thread.join()
            repos = self.client.get(REPO_PATH)
            self.assertEqual(len(repos), number_to_create, repos)
        finally:
            for thread in delete_threads:
                thread.start()
            for thread in delete_threads:
                thread.join()

    def test_content(self):
        """
        Test pagination for different endpoints.

        Test pagination for repository versions, added and removed content.
        """
        # Add content to Pulp, create a repo, and add content to repo.
        populate_pulp(self.cfg, urljoin(FILE_MANY_FEED_URL, 'PULP_MANIFEST'))
        contents = sample(self.client.get(FILE_CONTENT_PATH), FILE_MANY_FEED_COUNT)
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        contents = sample(self.client.get(FILE_CONTENT_PATH), FILE_MANY_FEED_COUNT)

        def add_content():
            """Repeatedly pop an item from ``contents``, and add to repo."""
            while True:
                try:
                    content = contents.pop()
                    self.client.post(
                        repo['_versions_href'],
                        {'add_content_units': [content['_href']]}  # pylint:disable=unsubscriptable-object
                    )
                except IndexError:
                    break

        threads = tuple(Thread(target=add_content) for _ in range(8))
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Verify state of system.
        repo = self.client.get(repo['_href'])
        repo_versions = get_versions(repo)
        self.assertEqual(len(repo_versions), FILE_MANY_FEED_COUNT, repo_versions)
        content = get_content(repo)
        self.assertEqual(len(content), FILE_MANY_FEED_COUNT, content)
        added_content = get_added_content(repo)
        self.assertEqual(len(added_content), 1, added_content)
        removed_content = get_removed_content(repo)
        self.assertEqual(len(removed_content), 0, removed_content)
