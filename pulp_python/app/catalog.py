"""Helpers for the repository package list."""

from django import VERSION as DJANGO_VERSION
from django.contrib.postgres.aggregates import JSONBAgg
from django.db.models import Case, Func, IntegerField, JSONField, Value, When
from packaging.version import InvalidVersion, Version

from pulp_python.app.models import PythonPackageContent


def _version_sort_key(version):
    """Keep legacy invalid versions browsable, after valid PEP 440 versions."""
    try:
        return (True, Version(version))
    except InvalidVersion:
        return (False, version)


class PackageVersions(JSONBAgg):
    """Map versions to [content ID, license expression], keeping the last file."""

    function = "JSONB_OBJECT_AGG"
    arity = 2


def package_catalog_queryset(content, ordering=("name_normalized",)):
    """Group package names and load their representative versions in the same query.

    Wheel and sdist of the same `(name_normalized, version)` collapse to one
    row. An sdist is preferred; otherwise the newest `pulp_created` is kept.
    """
    # The aggregate keeps the last file for each stored version.
    file_ordering = {
        "order_by" if DJANGO_VERSION >= (5, 2) else "ordering": (
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
                Func(
                    "pk",
                    "license_expression",
                    function="jsonb_build_array",
                    output_field=JSONField(),
                ),
                **file_ordering,
            )
        )
    )


def assemble_package_index(package_rows):
    """Sort the page's versions and bulk-load metadata from their highest versions."""
    if not package_rows:
        return []

    for row in package_rows:
        row["versions"] = sorted(
            (
                {"version": version, "pk": unit[0], "license_expression": unit[1]}
                for version, unit in row["versions"].items()
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
            pk__in=[row["versions"][0]["pk"] for row in package_rows]
        )
        .order_by()
        .values("pk", *fields)
    }
    return [
        {
            **metadata[row["versions"][0]["pk"]],
            "versions": [
                {"version": unit["version"], "license_expression": unit["license_expression"]}
                for unit in row["versions"]
            ],
        }
        for row in package_rows
    ]
