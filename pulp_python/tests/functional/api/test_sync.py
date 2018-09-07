import unittest
from pulp_smash import api, config, exceptions
from pulp_smash.pulp3.constants import REPO_PATH
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_added_content,
    get_content,
    get_removed_content,
    sync
)

from pulp_python.tests.functional.constants import (
    PYTHON_REMOTE_PATH,
    PYTHON_XS_PROJECT_SPECIFIER,
    PYTHON_XS_PACKAGE_COUNT,
    PYTHON_SM_PROJECT_SPECIFIER,
    PYTHON_SM_PACKAGE_COUNT,
    PYTHON_MD_PROJECT_SPECIFIER,
    PYTHON_MD_PACKAGE_COUNT,
    PYTHON_UNAVAILABLE_PACKAGE_COUNT,
    PYTHON_UNAVAILABLE_PROJECT_SPECIFIER,
    PYTHON_PRERELEASE_TEST_SPECIFIER,
    PYTHON_WITH_PRERELEASE_COUNT,
    PYTHON_WITHOUT_PRERELEASE_COUNT
)
from pulp_python.tests.functional.utils import gen_python_remote
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class BasicPythonSyncTestCase(unittest.TestCase):
    """
    Sync a repository with the python plugin.
    """

    @classmethod
    def setUpClass(cls):
        """
        Create class-wide variables.
        """
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

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
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        body = gen_python_remote()
        remote = self.client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['_href'])

        # Sync the repository.
        self.assertIsNone(repo['_latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])

        self.assertIsNotNone(repo['_latest_version_href'])
        self.assertEqual(len(get_content(repo)), PYTHON_XS_PACKAGE_COUNT)
        self.assertEqual(len(get_added_content(repo)), PYTHON_XS_PACKAGE_COUNT)

        # Sync the repository again.
        latest_version_href = repo['_latest_version_href']
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])

        self.assertNotEqual(latest_version_href, repo['_latest_version_href'])
        self.assertEqual(len(get_content(repo)), PYTHON_XS_PACKAGE_COUNT)
        self.assertEqual(len(get_added_content(repo)), 0)


class SyncInvalidURLTestCase(unittest.TestCase):
    """Sync a repository with an invalid url on the Remote."""

    def test_all(self):
        """
        Sync a repository using a Remote url that does not exist.

        Test that we get a task failure.

        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)

        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])

        body = gen_python_remote(url="http://i-am-an-invalid-url.com/invalid/")
        remote = client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])

        with self.assertRaises(exceptions.TaskReportError):
            sync(cfg, remote, repo)


class PrereleasesTestCase(unittest.TestCase):
    """
    Sync a repository with and without prereleases included by the Remote.
    """

    @classmethod
    def setUpClass(cls):
        """
        Create class-wide variables.
        """
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

        cls.remote = {}
        cls.repo = cls.client.post(REPO_PATH, gen_repo())

    @classmethod
    def tearDownClass(cls):
        """
        Clean class-wide variable.
        """
        cls.client.delete(cls.repo['_href'])
        cls.client.delete(cls.remote['_href'])

    def test_01_excluding_prereleases(self):
        """
        Sync a Remote, excluding prereleases.

        Do the following:

        1. Create a remote with prereleases=False.
        2. Sync the remote.
        3. Assert that the content counts in the repo match the non-prerelease packages matched
           by the specifiers.

        """
        body = gen_python_remote(includes=PYTHON_PRERELEASE_TEST_SPECIFIER, prereleases=False)
        type(self).remote = self.client.post(PYTHON_REMOTE_PATH, body)

        sync(self.cfg, self.remote, self.repo)
        type(self).repo = self.client.get(self.repo['_href'])

        self.assertEqual(len(get_content(self.repo)), PYTHON_WITHOUT_PRERELEASE_COUNT)

    def test_02_including_prereleases(self):
        """
        Sync a Remote, including prereleases.

        Do the following:

        1. Update the remote to include pre-releases.
        2. Sync the remote again.
        3. Assert that the content counts in the repo match *all* the packages matched by the
           specifier, including prereleases.

        """
        body = {'prereleases': True}
        self.client.patch(self.remote['_href'], body)
        type(self).remote = self.client.get(self.remote['_href'])

        sync(self.cfg, self.remote, self.repo)
        type(self).repo = self.client.get(self.repo['_href'])

        self.assertEqual(len(get_content(self.repo)), PYTHON_WITH_PRERELEASE_COUNT)
        self.assertEqual(len(get_added_content(self.repo)),
                         PYTHON_WITH_PRERELEASE_COUNT - PYTHON_WITHOUT_PRERELEASE_COUNT)

    def test_03_removing_units(self):
        """
        Sync a Remote, excluding prereleases again.

        Just to be sure that the units are being properly removed afterwards.

        Do the following:

        1. Update the remote to exclude pre-releases again.
        2. Sync the remote again.
        3. Assert that we're back to the state in test_01_excluding_prereleases.

        """
        body = {'prereleases': False}
        self.client.patch(self.remote['_href'], body)
        type(self).remote = self.client.get(self.remote['_href'])

        sync(self.cfg, self.remote, self.repo)
        type(self).repo = self.client.get(self.repo['_href'])

        self.assertEqual(len(get_content(self.repo)), PYTHON_WITHOUT_PRERELEASE_COUNT)
        self.assertEqual(len(get_removed_content(self.repo)),
                         PYTHON_WITH_PRERELEASE_COUNT - PYTHON_WITHOUT_PRERELEASE_COUNT)


class IncludesExcludesTestCase(unittest.TestCase):
    """
    Test behavior of the includes and excludes fields on the Remote during sync.
    """

    @classmethod
    def setUpClass(cls):
        """
        Create class-wide variables.
        """
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

        cls.remote = {}
        cls.repo = cls.client.post(REPO_PATH, gen_repo())

    @classmethod
    def tearDownClass(cls):
        """
        Clean class-wide variable.
        """
        cls.client.delete(cls.repo['_href'])
        cls.client.delete(cls.remote['_href'])

    def test_01_basic_include(self):
        """
        Test updating the remote and performing normal sync.

        Really just a setup for the next test.

        Do the following:

        1. Create a remote.
        2. Sync the remote.
        3. Assert that the content counts in the repo match the correct count for the specifier.

        """
        body = gen_python_remote(includes=PYTHON_XS_PROJECT_SPECIFIER)
        type(self).remote = self.client.post(PYTHON_REMOTE_PATH, body)

        sync(self.cfg, self.remote, self.repo)
        type(self).repo = self.client.get(self.repo['_href'])

        self.assertEqual(len(get_content(self.repo)), PYTHON_XS_PACKAGE_COUNT)

    def test_02_add_superset_include(self):
        """
        Test updating the remote with a larger set of includes, and syncing again.

        Do the following:

        1. Update the remote with a larger specifier that is a strict superset of the previous one.
        2. Sync the remote again.
        3. Assert that the content counts in the repo increased to match the new correct count.

        """
        body = {'includes': PYTHON_MD_PROJECT_SPECIFIER}
        self.client.patch(self.remote['_href'], body)
        type(self).remote = self.client.get(self.remote['_href'])

        sync(self.cfg, self.remote, self.repo)
        type(self).repo = self.client.get(self.repo['_href'])

        self.assertEqual(len(get_content(self.repo)), PYTHON_MD_PACKAGE_COUNT)

    def test_03_add_subset_exclude(self):
        """
        Test that excluding a subset of the packages will reduce the count by that amount.

        Do the following:

        1. Update the remote to exclude a specifier that is a strict subset of the previous one.
        2. Sync the remote again.
        3. Assert that that the content counts in the repo decreased by the count of the
           excludes specifier.

        """
        body = {'excludes': PYTHON_SM_PROJECT_SPECIFIER}
        self.client.patch(self.remote['_href'], body)
        type(self).remote = self.client.get(self.remote['_href'])

        sync(self.cfg, self.remote, self.repo)
        type(self).repo = self.client.get(self.repo['_href'])

        self.assertEqual(len(get_content(self.repo)),
                         PYTHON_MD_PACKAGE_COUNT - PYTHON_SM_PACKAGE_COUNT)

    def test_04_remove_excludes(self):
        """
        Test that removing some of the excludes increases the count again.

        Do the following:

        1. Update the remote to exclude a specifier that is smaller than the previous one.
        2. Sync the remote again.
        3. Assert that the content counts in the repo have increased again, to the count
           of the smaller excludes specifier.

        """
        body = {'excludes': PYTHON_XS_PROJECT_SPECIFIER}
        self.client.patch(self.remote['_href'], body)
        type(self).remote = self.client.get(self.remote['_href'])

        sync(self.cfg, self.remote, self.repo)
        type(self).repo = self.client.get(self.repo['_href'])

        self.assertEqual(len(get_content(self.repo)),
                         PYTHON_MD_PACKAGE_COUNT - PYTHON_XS_PACKAGE_COUNT)


class UnavailableProjectsTestCase(unittest.TestCase):
    """
    Test syncing with projects that aren't on the upstream remote.

    Tests that sync doesn't fail if the Remote contains projects (includes or excludes) for which
    metadata does not exist on the upstream remote.
    """

    @classmethod
    def setUpClass(cls):
        """
        Create class-wide variables.
        """
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_include_unavailable_projects(self):
        """
        Test that the sync doesn't fail if some included projects aren't available.

        Do the following:

        1. Create a remote.
        2. Sync the remote.
        3. Assert that the content counts in the repo match the correct count for the specifier.

        """
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        body = gen_python_remote(includes=PYTHON_UNAVAILABLE_PROJECT_SPECIFIER)
        remote = self.client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['_href'])

        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])

        self.assertEqual(len(get_content(repo)), PYTHON_UNAVAILABLE_PACKAGE_COUNT)

    def test_exclude_unavailable_projects(self):
        """
        Test that sync doesn't fail if some of the excluded projects aren't available.

        Do the following:

        1. Update the remote to exclude a specifier that is smaller than the previous one.
        2. Sync the remote again.
        3. Assert that the content counts in the repo have increased again, to the count
           of the smaller excludes specifier.

        """
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        body = gen_python_remote(
            includes=PYTHON_MD_PROJECT_SPECIFIER,
            excludes=PYTHON_UNAVAILABLE_PROJECT_SPECIFIER
        )
        remote = self.client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['_href'])

        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['_href'])

        self.assertEqual(len(get_content(repo)),
                         PYTHON_MD_PACKAGE_COUNT - PYTHON_UNAVAILABLE_PACKAGE_COUNT)
