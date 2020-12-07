# coding=utf-8
"""Tests that perform actions over content unit."""
import unittest

from pulp_smash import cli
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import gen_repo, gen_distribution, delete_orphans

from pulp_python.tests.functional.constants import (
    PYTHON_FIXTURE_URL,
    PYTHON_FIXTURES_PACKAGES,
    PYTHON_FIXTURES_FILENAMES,
    PYTHON_LIST_PROJECT_SPECIFIER,
    PYPI_URL,
)

from pulp_python.tests.functional.utils import (
    gen_artifact,
    gen_python_client,
    gen_python_content_attrs,
    cfg,
    publish,
    gen_python_remote,
)
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401
from urllib.parse import urljoin, urlsplit

from pulpcore.client.pulp_python import (
    RepositoriesPythonApi,
    RemotesPythonApi,
    PublicationsPypiApi,
    ContentPackagesApi,
    DistributionsPypiApi,
    RepositorySyncURL,
)

from pulp_smash.utils import http_get


class PipInstallContentTestCase(unittest.TestCase):
    """
    Verify whether content served by Pulp can be consumed through pip install.
    Workflows tested are:
    1) create repo -> upload package artifact -> create content -> add content to repo -> publish
    repo -> distribute publication -> consume through pip
    2) create repo -> sync with remote -> publish repo -> distribute publication -> consume through
       pip
    """

    @classmethod
    def setUpClass(cls):
        """
        Check if packages to install through tests are already installed
        """
        cls.client = gen_python_client()
        cls.cli_client = cli.Client(cfg)
        cls.PACKAGES = PYTHON_FIXTURES_PACKAGES
        cls.PACKAGES_URLS = [
            urljoin(urljoin(PYTHON_FIXTURE_URL, "packages/"), filename)
            for filename in PYTHON_FIXTURES_FILENAMES
        ]
        cls.PACKAGES_FILES = [{"file": http_get(file)} for file in cls.PACKAGES_URLS]
        delete_orphans()
        for pkg in cls.PACKAGES:
            cls.assertFalse(
                cls,
                cls.check_install(cls.cli_client, pkg),
                "{} is already installed".format(pkg),
            )
        cls.repo_api = RepositoriesPythonApi(cls.client)
        cls.remote_api = RemotesPythonApi(cls.client)
        cls.content_api = ContentPackagesApi(cls.client)
        cls.publications_api = PublicationsPypiApi(cls.client)
        cls.distro_api = DistributionsPypiApi(cls.client)

    def test_workflow_01(self):
        """
        Verify workflow 1
        """
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        artifacts = []
        for pkg in self.PACKAGES_URLS:
            artifacts.append(gen_artifact(pkg))

        for filename, artifact in zip(PYTHON_FIXTURES_FILENAMES, artifacts):
            content_response = self.content_api.create(
                **gen_python_content_attrs(artifact, filename)
            )
            created_resources = monitor_task(content_response.task).created_resources
            self.repo_api.modify(
                repo.pulp_href, {"add_content_units": created_resources}
            )
        repo = self.repo_api.read(repo.pulp_href)
        distribution = self.gen_pub_dist(repo)

        self.addCleanup(delete_orphans, cfg)
        self.check_consume(distribution.to_dict())

    def test_workflow_02(self):
        """
        Verify workflow 2

        Do the following:

        1. Create, populate, publish, and distribute a repository.
        2. Pip install a package from the pulp repository.
        3. Check pip install was successful.

        This test targets the following issues:
        * `Pulp #4682 <https://pulp.plan.io/issues/4682>`_
        * `Pulp #4677 <https://pulp.plan.io/issues/4677>`_
        """
        repo = self.repo_api.create(gen_repo())
        self.addCleanup(self.repo_api.delete, repo.pulp_href)

        body = gen_python_remote(includes=PYTHON_LIST_PROJECT_SPECIFIER)
        remote = self.remote_api.create(body)
        self.addCleanup(self.remote_api.delete, remote.pulp_href)

        repository_sync_data = RepositorySyncURL(remote=remote.pulp_href)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = self.repo_api.read(repo.pulp_href)

        distribution = self.gen_pub_dist(repo)
        self.check_consume(distribution.to_dict())

    def check_consume(self, distribution):
        """Tests that pip packages hosted in a distribution can be consumed"""
        host_base_url = cfg.get_content_host_base_url()
        url = "".join(
            [host_base_url, "/pulp/content/", distribution["base_path"], "/simple/"]
        )
        for pkg in self.PACKAGES:
            out = self.install(self.cli_client, pkg, host=url)
            self.assertTrue(self.check_install(self.cli_client, pkg), out)
            self.addCleanup(self.uninstall, self.cli_client, pkg)

    def gen_pub_dist(self, repo):
        """Takes a repo and generates a publication and then distributes it"""
        publication = publish(repo.to_dict())
        self.addCleanup(self.publications_api.delete, publication["pulp_href"])

        body = gen_distribution()
        body["publication"] = publication["pulp_href"]
        distro_response = self.distro_api.create(body)
        distro = self.distro_api.read(monitor_task(distro_response.task).created_resources[0])
        self.addCleanup(self.distro_api.delete, distro.pulp_href)
        return distro

    @staticmethod
    def check_install(cli_client, package):
        """Returns true if python package is installed, false otherwise"""
        return cli_client.run(("pip", "list")).stdout.find(package) != -1

    @staticmethod
    def install(cli_client, package, host=PYPI_URL):
        """Installs a pip package from the host url"""
        return cli_client.run(
            (
                "pip",
                "install",
                "--no-deps",
                "--trusted-host",
                urlsplit(host).hostname,
                "-i",
                host,
                package,
            )
        ).stdout

    @staticmethod
    def uninstall(cli_client, package):
        """
        Uninstalls a pip package and returns the version number
        Uninstall Message format: "Found existing installation: package X.X.X ..."
        """
        return cli_client.run(("pip", "uninstall", package, "-y")).stdout.split()[4]
