import logging
import uuid
from gettext import gettext as _

from django.db.models.query import QuerySet
from pulpcore.plugin.models import ProgressReport
from pulpcore.plugin.util import get_domain

from pulp_python.app.models import PythonPackageContent, PythonRepository
from pulp_python.app.utils import artifact_to_python_content_data

log = logging.getLogger(__name__)


def repair(repository_pk: uuid.UUID) -> None:
    """
    Repairs metadata of all packages for the specified repository.

    Args:
        repository_pk (uuid.UUID): The primary key of the repository to repair.

    Returns:
        None
    """
    repository = PythonRepository.objects.get(pk=repository_pk)

    log.info(
        _(
            "Repairing packages' metadata for the latest version of repository {}."
        ).format(repository.name)
    )
    content_set = repository.latest_version().content.values_list("pk", flat=True)
    content = PythonPackageContent.objects.filter(pk__in=content_set)

    num_repaired = repair_metadata(content)
    log.info(_("{} packages' metadata repaired.").format(num_repaired))


def repair_metadata(content: QuerySet[PythonPackageContent]) -> int:
    """
    Repairs metadata for a queryset of PythonPackageContent objects
    and updates the progress report.

    Args:
        content (QuerySet[PythonPackageContent]): The queryset of items to repair.

    Returns:
        int: The number of packages that were repaired.
    """
    # TODO: Add on_demand content repair
    immediate_content = content.filter(contentartifact__artifact__isnull=False)
    domain = get_domain()

    batch = []
    set_of_update_fields = set()
    total_repaired = 0

    progress_report = ProgressReport(
        message="Repairing packages' metadata",
        code="repair.metadata",
        total=immediate_content.count(),
    )
    progress_report.save()
    with progress_report:
        for package in progress_report.iter(
            immediate_content.prefetch_related("_artifacts").iterator(chunk_size=1000)
        ):
            new_data = artifact_to_python_content_data(
                package.filename, package._artifacts.get(), domain
            )
            changed = False
            for field, value in new_data.items():
                if getattr(package, field) != value:
                    setattr(package, field, value)
                    set_of_update_fields.add(field)
                    changed = True
            if changed:
                batch.append(package)
            if len(batch) == 1000:
                total_repaired += len(batch)
                PythonPackageContent.objects.bulk_update(batch, set_of_update_fields)
                batch = []
                set_of_update_fields.clear()

    if batch:
        total_repaired += len(batch)
        PythonPackageContent.objects.bulk_update(batch, set_of_update_fields)

    return total_repaired
