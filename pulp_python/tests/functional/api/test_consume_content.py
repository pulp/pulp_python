import unittest

from pulp_smash import api, config, cli, utils
from pulp_smash.pulp3.utils import gen_repo, gen_distribution, sync, delete_orphans

from pulp_python.tests.functional.utils import (
    gen_python_publication,
    gen_python_remote,
)

from pulp_python.tests.functional.constants import (
    PYTHON_FIXTURES_URL,
    PYTHON_REMOTE_PATH,
    PYTHON_DISTRIBUTION_PATH,
    PYTHON_REPO_PATH,
    PYPI_URL,
    PYTHON_CONTENT_PATH,
    PYTHON_FIXTURES_FILENAMES,
    PYTHON_FIXTURES_PACKAGES,
    PYTHON_LIST_PROJECT_SPECIFIER,
)

from pulp_smash.pulp3.constants import ARTIFACTS_PATH
from urllib.parse import urljoin, urlsplit


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
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.cli_client = cli.Client(cls.cfg)
        cls.prior_packages = []
        cls.PACKAGES = PYTHON_FIXTURES_PACKAGES
        cls.PACKAGES_URLS = [
            urljoin(urljoin(PYTHON_FIXTURES_URL, "packages/"), filename)
            for filename in PYTHON_FIXTURES_FILENAMES
        ]
        cls.PACKAGES_FILES = [
            {"file": utils.http_get(file)} for file in cls.PACKAGES_URLS
        ]
        delete_orphans(cls.cfg)
        for pkg in cls.PACKAGES:
            cls.assertFalse(cls, cls.check_install(cls.cli_client, pkg),
                            "{} is already installed".format(pkg))

    def test_workflow_01(self):
        """
        Verify workflow 1
        """
        repo = self.client.post(PYTHON_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        artifacts = []
        for pkg in self.PACKAGES_FILES:
            artifacts.append(self.client.post(ARTIFACTS_PATH, files=pkg))

        for filename, artifact in zip(PYTHON_FIXTURES_FILENAMES, artifacts):
            task_url = self.client.post(
                PYTHON_CONTENT_PATH,
                data={
                    "filename": filename,
                    "relative_path": filename,
                    "artifact": artifact["pulp_href"],
                },
            )
            task = tuple(api.poll_spawned_tasks(self.cfg, task_url))
            content_url = task[-1]["created_resources"][0]
            self.client.post(
                urljoin(repo["pulp_href"], "modify/"),
                {"add_content_units": [content_url]},
            )
        repo = self.client.get(repo["pulp_href"])
        distribution = self.gen_pub_dist(repo)
        self.addCleanup(delete_orphans, self.cfg)
        self.check_consume(distribution)

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
        repo = self.client.post(PYTHON_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo["pulp_href"])

        body = gen_python_remote(
            PYTHON_FIXTURES_URL, includes=PYTHON_LIST_PROJECT_SPECIFIER
        )
        remote = self.client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote["pulp_href"])

        sync(self.cfg, remote, repo)
        repo = self.client.get(repo["pulp_href"])
        distribution = self.gen_pub_dist(repo)
        self.check_consume(distribution)

    def check_consume(self, distribution):
        """Tests that pip packages hosted in a distribution can be consumed"""
        host_base_url = self.cfg.get_content_host_base_url()
        url = "".join(
            [host_base_url, "/pulp/content/", distribution["base_path"], "/simple/"]
        )
        for pkg in self.PACKAGES:
            out = self.install(self.cli_client, pkg, host=url)
            self.assertTrue(self.check_install(self.cli_client, pkg), out)
            self.addCleanup(self.uninstall, self.cli_client, pkg)

    def gen_pub_dist(self, repo):
        """Takes a repo and generates a publication and then distributes it"""
        publication = gen_python_publication(self.cfg, repository=repo)
        self.addCleanup(self.client.delete, publication["pulp_href"])

        body = gen_distribution()
        body["publication"] = publication["pulp_href"]
        distribution = self.client.using_handler(api.task_handler).post(
            PYTHON_DISTRIBUTION_PATH, body
        )
        return distribution

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
