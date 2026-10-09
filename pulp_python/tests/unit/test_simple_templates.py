import pytest

from pulp_python.app.utils import write_simple_detail, write_simple_index

XSS_VECTORS = [
    ('<script>alert("xss")</script>', "&lt;script&gt;"),
    ("<img src=x onerror=alert(1)>", "&lt;img"),
    ('" onclick="alert(1)"', "&#34;"),
    ("a&b", "a&amp;b"),
]


def test_index_renders_valid_names():
    """Test that valid package names render correctly in the simple index page."""
    page = write_simple_index(["aprojectname", "under_score", "da-sh", "ungefährlich"])
    assert "aprojectname" in page
    assert "under-score" in page
    assert "da-sh" in page
    assert "ungefährlich" in page


@pytest.mark.parametrize("name,escaped", XSS_VECTORS)
def test_index_escapes_html(name, escaped):
    """Test that autoescape neutralizes HTML injection in the simple index page."""
    page = write_simple_index([name])
    assert name not in page
    assert escaped in page


@pytest.mark.parametrize("name,escaped", XSS_VECTORS)
def test_detail_escapes_html(name, escaped):
    """Test that autoescape neutralizes HTML injection in the simple detail page."""
    page = write_simple_detail(name, [])
    assert name not in page
    assert escaped in page


def test_detail_escapes_package_fields():
    """Test that autoescape neutralizes HTML injection in package metadata fields."""
    packages = [
        {
            "filename": "<img src=x onerror=alert(1)>",
            "url": 'http://evil.com/"><script>alert(1)</script>',
            "sha256": "abc123",
            "requires_python": None,
            "yanked": False,
            "yanked_reason": "",
            "metadata_sha256": None,
            "provenance": None,
        }
    ]
    page = write_simple_detail("safe-name", packages)
    assert "<img src=x onerror=alert(1)>" not in page
    assert "&lt;img src=x onerror=alert(1)&gt;" in page
    assert 'http://evil.com/"><script>alert(1)</script>' not in page
    assert "http://evil.com/&#34;&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in page
