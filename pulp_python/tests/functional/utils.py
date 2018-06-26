import uuid

from pulp_smash import api
from pulp_smash.tests.pulp3 import utils
from pulp_smash.tests.pulp3.constants import REPO_PATH
from pulp_smash.tests.pulp3.utils import gen_repo, sync

from pulp_python.tests.functional.constants import (
    PYTHON_CONTENT_PATH,
    PYTHON_PROJECT_LIST,
    PYTHON_PYPI_URL,
    PYTHON_REMOTE_PATH
)


def set_up_module():
    """
    Skip tests Pulp 3 isn't under test or if pulp-python isn't installed.
    """
    utils.require_pulp_3()
    utils.require_pulp_plugins({'pulp_python'})


def gen_remote(url=PYTHON_PYPI_URL, **kwargs):
    """
    Return a semi-random dict for use in creating an remote.

    Kwargs:
        url (str): The URL to a Python remote repository
        **kwargs: Specified parameters for the Remote
    """
    return {
        'name': str(uuid.uuid4()),
        'projects': PYTHON_PROJECT_LIST,
        'url': url,
        **kwargs,
    }


def gen_publisher(**kwargs):
    """
    Return a semi-random dict for use in creating a publisher.

    Kwargs:
        **kwargs: Specified parameters for the Publisher

    """
    return {'name': str(uuid.uuid4()), **kwargs}


def populate_pulp(cfg, url=None):
    """
    Add python content to Pulp.

    Args:
        cfg (pulp_smash.config.PulpSmashConfig): Information about a Pulp application
        url (str): The URL to a Python remote repository

    Returns:
        list: A list of dicts, where each dict describes one python content in Pulp.

    """
    if url is None:
        url = PYTHON_PYPI_URL
    client = api.Client(cfg, api.json_handler)
    remote = {}
    repo = {}
    try:
        remote.update(client.post(PYTHON_REMOTE_PATH, gen_remote(url)))
        repo.update(client.post(REPO_PATH, gen_repo()))
        sync(cfg, remote, repo)
    finally:
        if remote:
            client.delete(remote['_href'])
        if repo:
            client.delete(repo['_href'])
    return client.get(PYTHON_CONTENT_PATH)['results']
