import logging
from gettext import gettext as _
from uuid import UUID

from django.db.models.query import QuerySet
from pulp_python.app.models import PythonPackageContent, PythonRepository
from pulp_python.app.utils import artifact_to_python_content_data
from pulpcore.plugin.models import ProgressReport
from pulpcore.plugin.util import get_domain

log = logging.getLogger(__name__)


BULK_SIZE = 1000


def repair(repository_pk: UUID) -> None:
    """
    Repairs metadata of all packages for the specified repository.

    Args:
        repository_pk (UUID): The primary key of the repository to repair.

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
    immediate_content = (
        content.filter(contentartifact__artifact__isnull=False)
        .distinct()
        .prefetch_related("_artifacts")
    )
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
            immediate_content.iterator(chunk_size=BULK_SIZE)
        ):
            new_data = artifact_to_python_content_data(
                package.filename, package._artifacts.get(), domain
            )
            total_repaired += update_package_if_needed(
                package, new_data, batch, set_of_update_fields
            )

    if batch:
        total_repaired += len(batch)
        PythonPackageContent.objects.bulk_update(batch, set_of_update_fields)

    return total_repaired


def update_package_if_needed(
    package: PythonPackageContent,
    new_data: dict,
    batch: list[PythonPackageContent],
    set_of_update_fields: set[str],
) -> int:
    """
    Compares the current package data with new data and updates the package
    if needed ("batch" and "set_of_update_fields" are updated in-place).

    Args:
        package: Package to check and update.
        new_data: A dict of new field values to compare against the package.
        batch: A list of packages that were updated.
        set_of_update_fields: A set of package field names that were updated.

    Returns:
        The count of repaired packages (increments in multiples of BULK_SIZE only).
    """
    total_repaired = 0
    changed = False
    for field, value in new_data.items():
        if getattr(package, field) != value:
            setattr(package, field, value)
            set_of_update_fields.add(field)
            changed = True
    if changed:
        batch.append(package)

    if len(batch) == BULK_SIZE:
        PythonPackageContent.objects.bulk_update(batch, set_of_update_fields)
        total_repaired += BULK_SIZE
        batch.clear()
        set_of_update_fields.clear()

    return total_repaired
