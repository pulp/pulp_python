from functools import partial
from unittest import SkipTest

from pulp_smash import api, selectors
from pulp_smash.pulp3 import utils
from pulp_smash.pulp3.constants import REPO_PATH
from pulp_smash.pulp3.utils import (
    gen_publisher,
    gen_remote,
    gen_repo,
    get_content,
    sync
)

from pulp_python.tests.functional.constants import (
    PYTHON_CONTENT_PATH,
    PYTHON_EMPTY_PROJECT_SPECIFIER,
    PYTHON_FIXTURES_URL,
    PYTHON_REMOTE_PATH,
    PYTHON_XS_PROJECT_SPECIFIER,
)


def set_up_module():
    """
    Skip tests Pulp 3 isn't under test or if pulp-python isn't installed.
    """
    utils.require_pulp_3(SkipTest)
    utils.require_pulp_plugins({'pulp_python'}, SkipTest)


def gen_python_remote(url=PYTHON_FIXTURES_URL, includes=None, excludes=None,
                      prereleases=False, **kwargs):
    """
    Return a semi-random dict for use in creating a remote.

    Kwargs:
        url (str): The URL to a Python remote repository
        includes (iterable): An iterable of dicts containing project specifier dicts.
        **kwargs: Specified parameters for the Remote

    """
    remote = gen_remote(url)
    if includes is None:
        includes = PYTHON_XS_PROJECT_SPECIFIER
    if excludes is None:
        excludes = PYTHON_EMPTY_PROJECT_SPECIFIER

    # Remote also supports "excludes" and "prereleases".
    python_extra_fields = {
        'includes': includes,
        **kwargs,
    }
    remote.update(python_extra_fields)
    return remote


def gen_python_publisher(**kwargs):
    """
    Return a semi-random dict for use in creating a publisher.

    Kwargs:
        **kwargs: Specified parameters for the Publisher

    """
    publisher = gen_publisher()
    python_extra_fields = {
        **kwargs,
    }
    publisher.update(python_extra_fields)
    return publisher


def get_content_unit_paths(repo):
    """
    Return the relative path of content units present in a file repository.

    Args:
        repo (dict): A dict of information about the repository.

    Returns:
        list: The paths of units present in a given repository.

    """
    return [content_unit['filename'] for content_unit in get_content(repo)]


def populate_pulp(cfg, remote=None):
    """
    Add python content to Pulp.

    Args:
        cfg (pulp_smash.config.PulpSmashConfig): Information about a Pulp application
        remote (dict): A dict of information about the remote.

    Returns:
        list: A list of dicts, where each dict describes one python content in Pulp.

    """
    if remote is None:
        remote = gen_python_remote()
    client = api.Client(cfg, api.json_handler)
    repo = {}
    try:
        remote.update(client.post(PYTHON_REMOTE_PATH, remote))
        repo.update(client.post(REPO_PATH, gen_repo()))
        sync(cfg, remote, repo)
    finally:
        if remote:
            client.delete(remote['_href'])
        if repo:
            client.delete(repo['_href'])
    return client.get(PYTHON_CONTENT_PATH)['results']


skip_if = partial(selectors.skip_if, exc=SkipTest)
