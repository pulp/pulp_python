# coding=utf-8
"""Tests that python plugin can fully mirror PyPi and other Pulp repositories"""
import unittest

from pulp_smash import config
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import gen_repo, get_content_summary

from pulp_python.tests.functional.constants import PYTHON_CONTENT_NAME
from pulp_python.tests.functional.utils import gen_python_client, gen_python_remote
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulpcore import TasksApi, ApiClient as CoreApiClient, Configuration
from pulpcore.client.pulp_python import (
    RepositoriesPythonApi,
    RepositorySyncURL,
    RemotesPythonApi,
)
import socket


@unittest.skip
class PyPiMirrorTestCase(unittest.TestCase):
    """
    Testing Pulp's full syncing ability of Python repositories

     This test targets the following issues:

    * `Pulp #985 <https://pulp.plan.io/issues/985>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = gen_python_client()
        configuration = Configuration()
        configuration.username = 'admin'
        configuration.password = 'password'
        configuration.host = 'http://{}:24817'.format(socket.gethostname())
        configuration.safe_chars_for_path_param = '/'
        cls.core_client = CoreApiClient(configuration)

    def test_on_demand_pypi_full_sync(self):
        """This test syncs all of PyPi"""
        repo_api = RepositoriesPythonApi(self.client)
        remote_api = RemotesPythonApi(self.client)
        tasks_api = TasksApi(self.core_client)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        body = gen_python_remote("https://pypi.org", includes=[], policy="on_demand")
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        # Sync the repository.
        self.assertEqual(repo.latest_version_href, f"{repo.pulp_href}versions/0/")
        repository_sync_data = RepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = repo_api.read(repo.pulp_href)

        sync_task = tasks_api.read(sync_response.task)
        time_diff = sync_task.finished_at - sync_task.started_at
        print("Delete time: {} seconds".format(time_diff.seconds))

        self.assertIsNotNone(repo.latest_version_href)
        # As of August 11 2020, all_packages() returns 253,587 packages,
        # only 248,677 of them were downloadable
        self.assertTrue(get_content_summary(repo.to_dict())[PYTHON_CONTENT_NAME] > 245000)
