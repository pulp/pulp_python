from urllib.parse import urljoin

from pulp_smash import config
from pulp_smash.pulp3.constants import (
    BASE_DISTRIBUTION_PATH,
    BASE_PUBLICATION_PATH,
    BASE_REMOTE_PATH,
    BASE_REPO_PATH,
    BASE_CONTENT_PATH,
)


PULP_FIXTURES_BASE_URL = config.get_config().get_fixtures_url()

PYPI_URL = "https://pypi.org/"

PYTHON_CONTENT_NAME = "python.python"

PYTHON_CONTENT_PATH = urljoin(BASE_CONTENT_PATH, "python/packages/")

PYTHON_DISTRIBUTION_PATH = urljoin(BASE_DISTRIBUTION_PATH, "python/pypi/")

PYTHON_FIXTURES_URL = urljoin(PULP_FIXTURES_BASE_URL, "python-pypi/")

PYTHON_PUBLICATION_PATH = urljoin(BASE_PUBLICATION_PATH, "python/pypi/")

PYTHON_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, "python/python/")

PYTHON_REPO_PATH = urljoin(BASE_REPO_PATH, "python/python/")

PULP_CONTENT_HOST_BASE_URL = config.get_config().get_content_host_base_url()

PULP_CONTENT_BASE_URL = urljoin(PULP_CONTENT_HOST_BASE_URL, "pulp/content/")

PULP_PYPI_BASE_URL = "/pypi/"

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
PYTHON_SM_FIXTURE_RELEASES = {
    "aiohttp": ["aiohttp-3.3.0.tar.gz", "aiohttp-3.2.1.tar.gz", "aiohttp-3.2.0.tar.gz"],
    "Django": [
        "Django-1.10.4.tar.gz",
        "Django-1.10.4-py2.py3-none-any.whl",
        "Django-1.10.3.tar.gz",
        "Django-1.10.3-py2.py3-none-any.whl",
        "Django-1.10.2.tar.gz",
        "Django-1.10.2-py2.py3-none-any.whl",
        "Django-1.10.1.tar.gz",
        "Django-1.10.1-py2.py3-none-any.whl",
    ],
    "celery": [
        "celery-4.2.0-py2.py3-none-any.whl",
        "celery-4.1.1-py2.py3-none-any.whl",
    ],
}
PYTHON_SM_FIXTURE_CHECKSUMS = {
    "aiohttp-3.3.0.tar.gz": "3128d3ef7b575dbb272cdacd4d4c9a7cf67b18899e96260d55ae3a5782d886e7",
    "aiohttp-3.2.1.tar.gz": "1b95d53f8dac13898f0a3e4af76f6f36d540fbfaefc4f4c9f43e436fa0e53d22",
    "aiohttp-3.2.0.tar.gz": "1be3903fe6a36d20492e74efb326522dd4702bf32b45ffc7acbc0fb34ab240a6",
    "Django-1.10.4.tar.gz": "fff7f062e510d812badde7cfc57745b7779edb4d209b2bc5ea8d954c22305c2b",
    "Django-1.10.4-py2.py3-none-any.whl":
        "a8e1a552205cda15023c39ecf17f7e525e96c5b0142e7879e8bd0c445351f2cc",
    "Django-1.10.3.tar.gz": "6f92f08dee8a1bd7680e098a91bf5acd08b5cdfe74137f695b60fd79f4478c30",
    "Django-1.10.3-py2.py3-none-any.whl":
        "94426cc28d8721fbf13c333053f08d32427671a4ca7986f7030fc82bdf9c88c1",
    "Django-1.10.2.tar.gz": "e127f12a0bfb34843b6e8c82f91e26fff6445a7ca91d222c0794174cf97cbce1",
    "Django-1.10.2-py2.py3-none-any.whl":
        "4d48ab8e84a7c8b2bc4b2f4f199bc3a8bfcc9cbdbc29e355ac5c44a501d73a1a",
    "Django-1.10.1.tar.gz": "d6e6c5b25cb67f46afd7c82f536529b11981183423dad8932e15bce93d1a24f3",
    "Django-1.10.1-py2.py3-none-any.whl":
        "3d689905cd0635bbb33b87f9a5df7ca70a3db206faae4ec58cda5e7f5f47050d",
    "celery-4.2.0-py2.py3-none-any.whl":
        "2082cbd82effa8ac8a8a58977d70bb203a9f362817e3b66f4578117b9f93d8a9",
    "celery-4.1.1-py2.py3-none-any.whl":
        "6fc4678d1692af97e137b2a9f1c04efd8e7e2fb7134c5c5ad60738cdd927762f",
}

PYTHON_MD_PROJECT_SPECIFIER = [
    "shelf-reader",  # matches 2
    "aiohttp>=3.2.0,<3.3.1",  # matches 3
    "celery~=4.0",  # matches 5
    "Django>1.10.0,<=2.0.6",  # matches 16
]
PYTHON_MD_PACKAGE_COUNT = 26
PYTHON_MD_FIXTURE_SUMMARY = {PYTHON_CONTENT_NAME: PYTHON_MD_PACKAGE_COUNT}
PYTHON_MD_PYPI_SUMMARY = {"projects": 4, "releases": 17, "files": 26}

PYTHON_LG_PROJECT_SPECIFIER = [
    "aiohttp",  # matches 7
    "celery",  # matches 13
    "Django",  # matches 31
    "scipy",  # matches 23
    "shelf-reader",  # matches 2
]
PYTHON_LG_PACKAGE_COUNT = 76
PYTHON_LG_FIXTURE_SUMMARY = {PYTHON_CONTENT_NAME: PYTHON_LG_PACKAGE_COUNT}
PYTHON_LG_FIXTURE_COUNTS = {
    "latest_3": 35,
    "sdist": 23,
    "bdist_wheel": 53,
}

DJANGO_LATEST_3 = 4  # latest version has 2 dists, each other has 1
SCIPY_COUNTS = {
    "total": 23,  # scipy has 23 different release files for the same release
    "windows": 8,
    "macos": 4,
    "linux": 10,
    "no_os": 1,
}


# Intended to be used with the XS specifier
PYTHON_EGG_FILENAME = "shelf-reader-0.1.tar.gz"
PYTHON_EGG_URL = urljoin(urljoin(PYTHON_FIXTURES_URL, "packages/"), PYTHON_EGG_FILENAME)
PYTHON_EGG_SHA256 = "04cfd8bb4f843e35d51bfdef2035109bdea831b55a57c3e6a154d14be116398c"

# Intended to be used with the XS specifier
PYTHON_WHEEL_FILENAME = "shelf_reader-0.1-py2-none-any.whl"
PYTHON_WHEEL_URL = urljoin(
    urljoin(PYTHON_FIXTURES_URL, "packages/"), PYTHON_WHEEL_FILENAME
)
PYTHON_WHEEL_SHA256 = "2eceb1643c10c5e4a65970baf63bde43b79cbdac7de81dae853ce47ab05197e9"

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
    "classifiers": "[]",
}

# Info data for Shelf-reader
PYTHON_INFO_DATA = {
    "name": "shelf-reader",
    "version": "0.1",
    # "metadata_version": "",  # Maybe program "1.1" into parse_metadata of app/utils.py
    "summary": "Make sure your collections are in call number order.",
    "keywords": "library barcode call number shelf collection",
    "home_page": "https://github.com/asmacdo/shelf-reader",
    "download_url": "UNKNOWN",
    "author": "Austin Macdonald",
    "author_email": "asmacdo@gmail.com",
    "maintainer": "",
    "maintainer_email": "",
    # "license": "GNU GENERAL PUBLIC LICENSE Version 2, June 1991",
    "requires_python": None,
    "project_url": "https://pypi.org/project/shelf-reader/",
    "platform": "UNKNOWN",
    # "supported_platform": None,
    "requires_dist": None,
    # "provides_dist": [],
    # "obsoletes_dist": [],
    # "requires_external": [],
    "classifiers": ['Development Status :: 4 - Beta', 'Environment :: Console',
                    'Intended Audience :: Developers',
                    'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
                    'Natural Language :: English', 'Programming Language :: Python :: 2',
                    'Programming Language :: Python :: 2.7'],
    "downloads": {"last_day": -1, "last_month": -1, "last_week": -1},
    # maybe add description, license is long for this one
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

DEFAULT_BANDER_REMOTE_BODY = {
    "url": "https://pypi.org",
    "download_concurrency": 3,
    "policy": "on_demand",
    "prereleases": False,
    "excludes": ["example1", "example2"]
}

BANDERSNATCH_CONF = b"""
[mirror]
; The directory where the mirror data will be stored.
directory = /srv/pypi
; Save JSON metadata into the web tree:
json = false

; scheme for PyPI server MUST be https
master = https://pypi.org

; The network socket timeout to use for all connections.
timeout = 10
global-timeout = 18000

; Number of worker threads to use for parallel downloads.
workers = 3

; Whether to hash package indexes
hash-index = false

; Whether to stop a sync quickly after an error is found or whether to continue
; syncing but not marking the sync as successful.
stop-on-error = false

storage-backend = filesystem

; Number of consumers which verify metadata
verifiers = 3

; Configure a file to write out the list of files downloaded during the mirror.
diff-file = {{mirror_directory}}/mirrored-files
diff-append-epoch = false

; Enable filtering plugins
[plugins]
; Enable all or specific plugins - e.g. allowlist_project
enabled = all

[blocklist]
; List of PyPI packages not to sync - Useful if malicious packages are mirrored
packages =
    example1
    example2

"""

SHELF_BDIST_PYTHON_DOWNLOAD = {
    "comment_text": "",
    "digests": {
        # "md5": "69b867d206f1ff984651aeef25fc54f9",
        "sha256": "2eceb1643c10c5e4a65970baf63bde43b79cbdac7de81dae853ce47ab05197e9"
    },
    "downloads": -1,
    "filename": "shelf_reader-0.1-py2-none-any.whl",
    "has_sig": False,
    # "md5_digest": "69b867d206f1ff984651aeef25fc54f9",
    "packagetype": "bdist_wheel",
    "python_version": "2.7",
    "requires_python": None,
    "size": 22455,
    "yanked": False,
    "yanked_reason": None
}

SHELF_SDIST_PYTHON_DOWNLOAD = {
    "comment_text": "",
    "digests": {
        # "md5": "2dac570a33d88ca224be86759be59376",
        "sha256": "04cfd8bb4f843e35d51bfdef2035109bdea831b55a57c3e6a154d14be116398c"
    },
    "downloads": -1,
    "filename": "shelf-reader-0.1.tar.gz",
    "has_sig": False,
    # "md5_digest": "2dac570a33d88ca224be86759be59376",
    "packagetype": "sdist",
    # "python_version": "source", # This is the correct value, but hard to generate
    "requires_python": None,
    "size": 19097,
    "yanked": False,
    "yanked_reason": None
}

SHELF_0DOT1_RELEASE = [SHELF_BDIST_PYTHON_DOWNLOAD, SHELF_SDIST_PYTHON_DOWNLOAD]

SHELF_PYTHON_JSON = {
    "info": PYTHON_INFO_DATA,
    "last_serial": 0,
    "releases": {
        "0.1": SHELF_0DOT1_RELEASE
    },
    "urls": SHELF_0DOT1_RELEASE

}
