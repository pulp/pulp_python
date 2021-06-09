# coding=utf-8
"""Tests that perform actions over content unit."""
from pulp_smash.pulp3.bindings import monitor_task, PulpTaskError
from pulp_smash.pulp3.utils import delete_orphans

from pulp_python.tests.functional.utils import (
    gen_artifact,
    gen_python_content_attrs,
    skip_if,
    TestCaseUsingBindings,
    TestHelpersMixin,
)
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin

from pulp_smash.utils import http_get
from pulp_python.tests.functional.constants import (
    PYTHON_FIXTURES_URL,
    PYTHON_PACKAGE_DATA,
    PYTHON_EGG_FILENAME,
    PYTHON_EGG_URL,
    PYTHON_SM_FIXTURE_CHECKSUMS,
)


class ContentUnitTestCase(TestCaseUsingBindings, TestHelpersMixin):
    """CRUD content unit.

    This test targets the following issues:

    * `Pulp #2872 <https://pulp.plan.io/issues/2872>`_
    * `Pulp #3445 <https://pulp.plan.io/issues/3445>`_
    * `Pulp Smash #870 <https://github.com/pulp/pulp-smash/issues/870>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variable."""
        super().setUpClass()
        delete_orphans()
        cls.content_unit = {}
        cls.artifact = gen_artifact()

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        delete_orphans()

    def test_01_create_content_unit(self):
        """Create content unit."""
        attrs = gen_python_content_attrs(self.artifact)
        response = self.content_api.create(**attrs)
        created_resources = monitor_task(response.task).created_resources
        content_unit = self.content_api.read(created_resources[0])
        self.content_unit.update(content_unit.to_dict())
        self.check_package_data(self.content_unit)

    @skip_if(bool, "content_unit", False)
    def test_02_read_content_unit(self):
        """Read a content unit by its href."""
        content_unit = self.content_api.read(self.content_unit["pulp_href"]).to_dict()
        for key, val in self.content_unit.items():
            with self.subTest(key=key):
                self.assertEqual(content_unit[key], val)

    @skip_if(bool, "content_unit", False)
    def test_02_read_content_units(self):
        """Read a content unit by its relative_path."""
        page = self.content_api.list(filename=self.content_unit["filename"])
        self.assertEqual(len(page.results), 1)
        for key, val in self.content_unit.items():
            with self.subTest(key=key):
                self.assertEqual(page.results[0].to_dict()[key], val)

    @skip_if(bool, "content_unit", False)
    def test_03_partially_update(self):
        """Attempt to update a content unit using HTTP PATCH.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        attrs = gen_python_content_attrs(self.artifact)
        with self.assertRaises(AttributeError) as exc:
            self.content_api.partial_update(
                self.content_unit["pulp_href"], attrs
            )
        msg = "object has no attribute 'partial_update'"
        self.assertIn(msg, exc.exception.args[0])

    @skip_if(bool, "content_unit", False)
    def test_03_fully_update(self):
        """Attempt to update a content unit using HTTP PUT.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        attrs = gen_python_content_attrs(self.artifact)
        with self.assertRaises(AttributeError) as exc:
            self.content_api.update(self.content_unit["pulp_href"], attrs)
        msg = "object has no attribute 'update'"
        self.assertIn(msg, exc.exception.args[0])

    @skip_if(bool, "content_unit", False)
    def test_04_delete(self):
        """Attempt to delete a content unit using HTTP DELETE.

        This HTTP method is not supported and a HTTP exception is expected.
        """
        with self.assertRaises(AttributeError) as exc:
            self.content_api.delete(self.content_unit["pulp_href"])
        msg = "object has no attribute 'delete'"
        self.assertIn(msg, exc.exception.args[0])

    def test_05_upload_file_without_repo(self):
        """
        1) returns a task
        2) check task status complete
        3) check created resource of completed task
        4) ensure only one resource was created and it's a content unit
        """
        delete_orphans()
        response = self.do_upload()
        created_resources = monitor_task(response.task).created_resources
        content_unit = self.content_api.read(created_resources[0]).to_dict()
        self.assertEqual(len(created_resources), 1)
        self.check_package_data(content_unit)

    def test_06_upload_file_with_repo(self):
        """
        1) returns a task
        2) check task status complete
        3) check created resource of completed task
        4) ensure there was two resources created and are a content unit and a repository version
        """
        delete_orphans()
        repo = self._create_repository()
        response = self.do_upload(repository=repo.pulp_href)
        created_resources = monitor_task(response.task).created_resources
        self.assertEqual(len(created_resources), 2)
        content_list_search = self.content_api.list(
            repository_version_added=created_resources[0]
        ).results[0]
        content_unit = self.content_api.read(created_resources[1])
        self.assertEqual(content_unit.pulp_href, content_list_search.pulp_href)
        self.check_package_data(content_unit.to_dict())

    def test_07_upload_duplicate_file_without_repo(self):
        """
        1) upload file
        2) upload the same file again
        3) this should fail/send an error
        """
        delete_orphans()
        response = self.do_upload()
        created_resources = monitor_task(response.task).created_resources
        content_unit = self.content_api.read(created_resources[0])
        self.check_package_data(content_unit.to_dict())

        with self.assertRaises(PulpTaskError) as cm:
            monitor_task(self.do_upload().task)
        task_report = cm.exception.task.to_dict()
        msg = "This field must be unique"
        self.assertTrue("sha256" in task_report["error"]["description"])
        self.assertTrue(msg in task_report["error"]["description"])

    def test_08_upload_same_filename_different_artifact(self):
        """
        1) upload PYTHON_EGG file with PYTHON_EGG filename
        2) upload aiohttp-3.3.0.tar.gz with PYTHON_EGG filename
        3) assert that two content units where created
        """
        delete_orphans()
        response = self.do_upload()
        created_resources = monitor_task(response.task).created_resources
        content_unit = self.content_api.read(created_resources[0])
        self.assertEqual(len(created_resources), 1)

        url = urljoin(urljoin(PYTHON_FIXTURES_URL, "packages/"), "aiohttp-3.3.0.tar.gz")
        response = self.do_upload(remote_path=url)
        created_resources = monitor_task(response.task).created_resources
        content_unit2 = self.content_api.read(created_resources[0])
        self.assertEqual(len(created_resources), 1)
        self.assertNotEqual(content_unit.pulp_href, content_unit2.pulp_href)

    def test_09_upload_same_repo_filename_different_artifact(self):
        """
        1) create repository
        2) upload PYTHON_EGG file with PYTHON_EGG filename
        3) upload aiohttp-3.3.0.tar.gz with PYTHON_EGG filename
        4) assert only second content unit is in repository
        """
        delete_orphans()
        repo = self._create_repository()
        response = self.do_upload(repository=repo.pulp_href)
        created_resources = monitor_task(response.task).created_resources
        self.assertEqual(len(created_resources), 2)

        url = urljoin(urljoin(PYTHON_FIXTURES_URL, "packages/"), "aiohttp-3.3.0.tar.gz")
        response = self.do_upload(repository=repo.pulp_href, remote_path=url)
        created_resources = monitor_task(response.task).created_resources
        content_unit2 = self.content_api.read(created_resources[1])
        content_list_search = self.content_api.list(
            repository_version=created_resources[0]
        ).results
        self.assertEqual(len(content_list_search), 1)
        self.assertEqual(content_unit2.pulp_href, content_list_search[0].pulp_href)

    def test_10_upload_with_mismatched_sha256(self):
        """
        1) upload PYTHON_EGG file with aiohttp-3.3.0.tar.gz's sha256
        2) this should fail
        """
        delete_orphans()
        with self.assertRaises(PulpTaskError) as cm:
            sha256 = PYTHON_SM_FIXTURE_CHECKSUMS["aiohttp-3.3.0.tar.gz"]
            monitor_task(self.do_upload(sha256=sha256).task)
        task_report = cm.exception.task.to_dict()
        msg = "The uploaded artifact's sha256 checksum does not match the one provided"
        self.assertTrue(msg in task_report["error"]["description"])

    def do_upload(
        self, filename=PYTHON_EGG_FILENAME, remote_path=PYTHON_EGG_URL, **kwargs
    ):
        """Takes in attributes dict for a file and creates content from it"""
        with NamedTemporaryFile() as file_to_upload:
            file_to_upload.write(http_get(remote_path))
            attrs = {"file": file_to_upload.name, "relative_path": filename}
            attrs.update(kwargs)
            return self.content_api.create(**attrs)

    def check_package_data(self, content_unit, expected=PYTHON_PACKAGE_DATA):
        """Subset Dict comparision, checking if content_unit contains expected"""
        for k, v in expected.items():
            with self.subTest(key=k):
                self.assertEqual(content_unit[k], v)
