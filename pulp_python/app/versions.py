"""Catalog version helpers with no Django imports.

CI unit tests run with ``-p no:pulpcore``, so this module must stay importable
before Django apps are loaded.
"""

import re

from packaging.version import InvalidVersion, Version

# Last dot-segment is a rebuild if it is letters, dash, rest of that segment.
# POSIX string shared with SQL REGEXP_REPLACE. Not hard-coded to "rhlw".
BUILD_SUFFIX_PATTERN = r"\.[a-zA-Z]+-[^.]+$"
BUILD_SUFFIX_RE = re.compile(BUILD_SUFFIX_PATTERN)

PACKAGE_INDEX_ORDERING_FIELDS = frozenset({"name", "name_normalized", "last_updated"})
DEFAULT_PACKAGE_INDEX_ORDERING = ("name",)
NAME_NORMALIZED_SEARCH_MIN_LENGTH = 3


def strip_build_suffix(version):
    """Return ``version`` with a trailing rebuild suffix removed, else unchanged.

    A rebuild is the last dot-segment matching ``BUILD_SUFFIX_PATTERN``.
    """
    if not version:
        return version
    return BUILD_SUFFIX_RE.sub("", version)


def rebuild_release(version):
    """Return the rebuild qualifier without the leading dot, or an empty string."""
    if not version:
        return ""
    base = strip_build_suffix(version)
    if version == base:
        return ""
    if version.startswith(base + "."):
        return version[len(base) + 1 :]
    return ""


def version_sort_key(version):
    """PEP 440 sort key. Use with ``reverse=True`` for newest first.

    Invalid versions sort after all valid ones when ``reverse=True``.
    """
    if not version:
        return (-1, "")
    try:
        return (0, Version(version))
    except InvalidVersion:
        return (-1, str(version))


def normalize_package_index_ordering(raw_values):
    """Turn ``ordering`` query values into ``order_by`` arguments.

    Default is ``name``. Unknown fields raise ``ValueError``. ``last_updated``
    keeps ``name`` then ``name_normalized`` as a stable pagination tiebreaker.
    ``name_normalized`` is always appended when omitted so equal names paginate
    stably (rows are unique on that column).
    """
    fields = []
    for item in raw_values:
        if not item:
            continue
        for part in str(item).split(","):
            part = part.strip()
            if part:
                fields.append(part)

    if not fields:
        fields = list(DEFAULT_PACKAGE_INDEX_ORDERING)

    normalized = []
    seen = set()
    for field in fields:
        descending = field.startswith("-")
        name = field[1:] if descending else field
        if name not in PACKAGE_INDEX_ORDERING_FIELDS:
            raise ValueError(f"Unknown ordering field: '{name}'.")
        if name in seen:
            continue
        seen.add(name)
        normalized.append(f"-{name}" if descending else name)

    have = {term.lstrip("-") for term in normalized}
    if "name" not in have and "name_normalized" not in have:
        normalized.append("name")
    if "name_normalized" not in have:
        normalized.append("name_normalized")
    return normalized


def normalize_name_normalized_search(value):
    """Lowercase a ``name_normalized`` search string, or ``None`` if omitted."""
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if len(normalized) < NAME_NORMALIZED_SEARCH_MIN_LENGTH:
        raise ValueError(f"Must be at least {NAME_NORMALIZED_SEARCH_MIN_LENGTH} characters.")
    return normalized
