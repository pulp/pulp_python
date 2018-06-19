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


PYTHON_EMPTY_PROJECT_SPECIFIER = []

PYTHON_XS_PROJECT_SPECIFIER = [
    {"name": "shelf-reader", "version_specifier": "", "digests": []}  # matches 2
]
PYTHON_XS_PACKAGE_COUNT = 2

PYTHON_SM_PROJECT_SPECIFIER = [
    {"name": "aiohttp", "version_specifier": ">=3.2.0,<3.3.1", "digests": []},  # matches 2
    {"name": "celery", "version_specifier": ">4.1.0,<=4.2.0", "digests": []},  # matches 6
    {"name": "Django", "version_specifier": ">1.10.0,<1.10.5", "digests": []},  # matches 8
]
PYTHON_SM_PACKAGE_COUNT = 16

PYTHON_MD_PROJECT_SPECIFIER = [

]
PYTHON_MD_PACKAGE_COUNT = 0

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
