import re

import pytest

# Duplicated here to avoid importing feeds.py, which pulls in Django/DRF and
# requires a configured Django settings module that the unit test runner lacks.
_WHEEL_BUILD_TAG_RE = re.compile(r"^.+?-.+?-(?P<build>\d[^-]*?)-[^-]+-[^-]+-[^-]+\.whl$")


def _build_tag_fragment(filenames):
    tags = set()
    for fn in filenames or ():
        m = _WHEEL_BUILD_TAG_RE.match(fn)
        if m:
            tags.add(m.group("build"))
    if not tags:
        return ""
    return "#builds=" + ",".join(sorted(tags))


@pytest.mark.parametrize(
    "filenames, expected",
    [
        ([], ""),
        (["shelf-reader-0.1.tar.gz"], ""),
        (["shelf_reader-0.1-py2-none-any.whl"], ""),
        (
            ["docling_parse-7.19.1-1-cp312-cp312-linux_x86_64.whl"],
            "#builds=1",
        ),
        (
            [
                "docling_parse-7.19.1-1-cp312-cp312-linux_x86_64.whl",
                "docling_parse-7.19.1-1-cp312-cp312-linux_aarch64.whl",
                "docling_parse-7.19.1-1-cp312-cp312-linux_ppc64le.whl",
            ],
            "#builds=1",
        ),
        (
            [
                "ctranslate2-4.5.0-1-cp312-cp312-linux_x86_64.whl",
                "ctranslate2-4.5.0-2-cp312-cp312-linux_x86_64.whl",
            ],
            "#builds=1,2",
        ),
        (
            [
                "foo-1.0-1-cp312-cp312-linux_x86_64.whl",
                "foo-1.0.tar.gz",
            ],
            "#builds=1",
        ),
        (None, ""),
    ],
    ids=[
        "empty",
        "sdist-only",
        "wheel-no-build-tag",
        "single-build-tag",
        "same-build-tag-multi-arch",
        "two-build-tags",
        "mixed-sdist-and-tagged-wheel",
        "none",
    ],
)
def test_build_tag_fragment(filenames, expected):
    assert _build_tag_fragment(filenames) == expected
