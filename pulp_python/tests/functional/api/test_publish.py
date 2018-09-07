import unittest
from random import choice
from urllib.parse import urljoin

from requests.exceptions import HTTPError

from pulp_smash import api, config
from pulp_smash.pulp3.constants import REPO_PATH
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_versions,
    sync,
    publish
)

from pulp_python.tests.functional.constants import (
    PYTHON_CONTENT_PATH,
    PYTHON_PUBLISHER_PATH,
    PYTHON_FIXTURES_URL,
    PYTHON_REMOTE_PATH
)
from pulp_python.tests.functional.utils import gen_python_remote, gen_python_publisher
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class PublishAnyRepoVersionTestCase(unittest.TestCase):
    """
    Test whether a particular repository version can be published.

    This test targets the following issues:

    * `Pulp #3324 <https://pulp.plan.io/issues/3324>`_
    * `Pulp Smash #897 <https://github.com/PulpQE/pulp-smash/issues/897>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_all(self):
        """
        Test whether a particular repository version can be published.

        1. Create a repository with at least 2 repository versions.
        2. Create a publication by supplying the latest ``repository_version``.
        3. Assert that the publication ``repository_version`` attribute points
           to the latest repository version.
        4. Create a publication by supplying the non-latest
           ``repository_version``.
        5. Assert that the publication ``repository_version`` attribute points
           to the supplied repository version.
        6. Assert that an exception is raised when providing two different
           repository versions to be published at same time.

        """
        body = gen_python_remote(PYTHON_FIXTURES_URL)
        remote = self.client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(self.client.delete, remote['_href'])

        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])

        sync(self.cfg, remote, repo)

        publisher = self.client.post(PYTHON_PUBLISHER_PATH, gen_python_publisher())
        self.addCleanup(self.client.delete, publisher['_href'])

        # Step 1
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        for python_content in self.client.get(PYTHON_CONTENT_PATH)['results']:
            self.client.post(
                repo['_versions_href'],
                {'add_content_units': [python_content['_href']]}
            )
        versions = get_versions(repo)
        non_latest = choice(versions[:-1])['_href']

        # Step 2
        publication = publish(self.cfg, publisher, repo)

        # Step 3
        self.assertEqual(publication['repository_version'], versions[-1]['_href'])

        # Step 4
        publication = publish(self.cfg, publisher, repo, non_latest)

        # Step 5
        self.assertEqual(publication['repository_version'], non_latest)

        # Step 6
        with self.assertRaises(HTTPError):
            body = {
                'repository': repo['_href'],
                'repository_version': non_latest
            }
            self.client.post(urljoin(publisher['_href'], 'publish/'), body)
