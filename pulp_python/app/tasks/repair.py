import os
from gettext import gettext as _
import logging

import uuid
from django.conf import settings

from pulpcore.app.models.content import ContentQuerySet
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
        _(f"Repairing metadata for the latest version of repository {repository.name}.")
    )
    content_set = repository.latest_version().content.values_list("pk", flat=True)
    content = PythonPackageContent.objects.filter(pk__in=content_set)
    num_repaired = repair_metadata(content)
    log.info(
        _(
            f"{len(content_set)} packages processed, {num_repaired} package metadata repaired."
        )
    )


def repair_metadata(content: ContentQuerySet) -> int:
    """
    Repairs metadata for a queryset of PythonPackageContent objects.

    Args:
        content (ContentQuerySet): The queryset of PythonPackageContent items to repair.

    Returns:
        int: The number of packages that were repaired.
    """
    # TODO: Add on_demand content repair
    os.chdir(settings.WORKING_DIRECTORY)
    content = content.select_related("pulp_domain")
    immediate_content = content.filter(contentartifact__artifact__isnull=False)

    batch = []
    set_of_update_fields = set()
    total_repaired = 0

    for package in immediate_content.prefetch_related("_artifacts").iterator(
        chunk_size=1000
    ):
        new_data = artifact_to_python_content_data(
            package.filename, package._artifacts.get(), package.pulp_domain
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
