import pytest

from pulp_python.app.utils import strip_build_suffix


@pytest.mark.parametrize(
    "version,expected",
    [
        ("0.1", "0.1"),
        ("5.3.18", "5.3.18"),
        ("5.3.18.rhlw-00003", "5.3.18"),
        ("1.0.0.abc-1", "1.0.0"),
        ("1.0.0.ABC-99", "1.0.0"),
        ("1.0.foo-bar", "1.0.foo-bar"),
        ("1.0.rhlw-00003.extra", "1.0.rhlw-00003.extra"),
        ("", ""),
        (None, None),
    ],
)
def test_strip_build_suffix(version, expected):
    assert strip_build_suffix(version) == expected
