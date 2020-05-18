import unittest
from pulp_smash import api, cli, config, exceptions
from pulp_smash.pulp3.constants import MEDIA_PATH
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_content_summary,
    get_added_content_summary,
    get_removed_content_summary,
    sync
)

from pulp_python.tests.functional.constants import (
    PYTHON_CONTENT_NAME,
    PYTHON_REMOTE_PATH,
    PYTHON_REPO_PATH,
    PYTHON_XS_PROJECT_SPECIFIER,
    PYTHON_XS_FIXTURE_SUMMARY,
    PYTHON_XS_PACKAGE_COUNT,
    PYTHON_SM_PROJECT_SPECIFIER,
    PYTHON_SM_PACKAGE_COUNT,
    PYTHON_MD_PROJECT_SPECIFIER,
    PYTHON_MD_FIXTURE_SUMMARY,
    PYTHON_MD_PACKAGE_COUNT,
    PYTHON_UNAVAILABLE_PROJECT_SPECIFIER,
    PYTHON_UNAVAILABLE_PACKAGE_COUNT,
    PYTHON_PRERELEASE_TEST_SPECIFIER,
    PYTHON_WITH_PRERELEASE_COUNT,
    PYTHON_WITHOUT_PRERELEASE_COUNT,
    PYTHON_WITH_PRERELEASE_FIXTURE_SUMMARY,
    PYTHON_WITHOUT_PRERELEASE_FIXTURE_SUMMARY
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
        repo = self.client.post(PYTHON_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        body = gen_python_remote()
        remote = self.client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        # Sync the repository.
        self.assertEqual("{}versions/0/".format(repo['pulp_href']), repo['latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        self.assertEqual("{}versions/1/".format(repo['pulp_href']), repo['latest_version_href'])
        self.assertDictEqual(get_content_summary(repo), PYTHON_XS_FIXTURE_SUMMARY)
        self.assertDictEqual(get_added_content_summary(repo), PYTHON_XS_FIXTURE_SUMMARY)

        # Sync the repository again.
        latest_version_href = repo['latest_version_href']
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        self.assertEqual(latest_version_href, repo['latest_version_href'])

    def test_file_decriptors(self):
        """Test whether file descriptors are closed properly.

        This test targets the following issue:
        `Pulp #4073 <https://pulp.plan.io/issues/4073>`_

        Do the following:
        1. Check if 'lsof' is installed. If it is not, skip this test.
        2. Create and sync a repo.
        3. Run the 'lsof' command to verify that files in the
           path ``/var/lib/pulp/`` are closed after the sync.
        4. Assert that issued command returns `0` opened files.
        """
        cli_client = cli.Client(self.cfg, cli.echo_handler)

        # check if 'lsof' is available
        if cli_client.run(('which', 'lsof')).returncode != 0:
            raise unittest.SkipTest('lsof package is not present')

        repo = self.client.post(PYTHON_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        remote = self.client.post(PYTHON_REMOTE_PATH, gen_python_remote())
        self.addCleanup(self.client.delete, remote['pulp_href'])

        sync(self.cfg, remote, repo)

        cmd = 'lsof -t +D {}'.format(MEDIA_PATH).split()
        response = cli_client.run(cmd).stdout
        self.assertEqual(len(response), 0, response)


class SyncInvalidURLTestCase(unittest.TestCase):
    """Sync a repository with an invalid url on the Remote."""

    def test_all(self):
        """
        Sync a repository using a Remote url that does not exist.

        Test that we get a task failure.

        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)

        repo = client.post(PYTHON_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['pulp_href'])

        body = gen_python_remote(url="http://i-am-an-invalid-url.com/invalid/")
        remote = client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['pulp_href'])

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
        cls.repo = cls.client.post(PYTHON_REPO_PATH, gen_repo())

    @classmethod
    def tearDownClass(cls):
        """
        Clean class-wide variable.
        """
        cls.client.delete(cls.repo['pulp_href'])
        cls.client.delete(cls.remote['pulp_href'])

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
        type(self).repo = self.client.get(self.repo['pulp_href'])

        self.assertDictEqual(
            get_content_summary(self.repo),
            PYTHON_WITHOUT_PRERELEASE_FIXTURE_SUMMARY
        )

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
        self.client.patch(self.remote['pulp_href'], body)
        type(self).remote = self.client.get(self.remote['pulp_href'])

        sync(self.cfg, self.remote, self.repo)
        type(self).repo = self.client.get(self.repo['pulp_href'])

        self.assertEqual(get_content_summary(self.repo), PYTHON_WITH_PRERELEASE_FIXTURE_SUMMARY)
        self.assertEqual(
            get_added_content_summary(self.repo)[PYTHON_CONTENT_NAME],
            PYTHON_WITH_PRERELEASE_COUNT - PYTHON_WITHOUT_PRERELEASE_COUNT
        )

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
        self.client.patch(self.remote['pulp_href'], body)
        type(self).remote = self.client.get(self.remote['pulp_href'])

        sync(self.cfg, self.remote, self.repo, mirror=True)
        type(self).repo = self.client.get(self.repo['pulp_href'])

        self.assertDictEqual(
            get_content_summary(self.repo),
            PYTHON_WITHOUT_PRERELEASE_FIXTURE_SUMMARY
        )
        self.assertEqual(
            get_removed_content_summary(self.repo)[PYTHON_CONTENT_NAME],
            PYTHON_WITH_PRERELEASE_COUNT - PYTHON_WITHOUT_PRERELEASE_COUNT
        )


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
        cls.repo = cls.client.post(PYTHON_REPO_PATH, gen_repo())

    @classmethod
    def tearDownClass(cls):
        """
        Clean class-wide variable.
        """
        cls.client.delete(cls.repo['pulp_href'])
        cls.client.delete(cls.remote['pulp_href'])

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
        type(self).repo = self.client.get(self.repo['pulp_href'])

        self.assertDictEqual(get_content_summary(self.repo), PYTHON_XS_FIXTURE_SUMMARY)

    def test_02_add_superset_include(self):
        """
        Test updating the remote with a larger set of includes, and syncing again.

        Do the following:

        1. Update the remote with a larger specifier that is a strict superset of the previous one.
        2. Sync the remote again.
        3. Assert that the content counts in the repo increased to match the new correct count.

        """
        body = {'includes': PYTHON_MD_PROJECT_SPECIFIER}
        self.client.patch(self.remote['pulp_href'], body)
        type(self).remote = self.client.get(self.remote['pulp_href'])

        sync(self.cfg, self.remote, self.repo)
        type(self).repo = self.client.get(self.repo['pulp_href'])

        self.assertDictEqual(get_content_summary(self.repo), PYTHON_MD_FIXTURE_SUMMARY)

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
        self.client.patch(self.remote['pulp_href'], body)
        type(self).remote = self.client.get(self.remote['pulp_href'])

        sync(self.cfg, self.remote, self.repo, mirror=True)
        type(self).repo = self.client.get(self.repo['pulp_href'])

        self.assertEqual(
            get_content_summary(self.repo)[PYTHON_CONTENT_NAME],
            PYTHON_MD_PACKAGE_COUNT - PYTHON_SM_PACKAGE_COUNT
        )
        self.assertEqual(
            get_removed_content_summary(self.repo)[PYTHON_CONTENT_NAME],
            PYTHON_SM_PACKAGE_COUNT
        )

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
        self.client.patch(self.remote['pulp_href'], body)
        type(self).remote = self.client.get(self.remote['pulp_href'])

        sync(self.cfg, self.remote, self.repo, mirror=True)
        type(self).repo = self.client.get(self.repo['pulp_href'])

        self.assertEqual(
            get_content_summary(self.repo)[PYTHON_CONTENT_NAME],
            PYTHON_MD_PACKAGE_COUNT - PYTHON_XS_PACKAGE_COUNT
        )


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
        repo = self.client.post(PYTHON_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        body = gen_python_remote(includes=PYTHON_UNAVAILABLE_PROJECT_SPECIFIER)
        remote = self.client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        self.assertEqual(
            get_content_summary(repo)[PYTHON_CONTENT_NAME],
            PYTHON_UNAVAILABLE_PACKAGE_COUNT
        )

    def test_exclude_unavailable_projects(self):
        """
        Test that sync doesn't fail if some of the excluded projects aren't available.

        Do the following:

        1. Update the remote to exclude a specifier that is smaller than the previous one.
        2. Sync the remote again.
        3. Assert that the content counts in the repo have increased again, to the count
           of the smaller excludes specifier.

        """
        repo = self.client.post(PYTHON_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        body = gen_python_remote(
            includes=PYTHON_MD_PROJECT_SPECIFIER,
            excludes=PYTHON_UNAVAILABLE_PROJECT_SPECIFIER
        )
        remote = self.client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['pulp_href'])

        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])

        self.assertEqual(
            get_content_summary(repo)[PYTHON_CONTENT_NAME],
            PYTHON_MD_PACKAGE_COUNT - PYTHON_UNAVAILABLE_PACKAGE_COUNT
        )
