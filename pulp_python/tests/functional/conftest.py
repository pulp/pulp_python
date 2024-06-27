import pytest
import subprocess
import uuid

from pulp_smash.pulp3.utils import gen_distribution
from pulp_python.tests.functional.utils import gen_python_remote
from pulp_python.tests.functional.constants import PYTHON_URL, PYTHON_EGG_FILENAME

from pulpcore.client.pulp_python import (
    ApiClient,
    ContentPackagesApi,
    DistributionsPypiApi,
    PublicationsPypiApi,
    RepositoriesPythonApi,
    RepositoriesPythonVersionsApi,
    RemotesPythonApi,
)


# Bindings API Fixtures

@pytest.fixture
def python_bindings_client(cid, bindings_cfg):
    """Provides the python bindings client object."""
    api_client = ApiClient(bindings_cfg)
    api_client.default_headers["Correlation-ID"] = cid
    return api_client


@pytest.fixture
def python_repo_api_client(python_bindings_client):
    """Provides the Python Repository API client object."""
    return RepositoriesPythonApi(python_bindings_client)


@pytest.fixture
def python_repo_version_api_client(python_bindings_client):
    """Provides the Python Repository Version API client object."""
    return RepositoriesPythonVersionsApi(python_bindings_client)


@pytest.fixture
def python_distro_api_client(python_bindings_client):
    """Provides the Python Distribution API client object."""
    return DistributionsPypiApi(python_bindings_client)


@pytest.fixture
def python_content_api_client(python_bindings_client):
    """Provides the Python Package Content API client object."""
    return ContentPackagesApi(python_bindings_client)


@pytest.fixture
def python_remote_api_client(python_bindings_client):
    """Provides the Python Remotes API client object."""
    return RemotesPythonApi(python_bindings_client)


@pytest.fixture
def python_publication_api_client(python_bindings_client):
    """Proves the Python Publication API client object."""
    return PublicationsPypiApi(python_bindings_client)


# Object Generation Fixtures

@pytest.fixture
def python_repo_factory(python_repo_api_client, gen_object_with_cleanup):
    """A factory to generate a Python Repository with auto-cleanup."""
    def _gen_python_repo(**kwargs):
        kwargs.setdefault("name", str(uuid.uuid4()))
        return gen_object_with_cleanup(python_repo_api_client, kwargs)

    return _gen_python_repo


@pytest.fixture
def python_repo(python_repo_factory):
    """Creates a Python Repository and deletes it at test cleanup time."""
    return python_repo_factory()


@pytest.fixture
def python_distribution_factory(python_distro_api_client, gen_object_with_cleanup):
    """A factory to generate a Python Distribution with auto-cleanup."""
    def _gen_python_distribution(**kwargs):
        distro_data = gen_distribution(**kwargs)
        return gen_object_with_cleanup(python_distro_api_client, distro_data)

    yield _gen_python_distribution


@pytest.fixture
def python_publication_factory(python_publication_api_client, gen_object_with_cleanup):
    """A factory to generate a Python Publication with auto-cleanup."""
    def _gen_python_publication(repository, version=None):
        if version:
            body = {"repository_version": f"{repository.versions_href}{version}/"}
        else:
            body = {"repository": repository.pulp_href}
        return gen_object_with_cleanup(python_publication_api_client, body)

    yield _gen_python_publication


@pytest.fixture
def python_remote_factory(python_remote_api_client, gen_object_with_cleanup):
    """A factory to generate a Python Remote with auto-cleanup."""
    def _gen_python_remote(**kwargs):
        body = gen_python_remote(**kwargs)
        return gen_object_with_cleanup(python_remote_api_client, body)

    yield _gen_python_remote


@pytest.fixture
def python_repo_with_sync(
    python_repo_api_client, python_repo_factory, python_remote_factory, monitor_task
):
    """A factory to generate a Python Repository synced with the passed in Remote."""
    def _gen_python_repo_sync(remote=None, mirror=False, repository=None, **body):
        kwargs = {}
        if pulp_domain := body.get("pulp_domain"):
            kwargs["pulp_domain"] = pulp_domain
        remote = remote or python_remote_factory(**kwargs)
        repo = repository or python_repo_factory(**body)
        sync_body = {"mirror": mirror, "remote": remote.pulp_href}
        monitor_task(python_repo_api_client.sync(repo.pulp_href, sync_body).task)
        return python_repo_api_client.read(repo.pulp_href)

    yield _gen_python_repo_sync


@pytest.fixture
def download_python_file(tmp_path, http_get):
    """Download a Python file and return its path."""
    def _download_python_file(relative_path, url):
        file_path = tmp_path / relative_path
        with open(file_path, mode="wb") as f:
            f.write(http_get(url))
        return file_path

    yield _download_python_file


@pytest.fixture
def python_file(download_python_file):
    """Get a default (shelf-reader.tar.gz) Python file."""
    return download_python_file(PYTHON_EGG_FILENAME, PYTHON_URL)


@pytest.fixture
def python_content_factory(python_content_api_client, download_python_file, monitor_task):
    """A factory to create a Python Package Content."""
    def _gen_python_content(relative_path=PYTHON_EGG_FILENAME, url=None, **body):
        body["relative_path"] = relative_path
        if url:
            body["file"] = download_python_file(relative_path, url)
        elif not any(x in body for x in ("artifact", "file", "upload")):
            body["file"] = download_python_file(PYTHON_EGG_FILENAME, PYTHON_URL)
        if repo := body.get("repository"):
            repo_href = repo if isinstance(repo, str) else repo.pulp_href
            body["repository"] = repo_href

        task = python_content_api_client.create(**body).task
        response = monitor_task(task)
        return python_content_api_client.read(response.created_resources[0])

    yield _gen_python_content


# Utility fixtures


@pytest.fixture
def shelf_reader_cleanup():
    """Take care of uninstalling shelf-reader before/after the test."""
    cmd = ("pip", "uninstall", "shelf-reader", "-y")
    subprocess.run(cmd)
    yield
    subprocess.run(cmd)


@pytest.fixture
def python_content_summary(python_repo_api_client, python_repo_version_api_client):
    """Get a summary of the repository version's content."""
    def _gen_summary(repository_version=None, repository=None, version=None):
        if repository_version is None:
            repo_href = get_href(repository)
            if version:
                repo_ver_href = f"{repo_href}versions/{version}/"
            else:
                repo_ver_href = python_repo_api_client.read(repo_href).latest_version_href
        else:
            repo_ver_href = get_href(repository_version)
        return python_repo_version_api_client.read(repo_ver_href).content_summary

    yield _gen_summary


def get_href(item):
    """Tries to get the href from the given item, whether it is a string or object."""
    return item if isinstance(item, str) else item.pulp_href
