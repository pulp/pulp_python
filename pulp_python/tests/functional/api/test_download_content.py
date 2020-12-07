# coding=utf-8
"""Tests that verify download of content served by Pulp."""
import hashlib
import json
import unittest
import requests
from random import choice
from urllib.parse import urljoin

from pulp_smash import config, utils
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import (
    download_content_unit,
    gen_distribution,
    gen_repo,
    get_content_summary,
)
from pulp_python.tests.functional.constants import (
    PYTHON_FIXTURE_URL,
    SHELF_PYTHON_JSON,
    PYTHON_LG_FIXTURE_SUMMARY,
    PYTHON_LG_PROJECT_SPECIFIER,
)
from pulp_python.tests.functional.utils import (
    gen_python_client,
    get_python_content_paths,
    gen_python_remote,
    publish,
)
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_python import (
    DistributionsPypiApi,
    PublicationsPypiApi,
    RepositoriesPythonApi,
    RepositorySyncURL,
    RemotesPythonApi,
    PythonPythonPublication,
)

PYPI_LAST_SERIAL = "X-PYPI-LAST-SERIAL"
PYPI_SERIAL_CONSTANT = 1000000000


class DownloadContentTestCase(unittest.TestCase):
    """Verify whether content served by pulp can be downloaded."""

    def test_all(self):
        """Verify whether content served by pulp can be downloaded.

        The process of publishing content is more involved in Pulp 3 than it
        was under Pulp 2. Given a repository, the process is as follows:

        1. Create a publication from the repository. (The latest repository
           version is selected if no version is specified.) A publication is a
           repository version plus metadata.
        2. Create a distribution from the publication. The distribution defines
           at which URLs a publication is available, e.g.
           ``http://example.com/content/foo/`` and
           ``http://example.com/content/bar/``.

        Do the following:

        1. Create, populate, publish, and distribute a repository.
        2. Select a random content unit in the distribution. Download that
           content unit from Pulp, and verify that the content unit has the
           same checksum when fetched directly from Pulp-Fixtures.

        This test targets the following issues:

        * `Pulp #2895 <https://pulp.plan.io/issues/2895>`_
        * `Pulp Smash #872 <https://github.com/pulp/pulp-smash/issues/872>`_
        """
        client = gen_python_client()
        repo_api = RepositoriesPythonApi(client)
        remote_api = RemotesPythonApi(client)
        publications = PublicationsPypiApi(client)
        distributions = DistributionsPypiApi(client)

        repo = repo_api.create(gen_repo())
        self.addCleanup(repo_api.delete, repo.pulp_href)

        body = gen_python_remote()
        remote = remote_api.create(body)
        self.addCleanup(remote_api.delete, remote.pulp_href)

        # Sync a Repository
        repository_sync_data = RepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = repo_api.read(repo.pulp_href)

        # Create a publication.
        publish_data = PythonPythonPublication(repository=repo.pulp_href)
        publish_response = publications.create(publish_data)
        created_resources = monitor_task(publish_response.task).created_resources
        publication_href = created_resources[0]
        self.addCleanup(publications.delete, publication_href)

        # Create a distribution.
        body = gen_distribution()
        body["publication"] = publication_href
        distribution_response = distributions.create(body)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = distributions.read(created_resources[0])
        self.addCleanup(distributions.delete, distribution.pulp_href)

        # Pick a content unit (of each type), and download it from both Pulp Fixtures…
        unit_paths = [
            choice(paths) for paths in get_python_content_paths(repo.to_dict()).values()
        ]
        fixtures_hashes = [
            hashlib.sha256(
                utils.http_get(
                    urljoin(urljoin(PYTHON_FIXTURE_URL, "packages/"), unit_path[0])
                )
            ).hexdigest()
            for unit_path in unit_paths
        ]

        # …and Pulp.
        pulp_hashes = []
        cfg = config.get_config()
        for unit_path in unit_paths:
            content = download_content_unit(cfg, distribution.to_dict(), unit_path[1])
            pulp_hashes.append(hashlib.sha256(content).hexdigest())

        self.assertEqual(fixtures_hashes, pulp_hashes)


class PublishPyPiJSON(unittest.TestCase):
    """Test whether a distributed Python repository has a PyPi json endpoint
    a.k.a Can be consumed by another Pulp instance

    Test targets the following issue:

    * `Pulp #2886 <https://pulp.plan.io/issues/2886>`_
    """

    @classmethod
    def setUpClass(cls):
        """Sets up the class"""
        client = gen_python_client()
        cls.cfg = config.get_config()
        cls.repo_api = RepositoriesPythonApi(client)
        cls.remote_api = RemotesPythonApi(client)
        cls.publications_api = PublicationsPypiApi(client)
        cls.distro_api = DistributionsPypiApi(client)

    @classmethod
    def setUp(cls):
        """Sets up the repo before every test"""
        cls.repo = cls.repo_api.create(gen_repo())

    def test_pypi_json(self):
        """Checks the basics 'pypi/{package_name}/json' endpoint
        Steps:
            1. Create Repo and Remote to only sync shelf-reader
            2. Sync with immediate policy
            3. Publish and Distribute new Repo
            4. Access JSON endpoint and verify received JSON matches source
        """
        self.addCleanup(self.repo_api.delete, self.repo.pulp_href)
        body = gen_python_remote(includes=["shelf-reader"], policy="immediate")
        self.sync_to_remote(body, create=True)
        self.addCleanup(self.remote_api.delete, self.remote.pulp_href)
        distro = self.gen_pub_dist()
        rel_url = "pypi/shelf-reader/json"
        package_json = download_content_unit(self.cfg, distro.to_dict(), rel_url)
        package = json.loads(package_json)
        self.assertEqual(SHELF_PYTHON_JSON["last_serial"], package["last_serial"])
        self.assertTrue(SHELF_PYTHON_JSON["info"].items() <= package["info"].items())
        self.assertEqual(len(SHELF_PYTHON_JSON["urls"]), len(package["urls"]))
        self.assert_download_info(SHELF_PYTHON_JSON["urls"], package["urls"],
                                  "Failed to match URLS")
        self.assertTrue(SHELF_PYTHON_JSON["releases"].keys() <= package["releases"].keys())
        for version in SHELF_PYTHON_JSON["releases"].keys():
            self.assert_download_info(SHELF_PYTHON_JSON["releases"][version],
                                      package["releases"][version], "Failed to match version")

    def assert_download_info(self, expected, received, message="Failed to match"):
        """
        Each version has a list of dists of that version, but the lists might
        not be in the same order, so check each dist of the second list
        """
        for dist in expected:
            dist = dict(dist)
            matched = False
            dist_items = dist.items()
            for dist2 in received:
                dist2 = dict(dist2)
                dist2["digests"].pop("md5", "")
                if dist_items <= dist2.items():
                    matched = True
                    break
            self.assertTrue(matched, message)

    def test_pypi_last_serial(self):
        """
        Checks that the endpoint has the header PYPI_LAST_SERIAL and is set
        TODO when serial field is added to Repo's, check this header against that
        """
        self.addCleanup(self.repo_api.delete, self.repo.pulp_href)
        body = gen_python_remote(includes=["shelf-reader"])
        self.sync_to_remote(body, create=True)
        distro = self.gen_pub_dist().to_dict()
        rel_url = "pypi/shelf-reader/json"
        url_fragments = [
            self.cfg.get_content_host_base_url(),
            "pulp/content",
            distro["base_path"],
            rel_url,
        ]
        unit_url = "/".join(url_fragments)
        response = requests.get(unit_url)
        self.assertIn(PYPI_LAST_SERIAL, response.headers)
        self.assertEqual(response.headers[PYPI_LAST_SERIAL], str(PYPI_SERIAL_CONSTANT))

    @unittest.skip("Content can not be synced without https")
    def test_basic_pulp_to_pulp_sync(self):
        """
        This test checks that the JSON endpoint is setup correctly to allow one Pulp instance
        to perform a basic sync from another Pulp instance
        """
        self.addCleanup(self.repo_api.delete, self.repo.pulp_href)
        body = gen_python_remote(includes=PYTHON_LG_PROJECT_SPECIFIER, policy="on_demand",
                                 prereleases=True)
        self.sync_to_remote(body, create=True)
        self.addCleanup(self.remote_api.delete, self.remote.pulp_href)
        self.assertEqual(get_content_summary(self.repo.to_dict()), PYTHON_LG_FIXTURE_SUMMARY)
        distro = self.gen_pub_dist().to_dict()
        url_fragments = [
            self.cfg.get_content_host_base_url(),
            "pulp/content",
            distro["base_path"],
            ""
        ]
        unit_url = "/".join(url_fragments)

        repo2 = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo2.pulp_href)
        body2 = gen_python_remote(url=unit_url, includes=PYTHON_LG_PROJECT_SPECIFIER,
                                  policy="on_demand", prereleases=True)
        self.repo = repo2
        self.sync_to_remote(body2, create=True)
        self.assertEqual(get_content_summary(self.repo.to_dict()), PYTHON_LG_FIXTURE_SUMMARY)
        self.addCleanup(self.remote_api.delete, self.remote.pulp_href)

    def sync_to_remote(self, body, create=False, mirror=False):
        """Takes a body and creates/updates a remote object, then it performs a sync"""
        if create:
            self.remote = self.remote_api.create(body)
        else:
            remote_task = self.remote_api.partial_update(self.remote.pulp_href, body)
            monitor_task(remote_task.task)
            self.remote = self.remote_api.read(self.remote.pulp_href)

        repository_sync_data = RepositorySyncURL(
            remote=self.remote.pulp_href, mirror=mirror
        )
        sync_response = self.repo_api.sync(self.repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        self.repo = self.repo_api.read(self.repo.pulp_href)

    def gen_pub_dist(self):
        """Takes a repo and generates a publication and then distributes it"""
        publication = publish(self.repo.to_dict())
        self.addCleanup(self.publications_api.delete, publication["pulp_href"])

        body = gen_distribution()
        body["publication"] = publication["pulp_href"]
        distro_response = self.distro_api.create(body)
        distro = self.distro_api.read(monitor_task(distro_response.task).created_resources[0])
        self.addCleanup(self.distro_api.delete, distro.pulp_href)
        return distro
