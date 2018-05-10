# import hashlib
import unittest
from unittest import skip
from urllib.parse import urljoin

from pulp_smash import api, config
from pulp_smash.tests.pulp3.constants import REPO_PATH, DISTRIBUTION_PATH
from pulp_smash.tests.pulp3.utils import (gen_repo, gen_distribution, get_auth, get_added_content,
                                          get_versions, publish, sync)

from pulp_python.tests.functional.constants import (PYTHON_PUBLISHER_PATH, PYTHON_REMOTE_PATH,
                                                    PYTHON_PYPI_URL, PYTHON_CONTENT_PATH)
from pulp_python.tests.functional.utils import gen_publisher, gen_remote
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:E722

# from pulp_smash.constants import FILE_URL


@skip("needs better fixtures")
class AutoDistributionTestCase(unittest.TestCase):
    """Test auto distribution."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables.

        Add content to Pulp.
        """
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.client.request_kwargs['auth'] = get_auth()
        body = gen_remote(PYTHON_PYPI_URL)
        remote = {}
        repo = {}
        try:
            remote.update(cls.client.post(PYTHON_REMOTE_PATH, body))
            repo.update(cls.client.post(REPO_PATH, gen_repo()))
            sync(cls.cfg, remote, repo)
        finally:
            if remote:
                cls.client.delete(remote['_href'])
            if repo:
                cls.client.delete(repo['_href'])
        cls.contents = cls.client.get(PYTHON_CONTENT_PATH)['results'][:2]

    def test_repo_auto_distribution(self):
        """Test auto distribution of a repository.

        This test targets the following issue:

        * `Pulp Smash #947 <https://github.com/PulpQE/pulp-smash/issues/947>`_

        Do the following:

        1. Create a repository that has at least one repository version.
        2. Create a publisher.
        3. Create a distribution and set the repository and publishera to the
           previous created ones.
        4. Create a publication using the latest repository version.
        5. Assert that the previous distribution has a  ``publication`` set as
           the one created in step 4.
        6. Create a new repository version by adding content to the repository.
        7. Create another publication using the just created repository
           version.
        8. Assert that distribution now has the ``publication`` set to the
           publication created in the step 7.
        9. Verify that content added in the step 7 is now available to download
           from distribution, and verify that the content unit has the same
           checksum when fetched directly from Pulp-Fixtures.
        """
        self.assertGreaterEqual(len(self.contents), 2, self.contents)

        # Create a repository.
        repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['_href'])
        self.client.post(
            repo['_versions_href'],
            {'add_content_units': [self.contents[0]['_href']]}
        )
        repo = self.client.get(repo['_href'])

        # Create publisher.
        publisher = self.client.post(PYTHON_PUBLISHER_PATH, gen_publisher())
        self.addCleanup(self.client.delete, publisher['_href'])

        # Create a distribution
        body = gen_distribution()
        body['repository'] = repo['_href']
        body['publisher'] = publisher['_href']
        distribution = self.client.post(DISTRIBUTION_PATH, body)
        self.addCleanup(self.client.delete, distribution['_href'])
        last_version_href = get_versions(repo)[-1]['_href']
        publication = publish(
            self.cfg, publisher, repo, last_version_href)
        self.addCleanup(self.client.delete, publication['_href'])
        distribution = self.client.get(distribution['_href'])

        # Assert that distribution was updated as per step 5.
        self.assertEqual(distribution['publication'], publication['_href'])

        # Create a new repository version.
        self.client.post(
            repo['_versions_href'],
            {'add_content_units': [self.contents[1]['_href']]}
        )
        repo = self.client.get(repo['_href'])
        last_version_href = get_versions(repo)[-1]['_href']
        publication = publish(
            self.cfg, publisher, repo, last_version_href)
        self.addCleanup(self.client.delete, publication['_href'])
        distribution = self.client.get(distribution['_href'])

        # Assert that distribution was updated as per step 8.
        self.assertEqual(distribution['publication'], publication['_href'])
        unit_path = get_added_content(
            repo, last_version_href)['results'][0]['relative_path']
        unit_url = self.cfg.get_systems('api')[0].roles['api']['scheme']
        unit_url += '://' + distribution['base_url'] + '/'
        unit_url = urljoin(unit_url, unit_path)

        self.client.response_handler = api.safe_handler
        # pulp_hash = hashlib.sha256(self.client.get(unit_url).content).hexdigest()
        # fixtures_hash = hashlib.sha256(utils.http_get(urljoin(FILE_URL, unit_path))).hexdigest()

        # Verify checksum. Step 9.
        # self.assertEqual(fixtures_hash, pulp_hash)
