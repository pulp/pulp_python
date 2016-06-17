import itertools

from pulp.server.controllers import repository as repo_controller
from pulp.server.db.querysets import QuerySetPreventCache


class PythonPackageQuerySet(QuerySetPreventCache):
    """
    Custom querysets for Python packages.
    """

    def packages_in_repo(self, repo_id):
        """
        Query for all Python packages in a repository.

        :param repo_id: Identifies the repository from which to retrieve packages
        :type  repo_id: basestring
        :return: QuerySet containing each package in the repo
        :rtype:  mongoengine.queryset.QuerySet
        """
        unit_qs = repo_controller.get_unit_model_querysets(repo_id, self._document)
        return itertools.chain(*unit_qs)

    def packages_by_project(self, repo_id):
        """
        Query for all Python packages, organized by project.

        :param repo_id: Identifies the repository from which to retrieve packages
        :type  repo_id: basestring
        :return: Dictionary containing packages in the repo, organized by project name
        :rtype:  dict
        """
        packages = self.packages_in_repo(repo_id)
        projects = {}

        for pkg in packages:
            projects.setdefault(pkg.name, []).append(pkg)

        return projects
