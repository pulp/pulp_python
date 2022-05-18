import pytest

from pulp_smash.pulp3.utils import gen_distribution, gen_repo
from pulp_python.tests.functional.utils import gen_python_remote

from pulpcore.client.pulp_python import (
    ApiClient,
    ContentPackagesApi,
    DistributionsPypiApi,
    PublicationsPypiApi,
    RepositoriesPythonApi,
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
def python_repo(python_repo_api_client, gen_object_with_cleanup):
    """Creates a Python Repository and deletes it at test cleanup time."""
    return gen_object_with_cleanup(python_repo_api_client, gen_repo())


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
