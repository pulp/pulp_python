from urllib.parse import urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL
from pulp_smash.tests.pulp3.constants import (
    BASE_PUBLISHER_PATH,
    BASE_REMOTE_PATH,
    CONTENT_PATH
)


PYTHON_CONTENT_PATH = urljoin(CONTENT_PATH, 'python/packages/')

PYTHON_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'python/')

PYTHON_PUBLISHER_PATH = urljoin(BASE_PUBLISHER_PATH, 'python/')


PYTHON_PROJECT_LIST = [{"digests": [], "name": "shelf-reader", "version_specifier": ""}]

PYTHON_PYPI_URL = urljoin(PULP_FIXTURES_BASE_URL, 'python-pypi/')

PYTHON_PACKAGE_COUNT = 2

PYTHON_URL = urljoin(PYTHON_PYPI_URL, '.....')  # TODO
