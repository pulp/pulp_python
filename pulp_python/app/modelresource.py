from pulpcore.plugin.importexport import BaseContentResource
from pulp_python.app.models import (
    PythonPackageContent,
)

class PythonPackageContentResource(BaseContentResource):
    """
    Resource for import/export of python_pythonpackagecontent entities.
    """

    class Meta:
        model = PythonPackageContent
        import_id_fields = model.natural_key_fields()

IMPORT_ORDER = [PythonPackageContentResource]
