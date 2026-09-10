"""Unit tests for catalog version helpers.

CI runs these with ``pytest -p no:pulpcore``. Import ``versions``, not ``utils``
or ``catalog``: those pull in Django models and fail collection with
AppRegistryNotReady.
"""

import pytest

from pulp_python.app.versions import (
    normalize_name_normalized_search,
    normalize_package_index_ordering,
    rebuild_release,
    strip_build_suffix,
    version_sort_key,
)


@pytest.mark.parametrize(
    "version,expected",
    [
        ("0.1", "0.1"),
        ("5.3.17", "5.3.17"),
        ("5.3.18", "5.3.18"),
        ("5.3.180", "5.3.180"),
        ("5.3.17.rhlw-00001", "5.3.17"),
        ("5.3.18.rhlw-00003", "5.3.18"),
        ("5.3.17.rhlw-00001-n0001", "5.3.17"),
        ("5.3.18.lw-1", "5.3.18"),
        ("1.0.0.abc-1", "1.0.0"),
        ("1.0.0.ABC-99", "1.0.0"),
        ("1.0.foo-bar", "1.0"),
        ("1.0.rhlw-١", "1.0"),
        ("4.3.0-redhat-1", "4.3.0-redhat-1"),
        ("5.3.18-anything", "5.3.18-anything"),
        ("5.3.18.anything", "5.3.18.anything"),
        ("1.0.rhlw-00003.extra", "1.0.rhlw-00003.extra"),
        ("1.0.rhlw-", "1.0.rhlw-"),
        ("", ""),
        (None, None),
    ],
)
def test_strip_build_suffix(version, expected):
    assert strip_build_suffix(version) == expected


@pytest.mark.parametrize(
    "version,expected",
    [
        ("5.3.18", ""),
        ("5.3.17.rhlw-00001", "rhlw-00001"),
        ("5.3.18.rhlw-00003", "rhlw-00003"),
        ("5.3.17.rhlw-00001-n0001", "rhlw-00001-n0001"),
        ("5.3.18.lw-1", "lw-1"),
        ("0.1.rhlw-00003", "rhlw-00003"),
        ("1.0.foo-bar", "foo-bar"),
        ("1.0.rhlw-١", "rhlw-١"),
        ("5.3.18.anything", ""),
        ("4.3.0-redhat-1", ""),
        ("5.3.18-anything", ""),
        ("1.0.rhlw-", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_rebuild_release(version, expected):
    assert rebuild_release(version) == expected


@pytest.mark.parametrize(
    "versions,expected",
    [
        # Lexical descending would put 1.9 before 1.2 before 1.10.
        (["1.10", "1.9", "1.2"], ["1.10", "1.9", "1.2"]),
        (["1.10.1", "1.10.4", "1.10.2", "1.10.3"], ["1.10.4", "1.10.3", "1.10.2", "1.10.1"]),
        ([], []),
        ([""], [""]),
    ],
)
def test_version_sort_key_newest_first(versions, expected):
    assert sorted(versions, key=version_sort_key, reverse=True) == expected


def test_version_sort_key_empty_and_invalid():
    assert version_sort_key("") == (-1, "")
    assert version_sort_key(None) == (-1, "")
    assert sorted(["1.0", "not-a-version"], key=version_sort_key, reverse=True) == [
        "1.0",
        "not-a-version",
    ]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ([], ["name", "name_normalized"]),
        ([""], ["name", "name_normalized"]),
        (["name"], ["name", "name_normalized"]),
        (["name,name_normalized"], ["name", "name_normalized"]),
        (["-name"], ["-name", "name_normalized"]),
        (["name_normalized"], ["name_normalized"]),
        (["last_updated"], ["last_updated", "name", "name_normalized"]),
        (["-last_updated"], ["-last_updated", "name", "name_normalized"]),
        (["-last_updated", "name_normalized"], ["-last_updated", "name_normalized"]),
    ],
)
def test_normalize_package_index_ordering(raw, expected):
    assert normalize_package_index_ordering(raw) == expected


def test_normalize_package_index_ordering_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown ordering field"):
        normalize_package_index_ordering(["group_id"])


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("djan", "djan"),
        ("DJAN", "djan"),
        ("JAN", "jan"),
        ("  HTTP ", "http"),
    ],
)
def test_normalize_name_normalized_search(value, expected):
    assert normalize_name_normalized_search(value) == expected


@pytest.mark.parametrize("value", ["a", "ab", "DJ", "  x  "])
def test_normalize_name_normalized_search_rejects_short(value):
    with pytest.raises(ValueError, match="at least 3 characters"):
        normalize_name_normalized_search(value)
