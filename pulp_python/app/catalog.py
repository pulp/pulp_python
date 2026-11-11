"""Helpers for the repository package catalog."""

from django import VERSION as DJANGO_VERSION
from django.contrib.postgres.aggregates import JSONBAgg
from django.db.models import Case, IntegerField, Value, When
from packaging.version import InvalidVersion, Version

from pulp_python.app.models import PythonPackageContent


def _version_sort_key(version):
    """Sort invalid version strings after valid PEP 440 versions."""
    try:
        return (True, Version(version))
    except InvalidVersion:
        return (False, version)


class PackageVersions(JSONBAgg):
    """Aggregate values by version, keeping the last value for duplicate keys."""

    function = "JSONB_OBJECT_AGG"
    arity = 2


def package_catalog_queryset(content, ordering=("name_normalized",)):
    """Collect version timestamps and metadata IDs for each normalized package name.

    Wheels and sdists with the same version share an aggregate entry.
    Each timestamp is the newest file's `pulp_created`. Use sdist metadata when available.
    """
    # Aggregate ordering selects the newest timestamp and prefers sdist metadata.
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
                "pulp_created",
                **{ordering_argument: ("pulp_created",)},
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
                {"version": version, "last_updated": updated}
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
