# coding=utf-8
"""Tests that perform actions over content unit."""
from pulp_smash import cli
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import delete_orphans, modify_repo

from pulp_python.tests.functional.constants import (
    PYTHON_FIXTURE_URL,
    PYTHON_FIXTURES_PACKAGES,
    PYTHON_FIXTURES_FILENAMES,
    PYTHON_LIST_PROJECT_SPECIFIER,
    PYPI_URL,
)

from pulp_python.tests.functional.utils import (
    cfg,
    gen_artifact,
    gen_python_content_attrs,
    TestCaseUsingBindings,
    TestHelpersMixin,
)
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401
from urllib.parse import urljoin, urlsplit

from pulp_smash.utils import http_get


class PipInstallContentTestCase(TestCaseUsingBindings, TestHelpersMixin):
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
        super().setUpClass()
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

    def test_workflow_01(self):
        """
        Verify workflow 1
        """
        created_contents = []
        for pkg, filename in zip(self.PACKAGES_URLS, PYTHON_FIXTURES_FILENAMES):
            content_response = self.content_api.create(
                **gen_python_content_attrs(gen_artifact(pkg), filename)
            )
            created_contents.extend(monitor_task(content_response.task).created_resources)
            created_contents = [self.content_api.read(href).to_dict() for href in created_contents]

        repo = self._create_repository()
        # Add content
        modify_repo(cfg, repo.to_dict(), add_units=created_contents)
        repo = self.repo_api.read(repo.pulp_href)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)

        self.addCleanup(delete_orphans, cfg)
        self.check_consume(distro.to_dict())

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
        remote = self._create_remote(includes=PYTHON_LIST_PROJECT_SPECIFIER)
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)
        self.check_consume(distro.to_dict())

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
