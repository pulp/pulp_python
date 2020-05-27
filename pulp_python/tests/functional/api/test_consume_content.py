import unittest

from pulp_smash import api, config, cli
from pulp_smash.pulp3.utils import (
    gen_repo,
    gen_distribution,
    sync,
)

from pulp_python.tests.functional.utils import (
    gen_python_publication,
    gen_python_remote,
)

from pulp_python.tests.functional.constants import (
    PYTHON_FIXTURES_URL,
    PYTHON_REMOTE_PATH,
    PYTHON_DISTRIBUTION_PATH,
    PYTHON_REPO_PATH,
)

from urllib.parse import urlsplit


class PipInstallContentTestCase(unittest.TestCase):
    """
    Verify whether content served by Pulp can be consumed through pip install.
    """

    def test_install(self):
        """
        Verify whether content served by Pulp can be consumed through pip install.

        Do the following:

        1. Create, populate, publish, and distribute a repository.
        2. Pip install a package from the pulp repository.
        3. Check pip install was successful.

        This test targets the following issues:
        * `Pulp #4682 <https://pulp.plan.io/issues/4682>`_
        * `Pulp #4677 <https://pulp.plan.io/issues/4677>`_
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)

        repo = client.post(PYTHON_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo["pulp_href"])

        body = gen_python_remote(PYTHON_FIXTURES_URL)
        remote = client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote["pulp_href"])

        sync(cfg, remote, repo)
        repo = client.get(repo["pulp_href"])

        publication = gen_python_publication(cfg, repository=repo)
        self.addCleanup(client.delete, publication["pulp_href"])

        body = gen_distribution()
        body["publication"] = publication["pulp_href"]
        distribution = client.using_handler(api.task_handler).post(
            PYTHON_DISTRIBUTION_PATH, body
        )
        self.addCleanup(client.delete, distribution["pulp_href"])

        cli_client = cli.Client(cfg)
        # uninstall package before trying to install it
        if self.check_install(cli_client, "shelf-reader"):
            cli_client.run(("pip", "uninstall", "shelf-reader", "-y"))

        host_base_url = cfg.get_content_host_base_url()
        url = "".join(
            [host_base_url, "/pulp/content/", distribution["base_path"], "/simple/"]
        )
        # Pip install shelf-reader
        out = cli_client.run(
            (
                "pip",
                "install",
                "--trusted-host",
                urlsplit(host_base_url).hostname,
                "-i",
                url,
                "shelf-reader",
            )
        ).stdout
        self.addCleanup(cli_client.run, ("pip", "uninstall", "shelf-reader", "-y"))

        # check that pip correctly installed
        self.assertTrue(self.check_install(cli_client, "shelf-reader"), out)

    def check_install(self, cli_client, package):
        """Returns true if python package is installed, false otherwise"""
        return cli_client.run(("pip", "list")).stdout.find(package) != -1
