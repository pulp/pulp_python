"""Tests all the PyPI apis available at `pypi/`."""
import os
import requests
import subprocess
import tempfile

from urllib.parse import urljoin

from pulp_smash.pulp3.bindings import monitor_task, tasks as task_api
from pulp_smash.pulp3.utils import get_added_content_summary, get_content_summary
from pulp_python.tests.functional.constants import (
    PYTHON_CONTENT_NAME,
    PYTHON_SM_PROJECT_SPECIFIER,
    PYTHON_SM_FIXTURE_RELEASES,
    PYTHON_SM_FIXTURE_CHECKSUMS,
    PYTHON_MD_PROJECT_SPECIFIER,
    PYTHON_MD_PYPI_SUMMARY,
    PULP_CONTENT_BASE_URL,
    PULP_PYPI_BASE_URL,
    PYTHON_EGG_FILENAME,
    PYTHON_EGG_URL,
    PYTHON_EGG_SHA256,
    PYTHON_WHEEL_FILENAME,
    PYTHON_WHEEL_URL,
    PYTHON_WHEEL_SHA256,
    SHELF_PYTHON_JSON,
)

from pulp_python.tests.functional.utils import (
    py_client as client,
    ensure_simple,
    TestCaseUsingBindings,
    TestHelpersMixin,
)
from pulpcore.client.pulp_python import PypiApi

PYPI_LAST_SERIAL = "X-PYPI-LAST-SERIAL"
PYPI_SERIAL_CONSTANT = 1000000000
HOST = client.configuration.host
PYPI_HOST = urljoin(HOST, PULP_PYPI_BASE_URL)


class PyPISummaryTestCase(TestCaseUsingBindings, TestHelpersMixin):
    """Tests the summary response of the base url of an index."""

    @classmethod
    def setUpClass(cls):
        """Set up class variables."""
        super().setUpClass()
        cls.pypi_api = PypiApi(client)

    def test_empty_index(self):
        """Checks that summary stats are 0 when index is empty."""
        _, distro = self._create_empty_repo_and_distribution()

        summary = self.pypi_api.read(path=distro.base_path)
        self.assertTrue(not any(summary.to_dict().values()))

    def test_live_index(self):
        """Checks summary stats are correct for indexes pointing to repositories."""
        remote = self._create_remote(includes=PYTHON_MD_PROJECT_SPECIFIER)
        repo = self._create_repo_and_sync_with_remote(remote)
        distro = self._create_distribution_from_repo(repo)

        summary = self.pypi_api.read(path=distro.base_path)
        self.assertDictEqual(summary.to_dict(), PYTHON_MD_PYPI_SUMMARY)

    def test_published_index(self):
        """Checks summary stats are correct for indexes pointing to publications."""
        remote = self._create_remote(includes=PYTHON_MD_PROJECT_SPECIFIER)
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)

        summary = self.pypi_api.read(path=distro.base_path)
        self.assertDictEqual(summary.to_dict(), PYTHON_MD_PYPI_SUMMARY)


class PyPIPackageUpload(TestCaseUsingBindings, TestHelpersMixin):
    """Tests the package upload endpoints of an index."""

    @classmethod
    def setUpClass(cls):
        """Set up class variables."""
        super().setUpClass()
        cls.pypi_api = PypiApi(client)
        cls.dists_dir = tempfile.TemporaryDirectory()
        cls.egg = os.path.join(cls.dists_dir.name, PYTHON_EGG_FILENAME)
        cls.wheel = os.path.join(cls.dists_dir.name, PYTHON_WHEEL_FILENAME)
        with open(cls.egg, "wb") as fp:
            fp.write(requests.get(PYTHON_EGG_URL).content)
        with open(cls.wheel, "wb") as fp:
            fp.write(requests.get(PYTHON_WHEEL_URL).content)

    @classmethod
    def tearDownClass(cls):
        """Tear down class variables."""
        cls.dists_dir.cleanup()

    def test_package_upload(self):
        """Tests that packages can be uploaded."""
        repo, distro = self._create_empty_repo_and_distribution()
        url = urljoin(PYPI_HOST, distro.base_path + "/legacy/")
        response = requests.post(
            url,
            data={"sha256_digest": PYTHON_EGG_SHA256},
            files={"content": open(self.egg, "rb")},
        )
        self.assertEqual(response.status_code, 200)
        task = response.json()["task"]
        monitor_task(task)
        content = get_added_content_summary(repo, f"{repo.versions_href}1/")
        self.assertDictEqual({PYTHON_CONTENT_NAME: 1}, content)
        # Test re-uploading same package gives 400 Bad Request
        response = requests.post(
            url,
            data={"sha256_digest": PYTHON_EGG_SHA256},
            files={"content": open(self.egg, "rb")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.reason, f"Package {PYTHON_EGG_FILENAME} already exists in index"
        )

    def test_package_upload_session(self):
        """Tests that multiple uploads will be broken up into multiple tasks."""
        repo, distro = self._create_empty_repo_and_distribution()
        url = urljoin(PYPI_HOST, distro.base_path + "/legacy/")
        session = requests.Session()
        response = session.post(
            url,
            data={"sha256_digest": PYTHON_EGG_SHA256},
            files={"content": open(self.egg, "rb")},
        )
        self.assertEqual(response.status_code, 200)
        response = response.json()
        monitor_task(response["task"])
        response2 = session.post(
            url,
            data={"sha256_digest": PYTHON_WHEEL_SHA256},
            files={"content": open(self.wheel, "rb")},
        )
        self.assertEqual(response2.status_code, 200)
        response2 = response2.json()
        self.assertNotEqual(response["task"], response2["task"])
        monitor_task(response2["task"])
        content = get_content_summary(repo, f"{repo.versions_href}2/")
        self.assertDictEqual({PYTHON_CONTENT_NAME: 2}, content)

    def test_package_upload_simple(self):
        """Tests that the package upload endpoint exposed at `/simple/` works."""
        repo, distro = self._create_empty_repo_and_distribution()
        url = urljoin(PYPI_HOST, distro.base_path + "/simple/")
        response = requests.post(
            url,
            data={"sha256_digest": PYTHON_EGG_SHA256},
            files={"content": open(self.egg, "rb")},
        )
        self.assertEqual(response.status_code, 200)
        task = response.json()["task"]
        monitor_task(task)
        content = get_added_content_summary(repo, f"{repo.versions_href}1/")
        self.assertDictEqual({PYTHON_CONTENT_NAME: 1}, content)

    def test_twine_upload(self):
        """Tests that packages can be properly uploaded through Twine."""
        repo, distro = self._create_empty_repo_and_distribution()
        url = urljoin(PYPI_HOST, distro.base_path + "/legacy/")
        username, password = "admin", "password"
        subprocess.run(
            (
                "twine",
                "upload",
                "--repository-url",
                url,
                self.dists_dir.name + "/*",
                "-u",
                username,
                "-p",
                password,
            ),
            capture_output=True,
            check=True,
        )
        tasks = task_api.list(reserved_resources_record=[repo.pulp_href]).results
        for task in reversed(tasks):
            t = monitor_task(task.pulp_href)
            repo_ver_href = t.created_resources[-1]
        content = get_content_summary(repo, f"{repo_ver_href}")
        self.assertDictEqual({PYTHON_CONTENT_NAME: 2}, content)

        # Test re-uploading same packages gives error
        with self.assertRaises(subprocess.CalledProcessError):
            subprocess.run(
                (
                    "twine",
                    "upload",
                    "--repository-url",
                    url,
                    self.dists_dir.name + "/*",
                    "-u",
                    username,
                    "-p",
                    password,
                ),
                capture_output=True,
                check=True,
            )

        # Test re-uploading same packages with --skip-existing works
        output = subprocess.run(
            (
                "twine",
                "upload",
                "--repository-url",
                url,
                self.dists_dir.name + "/*",
                "-u",
                username,
                "-p",
                password,
                "--skip-existing",
            ),
            capture_output=True,
            check=True,
            text=True
        )
        self.assertEqual(output.stdout.count("Skipping"), 2)


class PyPISimpleApi(TestCaseUsingBindings, TestHelpersMixin):
    """Tests that the simple api is correct."""

    def test_simple_redirect_with_publications(self):
        """Checks that requests to `/simple/` get redirected when serving a publication."""
        remote = self._create_remote()
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)
        response = requests.get(urljoin(PYPI_HOST, f"{distro.base_path}/simple/"))
        self.assertEqual(
            response.url,
            str(urljoin(PULP_CONTENT_BASE_URL, f"{distro.base_path}/simple/")),
        )

    def test_simple_correctness_live(self):
        """Checks that the simple api on live distributions are correct."""
        remote = self._create_remote(includes=PYTHON_SM_PROJECT_SPECIFIER)
        repo = self._create_repo_and_sync_with_remote(remote)
        distro = self._create_distribution_from_repo(repo)
        proper, msgs = ensure_simple(
            urljoin(PYPI_HOST, f"{distro.base_path}/simple/"),
            PYTHON_SM_FIXTURE_RELEASES,
            sha_digests=PYTHON_SM_FIXTURE_CHECKSUMS,
        )
        self.assertTrue(proper, msg=msgs)


class PyPIPackageMetadata(TestCaseUsingBindings, TestHelpersMixin):
    """Test whether a distributed Python repository has a PyPI json endpoint."""

    def test_pypi_json(self):
        """Checks the data of `pypi/{package_name}/json` endpoint."""
        remote = self._create_remote(policy="immediate")
        repo = self._create_repo_and_sync_with_remote(remote)
        distro = self._create_distribution_from_repo(repo)
        rel_url = f"{distro.base_path}/pypi/shelf-reader/json"
        response = requests.get(urljoin(PYPI_HOST, rel_url))
        self.assert_pypi_json(response.json())

    def test_pypi_json_content_app(self):
        """Checks that the pypi json endpoint of the content app still works. Needs Publication."""
        remote = self._create_remote(policy="immediate")
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)
        rel_url = f"{distro.base_path}/pypi/shelf-reader/json/"
        response = requests.get(urljoin(PULP_CONTENT_BASE_URL, rel_url))
        self.assert_pypi_json(response.json())

    def test_pypi_last_serial(self):
        """
        Checks that the endpoint has the header PYPI_LAST_SERIAL and is set
        TODO when serial field is added to Repo's, check this header against that
        """
        remote = self._create_remote()
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)
        content_url = urljoin(
            PULP_CONTENT_BASE_URL, f"{distro.base_path}/pypi/shelf-reader/json"
        )
        pypi_url = urljoin(PYPI_HOST, f"{distro.base_path}/pypi/shelf-reader/json/")
        for url in [content_url, pypi_url]:
            response = requests.get(url)
            self.assertIn(PYPI_LAST_SERIAL, response.headers, msg=url)
            self.assertEqual(
                response.headers[PYPI_LAST_SERIAL], str(PYPI_SERIAL_CONSTANT), msg=url
            )

    def assert_pypi_json(self, package):
        """Asserts that shelf-reader package json is correct."""
        self.assertEqual(SHELF_PYTHON_JSON["last_serial"], package["last_serial"])
        self.assertTrue(SHELF_PYTHON_JSON["info"].items() <= package["info"].items())
        self.assertEqual(len(SHELF_PYTHON_JSON["urls"]), len(package["urls"]))
        self.assert_download_info(
            SHELF_PYTHON_JSON["urls"], package["urls"], "Failed to match URLS"
        )
        self.assertTrue(
            SHELF_PYTHON_JSON["releases"].keys() <= package["releases"].keys()
        )
        for version in SHELF_PYTHON_JSON["releases"].keys():
            self.assert_download_info(
                SHELF_PYTHON_JSON["releases"][version],
                package["releases"][version],
                "Failed to match version",
            )

    def assert_download_info(self, expected, received, message="Failed to match"):
        """
        Each version has a list of dists of that version, but the lists might
        not be in the same order, so check each dist of the second list
        """
        for dist in expected:
            dist = dict(dist)
            matched = False
            dist_items = dist.items()
            for dist2 in received:
                dist2 = dict(dist2)
                dist2["digests"].pop("md5", "")
                if dist_items <= dist2.items():
                    matched = True
                    break
            self.assertTrue(matched, message)
