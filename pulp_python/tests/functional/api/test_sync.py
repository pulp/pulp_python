import unittest
from pulp_smash import api, config
from pulp_smash.pulp3.constants import REPO_PATH
from pulp_smash.pulp3.utils import gen_repo, get_added_content, get_content, sync

from pulp_python.tests.functional.constants import (
    PYTHON_REMOTE_PATH,
    PYTHON_XS_PACKAGE_COUNT,
)
from pulp_python.tests.functional.utils import gen_python_remote
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class BasicSyncPythonRepoTestCase(unittest.TestCase):
    """
    Sync a repository with the python plugin.
    """

    @classmethod
    def setUpClass(cls):
        """
        Create class-wide variables.
        """
        cls.cfg = config.get_config()

    def test_sync(self):
        """
        Sync repositories with the python plugin.

        In order to sync a repository a remote has to be associated within
        this repository. When a repository is created this version field is set
        as None. After a sync the repository version is updated.

        Do the following:

        1. Create a repository, and a remote.
        2. Assert that repository version is None.
        3. Sync the remote.
        4. Assert that repository version is not None.
        5. Assert that the correct number of units were added and are present in the repo.
        6. Sync the remote one more time.
        7. Assert that repository version is different from the previous one.
        8. Assert that the same number of are present and that no units were added.

        """
        client = api.Client(self.cfg, api.json_handler)

        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])

        body = gen_python_remote()
        remote = client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])

        # Sync the repository.
        self.assertIsNone(repo['_latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = client.get(repo['_href'])

        self.assertIsNotNone(repo['_latest_version_href'])
        self.assertEqual(len(get_content(repo)), PYTHON_XS_PACKAGE_COUNT)
        self.assertEqual(len(get_added_content(repo)), PYTHON_XS_PACKAGE_COUNT)

        # Sync the repository again.
        latest_version_href = repo['_latest_version_href']
        sync(self.cfg, remote, repo)
        repo = client.get(repo['_href'])

        self.assertNotEqual(latest_version_href, repo['_latest_version_href'])
        self.assertEqual(len(get_content(repo)), PYTHON_XS_PACKAGE_COUNT)
        self.assertEqual(len(get_added_content(repo)), 0)
