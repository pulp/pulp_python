"""Helpers for repository package catalog, metrics, and rebuild collapse."""

from collections import defaultdict

from django.db.models import CharField, Func, Max, Min, Q, Value
from packaging.version import InvalidVersion, Version

from pulp_python.app.models import PythonPackageContent
from pulp_python.app.utils import BUILD_SUFFIX_PG_REGEX


def base_version_annotation(field_name="version"):
    """SQL expression that strips a trailing rebuild suffix from ``version``.

    PostgreSQL POSIX regex does not treat ``\\d`` as digits, so the SQL pattern
    uses ``[0-9]`` while the Python pattern in ``strip_build_suffix`` uses ``\\d``.
    Implemented with ``REGEXP_REPLACE`` so it does not depend on Django's
    ``RegexpReplace`` (not present in every Django 4.2/5.2 packaging Pulp uses).
    """
    return Func(
        field_name,
        Value(BUILD_SUFFIX_PG_REGEX),
        Value(""),
        function="REGEXP_REPLACE",
        output_field=CharField(),
    )


def collapse_python_builds(queryset):
    """Keep one content unit per ``(name_normalized, base_version)``.

    ``base_version`` is ``version`` with a trailing rebuild suffix stripped.
    The unit with the latest ``pulp_created`` is kept. Callers that want one
    row per logical version (not per wheel/sdist) should also filter
    ``packagetype``.
    """
    return (
        queryset.prefetch_related(None)
        .annotate(_collapse_base_version=base_version_annotation())
        .order_by("name_normalized", "_collapse_base_version", "-pulp_created")
        .distinct("name_normalized", "_collapse_base_version")
    )


def python_packages_in_version(repository_version):
    """Python package content contained in ``repository_version``."""
    if repository_version is None:
        return PythonPackageContent.objects.none()
    return PythonPackageContent.objects.filter(pk__in=repository_version.content)


def apply_package_prefix_filters(queryset, name_normalized_prefix=None, name_prefix=None):
    """Apply case-insensitive prefix filters used by the package index."""
    if name_normalized_prefix:
        queryset = queryset.filter(name_normalized__istartswith=name_normalized_prefix)
    if name_prefix:
        queryset = queryset.filter(name__istartswith=name_prefix)
    return queryset


def distinct_package_names_qs(content_qs):
    """One row per distinct ``name_normalized``, ordered for stable pagination."""
    return (
        content_qs.order_by()
        .values("name_normalized")
        .annotate(name=Max("name"))
        .order_by("name_normalized")
    )


def _version_sort_key(version):
    try:
        return (0, Version(version))
    except InvalidVersion:
        return (1, version)


def assemble_package_index(content_qs, name_rows, repository):
    """Build package-index dicts for ``name_rows``.

    ``created_at`` is the earliest repository-membership time
    (``RepositoryContent.pulp_created``) of any file of that logical version
    in ``repository``, falling back to the content unit's ``pulp_created``.
    """
    if not name_rows:
        return []

    names = [row["name_normalized"] for row in name_rows]
    name_by_normalized = {row["name_normalized"]: row["name"] for row in name_rows}

    release_rows = (
        content_qs.filter(name_normalized__in=names)
        .annotate(_base_version=base_version_annotation())
        .values("name_normalized", "_base_version")
        .annotate(
            membership_created=Min(
                "version_memberships__pulp_created",
                filter=Q(
                    version_memberships__repository=repository,
                    version_memberships__version_removed__isnull=True,
                ),
            ),
            unit_created=Min("pulp_created"),
        )
    )

    releases_by_name = defaultdict(list)
    for rel in release_rows:
        releases_by_name[rel["name_normalized"]].append(rel)

    result = []
    for row in name_rows:
        normalized = row["name_normalized"]
        rels = sorted(
            releases_by_name.get(normalized, []),
            key=lambda item: _version_sort_key(item["_base_version"]),
        )
        versions = [item["_base_version"] for item in rels]
        latest_releases = [
            {
                "version": item["_base_version"],
                "release": "",
                "created_at": item["membership_created"] or item["unit_created"],
            }
            for item in rels
        ]
        result.append(
            {
                "name": name_by_normalized[normalized],
                "name_normalized": normalized,
                "versions": versions,
                "latest_releases": latest_releases,
            }
        )
    return result


def repository_metrics(content_qs):
    """Distinct package / logical-version / build counts for package content.

    Identity is always ``PythonPackageContent`` (not filtered by packagetype):

    * ``package_count``: distinct ``name_normalized``
    * ``version_count``: distinct ``(name_normalized, base_version)``
    * ``build_count``: distinct ``(name_normalized, version)``

    Until rebuild suffixes exist, ``version_count`` equals ``build_count``.
    """
    content_qs = content_qs.order_by()
    return {
        "package_count": content_qs.values("name_normalized").distinct().count(),
        "version_count": (
            content_qs.annotate(_base_version=base_version_annotation())
            .values("name_normalized", "_base_version")
            .distinct()
            .count()
        ),
        "build_count": content_qs.values("name_normalized", "version").distinct().count(),
    }
