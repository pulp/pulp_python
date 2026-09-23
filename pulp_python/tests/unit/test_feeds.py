import pytest

from pulp_python.app.pypi.feeds import _build_tag_fragment


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
