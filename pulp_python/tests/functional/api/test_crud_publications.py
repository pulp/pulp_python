# coding=utf-8
"""Tests that publish python plugin repositories."""
import unittest
from random import choice

from pulp_smash import config
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import gen_repo, get_content, get_versions, modify_repo

from pulp_python.tests.functional.constants import PYTHON_CONTENT_NAME
from pulp_python.tests.functional.utils import gen_python_client, gen_python_remote
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_python import (
    PublicationsPypiApi,
    RepositoriesPythonApi,
    RepositorySyncURL,
    RemotesPythonApi,
    PythonPythonPublication,
)
from pulpcore.client.pulp_python.exceptions import ApiException


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


class PublishOnDemandContent(unittest.TestCase):
    """Test whether a 'on_demand' synced repository can be published.

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
        client = gen_python_client()
        repo_api = RepositoriesPythonApi(client)
        remote_api = RemotesPythonApi(client)
        publications = PublicationsPypiApi(client)

        body = gen_python_remote(policy="on_demand")
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        repository_sync_data = RepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = repo_api.read(repo.pulp_href)

        publish_data = PythonPythonPublication(repository=repo.pulp_href)
        publish_response = publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        self.addCleanup(publications.delete, publication_href)
        publication = publications.read(publication_href)

        self.assertEqual(publication.repository_version, repo.latest_version_href)

    # TODO TEST LIST
    # TODO TEST PARTIAL AND FULL UPDATE
    # TODO Maybe test DELETE
