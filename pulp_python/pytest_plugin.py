import pytest
import uuid
import subprocess

from pulpcore.tests.functional.utils import BindingsNamespace
from pulp_python.tests.functional.constants import (
    PYTHON_FIXTURE_URL,
    PYTHON_XS_PROJECT_SPECIFIER,
    PYTHON_EGG_FILENAME,
    PYTHON_URL,
)


# Bindings API Fixtures


@pytest.fixture(scope="session")
def python_bindings(_api_client_set, bindings_cfg):
    """
    A namespace providing preconfigured pulp_python api clients.

    e.g. `python_bindings.RepositoriesPythonApi.list()`.
    """
    from pulpcore.client import pulp_python as python_bindings_module

    api_client = python_bindings_module.ApiClient(bindings_cfg)
    _api_client_set.add(api_client)
    yield BindingsNamespace(python_bindings_module, api_client)
    _api_client_set.remove(api_client)


# Object Generation Fixtures


@pytest.fixture
def python_repo_factory(python_bindings, gen_object_with_cleanup):
    """A factory to generate a Python Repository with auto-cleanup."""
    def _gen_python_repo(remote=None, pulp_domain=None, **body):
        body.setdefault("name", str(uuid.uuid4()))
        kwargs = {}
        if pulp_domain:
            kwargs["pulp_domain"] = pulp_domain
        if remote:
            body["remote"] = remote if isinstance(remote, str) else remote.pulp_href
        return gen_object_with_cleanup(python_bindings.RepositoriesPythonApi, body, **kwargs)

    return _gen_python_repo


@pytest.fixture
def python_repo(python_repo_factory):
    """Creates a Python Repository and deletes it at test cleanup time."""
    return python_repo_factory()


@pytest.fixture
def python_distribution_factory(python_bindings, gen_object_with_cleanup):
    """A factory to generate a Python Distribution with auto-cleanup."""
    def _gen_python_distribution(
        publication=None, repository=None, version=None, pulp_domain=None, **body
    ):
        name = str(uuid.uuid4())
        body.setdefault("name", name)
        body.setdefault("base_path", name)
        if publication:
            body["publication"] = get_href(publication)
        elif repository:
            repo_href = get_href(repository)
            if version:
                if version.isnumeric():
                    ver_href = f"{repo_href}versions/{version}/"
                else:
                    ver_href = get_href(version)
                body = {"repository_version": ver_href}
            else:
                body["repository"] = repo_href
        kwargs = {}
        if pulp_domain:
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(python_bindings.DistributionsPypiApi, body, **kwargs)

    yield _gen_python_distribution


@pytest.fixture
def python_publication_factory(python_bindings, gen_object_with_cleanup):
    """A factory to generate a Python Publication with auto-cleanup."""
    def _gen_python_publication(repository, version=None, pulp_domain=None):
        repo_href = get_href(repository)
        if version:
            if version.isnumeric():
                ver_href = f"{repo_href}versions/{version}/"
            else:
                ver_href = get_href(version)
            body = {"repository_version": ver_href}
        else:
            body = {"repository": repo_href}
        kwargs = {}
        if pulp_domain:
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(python_bindings.PublicationsPypiApi, body, **kwargs)

    yield _gen_python_publication


@pytest.fixture
def python_remote_factory(python_bindings, gen_object_with_cleanup):
    """A factory to generate a Python Remote with auto-cleanup."""
    def _gen_python_remote(url=PYTHON_FIXTURE_URL, includes=None, pulp_domain=None, **body):
        body.setdefault("name", str(uuid.uuid4()))
        body.setdefault("url", url)
        if includes is None:
            includes = PYTHON_XS_PROJECT_SPECIFIER
        body["includes"] = includes
        kwargs = {}
        if pulp_domain:
            kwargs["pulp_domain"] = pulp_domain
        return gen_object_with_cleanup(python_bindings.RemotesPythonApi, body, **kwargs)

    yield _gen_python_remote


@pytest.fixture
def python_repo_with_sync(
    python_bindings, python_repo_factory, python_remote_factory, monitor_task
):
    """A factory to generate a Python Repository synced with the passed in Remote."""
    def _gen_python_repo_sync(remote=None, mirror=False, repository=None, **body):
        kwargs = {}
        if pulp_domain := body.get("pulp_domain"):
            kwargs["pulp_domain"] = pulp_domain
        remote = remote or python_remote_factory(**kwargs)
        repo = repository or python_repo_factory(**body)
        sync_body = {"mirror": mirror, "remote": remote.pulp_href}
        monitor_task(python_bindings.RepositoriesPythonApi.sync(repo.pulp_href, sync_body).task)
        return python_bindings.RepositoriesPythonApi.read(repo.pulp_href)

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
def python_content_factory(python_bindings, download_python_file, monitor_task):
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

        task = python_bindings.ContentPackagesApi.create(**body).task
        response = monitor_task(task)
        return python_bindings.ContentPackagesApi.read(response.created_resources[0])

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
def python_content_summary(python_bindings):
    """Get a summary of the repository version's content."""
    def _gen_summary(repository_version=None, repository=None, version=None):
        if repository_version is None:
            repo_href = get_href(repository)
            if version:
                repo_ver_href = f"{repo_href}versions/{version}/"
            else:
                repo_api = python_bindings.RepositoriesPythonApi
                repo_ver_href = repo_api.read(repo_href).latest_version_href
        else:
            repo_ver_href = get_href(repository_version)
        return python_bindings.RepositoriesPythonVersionsApi.read(repo_ver_href).content_summary

    yield _gen_summary


def get_href(item):
    """Tries to get the href from the given item, whether it is a string or object."""
    return item if isinstance(item, str) else item.pulp_href
