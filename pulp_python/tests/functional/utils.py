import uuid

from pulp_smash.tests.pulp3 import utils

from .constants import PYTHON_PROJECT_LIST


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulp-python isn't installed."""
    utils.require_pulp_3()
    utils.require_pulp_plugins({'pulp_python'})


def gen_remote():
    """Return a semi-random dict for use in creating an remote."""
    return {
        'name': str(uuid.uuid4()),
        'projects': PYTHON_PROJECT_LIST,
    }


def gen_publisher():
    """Return a semi-random dict for use in creating a publisher."""
    return {
        'name': str(uuid.uuid4()),
    }
