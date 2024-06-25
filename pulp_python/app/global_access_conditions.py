from django.conf import settings


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
