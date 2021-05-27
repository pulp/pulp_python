# coding=utf-8
"""Utilities for tests for the python plugin."""
from functools import partial
from unittest import SkipTest, TestCase
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin
from lxml import html

from pulp_smash import config, selectors
from pulp_smash.utils import http_get
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import (
    gen_distribution,
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
    DistributionsPypiApi,
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
    require_pulp_plugins({"python"}, SkipTest)


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
distributions_api = DistributionsPypiApi(py_client)
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
    with NamedTemporaryFile() as temp_file:
        temp_file.write(http_get(url))
        temp_file.flush()
        artifact = ArtifactsApi(core_client).create(file=temp_file.name)
        return artifact.to_dict()


class TestCaseUsingBindings(TestCase):
    """A parent TestCase that instantiates the various bindings used throughout tests."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.client = py_client
        cls.core_client = core_client
        cls.repo_api = repo_api
        cls.remote_api = remote_api
        cls.publications_api = pub_api
        cls.distributions_api = distributions_api
        cls.content_api = content_api


class TestHelpersMixin:
    """A common place for sync helper functions."""

    def _create_repository(self, cleanup=True, **kwargs):
        """Create `PythonRepository`"""
        repo = self.repo_api.create(gen_repo(**kwargs))
        if cleanup:
            self.addCleanup(self.repo_api.delete, repo.pulp_href)
        return repo

    def _create_remote(self, cleanup=True, **kwargs):
        """Create `PythonRemote`."""
        remote = self.remote_api.create(gen_python_remote(**kwargs))
        if cleanup:
            self.addCleanup(self.remote_api.delete, remote.pulp_href)
        return remote

    def _create_repo_and_sync_with_remote(self, remote, **kwargs):
        """
        Create a repository and then sync with the provided `remote`.

        Args:
            remote: The remote to be sync with

        Returns:
            repository: The created repository object to be asserted to.
        """
        # Create the repository.
        repo = self.repo_api.create(gen_repo(remote=remote.pulp_href))
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        return self._sync_repo(repo, remote=remote.pulp_href, **kwargs)

    def _create_repo_with_attached_remote_and_sync(self, remote, **kwargs):
        """
        Create a repository with the remote attached, and then sync without specifying the `remote`.

        Args:
            remote: The remote to attach to the repository

        Returns:
            repository: The created repository object to be asserted to.
        """
        # Create the repository.
        repo = self.repo_api.create(gen_repo(remote=remote.pulp_href))
        self.addCleanup(self.repo_api.delete, repo.pulp_href)
        return self._sync_repo(repo, **kwargs)

    def _sync_repo(self, repo, **kwargs):
        """
        Sync the repo with optional `kwarg` parameters passed on to the sync method.

        Args:
            repo: The repository to sync

        Returns:
            repository: The updated repository after the sync is complete
        """
        repository_sync_data = RepositorySyncURL(**kwargs)
        sync_response = self.repo_api.sync(repo.pulp_href, repository_sync_data)
        monitor_task(sync_response.task)
        repo = self.repo_api.read(repo.pulp_href)
        return repo

    def _create_distribution(self, cleanup=True, **kwargs):
        """Create a `PythonDistribution`."""
        body = gen_distribution(**kwargs)
        distribution_create = self.distributions_api.create(body)
        created_resources = monitor_task(distribution_create.task).created_resources
        distribution = self.distributions_api.read(created_resources[0])
        if cleanup:
            self.addCleanup(self.distributions_api.delete, distribution.pulp_href)
        return distribution

    def _create_distribution_from_repo(self, repo, cleanup=True):
        """
        Create a `PythonDistribution` serving the `repo`.

        Args:
            repo: The repository to serve with the `PythonDistribution`
            cleanup: Whether the distribution should be cleaned up

        Returns:
            The created `PythonDistribution`.
        """
        # Create a distribution.
        return self._create_distribution(cleanup, repository=repo.pulp_href)

    def _create_empty_repo_and_distribution(self, cleanup=True, **repo_kwargs):
        """
        Creates an empty `PythonRepository` and an `PythonDistribution` serving that repository.

        Args:
            cleanup: Whether the repository and distribution should be cleaned up

        Returns:
            Tuple of the created `PythonRepository`, `PythonDistribution`
        """
        repo = self.repo_api.create(gen_repo(**repo_kwargs))
        if cleanup:
            self.addCleanup(self.repo_api.delete, repo.pulp_href)
        return repo, self._create_distribution_from_repo(repo, cleanup=cleanup)

    def _create_publication(self, repository, version=None, cleanup=True):
        """
        Creates a `PythonPublication` from the `PythonRepository`.

        Args:
            repository: The repository to use for the publication
            version: Optional - The version to repo_version to use, either an int or href
            cleanup: whether to cleanup the publication

        Returns:
            The created `PythonPublication`
        """
        if version is not None:
            try:
                rv_href = f"{repository.versions_href}{int(version)}/"
            except ValueError:
                rv_href = version
            publish_data = PythonPythonPublication(repository_version=rv_href)
        else:
            publish_data = PythonPythonPublication(repository=repository.pulp_href)
        publish_response = self.publications_api.create(publish_data)
        pub = self.publications_api.read(monitor_task(publish_response.task).created_resources[0])
        if cleanup:
            self.addCleanup(self.publications_api.delete, pub.pulp_href)
        return pub

    def _create_distribution_from_publication(self, pub, cleanup=True):
        """
        Create an `PythonDistribution` serving the `pub`.

        Args:
            pub: The publication to serve with the `PythonDistribution`
            repo: Optional repo to create the publication from if pub is not set
            version: Optional version to create the publication from if pub is not set
            cleanup: Whether the distribution should be cleaned up

        Returns:
            The created `PythonDistribution`.
        """
        return self._create_distribution(cleanup, publication=pub.pulp_href)


def ensure_simple(simple_url, packages, sha_digests=None):
    """
    Tests that the simple api at `url` matches the packages supplied.
    `packages`: dictionary of form {package_name: [release_filenames]}
    First check `/simple/index.html` has each package name, no more, no less
    Second check `/simple/package_name/index.html` for each package exists
    Third check each package's index has all their releases listed, no more, no less
    Returns tuple (`proper`: bool, `error_msg`: str)
    *Technically, if there was a bug, other packages' indexes could be posted, but not present
    in the simple index and thus be accessible from the distribution, but if one can't see it
    how would one know that it's there?*
    """
    def explore_links(page_url, page_name, links_found, msgs):
        legit_found_links = []
        page = html.fromstring(http_get(page_url))
        page_links = page.xpath("/html/body/a")
        for link in page_links:
            if link.text in links_found:
                if links_found[link.text]:
                    msgs += f"\nDuplicate {page_name} name {link.text}"
                links_found[link.text] = True
                if link.get("href"):
                    legit_found_links.append(link.get("href"))
                else:
                    msgs += f"\nFound {page_name} link without href {link.text}"
            else:
                msgs += f"\nFound extra {page_name} link {link.text}"
        return legit_found_links

    packages_found = {name: False for name in packages.keys()}
    releases_found = {name: False for releases in packages.values() for name in releases}
    msgs = ""
    found_release_links = explore_links(simple_url, "simple", packages_found, msgs)
    dl_links = []
    for rel_link in found_release_links:
        dl_links += explore_links(urljoin(simple_url, rel_link), "release", releases_found, msgs)
    for dl_link in dl_links:
        package_link, _, sha = dl_link.partition("#sha256=")
        if len(sha) != 64:
            msgs += f"\nRelease download link has bad sha256 {dl_link}"
        if sha_digests:
            package = package_link.split("/")[-1]
            if sha_digests[package] != sha:
                msgs += f"\nRelease has bad sha256 attached to it {package}"
    msgs += "".join(map(lambda x: f"\nSimple link not found for {x}",
                        [name for name, val in packages_found.items() if not val]))
    msgs += "".join(map(lambda x: f"\nReleases link not found for {x}",
                        [name for name, val in releases_found.items() if not val]))
    return len(msgs) == 0, msgs
