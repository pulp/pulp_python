import logging
from collections import defaultdict
from gettext import gettext as _
from itertools import groupby
from uuid import UUID

from django.db.models import Prefetch
from django.db.models.query import QuerySet
from pulp_python.app.models import PythonPackageContent, PythonRepository
from pulp_python.app.utils import (
    artifact_to_metadata_artifact,
    artifact_to_python_content_data,
    fetch_json_release_metadata,
    parse_metadata,
)
from pulpcore.plugin.models import Artifact, ContentArtifact, ProgressReport
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
        _("Repairing packages' metadata for the latest version of repository {}.").format(
            repository.name
        )
    )
    content_set = repository.latest_version().content.values_list("pk", flat=True)
    content = PythonPackageContent.objects.filter(pk__in=content_set)

    num_repaired, pkgs_not_repaired, num_metadata_repaired, pkgs_metadata_not_repaired = (
        repair_metadata(content)
    )
    # Convert set() to 0
    if not pkgs_not_repaired:
        pkgs_not_repaired = 0
    if not pkgs_metadata_not_repaired:
        pkgs_metadata_not_repaired = 0

    log.info(
        _(
            "{} packages' metadata repaired. Not repaired packages due to either "
            "inaccessible URL or mismatched sha256: {}. "
            "{} metadata files repaired. Packages whose metadata files could not be repaired: {}."
        ).format(num_repaired, pkgs_not_repaired, num_metadata_repaired, pkgs_metadata_not_repaired)
    )


def repair_metadata(content: QuerySet[PythonPackageContent]) -> tuple[int, set[str], int, set[str]]:
    """
    Repairs metadata for a queryset of PythonPackageContent objects
    and updates the progress report.

    Args:
        content (QuerySet[PythonPackageContent]): The queryset of items to repair.

    Returns:
        tuple[int, set[str], int, set[str]]: A tuple containing:
            - The number of packages that were repaired.
            - A set of packages' PKs that were not repaired.
            - The number of metadata files that were repaired.
            - A set of packages' PKs without repaired metadata artifacts.
    """
    immediate_content = (
        content.filter(contentartifact__artifact__isnull=False)
        .distinct()
        .prefetch_related("_artifacts")
    )
    on_demand_content = (
        content.filter(contentartifact__artifact__isnull=True)
        .distinct()
        .prefetch_related(
            Prefetch(
                "contentartifact_set",
                queryset=ContentArtifact.objects.prefetch_related("remoteartifact_set"),
            )
        )
        .order_by("name", "version")
    )
    domain = get_domain()

    batch = []
    set_of_update_fields = set()
    total_repaired = 0
    # Keep track of on-demand packages that were not repaired
    pkgs_not_repaired = set()

    # Metadata artifacts and content artifacts
    metadata_batch = []
    total_metadata_repaired = 0
    pkgs_metadata_not_repaired = set()

    progress_report = ProgressReport(
        message="Repairing packages' metadata",
        code="repair.metadata",
        total=content.count(),
    )
    progress_report.save()
    with progress_report:
        for package in progress_report.iter(immediate_content.iterator(chunk_size=BULK_SIZE)):
            # Get the main artifact
            main_artifact = (
                package.contentartifact_set.exclude(relative_path__endswith=".metadata")
                .first()
                .artifact
            )
            new_data = artifact_to_python_content_data(package.filename, main_artifact, domain)
            total_metadata_repaired += update_metadata_artifact_if_needed(
                package,
                new_data.get("metadata_sha256"),
                main_artifact,
                metadata_batch,
                pkgs_metadata_not_repaired,
            )
            total_repaired += update_package_if_needed(
                package, new_data, batch, set_of_update_fields
            )

        # For on-demand content, we expect that:
        # 1. PythonPackageContent always has correct name and version
        # 2. RemoteArtifact always has correct sha256
        for (name, version), group in groupby(
            on_demand_content.iterator(chunk_size=BULK_SIZE),
            key=lambda x: (x.name, x.version),
        ):
            group_set = set(group)
            grouped_by_url = defaultdict(list)

            for package in group_set:
                for ra in (
                    package.contentartifact_set.exclude(relative_path__endswith=".metadata")
                    .first()
                    .remoteartifact_set.all()
                ):
                    grouped_by_url[ra.remote.url].append((package, ra))

            # Prioritize the URL that can serve the most packages
            for url, pkg_ra_pairs in sorted(
                grouped_by_url.items(), key=lambda x: len(x[1]), reverse=True
            ):
                if not group_set:
                    break  # No packages left to repair, move onto the next group
                remotes = set([pkg_ra[1].remote for pkg_ra in pkg_ra_pairs])
                try:
                    json_data = fetch_json_release_metadata(name, version, remotes)
                except Exception:
                    continue

                for package, ra in pkg_ra_pairs:
                    if package not in group_set:
                        continue  # Package was already repaired
                    # Extract data only for the specific distribution being checked
                    dist_data = None
                    for dist in json_data["urls"]:
                        if ra.sha256 == dist["digests"]["sha256"]:
                            dist_data = dist
                            break
                    if not dist_data:
                        continue

                    new_data = parse_metadata(json_data["info"], version, dist_data)
                    new_data.pop("url")  # url belongs to RemoteArtifact
                    total_repaired += update_package_if_needed(
                        package, new_data, batch, set_of_update_fields
                    )
                    group_set.remove(package)
                    progress_report.increment()
            # Store and track the unrepaired packages after all URLs are processed
            pkgs_not_repaired.update([p.pk for p in group_set])
            progress_report.increase_by(len(group_set))

    if batch:
        total_repaired += len(batch)
        PythonPackageContent.objects.bulk_update(batch, set_of_update_fields)

    if metadata_batch:
        not_repaired = _process_metadata_batch(metadata_batch)
        pkgs_metadata_not_repaired.update(not_repaired)
        total_metadata_repaired += len(metadata_batch) - len(not_repaired)

    return total_repaired, pkgs_not_repaired, total_metadata_repaired, pkgs_metadata_not_repaired


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


def update_metadata_artifact_if_needed(
    package: PythonPackageContent,
    new_metadata_sha256: str | None,
    main_artifact: Artifact,
    metadata_batch: list[tuple],
    pkgs_metadata_not_repaired: set[str],
) -> int:
    """
    Repairs metadata artifacts for wheel packages by creating missing metadata artifacts
    or updating existing ones when the metadata_sha256 differs. Only processes wheel files
    that have a valid new_metadata_sha256. Queues operations for batch processing.

    Args:
        package: Package to check for metadata changes.
        new_metadata_sha256: The correct metadata_sha256 extracted from the main artifact, or None.
        main_artifact: The main package artifact used to generate metadata.
        metadata_batch: List of tuples for batch processing (updated in-place).
        pkgs_metadata_not_repaired: Set of package PKs that failed repair (updated in-place).

    Returns:
        Number of repaired metadata artifacts (only when batch is flushed at BULK_SIZE).
    """
    total_metadata_repaired = 0

    if not package.filename.endswith(".whl") or not new_metadata_sha256:
        return total_metadata_repaired

    original_metadata_sha256 = package.metadata_sha256
    cas = package.contentartifact_set.filter(relative_path__endswith=".metadata")

    # Create missing
    if not cas:
        metadata_batch.append((package, main_artifact))
    # Fix existing
    elif new_metadata_sha256 != original_metadata_sha256:
        ca = cas.first()
        metadata_artifact = ca.artifact
        if metadata_artifact is None or (metadata_artifact.sha256 != new_metadata_sha256):
            metadata_batch.append((package, main_artifact))

    if len(metadata_batch) == BULK_SIZE:
        not_repaired = _process_metadata_batch(metadata_batch)
        pkgs_metadata_not_repaired.update(not_repaired)
        total_metadata_repaired += BULK_SIZE - len(not_repaired)
        metadata_batch.clear()

    return total_metadata_repaired


def _process_metadata_batch(metadata_batch: list[tuple]) -> set[str]:
    """
    Processes a batch of metadata repair operations by creating metadata artifacts
    and their corresponding ContentArtifacts.

    Args:
        metadata_batch: List of (package, main_artifact) tuples.

    Returns:
        Set of package PKs for which metadata artifacts could not be created.
    """
    not_repaired = set()
    content_artifacts = []

    for package, main_artifact in metadata_batch:
        metadata_artifact = artifact_to_metadata_artifact(package.filename, main_artifact)
        if metadata_artifact:
            ca = ContentArtifact(
                artifact=metadata_artifact,
                content=package,
                relative_path=f"{package.filename}.metadata",
            )
            content_artifacts.append(ca)
        else:
            not_repaired.add(package.pk)

    if content_artifacts:
        ContentArtifact.objects.bulk_create(
            content_artifacts,
            update_conflicts=True,
            update_fields=["artifact"],
            unique_fields=["content", "relative_path"],
        )

    return not_repaired
