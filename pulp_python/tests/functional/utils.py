# coding=utf-8
"""Utilities for tests for the python plugin."""
from functools import partial
import requests
from unittest import SkipTest
from tempfile import NamedTemporaryFile

from pulp_smash import config, selectors
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import (
    gen_remote,
    gen_repo,
    get_content,
    require_pulp_3,
    require_pulp_plugins,
)

from pulp_python.tests.functional.constants import (
    PYTHON_CONTENT_NAME,
    PYTHON_FIXTURE_URL,
    PYTHON_URL,
    PYTHON_EGG_FILENAME,
    PYTHON_XS_PROJECT_SPECIFIER,
)

from pulpcore.client.pulpcore import (
    ApiClient as CoreApiClient,
    ArtifactsApi,
    TasksApi,
)
from pulpcore.client.pulp_python import ApiClient as PythonApiClient
from pulpcore.client.pulp_python import (
    RepositoriesPythonApi,
    ContentPackagesApi,
    PublicationsPypiApi,
    PythonPythonPublication,
    RemotesPythonApi,
    RepositorySyncURL,
)

cfg = config.get_config()
configuration = cfg.get_bindings_config()


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulp_python isn't installed."""
    require_pulp_3(SkipTest)
    require_pulp_plugins({"pulp_python"}, SkipTest)


def gen_python_client():
    """Return an OBJECT for python client."""
    return PythonApiClient(configuration)


def gen_python_remote(url=PYTHON_FIXTURE_URL, includes=None, **kwargs):
    """Return a semi-random dict for use in creating a python Remote.

    :param url: The URL of an external content source.
    :param includes: An iterable of dicts containing project specifier dicts.
    :param **kwargs: Specified parameters for the Remote
    """
    remote = gen_remote(url)
    if includes is None:
        includes = PYTHON_XS_PROJECT_SPECIFIER

    # Remote also supports "excludes" and "prereleases".
    python_extra_fields = {
        "includes": includes,
        **kwargs,
    }
    remote.update(python_extra_fields)
    return remote


def get_python_content_paths(repo, version_href=None):
    """Return the relative path of content units present in a python repository.

    :param repo: A dict of information about the repository.
    :param version_href: The repository version to read.
    :returns: A dict of lists with the paths of units present in a given repository.
        Paths are given as pairs with the remote and the local version for different content types.
    """
    return {
        PYTHON_CONTENT_NAME: [
            (content_unit["filename"], content_unit["filename"])
            for content_unit in get_content(repo, version_href)[PYTHON_CONTENT_NAME]
        ],
    }


def gen_python_content_attrs(artifact, filename=PYTHON_EGG_FILENAME):
    """Generate a dict with content unit attributes.

    :param artifact: A dict of info about the artifact.
    :param filename: the name of the artifact being uploaded
    :returns: A semi-random dict for use in creating a content unit.
    """
    return {
        "artifact": artifact["pulp_href"],
        "relative_path": filename,
    }


core_client = CoreApiClient(configuration)
tasks = TasksApi(core_client)
py_client = gen_python_client()
repo_api = RepositoriesPythonApi(py_client)
remote_api = RemotesPythonApi(py_client)
pub_api = PublicationsPypiApi(py_client)
content_api = ContentPackagesApi(py_client)


def populate_pulp(url=PYTHON_FIXTURE_URL):
    """Add python contents to Pulp.

    :param pulp_smash.config.PulpSmashConfig: Information about a Pulp application.
    :param url: The python repository URL. Defaults to
        :data:`pulp_smash.constants.PYTHON_FIXTURE_URL`
    :returns: A list of dicts, where each dict describes one python content in Pulp.
    """
    remote = None
    repo = None
    try:
        remote = remote_api.create(gen_python_remote(url))
        repo = repo_api.create(gen_repo())

        repository_sync_data = RepositorySyncURL(remote=remote.pulp_href)
        sync_response = repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
    finally:
        if remote:
            remote_api.delete(remote.pulp_href)
        if repo:
            repo_api.delete(repo.pulp_href)
    return content_api.list().to_dict()["results"]


def publish(repo, version_href=None):
    """Publish a repository.
    :param repo: A dict of information about the repository.
    :param version_href: A href for the repo version to be published.
    :returns: A publication. A dict of information about the just created
        publication.
    """
    if version_href:
        publish_data = PythonPythonPublication(repository_href=version_href)
    else:
        publish_data = PythonPythonPublication(repository=repo["pulp_href"])

    publish_response = pub_api.create(publish_data)
    created_resources = monitor_task(publish_response.task).created_resources
    return pub_api.read(created_resources[0]).to_dict()


skip_if = partial(selectors.skip_if, exc=SkipTest)  # pylint:disable=invalid-name
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""


def gen_artifact(url=PYTHON_URL):
    """Creates an artifact."""
    response = requests.get(url)
    with NamedTemporaryFile() as temp_file:
        temp_file.write(response.content)
        temp_file.flush()
        artifact = ArtifactsApi(core_client).create(file=temp_file.name)
        return artifact.to_dict()
