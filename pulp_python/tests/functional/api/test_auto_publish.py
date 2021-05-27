# coding=utf-8
"""Tests automatic updating of publications and distributions."""
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import download_content_unit

from pulp_python.tests.functional.utils import (
    cfg,
    gen_python_remote,
    TestCaseUsingBindings,
    TestHelpersMixin
)
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401
from pulpcore.client.pulp_python import RepositorySyncURL


class AutoPublishDistributeTestCase(TestCaseUsingBindings, TestHelpersMixin):
    """Test auto-publish and auto-distribution"""

    def setUp(self):
        """Create remote, repo, publish settings, and distribution."""
        self.remote = self.remote_api.create(gen_python_remote(policy="immediate"))
        self.addCleanup(self.remote_api.delete, self.remote.pulp_href)
        self.repo, self.distribution = self._create_empty_repo_and_distribution(autopublish=True)

    def test_01_sync(self):
        """Assert that syncing the repository triggers auto-publish and auto-distribution."""
        self.assertEqual(self.publications_api.list().count, 0)
        self.assertTrue(self.distribution.publication is None)

        # Sync the repository.
        repository_sync_data = RepositorySyncURL(remote=self.remote.pulp_href)
        sync_response = self.repo_api.sync(self.repo.pulp_href, repository_sync_data)
        task = monitor_task(sync_response.task)

        # Check that all the appropriate resources were created
        self.assertGreater(len(task.created_resources), 1)
        self.assertEqual(self.publications_api.list().count, 1)
        download_content_unit(cfg, self.distribution.to_dict(), "simple/")

        # Sync the repository again. Since there should be no new repository version, there
        # should be no new publications or distributions either.
        sync_response = self.repo_api.sync(self.repo.pulp_href, repository_sync_data)
        task = monitor_task(sync_response.task)

        self.assertEqual(len(task.created_resources), 0)
        self.assertEqual(self.publications_api.list().count, 1)

    def test_02_modify(self):
        """Assert that modifying the repository triggers auto-publish and auto-distribution."""
        self.assertEqual(self.publications_api.list().count, 0)
        self.assertTrue(self.distribution.publication is None)

        # Modify the repository by adding a content unit
        content = self.content_api.list().results[0].pulp_href
        modify_response = self.repo_api.modify(
            self.repo.pulp_href, {"add_content_units": [content]}
        )
        task = monitor_task(modify_response.task)

        # Check that all the appropriate resources were created
        self.assertGreater(len(task.created_resources), 1)
        self.assertEqual(self.publications_api.list().count, 1)
        download_content_unit(cfg, self.distribution.to_dict(), "simple/")
