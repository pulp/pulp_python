import unittest
from random import randint
from urllib.parse import urlsplit

from pulp_smash import api, config, utils


from pulp_smash.tests.pulp3.constants import REPO_PATH
from pulp_smash.tests.pulp3.utils import gen_repo, get_auth, get_content, sync

from pulp_python.tests.functional.constants import (PYTHON_PYPI_URL,
                                                    PYTHON_REMOTE_PATH, PYTHON_PACKAGE_COUNT)
from pulp_python.tests.functional.utils import gen_remote
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:E722


class SyncPythonRepoTestCase(unittest.TestCase, utils.SmokeTest):
    """Sync repositories with the python plugin."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()

    def test_sync(self):
        """Sync repositories with the python plugin.

        In order to sync a repository an remote has to be associated within
        this repository. When a repository is created this version field is set
        as None. After a sync the repository version is updated.

        Do the following:

        1. Create a repository, and an remote.
        2. Assert that repository version is None.
        3. Sync the remote.
        4. Assert that repository version is not None.
        5. Sync the remote one more time.
        6. Assert that repository version is different from the previous one.
        """
        client = api.Client(self.cfg, api.json_handler)
        client.request_kwargs['auth'] = get_auth()
        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        body = gen_remote(PYTHON_PYPI_URL)
        remote = client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])

        # Sync the repository.
        self.assertIsNone(repo['_latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = client.get(repo['_href'])
        self.assertIsNotNone(repo['_latest_version_href'])

        # Sync the repository again.
        latest_version_href = repo['_latest_version_href']
        sync(self.cfg, remote, repo)
        repo = client.get(repo['_href'])
        self.assertNotEqual(latest_version_href, repo['_latest_version_href'])


class SyncChangeRepoVersionTestCase(unittest.TestCase):
    """Verify whether sync of repository updates repository version."""

    def test_all(self):
        """Verify whether the sync of a repository updates its version.

        This test explores the design choice stated in the `Pulp #3308`_ that a
        new repository version is created even if the sync does not add or
        remove any content units. Even without any changes to the remote if a
        new sync occurs, a new repository version is created.

        .. _Pulp #3308: https://pulp.plan.io/issues/3308

        Do the following:

        1. Create a repository, and an remote.
        2. Sync the repository an arbitrary number of times.
        3. Verify that the repository version is equal to the previous number
           of syncs.
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        client.request_kwargs['auth'] = get_auth()
        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        body = gen_remote(PYTHON_PYPI_URL)
        remote = client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])

        number_of_syncs = randint(1, 10)
        for _ in range(number_of_syncs):
            sync(cfg, remote, repo)

        repo = client.get(repo['_href'])
        path = urlsplit(repo['_latest_version_href']).path
        latest_repo_version = int(path.split('/')[-2])
        self.assertEqual(latest_repo_version, number_of_syncs)


class MultiResourceLockingTestCase(unittest.TestCase, utils.SmokeTest):
    """Verify multi-resourcing locking.

    This test targets the following issues:

    * `Pulp #3186 <https://pulp.plan.io/issues/3186>`_
    * `Pulp Smash #879 <https://github.com/PulpQE/pulp-smash/issues/879>`_
    """

    def test_all(self):
        """Verify multi-resourcing locking.

        Do the following:

        1. Create a repository, and a remote.
        2. Update the remote to point to a different url.
        3. Immediately run a sync. The sync should fire after the update and
           sync from the second url.
        4. Assert that remote url was updated.
        5. Assert that the number of units present in the repository is
           according to the updated url.
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        client.request_kwargs['auth'] = get_auth()
        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        body = gen_remote(PYTHON_PYPI_URL)  # TODO: use 2 repos and don't sync the same one twice
        remote = client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])
        url = {'url': PYTHON_PYPI_URL}
        client.patch(remote['_href'], url)
        sync(cfg, remote, repo)
        repo = client.get(repo['_href'])
        remote = client.get(remote['_href'])
        self.assertEqual(remote['url'], url['url'])
        self.assertEqual(len(get_content(repo)['results']), PYTHON_PACKAGE_COUNT)
