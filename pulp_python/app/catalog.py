"""Helpers for the repository package list."""

from collections import defaultdict
from urllib.parse import urlparse

from django.core.exceptions import FieldError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Case, IntegerField, Q, Value, When
from django.urls import Resolver404, resolve
from packaging.version import InvalidVersion, Version

from pulpcore.plugin.models import Repository, RepositoryContent, RepositoryVersion
from pulpcore.plugin.util import resolve_prn

from pulp_python.app.models import PythonPackageContent


def _version_sort_key(version):
    """PEP 440 sort key. Use with ``reverse=True`` for newest first.

    Invalid versions sort after all valid ones when ``reverse=True``.
    """
    if not version:
        return (-1, "")
    try:
        return (0, Version(version))
    except InvalidVersion:
        return (-1, str(version))


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


def distinct_package_names_qs(content_qs):
    """One row per distinct ``name_normalized``, ordered for stable pagination."""
    return content_qs.order_by().values("name_normalized").distinct().order_by("name_normalized")


def assemble_package_index(content_qs, name_rows, repository_version):
    """One catalog row per package name, with one content unit per stored version.

    Wheel and sdist of the same ``(name_normalized, version)`` collapse to one
    row. An sdist is preferred; otherwise the newest ``pulp_created`` is kept.
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
