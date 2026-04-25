import pytest

from pulpcore.tests.functional.utils import PulpTaskError

from pulp_python.tests.functional.constants import PYTHON_EGG_FILENAME, PYTHON_EGG_URL

CONTENT_BODY = {"relative_path": PYTHON_EGG_FILENAME, "file_url": PYTHON_EGG_URL}
BLOCKED_MSG = "Blocklisted packages cannot be added to this repository"


@pytest.mark.parallel
def test_crd_entry(python_bindings, python_repo):
    """
    CRD operations on blocklist entries return correct fields and update the entry count.
    """
    entries_data = [
        ({"name": "shelf-reader"}, "shelf-reader", None, None),
        ({"name": "shelf-reader", "version": "0.1"}, "shelf-reader", "0.1", None),
        ({"filename": PYTHON_EGG_FILENAME}, None, None, PYTHON_EGG_FILENAME),
    ]
    for body_kwargs, name, version, filename in entries_data:
        entry = python_bindings.RepositoriesPythonBlocklistEntriesApi.create(
            python_repo.pulp_href, python_bindings.PythonPythonBlocklistEntry(**body_kwargs)
        )
        assert entry.name == name
        assert entry.version == version
        assert entry.filename == filename
        assert entry.added_by == "prn:auth.user:1"
        assert entry.pulp_href is not None
        assert entry.prn is not None

    result = python_bindings.RepositoriesPythonBlocklistEntriesApi.list(python_repo.pulp_href)
    assert result.count == 3

    entry = result.results[0]
    python_bindings.RepositoriesPythonBlocklistEntriesApi.read(entry.pulp_href)

    python_bindings.RepositoriesPythonBlocklistEntriesApi.delete(entry.pulp_href)
    result = python_bindings.RepositoriesPythonBlocklistEntriesApi.list(python_repo.pulp_href)
    assert result.count == 2


@pytest.mark.parallel
@pytest.mark.parametrize(
    "body_kwargs, expected_msg",
    [
        ({"name": "shelf-reader"}, "this name and version already exists"),
        ({"name": "shelf-reader", "version": "0.1"}, "this name and version already exists"),
        ({"filename": PYTHON_EGG_FILENAME}, "this filename already exists"),
    ],
)
def test_duplicate_entry_rejected(python_bindings, python_repo, body_kwargs, expected_msg):
    """
    Creating a duplicate entry should fail.
    """
    python_bindings.RepositoriesPythonBlocklistEntriesApi.create(
        python_repo.pulp_href, python_bindings.PythonPythonBlocklistEntry(**body_kwargs)
    )
    with pytest.raises(python_bindings.ApiException) as ctx:
        python_bindings.RepositoriesPythonBlocklistEntriesApi.create(
            python_repo.pulp_href, python_bindings.PythonPythonBlocklistEntry(**body_kwargs)
        )
    assert ctx.value.status == 400
    assert expected_msg in ctx.value.body


@pytest.mark.parallel
@pytest.mark.parametrize(
    "body_kwargs, expected_msg",
    [
        ({"version": "0.1", "filename": PYTHON_EGG_FILENAME}, "version' cannot be used with"),
        ({"version": "0.1"}, "version' requires 'name'"),
        ({"name": "shelf-reader", "filename": PYTHON_EGG_FILENAME}, "Exactly one of"),
        ({}, "Exactly one of"),
        ({"name": "shelf-reader", "version": "not-a-version"}, "not a valid version"),
    ],
)
def test_invalid_entry_rejected(python_bindings, python_repo, body_kwargs, expected_msg):
    """
    Creating an entry with invalid data should fail.
    """
    with pytest.raises(python_bindings.ApiException) as ctx:
        python_bindings.RepositoriesPythonBlocklistEntriesApi.create(
            python_repo.pulp_href, python_bindings.PythonPythonBlocklistEntry(**body_kwargs)
        )
    assert ctx.value.status == 400
    assert expected_msg in ctx.value.body


@pytest.mark.parallel
def test_upload_blocked(monitor_task, python_bindings, python_repo):
    """
    Uploading a package matching a blocklist entry is rejected.
    """
    python_bindings.RepositoriesPythonBlocklistEntriesApi.create(
        python_repo.pulp_href,
        python_bindings.PythonPythonBlocklistEntry(name="shelf-reader", version="0.1"),
    )

    with pytest.raises(PulpTaskError) as exc:
        response = python_bindings.ContentPackagesApi.create(
            repository=python_repo.pulp_href, **CONTENT_BODY
        )
        monitor_task(response.task)
    assert BLOCKED_MSG in exc.value.task.error["description"]

    repo = python_bindings.RepositoriesPythonApi.read(python_repo.pulp_href)
    assert repo.latest_version_href.endswith("/0/")


@pytest.mark.parallel
def test_upload_allowed(monitor_task, python_bindings, python_repo):
    """
    Uploading a package is allowed when the blocklist entry targets a different version.
    """
    python_bindings.RepositoriesPythonBlocklistEntriesApi.create(
        python_repo.pulp_href,
        python_bindings.PythonPythonBlocklistEntry(name="shelf-reader", version="9.9"),
    )

    response = python_bindings.ContentPackagesApi.create(
        repository=python_repo.pulp_href, **CONTENT_BODY
    )
    monitor_task(response.task)

    repo = python_bindings.RepositoriesPythonApi.read(python_repo.pulp_href)
    assert repo.latest_version_href.endswith("/1/")


@pytest.mark.parallel
def test_modify_blocked(monitor_task, python_bindings, python_repo):
    """
    Adding a blocklisted package via repository modify is rejected.
    """
    python_bindings.RepositoriesPythonBlocklistEntriesApi.create(
        python_repo.pulp_href,
        python_bindings.PythonPythonBlocklistEntry(name="shelf-reader", version="0.1"),
    )

    response = python_bindings.ContentPackagesApi.create(**CONTENT_BODY)
    task = monitor_task(response.task)
    content = python_bindings.ContentPackagesApi.read(task.created_resources[0])

    with pytest.raises(python_bindings.ApiException) as exc:
        python_bindings.RepositoriesPythonApi.modify(
            python_repo.pulp_href, {"add_content_units": [content.pulp_href]}
        )
    assert exc.value.status == 400
    assert BLOCKED_MSG in exc.value.body

    repo = python_bindings.RepositoriesPythonApi.read(python_repo.pulp_href)
    assert repo.latest_version_href.endswith("/0/")
