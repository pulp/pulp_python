import logging
import uuid
from gettext import gettext as _

from django.db.models.query import QuerySet
from pulpcore.plugin.models import ProgressReport
from pulpcore.plugin.util import get_domain

from pulp_python.app.models import PythonPackageContent, PythonRepository
from pulp_python.app.utils import (
    artifact_to_python_content_data,
    fetch_json_release_metadata,
    parse_metadata,
)

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
    immediate_content = (
        content.filter(contentartifact__artifact__isnull=False)
        .distinct()
        .prefetch_related("_artifacts")
    )
    on_demand_content = (
        content.filter(contentartifact__artifact__isnull=True)
        .distinct()
        .prefetch_related("contentartifact_set__remoteartifact_set")
    )
    domain = get_domain()

    batch = []
    set_of_update_fields = set()
    total_repaired = 0

    progress_report = ProgressReport(
        message="Repairing packages' metadata",
        code="repair.metadata",
        total=content.count(),
    )
    progress_report.save()
    with progress_report:
        for package in progress_report.iter(
            immediate_content.iterator(chunk_size=1000)
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

        for package in progress_report.iter(
            on_demand_content.iterator(chunk_size=1000)
        ):
            remote_artifacts = (
                package.contentartifact_set.get().remoteartifact_set.all()
            )
            # We expect that PythonPackageContent always has correct name and version,
            # and RemoteArtifact always has correct sha256
            json_data = fetch_json_release_metadata(
                package.name, package.version, remote_artifacts.get().remote
            )
            dist_data = next(
                (
                    dist
                    for ra in remote_artifacts
                    for dist in json_data["urls"]
                    if ra.sha256 == dist["digests"]["sha256"]
                ),
                None,
            )
            if not dist_data:
                log.warning(
                    _("No matching distribution for {} was found.").format(package.name)
                )
                continue

            new_data = parse_metadata(json_data["info"], package.version, dist_data)
            new_data.pop("url")  # belongs to RemoteArtifact, not PythonPackageContent
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
