# TODO TEST PUBLISH
import unittest
from random import choice

from requests.exceptions import HTTPError

from pulp_smash import api, config
from pulp_smash.pulp3.utils import (
    gen_repo,
    get_content,
    get_versions,
    sync,
)

from pulp_python.tests.functional.constants import (
    PYTHON_CONTENT_NAME,
    PYTHON_FIXTURES_URL,
    PYTHON_REMOTE_PATH,
    PYTHON_REPO_PATH,
)
from pulp_python.tests.functional.utils import gen_python_remote, gen_python_publication
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class CRUDPythonPublicationsTestCase(unittest.TestCase):
    """
    CRUD publications.

        #     This test targets the following issues:
        #
        #     * `Pulp #3324 <https://pulp.plan.io/issues/3324>`_
        #     * `Pulp Smash #897 <https://github.com/PulpQE/pulp-smash/issues/897>`_

    """

    @classmethod
    def setUpClass(cls):
        """
        Create class-wide variables.

        """
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_01_all(self):
        """
        TODO: This needs to be broken up!

        Publication creation causes a publish task, which must also tested here.

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
        self.addCleanup(self.client.delete, remote['pulp_href'])

        repo = self.client.post(PYTHON_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        sync(self.cfg, remote, repo)

        # Step 1
        repo = self.client.get(repo['pulp_href'])
        for python_content in get_content(repo)[PYTHON_CONTENT_NAME]:
            self.client.post(
                repo['pulp_href'] + "modify/",
                {'add_content_units': [python_content['pulp_href']]}
            )
        versions = get_versions(repo)
        non_latest = choice(versions[:-1])

        # Step 2
        publication1 = gen_python_publication(self.cfg, repository=repo)

        # Step 3
        self.assertEqual(publication1['repository_version'], versions[-1]['pulp_href'])

        # Step 4
        publication2 = gen_python_publication(self.cfg, repository_version=non_latest)

        # Step 5
        self.assertEqual(publication2['repository_version'], non_latest['pulp_href'])

        # Step 6
        with self.assertRaises(HTTPError):
            gen_python_publication(
                self.cfg,
                repository_version=non_latest,
                repository=repo,
            )

        # TEST RETRIEVE
        """
        Read a publisher by its href.
        """
        publication_retrieved = self.client.get(publication1['pulp_href'])
        for key, val in publication1.items():
            with self.subTest(key=key):
                self.assertEqual(publication_retrieved[key], val)

        # TODO TEST LIST
        # TODO TEST PARTIAL AND FULL UPDATE

        # TEST DELETE
        """
        Delete a publisher.
        """
        self.client.delete(publication1['pulp_href'])
        with self.assertRaises(HTTPError):
            self.client.get(publication1['pulp_href'])
