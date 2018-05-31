import unittest
from unittest import skip
from random import choice

from pulp_smash import api, cli, config, utils
from pulp_smash.exceptions import CalledProcessError
from pulp_smash.tests.pulp3.constants import ARTIFACTS_PATH, REPO_PATH
from pulp_smash.tests.pulp3.utils import (gen_repo, get_auth, get_content, get_versions,
                                          delete_orphans, delete_version, sync)


from pulp_python.tests.functional.constants import (PYTHON_PYPI_URL, PYTHON_REMOTE_PATH,
                                                    PYTHON_CONTENT_PATH)
from pulp_python.tests.functional.utils import gen_remote
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:E722

from pulp_smash.constants import FILE2_URL


class DeleteOrphansTestCase(unittest.TestCase, utils.SmokeTest):
    """Test whether orphans can be clean up.

    An orphan artifact is an artifact that is not in any content units.
    An orphan content unit is a content unit that is not in any repository
    version.

    This test targets the following issues:

    * `Pulp #3442 <https://pulp.plan.io/issues/3442>`_
    * `Pulp Smash #914 <https://github.com/PulpQE/pulp-smash/issues/914>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.api_client = api.Client(cls.cfg, api.json_handler)
        cls.api_client.request_kwargs['auth'] = get_auth()
        cls.cli_client = cli.Client(cls.cfg)
        cls.sudo = () if cli.is_root(cls.cfg) else ('sudo',)

    def test_clean_orphan_content_unit(self):
        """Test whether orphan content units can be clean up.

        Do the following:

        1. Create, and sync a repo.
        2. Remove a content unit from the repo. This will create a second
           repository version, and create an orphan content unit.
        3. Assert that content unit that was removed from the repo and its
           artifact are present on disk.
        4. Delete orphans.
        5. Assert that the orphan content unit was cleaned up, and its artifact
           is not present on disk.
        """
        repo = self.api_client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.api_client.delete, repo['_href'])
        body = gen_remote(PYTHON_PYPI_URL)
        remote = self.api_client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(self.api_client.delete, remote['_href'])
        sync(self.cfg, remote, repo)
        repo = self.api_client.get(repo['_href'])
        content = choice(get_content(repo)['results'])

        # Create an orphan content unit.
        self.api_client.post(
            repo['_versions_href'],
            {'remove_content_units': [content['_href']]}
        )

        # Verify that the artifact is present on disk.
        artifact_path = self.api_client.get(content['artifact'])['file']
        cmd = self.sudo + ('ls', artifact_path)
        self.cli_client.run(cmd)

        # Delete first repo version. The previous removed content unit will be
        # an orphan.
        delete_version(repo, get_versions(repo)[0]['_href'])
        content_units = self.api_client.get(PYTHON_CONTENT_PATH)['results']
        self.assertIn(content, content_units)
        delete_orphans()
        content_units = self.api_client.get(PYTHON_CONTENT_PATH)['results']
        self.assertNotIn(content, content_units)

        # Verify that the artifact was removed from disk.
        with self.assertRaises(CalledProcessError):
            self.cli_client.run(cmd)

    @skip("needs better fixtures")
    def test_clean_orphan_artifact(self):
        """Test whether orphan artifacts units can be clean up."""
        repo = self.api_client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.api_client.delete, repo['_href'])
        files = {'file': utils.http_get(FILE2_URL)}
        artifact = self.api_client.post(ARTIFACTS_PATH, files=files)
        cmd = self.sudo + ('ls', artifact['file'])
        self.cli_client.run(cmd)
        delete_orphans()
        with self.assertRaises(CalledProcessError):
            self.cli_client.run(cmd)
