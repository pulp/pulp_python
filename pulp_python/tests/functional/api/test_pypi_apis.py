import pytest
import requests
import subprocess

from urllib.parse import urljoin

from pulp_python.tests.functional.constants import (
    PYTHON_SM_PROJECT_SPECIFIER,
    PYTHON_SM_FIXTURE_RELEASES,
    PYTHON_SM_FIXTURE_CHECKSUMS,
    PYTHON_MD_PROJECT_SPECIFIER,
    PYTHON_MD_PYPI_SUMMARY,
    PYTHON_EGG_FILENAME,
    PYTHON_EGG_URL,
    PYTHON_EGG_SHA256,
    PYTHON_WHEEL_FILENAME,
    PYTHON_WHEEL_URL,
    PYTHON_WHEEL_SHA256,
    SHELF_PYTHON_JSON,
)

from pulp_python.tests.functional.utils import ensure_simple


PYPI_LAST_SERIAL = "X-PYPI-LAST-SERIAL"
PYPI_SERIAL_CONSTANT = 1000000000


@pytest.fixture
def python_empty_repo_distro(python_repo_factory, python_distribution_factory):
    """Returns an empty repo with and distribution serving it."""
    def _generate_empty_repo_distro(repo_body=None, distro_body=None):
        repo_body = repo_body or {}
        distro_body = distro_body or {}
        repo = python_repo_factory(**repo_body)
        distro = python_distribution_factory(repository=repo, **distro_body)
        return repo, distro

    yield _generate_empty_repo_distro


@pytest.mark.parallel
def test_empty_index(python_bindings, python_empty_repo_distro):
    """Checks that summary stats are 0 when index is empty."""
    _, distro = python_empty_repo_distro()

    summary = python_bindings.PypiApi.read(path=distro.base_path)
    assert not any(summary.to_dict().values())


@pytest.mark.parallel
def test_live_index(
    python_bindings, python_repo_with_sync, python_remote_factory, python_distribution_factory
):
    """Checks summary stats are correct for indexes pointing to repositories."""
    remote = python_remote_factory(includes=PYTHON_MD_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)
    distro = python_distribution_factory(repository=repo)

    summary = python_bindings.PypiApi.read(path=distro.base_path)
    assert summary.to_dict() == PYTHON_MD_PYPI_SUMMARY


@pytest.mark.parallel
def test_published_index(
    python_bindings,
    python_repo_with_sync,
    python_remote_factory,
    python_publication_factory,
    python_distribution_factory,
):
    """Checks summary stats are correct for indexes pointing to publications."""
    remote = python_remote_factory(includes=PYTHON_MD_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)
    pub = python_publication_factory(repository=repo)
    distro = python_distribution_factory(publication=pub)

    summary = python_bindings.PypiApi.read(path=distro.base_path)
    assert summary.to_dict() == PYTHON_MD_PYPI_SUMMARY


@pytest.fixture(scope="module")
def python_package_dist_directory(tmp_path_factory, http_get):
    """Creates a temp dir to hold package distros for uploading."""
    dist_dir = tmp_path_factory.mktemp("dist")
    egg_file = dist_dir / PYTHON_EGG_FILENAME
    wheel_file = dist_dir / PYTHON_WHEEL_FILENAME
    with open(egg_file, "wb") as f:
        f.write(http_get(PYTHON_EGG_URL))
    with open(wheel_file, "wb") as f:
        f.write(http_get(PYTHON_WHEEL_URL))
    yield dist_dir, egg_file, wheel_file


@pytest.mark.parallel
def test_package_upload(
    python_content_summary, python_empty_repo_distro, python_package_dist_directory, monitor_task
):
    """Tests that packages can be uploaded."""
    repo, distro = python_empty_repo_distro()
    dist_dir, egg_file, wheel_file = python_package_dist_directory
    url = urljoin(distro.base_url, "legacy/")
    response = requests.post(
        url,
        data={"sha256_digest": PYTHON_EGG_SHA256},
        files={"content": open(egg_file, "rb")},
        auth=("admin", "password"),
    )
    assert response.status_code == 202
    monitor_task(response.json()["task"])
    summary = python_content_summary(repository=repo)
    assert summary.added["python.python"]["count"] == 1
    # Test re-uploading same package gives 400 Bad Request
    response = requests.post(
        url,
        data={"sha256_digest": PYTHON_EGG_SHA256},
        files={"content": open(egg_file, "rb")},
        auth=("admin", "password"),
    )
    assert response.status_code == 400
    assert response.reason == f"Package {PYTHON_EGG_FILENAME} already exists in index"


@pytest.mark.parallel
def test_package_upload_session(
    python_content_summary, python_empty_repo_distro, python_package_dist_directory, monitor_task
):
    """Tests that multiple uploads will be broken up into multiple tasks."""
    repo, distro = python_empty_repo_distro()
    url = urljoin(distro.base_url, "legacy/")
    dist_dir, egg_file, wheel_file = python_package_dist_directory
    session = requests.Session()
    response = session.post(
        url,
        data={"sha256_digest": PYTHON_EGG_SHA256},
        files={"content": open(egg_file, "rb")},
        auth=("admin", "password"),
    )
    assert response.status_code == 202
    task = monitor_task(response.json()["task"])
    response2 = session.post(
        url,
        data={"sha256_digest": PYTHON_WHEEL_SHA256},
        files={"content": open(wheel_file, "rb")},
        auth=("admin", "password"),
    )
    assert response2.status_code == 202
    task2 = monitor_task(response2.json()["task"])
    assert task != task2
    summary = python_content_summary(repository=repo)
    assert summary.present["python.python"]["count"] == 2


@pytest.mark.parallel
def test_package_upload_simple(
    python_content_summary, python_empty_repo_distro, python_package_dist_directory, monitor_task
):
    """Tests that the package upload endpoint exposed at `/simple/` works."""
    repo, distro = python_empty_repo_distro()
    url = urljoin(distro.base_url, "simple/")
    dist_dir, egg_file, wheel_file = python_package_dist_directory
    response = requests.post(
        url,
        data={"sha256_digest": PYTHON_EGG_SHA256},
        files={"content": open(egg_file, "rb")},
        auth=("admin", "password"),
    )
    assert response.status_code == 202
    monitor_task(response.json()["task"])
    summary = python_content_summary(repository=repo)
    assert summary.added["python.python"]["count"] == 1


@pytest.mark.parallel
def test_twine_upload(
    pulpcore_bindings,
    python_content_summary,
    python_empty_repo_distro,
    python_package_dist_directory,
    monitor_task,
):
    """Tests that packages can be properly uploaded through Twine."""
    repo, distro = python_empty_repo_distro()
    url = urljoin(distro.base_url, "legacy/")
    dist_dir, _, _ = python_package_dist_directory
    username, password = "admin", "password"
    subprocess.run(
        (
            "twine",
            "upload",
            "--repository-url",
            url,
            dist_dir / "*",
            "-u",
            username,
            "-p",
            password,
        ),
        capture_output=True,
        check=True,
    )
    tasks = pulpcore_bindings.TasksApi.list(reserved_resources=repo.pulp_href).results
    for task in reversed(tasks):
        t = monitor_task(task.pulp_href)
        repo_ver_href = t.created_resources[-1]
    summary = python_content_summary(repository_version=repo_ver_href)
    assert summary.present["python.python"]["count"] == 2

    # Test re-uploading same packages gives error
    with pytest.raises(subprocess.CalledProcessError):
        subprocess.run(
            (
                "twine",
                "upload",
                "--repository-url",
                url,
                dist_dir / "*",
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
            dist_dir / "*",
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
    assert output.stdout.count("Skipping") == 2


@pytest.mark.parallel
def test_simple_redirect_with_publications(
    python_remote_factory,
    python_repo_with_sync,
    python_publication_factory,
    python_distribution_factory,
    pulp_content_url,
):
    """Checks that requests to `/simple/` get redirected when serving a publication."""
    remote = python_remote_factory()
    repo = python_repo_with_sync(remote=remote)
    pub = python_publication_factory(repository=repo)
    distro = python_distribution_factory(publication=pub)
    response = requests.get(urljoin(distro.base_url, "simple/"))
    assert response.url == str(urljoin(pulp_content_url, f"{distro.base_path}/simple/"))


@pytest.mark.parallel
def test_simple_correctness_live(
    python_remote_factory, python_repo_with_sync, python_distribution_factory
):
    """Checks that the simple api on live distributions are correct."""
    remote = python_remote_factory(includes=PYTHON_SM_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)
    distro = python_distribution_factory(repository=repo)
    proper, msgs = ensure_simple(
        urljoin(distro.base_url, "simple/"),
        PYTHON_SM_FIXTURE_RELEASES,
        sha_digests=PYTHON_SM_FIXTURE_CHECKSUMS,
    )
    assert proper is True, msgs


@pytest.mark.parallel
def test_pypi_json(python_remote_factory, python_repo_with_sync, python_distribution_factory):
    """Checks the data of `pypi/{package_name}/json` endpoint."""
    remote = python_remote_factory(policy="immediate")
    repo = python_repo_with_sync(remote)
    distro = python_distribution_factory(repository=repo)
    response = requests.get(urljoin(distro.base_url, "pypi/shelf-reader/json"))
    assert_pypi_json(response.json())


@pytest.mark.parallel
def test_pypi_json_content_app(
    python_remote_factory,
    python_repo_with_sync,
    python_publication_factory,
    python_distribution_factory,
    pulp_content_url,
):
    """Checks that the pypi json endpoint of the content app still works. Needs Publication."""
    remote = python_remote_factory(policy="immediate")
    repo = python_repo_with_sync(remote)
    pub = python_publication_factory(repository=repo)
    distro = python_distribution_factory(publication=pub)
    rel_url = f"{distro.base_path}/pypi/shelf-reader/json/"
    response = requests.get(urljoin(pulp_content_url, rel_url))
    assert_pypi_json(response.json())


@pytest.mark.parallel
def test_pypi_last_serial(
    python_remote_factory,
    python_repo_with_sync,
    python_publication_factory,
    python_distribution_factory,
    pulp_content_url,
):
    """
    Checks that the endpoint has the header PYPI_LAST_SERIAL and is set
    TODO when serial field is added to Repo's, check this header against that
    """
    remote = python_remote_factory(policy="immediate")
    repo = python_repo_with_sync(remote)
    pub = python_publication_factory(repository=repo)
    distro = python_distribution_factory(publication=pub)
    content_url = urljoin(
        pulp_content_url, f"{distro.base_path}/pypi/shelf-reader/json"
    )
    pypi_url = urljoin(distro.base_url, "pypi/shelf-reader/json/")
    for url in [content_url, pypi_url]:
        response = requests.get(url)
        assert PYPI_LAST_SERIAL in response.headers, url
        assert response.headers[PYPI_LAST_SERIAL] == str(PYPI_SERIAL_CONSTANT), url


def assert_pypi_json(package):
    """Asserts that shelf-reader package json is correct."""
    assert SHELF_PYTHON_JSON["last_serial"] == package["last_serial"]
    assert SHELF_PYTHON_JSON["info"].items() <= package["info"].items()
    assert len(SHELF_PYTHON_JSON["urls"]) == len(package["urls"])
    assert_download_info(
        SHELF_PYTHON_JSON["urls"], package["urls"], "Failed to match URLS"
    )
    assert SHELF_PYTHON_JSON["releases"].keys() <= package["releases"].keys()
    for version in SHELF_PYTHON_JSON["releases"].keys():
        assert_download_info(
            SHELF_PYTHON_JSON["releases"][version],
            package["releases"][version],
            "Failed to match version",
        )


def assert_download_info(expected, received, message="Failed to match"):
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
        assert matched is True, message
