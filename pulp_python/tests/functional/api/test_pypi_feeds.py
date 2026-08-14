from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree as ET

import pytest
import requests

from pulp_python.tests.functional.constants import (
    PYTHON_EGG_FILENAME,
    PYTHON_EGG_URL,
    PYTHON_FIXTURES_URL,
    PYTHON_WHEEL_FILENAME,
    PYTHON_WHEEL_URL,
    TWINE_EGG_FILENAME,
    TWINE_EGG_URL,
    TWINE_WHEEL_FILENAME,
    TWINE_WHEEL_URL,
)

TWINE_500_WHEEL_FILENAME = "twine-5.0.0-py3-none-any.whl"
TWINE_500_WHEEL_URL = urljoin(urljoin(PYTHON_FIXTURES_URL, "packages/"), TWINE_500_WHEEL_FILENAME)


def _index_url(distro, bindings_cfg):
    """Build the index URL using the same origin the API client uses."""
    path = urlsplit(distro.base_url).path
    if not path.endswith("/"):
        path += "/"
    return bindings_cfg.host.rstrip("/") + path


def _get_feed(distro, relative, bindings_cfg):
    return requests.get(urljoin(_index_url(distro, bindings_cfg), relative))


def _parse_items(response):
    assert response.status_code == 200, response.text
    assert "application/rss+xml" in response.headers["Content-Type"]
    root = ET.fromstring(response.content)
    assert root.tag == "rss"
    channel = root.find("channel")
    assert channel is not None
    return channel.findall("item")


def _titles(items):
    return [item.findtext("title") for item in items]


@pytest.mark.parallel
def test_empty_feeds(bindings_cfg, python_empty_repo_distro):
    """Empty indexes return valid RSS documents with no items."""
    _, distro = python_empty_repo_distro()

    for relative in ("rss/updates.xml", "rss/packages.xml"):
        items = _parse_items(_get_feed(distro, relative, bindings_cfg))
        assert items == []

    response = _get_feed(distro, "rss/project/shelf-reader/releases.xml", bindings_cfg)
    assert response.status_code == 404


@pytest.mark.parallel
def test_feeds_projects_releases_and_files(
    bindings_cfg, python_content_factory, python_empty_repo_distro
):
    """Feeds collapse files to releases, track new projects vs new versions, and stay per-index."""
    repo, distro = python_empty_repo_distro()
    _, other_distro = python_empty_repo_distro()

    python_content_factory(PYTHON_EGG_FILENAME, url=PYTHON_EGG_URL, repository=repo)
    python_content_factory(PYTHON_WHEEL_FILENAME, url=PYTHON_WHEEL_URL, repository=repo)

    update_titles = _titles(_parse_items(_get_feed(distro, "rss/updates.xml", bindings_cfg)))
    package_titles = _titles(_parse_items(_get_feed(distro, "rss/packages.xml", bindings_cfg)))
    release_titles = _titles(
        _parse_items(_get_feed(distro, "rss/project/shelf-reader/releases.xml", bindings_cfg))
    )

    assert update_titles == ["shelf-reader 0.1"]
    assert package_titles == ["shelf-reader added to index"]
    assert release_titles == ["0.1"]
    assert _parse_items(_get_feed(other_distro, "rss/updates.xml", bindings_cfg)) == []

    python_content_factory(TWINE_500_WHEEL_FILENAME, url=TWINE_500_WHEEL_URL, repository=repo)

    update_titles = _titles(_parse_items(_get_feed(distro, "rss/updates.xml", bindings_cfg)))
    package_titles = _titles(_parse_items(_get_feed(distro, "rss/packages.xml", bindings_cfg)))
    assert update_titles == ["twine 5.0.0", "shelf-reader 0.1"]
    assert package_titles == ["twine added to index", "shelf-reader added to index"]

    python_content_factory(TWINE_WHEEL_FILENAME, url=TWINE_WHEEL_URL, repository=repo)
    python_content_factory(TWINE_EGG_FILENAME, url=TWINE_EGG_URL, repository=repo)

    update_titles = _titles(_parse_items(_get_feed(distro, "rss/updates.xml", bindings_cfg)))
    package_titles = _titles(_parse_items(_get_feed(distro, "rss/packages.xml", bindings_cfg)))
    twine_releases = _titles(
        _parse_items(_get_feed(distro, "rss/project/twine/releases.xml", bindings_cfg))
    )

    assert update_titles == ["twine 5.1.0", "twine 5.0.0", "shelf-reader 0.1"]
    assert package_titles == ["twine added to index", "shelf-reader added to index"]
    assert twine_releases == ["5.1.0", "5.0.0"]

    response = _get_feed(distro, "rss/project/does-not-exist/releases.xml", bindings_cfg)
    assert response.status_code == 404
    assert _parse_items(_get_feed(other_distro, "rss/updates.xml", bindings_cfg)) == []


@pytest.mark.parallel
def test_pinned_version_feeds(
    bindings_cfg,
    python_content_factory,
    python_distribution_factory,
    python_repo_factory,
):
    """Feeds for a pinned repository version stay frozen, as publication-backed indexes do."""
    repo = python_repo_factory()
    python_content_factory(PYTHON_EGG_FILENAME, url=PYTHON_EGG_URL, repository=repo)
    distro = python_distribution_factory(repository=repo, version="1")

    update_titles = _titles(_parse_items(_get_feed(distro, "rss/updates.xml", bindings_cfg)))
    package_titles = _titles(_parse_items(_get_feed(distro, "rss/packages.xml", bindings_cfg)))
    assert update_titles == ["shelf-reader 0.1"]
    assert package_titles == ["shelf-reader added to index"]

    item = _parse_items(_get_feed(distro, "rss/updates.xml", bindings_cfg))[0]
    assert item.findtext("link").endswith("pypi/shelf-reader/0.1/json")
    assert item.findtext("guid").endswith("pypi/shelf-reader/0.1/json")

    python_content_factory(TWINE_WHEEL_FILENAME, url=TWINE_WHEEL_URL, repository=repo)
    update_titles = _titles(_parse_items(_get_feed(distro, "rss/updates.xml", bindings_cfg)))
    assert update_titles == ["shelf-reader 0.1"]
