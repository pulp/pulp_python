from pulpcore.plugin.importexport import BaseContentResource
from pulpcore.plugin.modelresources import RepositoryResource
from pulpcore.plugin.util import get_domain
from pulp_python.app.models import (
    PythonPackageContent,
    PythonRepository,
)


class PythonPackageContentResource(BaseContentResource):
    """
    Resource for import/export of python_pythonpackagecontent entities.
    """

    def set_up_queryset(self):
        """
        :return: PythonPackageContent specific to a specified repo-version.
        """
        return PythonPackageContent.objects.filter(
            pk__in=self.repo_version.content, _pulp_domain=get_domain()
        )

    class Meta:
        model = PythonPackageContent
        import_id_fields = model.natural_key_fields()


class PythonRepositoryResource(RepositoryResource):
    """
    A resource for importing/exporting python repository entities
    """

    def set_up_queryset(self):
        """
        :return: A queryset containing one repository that will be exported.
        """
        return PythonRepository.objects.filter(pk=self.repo_version.repository)

    class Meta:
        model = PythonRepository


IMPORT_ORDER = [PythonPackageContentResource, PythonRepositoryResource]
