import pytest
import uuid

from pulpcore.client.pulp_python import ApiException, AsyncOperationResponse
from pulp_python.tests.functional.constants import (
    PYTHON_EGG_FILENAME,
    PYTHON_EGG_SHA256,
    PYTHON_EGG_URL,
)


@pytest.fixture
def gen_users(gen_user):
    """Returns a user generator function for the tests."""

    def _gen_users(role_names=list()):
        if isinstance(role_names, str):
            role_names = [role_names]
        viewer_roles = [f"python.{role}_viewer" for role in role_names]
        creator_roles = [f"python.{role}_creator" for role in role_names]
        alice = gen_user(model_roles=viewer_roles)
        bob = gen_user(model_roles=creator_roles)
        charlie = gen_user()
        return alice, bob, charlie

    return _gen_users


@pytest.fixture
def try_action(monitor_task):
    def _try_action(user, client, action, outcome, *args, **kwargs):
        action_api = getattr(client, f"{action}_with_http_info")
        try:
            with user:
                response, status, _ = action_api(*args, **kwargs, _return_http_data_only=False)
            if isinstance(response, AsyncOperationResponse):
                response = monitor_task(response.task)
        except ApiException as e:
            assert e.status == outcome, f"{e}"
        else:
            assert status == outcome, f"User performed {action} when they shouldn't been able to"
            return response

    return _try_action


@pytest.mark.parallel
def test_basic_actions(gen_users, python_bindings, try_action, python_repo):
    """Test list, read, create, update and delete apis."""
    alice, bob, charlie = gen_users("pythonrepository")

    a_list = try_action(alice, python_bindings.RepositoriesPythonApi, "list", 200)
    assert a_list.count >= 1
    b_list = try_action(bob, python_bindings.RepositoriesPythonApi, "list", 200)
    c_list = try_action(charlie, python_bindings.RepositoriesPythonApi, "list", 200)
    assert (b_list.count, c_list.count) == (0, 0)

    # Create testing
    try_action(
        alice, python_bindings.RepositoriesPythonApi, "create", 403, {"name": str(uuid.uuid4())}
    )
    repo = try_action(
        bob, python_bindings.RepositoriesPythonApi, "create", 201, {"name": str(uuid.uuid4())}
    )
    try_action(
        charlie, python_bindings.RepositoriesPythonApi, "create", 403, {"name": str(uuid.uuid4())}
    )

    # View testing
    try_action(alice, python_bindings.RepositoriesPythonApi, "read", 200, repo.pulp_href)
    try_action(bob, python_bindings.RepositoriesPythonApi, "read", 200, repo.pulp_href)
    try_action(charlie, python_bindings.RepositoriesPythonApi, "read", 404, repo.pulp_href)

    # Update testing
    update_args = [repo.pulp_href, {"name": str(uuid.uuid4())}]
    try_action(alice, python_bindings.RepositoriesPythonApi, "partial_update", 403, *update_args)
    try_action(bob, python_bindings.RepositoriesPythonApi, "partial_update", 202, *update_args)
    try_action(charlie, python_bindings.RepositoriesPythonApi, "partial_update", 404, *update_args)

    # Delete testing
    try_action(alice, python_bindings.RepositoriesPythonApi, "delete", 403, repo.pulp_href)
    try_action(charlie, python_bindings.RepositoriesPythonApi, "delete", 404, repo.pulp_href)
    try_action(bob, python_bindings.RepositoriesPythonApi, "delete", 202, repo.pulp_href)


def test_content_apis(
    python_bindings,
    gen_users,
    python_repo_with_sync,
    try_action,
    python_file,
):
    """Check content listing, scoping and upload APIs."""
    alice, bob, charlie = gen_users()
    aresponse = try_action(alice, python_bindings.ContentPackagesApi, "list", 200)
    bresponse = try_action(bob, python_bindings.ContentPackagesApi, "list", 200)
    cresponse = try_action(charlie, python_bindings.ContentPackagesApi, "list", 200)

    assert aresponse.count == bresponse.count == cresponse.count == 0

    alice, bob, charlie = gen_users(["pythonrepository"])
    repo = python_repo_with_sync()

    aresponse = try_action(alice, python_bindings.ContentPackagesApi, "list", 200)
    bresponse = try_action(bob, python_bindings.ContentPackagesApi, "list", 200)
    cresponse = try_action(charlie, python_bindings.ContentPackagesApi, "list", 200)

    assert aresponse.count > bresponse.count
    assert bresponse.count == cresponse.count == 0

    nested_role = {"users": [charlie.username], "role": "python.pythonrepository_viewer"}
    python_bindings.RepositoriesPythonApi.add_role(repo.pulp_href, nested_role)

    cresponse = try_action(charlie, python_bindings.ContentPackagesApi, "list", 200)
    assert cresponse.count > bresponse.count

    body = {"relative_path": PYTHON_EGG_FILENAME, "file": python_file}
    try_action(alice, python_bindings.ContentPackagesApi, "create", 400, **body)
    body["repository"] = repo.pulp_href
    try_action(bob, python_bindings.ContentPackagesApi, "create", 403, **body)
    try_action(charlie, python_bindings.ContentPackagesApi, "create", 403, **body)

    nested_role = {"users": [charlie.username], "role": "python.pythonrepository_owner"}
    python_bindings.RepositoriesPythonApi.add_role(repo.pulp_href, nested_role)
    try_action(charlie, python_bindings.ContentPackagesApi, "create", 202, **body)


@pytest.mark.parallel
def test_repository_apis(
    python_bindings,
    gen_users,
    python_repo_factory,
    python_remote_factory,
    try_action,
):
    """Test repository specific actions, Modify & Sync."""
    alice, bob, charlie = gen_users(["pythonrepository", "pythonremote"])
    # Sync tests
    with bob:
        bob_remote = python_remote_factory()
        repo = python_repo_factory(remote=bob_remote.pulp_href)
    body = {"remote": bob_remote.pulp_href}
    try_action(alice, python_bindings.RepositoriesPythonApi, "sync", 403, repo.pulp_href, body)
    try_action(bob, python_bindings.RepositoriesPythonApi, "sync", 202, repo.pulp_href, body)
    # Try syncing without specifying a remote
    try_action(bob, python_bindings.RepositoriesPythonApi, "sync", 202, repo.pulp_href, {})
    try_action(charlie, python_bindings.RepositoriesPythonApi, "sync", 404, repo.pulp_href, body)
    # Modify tests
    try_action(alice, python_bindings.RepositoriesPythonApi, "modify", 403, repo.pulp_href, {})
    try_action(bob, python_bindings.RepositoriesPythonApi, "modify", 202, repo.pulp_href, {})
    try_action(charlie, python_bindings.RepositoriesPythonApi, "modify", 404, repo.pulp_href, {})


@pytest.mark.parallel
def test_object_creation(
    python_bindings,
    gen_users,
    python_repo_factory,
    monitor_task,
    try_action,
):
    """Test that objects can only be created when having all the required permissions."""
    alice, bob, charlie = gen_users(["pythonrepository", "pythonpublication", "pythondistribution"])
    admin_repo = python_repo_factory()
    with bob:
        repo = python_repo_factory()
    try_action(
        bob,
        python_bindings.PublicationsPypiApi,
        "create",
        403,
        {"repository": admin_repo.pulp_href},
    )
    pub_from_repo_version = try_action(
        bob,
        python_bindings.PublicationsPypiApi,
        "create",
        202,
        {"repository_version": repo.latest_version_href},
    )
    assert pub_from_repo_version.created_resources[0] is not None
    pub = try_action(
        bob, python_bindings.PublicationsPypiApi, "create", 202, {"repository": repo.pulp_href}
    )
    pub = pub.created_resources[0]
    try_action(
        bob,
        python_bindings.DistributionsPypiApi,
        "create",
        403,
        {
            "repository": admin_repo.pulp_href,
            "name": str(uuid.uuid4()),
            "base_path": str(uuid.uuid4()),
        },
    )
    dis = try_action(
        bob,
        python_bindings.DistributionsPypiApi,
        "create",
        202,
        {
            "publication": pub,
            "name": str(uuid.uuid4()),
            "base_path": str(uuid.uuid4()),
        },
    ).created_resources[0]
    admin_body = {
        "repository": admin_repo.pulp_href,
        "publication": None,
        "name": str(uuid.uuid4()),
        "base_path": str(uuid.uuid4()),
    }
    bob_body = {
        "repository": repo.pulp_href,
        "publication": None,
        "name": str(uuid.uuid4()),
        "base_path": str(uuid.uuid4()),
    }
    try_action(bob, python_bindings.DistributionsPypiApi, "partial_update", 403, dis, admin_body)
    try_action(bob, python_bindings.DistributionsPypiApi, "partial_update", 202, dis, bob_body)
    monitor_task(python_bindings.DistributionsPypiApi.delete(dis).task)


@pytest.mark.parallel
def test_pypi_apis(
    python_bindings,
    gen_users,
    python_repo_factory,
    python_distribution_factory,
    anonymous_user,
    download_python_file,
    try_action
):
    alice, bob, charlie = gen_users(["pythonrepository", "pythondistribution"])
    with bob:
        repo = python_repo_factory()
        distro = python_distribution_factory(repository=repo)

    # Check that everyone can read the index & simple pages
    for user in (alice, bob, charlie, anonymous_user):
        for api in (python_bindings.PypiApi, python_bindings.PypiSimpleApi):
            try_action(user, api, "read", 200, path=distro.base_path)

    egg_file = download_python_file(PYTHON_EGG_FILENAME, PYTHON_EGG_URL)
    body = {"content": egg_file, "sha256_digest": PYTHON_EGG_SHA256, "path": distro.base_path}
    # Test uploads only for authorized users (alice & bob)
    try_action(anonymous_user, python_bindings.PypiSimpleApi, "create", 401, **body)
    try_action(charlie, python_bindings.PypiSimpleApi, "create", 403, **body)
    try_action(alice, python_bindings.PypiSimpleApi, "create", 403, **body)
    try_action(bob, python_bindings.PypiSimpleApi, "create", 202, **body)

    # Check that everyone can read the package simple & pypi pages
    body = {"package": "shelf-reader", "path": distro.base_path}
    for user in (alice, bob, charlie, anonymous_user):
        try_action(user, python_bindings.PypiSimpleApi, "pypi_simple_package_read", 200, **body)
    body = {"meta": "shelf-reader/json", "path": distro.base_path}
    for user in (alice, bob, charlie, anonymous_user):
        try_action(user, python_bindings.PypiMetadataApi, "read", 200, **body)
