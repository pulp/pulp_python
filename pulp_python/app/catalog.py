"""Helpers for the repository package catalog."""

from django import VERSION as DJANGO_VERSION
from django.contrib.postgres.aggregates import JSONBAgg
from django.db.models import Case, Exists, F, IntegerField, OuterRef, Q, Value, When
from django.utils.dateparse import parse_datetime
from packaging.version import InvalidVersion, Version

from pulp_python.app.models import PackageYank, PythonPackageContent


def package_catalog_content(repository_version):
    """Select unyanked files and their addition times in the repository version."""
    content = PythonPackageContent.objects.all()
    if repository_version is None:
        return content.annotate(repository_added=F("pulp_created")).none()
    yanks = repository_version.get_content(PackageYank.objects.all()).filter(
        name_normalized=OuterRef("name_normalized"), version=OuterRef("version")
    )
    return (
        content.filter(
            Q(version_memberships__version_removed__isnull=True)
            | Q(version_memberships__version_removed__number__gt=repository_version.number),
            version_memberships__repository_id=repository_version.repository_id,
            version_memberships__version_added__number__lte=repository_version.number,
        )
        .annotate(repository_added=F("version_memberships__pulp_created"))
        .filter(~Exists(yanks))
    )


def _version_sort_key(version):
    """Sort invalid version strings after valid PEP 440 versions."""
    try:
        return True, Version(version)
    except InvalidVersion:
        return False, version


class PackageVersions(JSONBAgg):
    """Aggregate values by version, keeping the last value for duplicate keys."""

    function = "JSONB_OBJECT_AGG"
    arity = 2


def package_catalog_queryset(content, ordering=("name_normalized",)):
    """Collect version timestamps and metadata IDs for each normalized package name.

    Wheels and sdists with the same version share an aggregate entry.
    Each timestamp is the latest file addition to the repository. Use sdist metadata when available.
    """
    # Aggregate ordering selects the latest addition time and prefers sdist metadata.
    ordering_argument = "order_by" if DJANGO_VERSION >= (5, 2) else "ordering"
    file_ordering = {
        ordering_argument: (
            "version",
            Case(
                When(packagetype="sdist", then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            "pulp_created",
            "-pk",
        )
    }
    return (
        content.order_by(*ordering)
        .values("name_normalized")
        .annotate(
            versions=PackageVersions(
                "version",
                "repository_added",
                **{ordering_argument: ("repository_added",)},
            ),
            metadata_ids=PackageVersions(
                "version",
                "pk",
                **file_ordering,
            ),
        )
    )


def assemble_package_index(package_rows):
    """Sort each package's versions and fetch metadata for its highest version in one query."""
    if not package_rows:
        return []

    for row in package_rows:
        row["versions"] = sorted(
            (
                {"version": version, "last_updated": parse_datetime(updated)}
                for version, updated in row["versions"].items()
            ),
            key=lambda unit: (_version_sort_key(unit["version"]), unit["version"]),
            reverse=True,
        )

    fields = (
        "name",
        "name_normalized",
        "summary",
        "description",
        "author",
        "author_email",
        "license",
    )
    metadata = {
        str(unit["pk"]): {field: unit[field] for field in fields}
        for unit in PythonPackageContent.objects.filter(
            pk__in=[row["metadata_ids"][row["versions"][0]["version"]] for row in package_rows]
        )
        .order_by()
        .values("pk", *fields)
    }
    return [
        {
            **metadata[row["metadata_ids"][row["versions"][0]["version"]]],
            "versions": row["versions"],
        }
        for row in package_rows
    ]
