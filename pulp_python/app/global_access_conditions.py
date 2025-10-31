from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from packaging.utils import canonicalize_name
from pathlib import PurePath
from pulp_python.app.models import PackagePermissionGuard
from pypi_simple import parse_filename, UnparsableFilenameError
from pulpcore.plugin.util import get_prn


# Access Condition methods that can be used with PyPI access policies


def index_has_perm(request, view, action, perm="python.view_pythondistribution"):
    """Access Policy condition that checks if the user has the perm on the index(distro)."""
    if request.user.has_perm(perm):
        return True
    if settings.DOMAIN_ENABLED:
        if request.user.has_perm(perm, obj=request.pulp_domain):
            return True
    return request.user.has_perm(perm, obj=view.distribution)


def index_has_repo_perm(request, view, action, perm="python.view_pythonrepository"):
    """
    Access Policy condition that checks if the user has the perm on the index's repository.

    If index doesn't have a repository, then default return True.
    """
    if request.user.has_perm(perm):
        return True
    if settings.DOMAIN_ENABLED:
        if request.user.has_perm(perm, obj=request.pulp_domain):
            return True
    if repo := view.distribution.repository:
        return request.user.has_perm(perm, obj=repo.cast())
    return True


def package_permission_check(request, view, action, policy_type="upload"):
    """
    Access Policy condition that checks PackagePermissionGuard for package-level permissions.
    
    Checks if the user/group has permission for the specific package being accessed.
    
    Args:
        policy_type: "download" or "upload" - which policy to check
    """
    if hasattr(view, "content_guard"):
        content_guard = view.content_guard
    else:
        content_guard = view.distribution.content_guard
    
    # If no guard attached, deny access
    if not content_guard or not isinstance(content_guard.cast(), PackagePermissionGuard):
        return False
    
    guard = content_guard.cast()
    policy = guard.download_policy if policy_type == "download" else guard.upload_policy
    
    # Extract package name from request
    package_name = None
    
    if policy_type == "upload":
        # For uploads, extract from filename in request.FILES
        # The file is uploaded as multipart/form-data with field name 'content'     
        if hasattr(request, 'FILES') and 'content' in request.FILES:
            file_obj = request.FILES['content']
            package_name = canonicalize_name(parse_filename(file_obj.name)[0])
    else:
        # For downloads, extract from URL path
        if hasattr(view, "kwargs"):
            # Check URL kwargs for package name
            if 'package' in view.kwargs:
                package_name = canonicalize_name(view.kwargs['package'])
            elif 'meta' in view.kwargs:
                # Metadata endpoint: pypi/{package}/json/ or pypi/{package}/{version}/json/
                meta_path = PurePath(view.kwargs['meta'])
                if meta_path.match("*/json") or meta_path.match("*/*/json"):
                    package_name = canonicalize_name(meta_path.parts[0])
        else:
            path = PurePath(request.path_info)
            try:
                package_name = parse_filename(path.name)[0]
            except UnparsableFilenameError:
                print(f"No package name found in path: {request.path_info}")
    
    # Downloads are permissive, only deny if package in policy but user is not listed
    # Uploads are strict, only allow if package in policy and user is listed
    if package_name not in policy:
        return policy_type == "download"
    
    allowed_prns = policy[package_name]
    if not request.user or isinstance(request.user, AnonymousUser):
        return False
    user_prn = get_prn(request.user)
    group_prns = [get_prn(group) for group in request.user.groups.all()]
    
    if user_prn and user_prn in allowed_prns:
        return True
    
    if any(group_prn in allowed_prns for group_prn in group_prns):
        return True

    return False
