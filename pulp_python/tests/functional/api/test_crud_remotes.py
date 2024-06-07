import pytest
import uuid

from pulp_python.tests.functional.constants import (
    BANDERSNATCH_CONF,
    DEFAULT_BANDER_REMOTE_BODY,
    PYTHON_INVALID_SPECIFIER_NO_NAME,
    PYTHON_INVALID_SPECIFIER_BAD_VERSION,
    PYTHON_VALID_SPECIFIER_NO_VERSION,
)


@pytest.mark.parallel
@pytest.mark.parametrize("kwargs", [{}, {"policy": "on_demand"}])
def test_remote_from_bandersnatch_config(kwargs, python_bindings, add_to_cleanup, tmp_path):
    """Verify whether it's possible to create a remote from a Bandersnatch config."""
    filename = tmp_path / "bandersnatch.conf"
    with open(filename, mode="wb") as config:
        config.write(BANDERSNATCH_CONF)
        config.flush()
    name = str(uuid.uuid4())
    remote = python_bindings.RemotesPythonApi.from_bandersnatch(filename, name, **kwargs).to_dict()
    add_to_cleanup(python_bindings.RemotesPythonApi, remote["pulp_href"])
    expected = _gen_expected_remote_body(name, **kwargs)
    for key, val in expected.items():
        assert remote[key] == val


@pytest.mark.parallel
def test_remote_default_policy(python_bindings, gen_object_with_cleanup, monitor_task):
    """Verify default download policy behavior and that it can be updated."""
    remote_body = {"name": str(uuid.uuid4()), "url": "https://test"}
    remote = gen_object_with_cleanup(python_bindings.RemotesPythonApi, remote_body)
    assert remote.policy == "on_demand"

    update = {"policy": "immediate"}
    monitor_task(python_bindings.RemotesPythonApi.partial_update(remote.pulp_href, update).task)
    remote = python_bindings.RemotesPythonApi.read(remote.pulp_href)
    assert remote.policy == "immediate"


@pytest.mark.parallel
def test_remote_invalid_project_specifier(python_bindings):
    """Test that creating a remote with an invalid project specifier fails."""
    # Test an include specifier without a "name" field.
    body = {
        "name": str(uuid.uuid4()),
        "url": "https://test",
        "includes": PYTHON_INVALID_SPECIFIER_NO_NAME,
    }
    with pytest.raises(python_bindings.ApiException):
        python_bindings.RemotesPythonApi.create(body)

    # Test an include specifier with an invalid "version_specifier" field value.
    body["includes"] = PYTHON_INVALID_SPECIFIER_BAD_VERSION
    with pytest.raises(python_bindings.ApiException):
        python_bindings.RemotesPythonApi.create(body)

    # Test an exclude specifier without a "name" field.
    body.pop("includes")
    body["excludes"] = PYTHON_INVALID_SPECIFIER_NO_NAME
    with pytest.raises(python_bindings.ApiException):
        python_bindings.RemotesPythonApi.create(body)

    # Test an exclude specifier with an invalid "version_specifier" field value.
    body["excludes"] = PYTHON_INVALID_SPECIFIER_BAD_VERSION
    with pytest.raises(python_bindings.ApiException):
        python_bindings.RemotesPythonApi.create(body)


@pytest.mark.parallel
def test_remote_version_specifier(python_bindings, add_to_cleanup):
    """Test that creating a remote with no "version_specifier" on the project specifier works."""
    # Test an include specifier without a "version_specifier" field.
    body = {
        "name": str(uuid.uuid4()),
        "url": "https://test",
        "includes": PYTHON_VALID_SPECIFIER_NO_VERSION,
    }
    remote = python_bindings.RemotesPythonApi.create(body)
    add_to_cleanup(python_bindings.RemotesPythonApi, remote.pulp_href)

    assert remote.includes[0] == PYTHON_VALID_SPECIFIER_NO_VERSION[0]

    # Test an exclude specifier without a "version_specifier" field.
    body = {
        "name": str(uuid.uuid4()),
        "url": "https://test",
        "excludes": PYTHON_VALID_SPECIFIER_NO_VERSION,
    }
    remote = python_bindings.RemotesPythonApi.create(body)
    add_to_cleanup(python_bindings.RemotesPythonApi, remote.pulp_href)

    assert remote.excludes[0] == PYTHON_VALID_SPECIFIER_NO_VERSION[0]


@pytest.mark.parallel
def test_remote_update_invalid_project_specifier(python_bindings, python_remote_factory):
    """Test that updating a remote with an invalid project specifier fails non-destructively."""
    remote = python_remote_factory()

    # Test an include specifier without a "name" field.
    body = {"includes": PYTHON_INVALID_SPECIFIER_NO_NAME}
    with pytest.raises(python_bindings.ApiException):
        python_bindings.RemotesPythonApi.partial_update(remote.pulp_href, body)

    # Test an include specifier with an invalid "version_specifier" field value.
    body = {"includes": PYTHON_INVALID_SPECIFIER_BAD_VERSION}
    with pytest.raises(python_bindings.ApiException):
        python_bindings.RemotesPythonApi.partial_update(remote.pulp_href, body)

    # Test an exclude specifier without a "name" field.
    body = {"excludes": PYTHON_INVALID_SPECIFIER_NO_NAME}
    with pytest.raises(python_bindings.ApiException):
        python_bindings.RemotesPythonApi.partial_update(remote.pulp_href, body)

    # Test an exclude specifier with an invalid "version_specifier" field value.
    body = {"excludes": PYTHON_INVALID_SPECIFIER_BAD_VERSION}
    with pytest.raises(python_bindings.ApiException):
        python_bindings.RemotesPythonApi.partial_update(remote.pulp_href, body)


def _gen_expected_remote_body(name, **kwargs):
    """Generates a remote body based on names and dictionary in kwargs"""
    # The defaults found in bandersnatch_conf
    body = DEFAULT_BANDER_REMOTE_BODY
    body["name"] = name
    # overwrite the defaults if specified in kwargs
    body.update(kwargs)
    return body
