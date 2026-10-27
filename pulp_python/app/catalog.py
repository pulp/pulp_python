"""Helpers for the repository package list."""

from collections import defaultdict

from django.db.models import Case, IntegerField, Value, When
from packaging.version import InvalidVersion, Version

from pulp_python.app.models import PythonPackageContent


def _version_sort_key(version):
    """PEP 440 sort key. Use with `reverse=True` for newest first.

    Invalid versions sort after all valid ones when `reverse=True`.
    """
    if not version:
        return (-1, "")
    try:
        return (0, Version(version))
    except InvalidVersion:
        return (-1, str(version))


def python_packages_in_version(repository_version):
    """Python package content contained in `repository_version`."""
    content = PythonPackageContent.objects.all()
    if repository_version is None:
        return content.none()
    return repository_version.get_content(content)


def distinct_package_names_qs(content_qs):
    """One row per distinct `name_normalized`, ordered for stable pagination."""
    return (
        content_qs.values("name_normalized")
        .distinct()
        .order_by(*(content_qs.query.order_by or ("name_normalized",)))
    )


def assemble_package_index(content_qs, name_rows, repository_version):
    """One catalog row per package name, with one content unit per stored version.

    Wheel and sdist of the same `(name_normalized, version)` collapse to one
    row. An sdist is preferred; otherwise the newest `pulp_created` is kept.
    Version strings are the values stored on the content unit, newest first.
    Summary, description, author, author email, and license are taken from the
    newest version because they do not vary by version.
    """
    if not name_rows or repository_version is None:
        return []

    names = [row["name_normalized"] for row in name_rows]
    by_name = defaultdict(list)
    # DISTINCT ON keeps the first row for each name and stored version.
    units = (
        content_qs.filter(name_normalized__in=names)
        .order_by(
            "name_normalized",
            "version",
            Case(
                When(packagetype="sdist", then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            "-pulp_created",
            "pk",
        )
        .distinct("name_normalized", "version")
    )
    for unit in units:
        by_name[unit.name_normalized].append(unit)

    result = []
    for row in name_rows:
        normalized = row["name_normalized"]
        versions = sorted(
            by_name.get(normalized, []),
            key=lambda unit: (_version_sort_key(unit.version), unit.filename),
            reverse=True,
        )
        source = versions[0] if versions else None
        result.append(
            {
                "name": source.name if source else normalized,
                "name_normalized": normalized,
                "summary": source.summary if source else "",
                "description": source.description if source else "",
                "author": source.author if source else "",
                "author_email": source.author_email if source else "",
                "license": source.license if source else "",
                "versions": [
                    {"version": unit.version, "license_expression": unit.license_expression}
                    for unit in versions
                ],
            }
        )
    return result
