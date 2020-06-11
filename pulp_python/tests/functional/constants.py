from urllib.parse import urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL
from pulp_smash.pulp3.constants import (
    BASE_DISTRIBUTION_PATH,
    BASE_PUBLICATION_PATH,
    BASE_REMOTE_PATH,
    BASE_REPO_PATH,
    BASE_CONTENT_PATH,
)


PYPI_URL = "https://pypi.org/"

PYTHON_CONTENT_NAME = "python.python"

PYTHON_CONTENT_PATH = urljoin(BASE_CONTENT_PATH, "python/packages/")

PYTHON_DISTRIBUTION_PATH = urljoin(BASE_DISTRIBUTION_PATH, "python/pypi/")

PYTHON_FIXTURES_URL = urljoin(PULP_FIXTURES_BASE_URL, "python-pypi/")

PYTHON_PUBLICATION_PATH = urljoin(BASE_PUBLICATION_PATH, "python/pypi/")

PYTHON_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, "python/python/")

PYTHON_REPO_PATH = urljoin(BASE_REPO_PATH, "python/python/")


# Specifier for testing empty syncs, or no excludes
PYTHON_EMPTY_PROJECT_SPECIFIER = []
# Specifier that includes projects that aren't in the test fixtures
PYTHON_UNAVAILABLE_PROJECT_SPECIFIER = [
    "shelf-reader",  # matches 2
    "aiohttp>=3.2.0,<3.3.1",  # matches 3
    "flake8",  # matches 0
    "pyramid",  # matches 0
    "pylint",  # matches 0
]
PYTHON_UNAVAILABLE_PACKAGE_COUNT = 5
PYTHON_UNAVAILABLE_FIXTURE_SUMMARY = {
    PYTHON_CONTENT_NAME: PYTHON_UNAVAILABLE_PACKAGE_COUNT
}

# no "name" field
PYTHON_INVALID_SPECIFIER_NO_NAME = [
    "",
]
# invalid "version_specifier" field
PYTHON_INVALID_SPECIFIER_BAD_VERSION = [
    "shelf-reader$3",
]
# no "version_specifier" field
PYTHON_VALID_SPECIFIER_NO_VERSION = ["shelf-reader"]

# Specifier for testing that the correct number of packages are synced when prereleases
# is set True or False on the remote.
PYTHON_PRERELEASE_TEST_SPECIFIER = [
    # matches 2 w/ prereleases, 1 w/o
    "aiohttp>3.3.1,<=3.3.2",
    # matches 13 w/ prereleases, 9 w/o
    "celery",
    # matches 31 w/ prereleases, 20 w/o
    "Django",
]
PYTHON_WITH_PRERELEASE_COUNT = 46
PYTHON_WITH_PRERELEASE_FIXTURE_SUMMARY = {
    PYTHON_CONTENT_NAME: PYTHON_WITH_PRERELEASE_COUNT
}
PYTHON_WITHOUT_PRERELEASE_COUNT = 30
PYTHON_WITHOUT_PRERELEASE_FIXTURE_SUMMARY = {
    PYTHON_CONTENT_NAME: PYTHON_WITHOUT_PRERELEASE_COUNT
}

# Specifier for basic sync / publish tests.
PYTHON_XS_PROJECT_SPECIFIER = ["shelf-reader"]  # matches 2
PYTHON_XS_PACKAGE_COUNT = 2
PYTHON_XS_FIXTURE_SUMMARY = {PYTHON_CONTENT_NAME: PYTHON_XS_PACKAGE_COUNT}

PYTHON_SM_PROJECT_SPECIFIER = [
    "aiohttp>=3.2.0,<3.3.1",  # matches 3
    "celery>4.1.0,<=4.2.0",  # matches 2
    "Django>1.10.0,<1.10.5",  # matches 8
]
PYTHON_SM_PACKAGE_COUNT = 13
PYTHON_SM_FIXTURE_SUMMARY = {PYTHON_CONTENT_NAME: PYTHON_SM_PACKAGE_COUNT}

PYTHON_MD_PROJECT_SPECIFIER = [
    "shelf-reader",  # matches 2
    "aiohttp>=3.2.0,<3.3.1",  # matches 3
    "celery~=4.0",  # matches 5
    "Django>1.10.0,<=2.0.6",  # matches 16
]
PYTHON_MD_PACKAGE_COUNT = 26
PYTHON_MD_FIXTURE_SUMMARY = {PYTHON_CONTENT_NAME: PYTHON_MD_PACKAGE_COUNT}

PYTHON_LG_PROJECT_SPECIFIER = [
    "aiohttp",  # matches 7
    "celery",  # matches 13
    "Django",  # matches 31
    "scipy",  # matches 23
    "shelf-reader",  # matches 2
]
PYTHON_LG_PACKAGE_COUNT = 76
PYTHON_LG_FIXTURE_SUMMARY = {PYTHON_CONTENT_NAME: PYTHON_LG_PACKAGE_COUNT}

# Intended to be used with the XS specifier
PYTHON_EGG_FILENAME = "shelf-reader-0.1.tar.gz"
PYTHON_EGG_URL = urljoin(urljoin(PYTHON_FIXTURES_URL, "packages/"), PYTHON_EGG_FILENAME)

# Intended to be used with the XS specifier
PYTHON_WHEEL_FILENAME = "shelf_reader-0.1-py2-none-any.whl"
PYTHON_WHEEL_URL = urljoin(
    urljoin(PYTHON_FIXTURES_URL, "packages/"), PYTHON_WHEEL_FILENAME
)

PYTHON_FIXTURES_PACKAGES = [
    "shelf-reader",
]
PYTHON_FIXTURES_FILENAMES = [
    "shelf-reader-0.1.tar.gz",
]
PYTHON_LIST_PROJECT_SPECIFIER = [
    "shelf-reader",
]

# Package Data for shelf-reader
PYTHON_PACKAGE_DATA = {
    "filename": "shelf-reader-0.1.tar.gz",
    "packagetype": "sdist",
    "name": "shelf-reader",
    "version": "0.1",
    "metadata_version": "1.1",
    "summary": "Make sure your collections are in call number order.",
    "keywords": "",
    "home_page": "https://github.com/asmacdo/shelf-reader",
    "download_url": "",
    "author": "Austin Macdonald",
    "author_email": "asmacdo@gmail.com",
    "maintainer": "",
    "maintainer_email": "",
    "license": "GNU GENERAL PUBLIC LICENSE Version 2, June 1991",
    "requires_python": "",
    "project_url": "",
    "platform": "",
    "supported_platform": "",
    "requires_dist": "[]",
    "provides_dist": "[]",
    "obsoletes_dist": "[]",
    "requires_external": "[]",
    "classifiers": [],
}


# Current tests use PYTHON_FIXTURES_URL with an 'S', remove after adding api tests
PYTHON_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, "python-pypi/")
"""The URL to a python repository."""

PYTHON_FIXTURE_COUNT = 2
"""The number of content units available at :data:`PYTHON_FIXTURE_URL`."""

PYTHON_FIXTURE_SUMMARY = {PYTHON_CONTENT_NAME: PYTHON_FIXTURE_COUNT}
"""The desired content summary after syncing :data:`PYTHON_FIXTURE_URL`."""

PYTHON_URL = urljoin(urljoin(PYTHON_FIXTURE_URL, "packages/"), PYTHON_EGG_FILENAME)
"""The URL to an python file at :data:`PYTHON_FIXTURE_URL`."""

# FIXME: replace this with your own fixture repository URL and metadata
PYTHON_INVALID_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, "python-invalid/")
"""The URL to an invalid python repository."""

# FIXME: replace this with your own fixture repository URL and metadata
PYTHON_LARGE_FIXTURE_URL = urljoin(PULP_FIXTURES_BASE_URL, "python_large/")
"""The URL to a python repository containing a large number of content units."""

# FIXME: replace this with the actual number of content units in your test fixture
PYTHON_LARGE_FIXTURE_COUNT = 25
"""The number of content units available at :data:`PYTHON_LARGE_FIXTURE_URL`."""
