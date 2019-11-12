import unittest

from requests.exceptions import HTTPError

from pulp_smash import api, config, utils
from pulp_smash.pulp3.utils import delete_orphans

from pulp_python.tests.functional.constants import (
    PYTHON_CONTENT_PATH,
    PYTHON_REPO_PATH,
    PYTHON_WHEEL_URL,
    PYTHON_WHEEL_FILENAME
)
from pulp_python.tests.functional.utils import skip_if
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class OneShotUploadTestCase(unittest.TestCase):
    """
    Test one-shot upload endpoint
    """

    @classmethod
    def setUp(cls):
        """
        Create class-wide variable.
        """
        cls.cfg = config.get_config()
        delete_orphans(cls.cfg)
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.test_file = {'file': utils.http_get(PYTHON_WHEEL_URL)}

    @classmethod
    def tearDown(cls):
        """
        Clean class-wide variable.
        """
        delete_orphans(cls.cfg)

    def test_01_upload_file_without_repo(self):
        """
        1) returns a task
        2) check task status complete
        3) check created resource of completed task
        4) ensure only one and it's a content unit
        """
        task_url = self.client.post(
            PYTHON_CONTENT_PATH,
            files=self.test_file,
            data={'filename': PYTHON_WHEEL_FILENAME,
                  'relative_path': PYTHON_WHEEL_FILENAME})
        task = self.client.get(task_url['task'])
        created_resource = task['created_resources'][0]
        content_unit = self.client.get(created_resource)
        new_filename = content_unit['filename']
        self.assertEqual(new_filename, PYTHON_WHEEL_FILENAME)
        self.assertEqual(len(task['created_resources']), 1)

    def test_02_upload_file_with_repo(self):
        """
        1) returns a task
        2) check task status complete
        3) check created resource of completed task
        4) ensure two and it's a content unit and a repository version
        5) ?
        """
        repo = self.client.post(PYTHON_REPO_PATH, data={'name': 'foo'})
        self.addCleanup(self.client.delete, repo['pulp_href'])
        task_url = self.client.post(PYTHON_CONTENT_PATH,
                                    files=self.test_file,
                                    data={'filename': PYTHON_WHEEL_FILENAME,
                                          'relative_path': PYTHON_WHEEL_FILENAME,
                                          'repository': repo['pulp_href']})
        task = self.client.get(task_url['task'])
        new_repo_version = task['created_resources'][0]
        version_content_query = self.client.get(
            new_repo_version
        )['content_summary']['added']['python.python']['href']
        version_content_url = self.client.get(version_content_query)['results'][0]['pulp_href']
        version_content_unit = self.client.get(version_content_url)
        version_content_filename = version_content_unit['filename']
        new_content_url = task['created_resources'][1]
        content_unit = self.client.get(new_content_url)
        new_filename = content_unit['filename']
        self.assertEqual(new_filename, PYTHON_WHEEL_FILENAME)
        self.assertEqual(version_content_filename, PYTHON_WHEEL_FILENAME)
        self.assertEqual(len(task['created_resources']), 2)

    def test_03_upload_duplicate_file_without_repo(self):
        """
        1) upload file
        2) upload the same file again
        3) this should fail/send an error
        """
        task_url = self.client.post(PYTHON_CONTENT_PATH,
                                    files=self.test_file,
                                    data={'filename': PYTHON_WHEEL_FILENAME,
                                          'relative_path': PYTHON_WHEEL_FILENAME})
        task = self.client.get(task_url['task'])
        created_resource = task['created_resources'][0]
        content_unit = self.client.get(created_resource)
        new_filename = content_unit['filename']
        self.assertEqual(new_filename, PYTHON_WHEEL_FILENAME)
        self.assertEqual(len(task['created_resources']), 1)
        try:
            self.client.post(PYTHON_CONTENT_PATH,
                             files=self.test_file,
                             data={'filename': PYTHON_WHEEL_FILENAME,
                                   'relative_path': PYTHON_WHEEL_FILENAME})
        except Exception as e:
            self.assertEqual(e.response.status_code, 400)


class ContentUnitTestCase(unittest.TestCase):
    """
    CRUD content unit.

    This test targets the following issues:

    * `Pulp #2872 <https://pulp.plan.io/issues/2872>`_
    * `Pulp #3445 <https://pulp.plan.io/issues/3445>`_
    * `Pulp Smash #870 <https://github.com/PulpQE/pulp-smash/issues/870>`_
    """

    @classmethod
    def setUpClass(cls):
        """
        Create class-wide variable.
        """
        cls.cfg = config.get_config()
        delete_orphans(cls.cfg)
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.test_file = {'file': utils.http_get(PYTHON_WHEEL_URL)}
        task_url = cls.client.post(PYTHON_CONTENT_PATH,
                                   files=cls.test_file,
                                   data={'filename': PYTHON_WHEEL_FILENAME,
                                         'relative_path': PYTHON_WHEEL_FILENAME})
        task = cls.client.get(task_url['task'])
        created_resource = task['created_resources'][0]
        cls.content_unit = cls.client.get(created_resource)

    @classmethod
    def tearDownClass(cls):
        """
        Clean class-wide variable.
        """
        delete_orphans(cls.cfg)

    @skip_if(bool, 'content_unit', False)
    def test_02_read_content_units(self):
        """
        Read a content unit by its filename.
        """
        page = self.client.get(PYTHON_CONTENT_PATH, params={
            'filename': PYTHON_WHEEL_FILENAME
        })
        self.assertEqual(len(page['results']), 1)

    @skip_if(bool, 'content_unit', False)
    def test_03_partially_update(self):
        """
        Attempt to update a content unit using HTTP PATCH.

        This HTTP method is not supported and a HTTP exception is expected.

        """
        with self.assertRaises(HTTPError) as exc:
            self.client.patch(self.content_unit['pulp_href'], {})
        self.assertEqual(exc.exception.response.status_code, 405)

    @skip_if(bool, 'content_unit', False)
    def test_03_fully_update(self):
        """
        Attempt to update a content unit using HTTP PUT.

        This HTTP method is not supported and a HTTP exception is expected.

        """
        with self.assertRaises(HTTPError) as exc:
            self.client.put(self.content_unit['pulp_href'], {})
        self.assertEqual(exc.exception.response.status_code, 405)

    @skip_if(bool, 'content_unit', False)
    def test_04_delete(self):
        """Attempt to delete a content unit using HTTP DELETE.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        with self.assertRaises(HTTPError) as exc:
            self.client.delete(self.content_unit['pulp_href'])
        self.assertEqual(exc.exception.response.status_code, 405)
