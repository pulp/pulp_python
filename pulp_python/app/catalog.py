"""Helpers for repository package catalog, metrics, and rebuild collapse."""

from collections import defaultdict
from urllib.parse import urlparse

from django.core.exceptions import FieldError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import CharField, FilteredRelation, Func, Max, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.urls import Resolver404, resolve

from pulpcore.plugin.models import Repository, RepositoryContent, RepositoryVersion
from pulpcore.plugin.util import resolve_prn

from pulp_python.app.models import PythonPackageContent
from pulp_python.app.versions import (
    BUILD_SUFFIX_PATTERN,
    DEFAULT_PACKAGE_INDEX_ORDERING,
    rebuild_release,
    version_sort_key,
)


def base_version_annotation(field_name="version"):
    """SQL expression that strips a PEP 440 local version from ``version``.

    Uses ``versions.BUILD_SUFFIX_PATTERN`` (POSIX) so Python ``strip_build_suffix``
    and this ``REGEXP_REPLACE`` stay aligned. Implemented with ``REGEXP_REPLACE``
    so it does not depend on Django's ``RegexpReplace`` (not present in every
    Django 4.2/5.2 packaging Pulp uses).
    """
    return Func(
        field_name,
        Value(BUILD_SUFFIX_PATTERN),
        Value(""),
        function="REGEXP_REPLACE",
        output_field=CharField(),
    )


def collapse_python_builds(queryset):
    """Keep one content unit per ``(name_normalized, base_version)``.

    ``base_version`` is ``version`` with a PEP 440 local version stripped.
    The unit with the latest ``pulp_created`` is kept. Callers that want one
    row per logical version (not per wheel/sdist) should also filter
    ``packagetype``.
    """
    # DISTINCT ON cannot reuse pulpcore's list prefetches (cloned lookups /
    # JOINs). Drop them, collapse, then prefetch artifacts for the reduced set.
    return (
        queryset.prefetch_related(None)
        .annotate(_collapse_base_version=base_version_annotation())
        .order_by("name_normalized", "_collapse_base_version", "-pulp_created")
        .distinct("name_normalized", "_collapse_base_version")
        .prefetch_related("contentartifact_set")
    )


def _in_version_bounds_q(repository_version, prefix=""):
    """Version-added/removed bounds for rows present in ``repository_version``.

    ``prefix`` is empty for ``RepositoryContent`` and ``in_repo__`` for the
    filtered membership join. Both catalog paths use this helper.
    """
    return Q(**{f"{prefix}version_added__number__lte": repository_version.number}) & (
        Q(**{f"{prefix}version_removed__isnull": True})
        | Q(**{f"{prefix}version_removed__number__gt": repository_version.number})
    )


def memberships_in_version(repository_version):
    """RepositoryContent rows contained in ``repository_version``.

    A subquery against this queryset keeps the content-id list in the database.
    ``RepositoryVersion.content`` inlines ``content_ids`` as one bound UUID per
    content unit whenever that array is shorter than 65535.
    """
    return RepositoryContent.objects.filter(
        repository_id=repository_version.repository_id,
    ).filter(_in_version_bounds_q(repository_version))


def python_packages_in_version(repository_version):
    """Python package content contained in ``repository_version``."""
    if repository_version is None:
        return PythonPackageContent.objects.none()
    content_ids = (
        memberships_in_version(repository_version)
        .filter(content__pulp_type=PythonPackageContent.get_pulp_type())
        .order_by()
        .values("content_id")
    )
    return PythonPackageContent.objects.filter(pk__in=content_ids)


def resolve_repository_version(href):
    """Load a repository version without selecting ``content_ids``.

    Accepts a repository-version or repository HREF/PRN. Domain-prefixed hrefs
    include ``pulp_domain`` in the resolved kwargs; that field lives on the
    repository, not ``RepositoryVersion``.
    """
    if not href:
        raise ValueError("No value supplied for repository version.")

    if href.startswith("prn:"):
        model, pk = resolve_prn(href)
        found_kwargs = {"pk": pk}
    else:
        try:
            match = resolve(urlparse(href).path)
        except Resolver404:
            raise ValueError(f"URI not valid: {href}") from None
        model = match.func.cls.queryset.model
        found_kwargs = match.kwargs

    if "pk" in found_kwargs:
        lookup = {"pk": found_kwargs["pk"]}
    else:
        lookup = {}
        for key, value in found_kwargs.items():
            if key.endswith("_pk"):
                lookup[f"{key[:-3]}__pk"] = value
            elif key == "pulp_domain":
                if hasattr(model, "pulp_domain"):
                    lookup["pulp_domain__name"] = value
            elif key in ("api_root", "version"):
                continue
            else:
                lookup[key] = value

    qs = model.objects.all()
    if issubclass(model, RepositoryVersion):
        qs = qs.defer("content_ids")
    try:
        obj = qs.get(**lookup)
    except model.DoesNotExist:
        raise ValueError(f"URI {href} not found.") from None
    except (model.MultipleObjectsReturned, DjangoValidationError, FieldError):
        raise ValueError(f"URI {href} is not a valid repository version.") from None

    if isinstance(obj, RepositoryVersion):
        return obj
    if isinstance(obj, Repository):
        try:
            return obj.versions.complete().defer("content_ids").latest()
        except RepositoryVersion.DoesNotExist:
            return None
    raise ValueError("Must be a repository version.")


def _membership_time(repository_version, newest=True):
    """Scalar membership time for one content row in this version.

    Valid on an ungrouped queryset (``created_at``). Do not place this inside
    ``Max()``: Postgres rejects a correlated subquery that references a column
    absent from ``GROUP BY``.
    """
    direction = "-pulp_created" if newest else "pulp_created"
    return Subquery(
        memberships_in_version(repository_version)
        .filter(content_id=OuterRef("pk"))
        .order_by(direction)
        .values("pulp_created")[:1]
    )


def annotate_grouped_last_updated(queryset, repository_version, include_name=False):
    """One ``last_updated`` per ``name_normalized``.

    The join is limited to this repository. Version bounds match
    ``memberships_in_version``. Falls back to the content unit's ``pulp_created``.
    """
    extra = {"name": Max("name")} if include_name else {}
    if repository_version is None:
        return queryset.values("name_normalized").annotate(
            last_updated=Max("pulp_created"), **extra
        )
    return (
        queryset.annotate(
            in_repo=FilteredRelation(
                "version_memberships",
                condition=Q(version_memberships__repository_id=repository_version.repository_id),
            )
        )
        .values("name_normalized")
        .annotate(
            last_updated=Coalesce(
                Max(
                    "in_repo__pulp_created",
                    filter=_in_version_bounds_q(repository_version, prefix="in_repo__"),
                ),
                Max("pulp_created"),
            ),
            **extra,
        )
    )


def _orders_by_field(ordering, field):
    return any(term.lstrip("-") == field for term in ordering)


def distinct_package_names_qs(content_qs, repository_version, ordering=None):
    """One row per distinct ``name_normalized``, ordered for stable pagination.

    ``last_updated`` is aggregated here only when it is a sort key. The default
    ``name_normalized`` order would otherwise compute that aggregate for every
    package before ``LIMIT``/``OFFSET`` can apply. The page assembler fills
    ``last_updated`` for the returned rows.
    """
    if ordering is None:
        ordering = DEFAULT_PACKAGE_INDEX_ORDERING
    qs = content_qs.order_by()
    if _orders_by_field(ordering, "last_updated"):
        qs = annotate_grouped_last_updated(
            qs, repository_version, include_name=_orders_by_field(ordering, "name")
        )
    elif _orders_by_field(ordering, "name"):
        # One row per package. ``ORDER BY name DESC`` picks the same
        # representative as ``Max(name)`` without a grouped aggregate on the
        # whole repository before LIMIT. Wrap as a subquery so the page can
        # ``ORDER BY name`` with ``LIMIT`` while membership stays in SQL.
        representatives = (
            qs.order_by("name_normalized", "-name").distinct("name_normalized").values("pk")
        )
        qs = qs.filter(pk__in=Subquery(representatives)).values("name", "name_normalized")
    else:
        qs = qs.values("name_normalized").distinct()
    return qs.order_by(*ordering)


def _last_updated_by_name(content_qs, name_rows, repository_version):
    """Newest membership time for each package name on this page."""
    names = [row["name_normalized"] for row in name_rows]
    scoped = content_qs
    if len(name_rows) <= 200:
        scoped = content_qs.filter(name_normalized__in=names)
    annotated = annotate_grouped_last_updated(scoped.order_by(), repository_version)
    return {row["name_normalized"]: row["last_updated"] for row in annotated}


def _names_by_normalized(content_qs, name_rows):
    """Representative ``name`` for each ``name_normalized`` on this page."""
    if "name" in name_rows[0]:
        return {row["name_normalized"]: row["name"] for row in name_rows}
    names = [row["name_normalized"] for row in name_rows]
    return dict(
        content_qs.filter(name_normalized__in=names)
        .order_by()
        .values("name_normalized")
        .annotate(name=Max("name"))
        .values_list("name_normalized", "name")
    )


def assemble_package_index(content_qs, name_rows, repository_version):
    """Build package-index dicts for ``name_rows``.

    ``versions`` are distinct logical versions, newest first (PEP 440).
    ``latest_releases`` keeps the newest rebuild (latest ``pulp_created``)
    per base version in the same order. ``created_at`` is that unit's
    repository-membership time (``RepositoryContent.pulp_created``), falling
    back to the content unit's ``pulp_created``. ``last_updated`` is the newest
    membership among all units for the package (any rebuild), taken from
    ``name_rows`` when the page query already annotated it.
    """
    if not name_rows or repository_version is None:
        return []

    names = [row["name_normalized"] for row in name_rows]
    name_by_normalized = _names_by_normalized(content_qs, name_rows)
    if "last_updated" in name_rows[0]:
        last_updated_by_name = None
    else:
        last_updated_by_name = _last_updated_by_name(content_qs, name_rows, repository_version)

    # values() keeps description/classifiers JSON off this DISTINCT ON sort.
    newest = list(
        content_qs.filter(name_normalized__in=names)
        .annotate(_base_version=base_version_annotation())
        .order_by("name_normalized", "_base_version", "-pulp_created")
        .distinct("name_normalized", "_base_version")
        .values("pk", "name_normalized", "version", "_base_version", "pulp_created")
    )

    memberships = {}
    if newest:
        memberships = dict(
            PythonPackageContent.objects.filter(pk__in=[row["pk"] for row in newest])
            .annotate(membership_created=_membership_time(repository_version, newest=False))
            .values_list("pk", "membership_created")
        )

    releases_by_name = defaultdict(list)
    for rel in newest:
        releases_by_name[rel["name_normalized"]].append(rel)

    result = []
    for row in name_rows:
        normalized = row["name_normalized"]
        rels = sorted(
            releases_by_name.get(normalized, []),
            key=lambda item: version_sort_key(item["_base_version"]),
            reverse=True,
        )
        versions = [item["_base_version"] for item in rels]
        latest_releases = [
            {
                "version": item["_base_version"],
                "release": rebuild_release(item["version"]),
                "created_at": memberships.get(item["pk"]) or item["pulp_created"],
            }
            for item in rels
        ]
        if last_updated_by_name is None:
            last_updated = row.get("last_updated")
        else:
            last_updated = last_updated_by_name.get(normalized)
        result.append(
            {
                "name": name_by_normalized[normalized],
                "name_normalized": normalized,
                "last_updated": last_updated,
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
