from urllib.parse import urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL
from pulp_smash.pulp3.constants import (
    BASE_PUBLISHER_PATH,
    BASE_REMOTE_PATH,
    CONTENT_PATH
)


PYTHON_CONTENT_PATH = urljoin(CONTENT_PATH, 'python/packages/')

PYTHON_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'python/')

PYTHON_PUBLISHER_PATH = urljoin(BASE_PUBLISHER_PATH, 'python/')

PYTHON_FIXTURES_URL = urljoin(PULP_FIXTURES_BASE_URL, 'python-pypi/')

PYPI_URL = "https://pypi.org/"


# Specifier for testing empty syncs, or no excludes
PYTHON_EMPTY_PROJECT_SPECIFIER = []
# Specifier that includes projects that aren't in the test fixtures
PYTHON_UNAVAILABLE_PROJECT_SPECIFIER = [
    {"name": "shelf-reader", "version_specifier": "", "digests": []},           # matches 2
    {"name": "aiohttp", "version_specifier": ">=3.2.0,<3.3.1", "digests": []},  # matches 3
    {"name": "flake8", "version_specifier": "", "digests": []},                 # matches 0
    {"name": "pyramid", "version_specifier": "", "digests": []},                # matches 0
    {"name": "pylint", "version_specifier": "", "digests": []},                 # matches 0
]
PYTHON_UNAVAILABLE_PACKAGE_COUNT = 5

# no "name" field
PYTHON_INVALID_SPECIFIER_NO_NAME = [
    {"nam": "shelf-reader", "version_specifier": ""},
]
# invalid "version_specifier" field
PYTHON_INVALID_SPECIFIER_BAD_VERSION = [
    {"name": "shelf-reader", "version_specifier": "$3"},
]
# no "version_specifier" field
PYTHON_VALID_SPECIFIER_NO_VERSION = [
    {"name": "shelf-reader", "version": ""},
]

# Specifier for testing that the correct number of packages are synced when prereleases
# is set True or False on the remote.
PYTHON_PRERELEASE_TEST_SPECIFIER = [
    # matches 2 w/ prereleases, 1 w/o
    {"name": "aiohttp", "version_specifier": ">3.3.1,<=3.3.2", "digests": []},
    # matches 13 w/ prereleases, 9 w/o
    {"name": "celery", "version_specifier": "", "digests": []},
    # matches 31 w/ prereleases, 20 w/o
    {"name": "Django", "version_specifier": "", "digests": []},
]
PYTHON_WITH_PRERELEASE_COUNT = 46
PYTHON_WITHOUT_PRERELEASE_COUNT = 30

# Specifier for basic sync / publish tests.
PYTHON_XS_PROJECT_SPECIFIER = [
    {"name": "shelf-reader", "version_specifier": "", "digests": []}  # matches 2
]
PYTHON_XS_PACKAGE_COUNT = 2

PYTHON_SM_PROJECT_SPECIFIER = [
    {"name": "aiohttp", "version_specifier": ">=3.2.0,<3.3.1", "digests": []},  # matches 3
    {"name": "celery", "version_specifier": ">4.1.0,<=4.2.0", "digests": []},   # matches 2
    {"name": "Django", "version_specifier": ">1.10.0,<1.10.5", "digests": []},  # matches 8
]
PYTHON_SM_PACKAGE_COUNT = 13

PYTHON_MD_PROJECT_SPECIFIER = [
    {"name": "shelf-reader", "version_specifier": "", "digests": []},           # matches 2
    {"name": "aiohttp", "version_specifier": ">=3.2.0,<3.3.1", "digests": []},  # matches 3
    {"name": "celery", "version_specifier": "~=4.0", "digests": []},            # matches 5
    {"name": "Django", "version_specifier": ">1.10.0,<=2.0.6", "digests": []},  # matches 16
]
PYTHON_MD_PACKAGE_COUNT = 26

PYTHON_LG_PROJECT_SPECIFIER = [
    {"name": "aiohttp", "version_specifier": "", "digests": []},  # matches 7
    {"name": "celery", "version_specifier": "", "digests": []},  # matches 13
    {"name": "Django", "version_specifier": "", "digests": []},  # matches 31
    {"name": "scipy", "version_specifier": "", "digests": []},  # matches 23
    {"name": "shelf-reader", "version_specifier": "", "digests": []},  # matches 2
]
PYTHON_LG_PACKAGE_COUNT = 76

# Intended to be used with the XS specifier
PYTHON_EGG_FILENAME = "shelf-reader-0.1.tar.gz"
PYTHON_EGG_URL = urljoin(
    urljoin(PYTHON_FIXTURES_URL, 'packages/'),
    PYTHON_EGG_FILENAME
)

# Intended to be used with the XS specifier
PYTHON_WHEEL_FILENAME = "shelf_reader-0.1-py2-none-any.whl"
PYTHON_WHEEL_URL = urljoin(
    urljoin(PYTHON_FIXTURES_URL, 'packages/'),
    PYTHON_WHEEL_FILENAME
)
