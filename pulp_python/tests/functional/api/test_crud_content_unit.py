from random import choice
import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config, utils
from pulp_smash.pulp3.constants import ARTIFACTS_PATH, REPO_PATH
from pulp_smash.pulp3.utils import (
    delete_orphans,
    gen_repo,
    get_content,
    sync,
)

from pulp_python.tests.functional.constants import (
    PYTHON_CONTENT_PATH,
    PYTHON_FIXTURES_URL,
    PYTHON_REMOTE_PATH,
    PYTHON_WHEEL_FILENAME,
    PYTHON_WHEEL_URL,
)
from pulp_python.tests.functional.utils import gen_python_remote, skip_if
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class ContentUnitTestCase(unittest.TestCase):
    """
    CRUD content unit.

    This test targets the following issues:

    * `Pulp #2872 <https://pulp.plan.io/issues/2872>`_
    * `Pulp Smash #870 <https://github.com/PulpQE/pulp-smash/issues/870>`_
    """

    @classmethod
    def setUpClass(cls):
        """
        Create class-wide variable.
        """
        cls.cfg = config.get_config()
        delete_orphans(cls.cfg)
        cls.content_unit = {}
        cls.client = api.Client(cls.cfg, api.json_handler)
        files = {'file': utils.http_get(PYTHON_WHEEL_URL)}
        cls.artifact = cls.client.post(ARTIFACTS_PATH, files=files)

    @classmethod
    def tearDownClass(cls):
        """
        Clean class-wide variable.
        """
        delete_orphans(cls.cfg)

    def test_01_create_content_unit(self):
        """
        Create content unit.
        """
        attrs = _gen_content_unit_attrs(self.artifact)
        self.content_unit.update(self.client.post(PYTHON_CONTENT_PATH, attrs))
        for key, val in attrs.items():
            with self.subTest(key=key):
                self.assertEqual(self.content_unit[key], val)

    @skip_if(bool, 'content_unit', False)
    def test_02_read_content_unit(self):
        """
        Read a content unit by its href.
        """
        content_unit = self.client.get(self.content_unit['_href'])
        for key, val in self.content_unit.items():
            with self.subTest(key=key):
                self.assertEqual(content_unit[key], val)

    @skip_if(bool, 'content_unit', False)
    def test_02_read_content_units(self):
        """
        Read a content unit by its filename.
        """
        page = self.client.get(PYTHON_CONTENT_PATH, params={
            'filename': self.content_unit['filename']
        })
        self.assertEqual(len(page['results']), 1)
        for key, val in self.content_unit.items():
            with self.subTest(key=key):
                self.assertEqual(page['results'][0][key], val)

    @skip_if(bool, 'content_unit', False)
    def test_03_partially_update(self):
        """
        Attempt to update a content unit using HTTP PATCH.

        This HTTP method is not supported and a HTTP exception is expected.

        """
        attrs = _gen_content_unit_attrs(self.artifact)
        with self.assertRaises(HTTPError):
            self.client.patch(self.content_unit['_href'], attrs)

    @skip_if(bool, 'content_unit', False)
    def test_03_fully_update(self):
        """
        Attempt to update a content unit using HTTP PUT.

        This HTTP method is not supported and a HTTP exception is expected.

        """
        attrs = _gen_content_unit_attrs(self.artifact)
        with self.assertRaises(HTTPError):
            self.client.put(self.content_unit['_href'], attrs)


def _gen_content_unit_attrs(artifact):
    """
    Generate a dict with content unit attributes.

    Args:
        artifact (dict): Info about the artifact.

    Returns:
        dict: A semi-random dict for use in creating a content unit.

    """
    return {
        'artifact': artifact['_href'],
        'filename': PYTHON_WHEEL_FILENAME,
    }


class DeleteContentUnitRepoVersionTestCase(unittest.TestCase):
    """
    Test whether content unit used by a repo version can be deleted.

    This test targets the following issues:

    * `Pulp #3418 <https://pulp.plan.io/issues/3418>`_
    * `Pulp Smash #900 <https://github.com/PulpQE/pulp-smash/issues/900>`_
    """

    def test_all(self):
        """
        Test whether content unit used by a repo version can be deleted.

        Do the following:

        1. Sync content to a repository.
        2. Attempt to delete a content unit present in a repository version.
           Assert that a HTTP exception was raised.
        3. Assert that number of content units present on the repository
           does not change after the attempt to delete one content unit.

        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)

        body = gen_python_remote(PYTHON_FIXTURES_URL)
        remote = client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])

        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])

        sync(cfg, remote, repo)

        repo = client.get(repo['_href'])
        content = get_content(repo)
        with self.assertRaises(HTTPError):
            client.delete(choice(content)['_href'])
        self.assertEqual(len(content), len(get_content(repo)))
