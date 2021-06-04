"""Tests all the PyPI apis available at `pulp_python/pypi/`."""
import requests

from urllib.parse import urljoin

from pulp_python.tests.functional.constants import (
    PYTHON_SM_PROJECT_SPECIFIER,
    PYTHON_SM_FIXTURE_RELEASES,
    PYTHON_SM_FIXTURE_CHECKSUMS,
    PYTHON_MD_PROJECT_SPECIFIER,
    PYTHON_MD_PYPI_SUMMARY,
    PULP_CONTENT_BASE_URL,
    PULP_PYPI_BASE_URL,
    SHELF_PYTHON_JSON
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


class PyPISimpleApi(TestCaseUsingBindings, TestHelpersMixin):
    """Tests that the simple api is correct."""

    def test_simple_redirect_with_publications(self):
        """Checks that requests to `/simple/` get redirected when serving a publication."""
        remote = self._create_remote()
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)
        response = requests.get(urljoin(PYPI_HOST, f'{distro.base_path}/simple/'))
        self.assertEqual(
            response.url, str(urljoin(PULP_CONTENT_BASE_URL, f"{distro.base_path}/simple/"))
        )

    def test_simple_correctness_live(self):
        """Checks that the simple api on live distributions are correct."""
        remote = self._create_remote(includes=PYTHON_SM_PROJECT_SPECIFIER)
        repo = self._create_repo_and_sync_with_remote(remote)
        distro = self._create_distribution_from_repo(repo)
        proper, msgs = ensure_simple(
            urljoin(PYPI_HOST, f'{distro.base_path}/simple/'),
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
        content_url = urljoin(PULP_CONTENT_BASE_URL, f"{distro.base_path}/pypi/shelf-reader/json")
        pypi_url = urljoin(PYPI_HOST, f"{distro.base_path}/pypi/shelf-reader/json/")
        for url in [content_url, pypi_url]:
            response = requests.get(url)
            self.assertIn(PYPI_LAST_SERIAL, response.headers, msg=url)
            self.assertEqual(response.headers[PYPI_LAST_SERIAL], str(PYPI_SERIAL_CONSTANT), msg=url)

    def assert_pypi_json(self, package):
        """Asserts that shelf-reader package json is correct."""
        self.assertEqual(SHELF_PYTHON_JSON["last_serial"], package["last_serial"])
        self.assertTrue(SHELF_PYTHON_JSON["info"].items() <= package["info"].items())
        self.assertEqual(len(SHELF_PYTHON_JSON["urls"]), len(package["urls"]))
        self.assert_download_info(SHELF_PYTHON_JSON["urls"], package["urls"],
                                  "Failed to match URLS")
        self.assertTrue(SHELF_PYTHON_JSON["releases"].keys() <= package["releases"].keys())
        for version in SHELF_PYTHON_JSON["releases"].keys():
            self.assert_download_info(SHELF_PYTHON_JSON["releases"][version],
                                      package["releases"][version], "Failed to match version")

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
