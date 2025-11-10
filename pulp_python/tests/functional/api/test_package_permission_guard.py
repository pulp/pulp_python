import pytest
import requests
import uuid

from pulp_python.tests.functional.constants import (
    PYTHON_EGG_FILENAME,
    PYTHON_EGG_SHA256,
)


@pytest.fixture
def package_permission_guard(python_bindings, gen_object_with_cleanup):
    """Fixture to create a PackagePermissionGuard."""
    def _create_guard(name=None, download_policy=None, upload_policy=None):
        body = {"name": name or str(uuid.uuid4())}
        if download_policy is not None:
            body["download_policy"] = download_policy
        if upload_policy is not None:
            body["upload_policy"] = upload_policy
        return gen_object_with_cleanup(
            python_bindings.ContentguardsPackagePermissionApi, body
        )
    return _create_guard


@pytest.mark.parallel
def test_package_permission_guard_add_remove(
    python_bindings,
    gen_user,
    package_permission_guard,
    pulpcore_bindings,
):
    """Test add and remove actions on PackagePermissionGuard."""
    user = gen_user(model_roles=["python.packagepermissionguard_creator"])
    test_user = gen_user()
    test_group = pulpcore_bindings.GroupsApi.create({"name": str(uuid.uuid4())})
    
    with user:
        guard = package_permission_guard()
        
        # Add download permissions
        add_body = {
            "packages": ["shelf-reader", "Django"],
            "users_groups": [user.user.pulp_href, test_user.user.prn, test_group.prn],
            "policy_type": "download"
        }
        python_bindings.ContentguardsPackagePermissionApi.add(guard.pulp_href, add_body)
        
        updated_guard = python_bindings.ContentguardsPackagePermissionApi.read(guard.pulp_href)
        assert "shelf-reader" in updated_guard.download_policy
        assert "django" in updated_guard.download_policy
        assert user.user.prn in updated_guard.download_policy["shelf-reader"]
        assert test_user.user.prn in updated_guard.download_policy["shelf-reader"]
        assert test_group.prn in updated_guard.download_policy["shelf-reader"]
        
        # Remove specific user/group from a package
        remove_body = {
            "packages": ["shelf-reader"],
            "users_groups": [test_user.user.prn],
            "policy_type": "download"
        }
        python_bindings.ContentguardsPackagePermissionApi.remove(guard.pulp_href, remove_body)
        
        updated_guard = python_bindings.ContentguardsPackagePermissionApi.read(guard.pulp_href)
        assert test_user.user.prn not in updated_guard.download_policy["shelf-reader"]
        assert user.user.prn in updated_guard.download_policy["shelf-reader"]
        assert test_group.prn in updated_guard.download_policy["shelf-reader"]
        
        # Remove all entries for a package using '*'
        remove_all_body = {
            "packages": ["django"],
            "users_groups": ["*"],
            "policy_type": "download"
        }
        python_bindings.ContentguardsPackagePermissionApi.remove(guard.pulp_href, remove_all_body)
        
        updated_guard = python_bindings.ContentguardsPackagePermissionApi.read(guard.pulp_href)
        assert "django" not in updated_guard.download_policy
        
        # Test removing all packages using '*' in packages
        remove_all_packages_body = {
            "packages": ["*"],
            "users_groups": [],
            "policy_type": "download"
        }
        python_bindings.ContentguardsPackagePermissionApi.remove(guard.pulp_href, remove_all_packages_body)
        
        updated_guard = python_bindings.ContentguardsPackagePermissionApi.read(guard.pulp_href)
        assert updated_guard.download_policy == {}


@pytest.mark.parallel
def test_package_permission_guard_download(
    python_bindings,
    gen_user,
    package_permission_guard,
    python_repo_factory,
    python_distribution_factory,
    python_publication_factory,
    python_file,
    pulp_content_url,
    monitor_task,
):
    """Test that PackagePermissionGuard controls package downloads."""
    allowed_user = gen_user()
    denied_user = gen_user()
    
    # Setup distribution with content guard
    repo = python_repo_factory()
    body = {"relative_path": PYTHON_EGG_FILENAME, "file": python_file, "repository": repo.pulp_href}
    response = python_bindings.ContentPackagesApi.create(**body)
    monitor_task(response.task)
    pub = python_publication_factory(repository=repo)
    guard = package_permission_guard(
        download_policy={"shelf-reader": [allowed_user.user.prn]}
    )
    distro = python_distribution_factory(
        publication=pub.pulp_href,
        content_guard=guard.pulp_href
    )
    
    # Test that allowed user can download
    download_url = f"{pulp_content_url}{distro.base_path}/{PYTHON_EGG_FILENAME}"
    response = requests.get(download_url, auth=(allowed_user.username, allowed_user.password))
    assert response.status_code == 200
    
    # Test that denied user cannot download
    response = requests.get(download_url, auth=(denied_user.username, denied_user.password))
    assert response.status_code == 403
    
    # Test that anonymous user cannot download
    response = requests.get(download_url)
    assert response.status_code == 403

    # Remove policy and test that anonymous and denied users can download
    remove_all_body = {
        "packages": ["shelf-reader"],
        "users_groups": ["*"],
        "policy_type": "download"
    }
    python_bindings.ContentguardsPackagePermissionApi.remove(guard.pulp_href, remove_all_body)
    response = requests.get(download_url, auth=(denied_user.username, denied_user.password))
    assert response.status_code == 200
    response = requests.get(download_url)
    assert response.status_code == 200


@pytest.mark.parallel
def test_package_permission_guard_upload(
    gen_user,
    package_permission_guard,
    python_repo_factory,
    python_distribution_factory,
    python_file,
):
    """Test that PackagePermissionGuard controls package uploads."""
    allowed_user = gen_user()
    denied_user = gen_user()
    
    # Setup repository and distribution
    repo = python_repo_factory()
    guard = package_permission_guard(
        upload_policy={"shelf-reader": [allowed_user.user.prn]}
    )
    distro = python_distribution_factory(
        repository=repo.pulp_href,
        content_guard=guard.pulp_href
    )

    url = f"{distro.base_url}simple/"
    # Test that denied user cannot upload
    response = requests.post(
        url,
        data={"sha256_digest": PYTHON_EGG_SHA256},
        files={"content": open(python_file, "rb")},
        auth=(denied_user.username, denied_user.password),
    )
    assert response.status_code == 403

    # Test that allowed user can upload
    response = requests.post(
        url,
        data={"sha256_digest": PYTHON_EGG_SHA256},
        files={"content": open(python_file, "rb")},
        auth=(allowed_user.username, allowed_user.password),
    )
    assert response.status_code == 202
