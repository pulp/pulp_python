import re
from email.utils import getaddresses
from urllib.parse import urljoin

from django.db.models import F, FilteredRelation, Max, Min, Q
from django.http.response import HttpResponse, HttpResponseNotFound
from django.utils.decorators import method_decorator
from django.utils.feedgenerator import Rss201rev2Feed
from django.views.decorators.cache import cache_control
from django.views.decorators.http import condition
from drf_spectacular.utils import extend_schema
from packaging.utils import canonicalize_name
from rest_framework.viewsets import ViewSet

from pulp_python.app.cache import PythonApiCache, find_base_path_cached
from pulp_python.app.pypi.views import PyPIMixin, _etag_func

UPDATES_LIMIT = 500
PACKAGES_LIMIT = 40
PROJECT_RELEASES_LIMIT = 40
RSS_CONTENT_TYPE = "application/rss+xml; charset=utf-8"

# XML 1.0 disallowed characters (Django still escapes <>&).
_INVALID_XML_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")


def sanitize_xml_text(value):
    """Return a string safe to place in an RSS text field."""
    if not value:
        return ""
    return _INVALID_XML_CHARS.sub("", str(value))


def format_author(author_email):
    """Return an RSS author email, or None if the value is not a usable address."""
    if not author_email:
        return None
    emails = []
    for _, email in getaddresses([author_email]):
        if "@" not in email:
            return None
        emails.append(email)
    return ", ".join(emails) or None


def annotate_added_at(content, repo_ver):
    """Annotate each package file with when it was added to this repository."""
    return content.annotate(
        active_membership=FilteredRelation(
            "version_memberships",
            condition=Q(
                version_memberships__repository=repo_ver.repository,
                version_memberships__version_removed=None,
            ),
        ),
        file_added_at=F("active_membership__pulp_created"),
    )


def iter_releases(content, repo_ver, name_normalized=None, limit=UPDATES_LIMIT):
    """Yield latest (name, version) releases in the served repository version."""
    qs = annotate_added_at(content, repo_ver)
    if name_normalized:
        qs = qs.filter(name_normalized=name_normalized)
    return (
        qs.order_by()
        .values("name_normalized", "version")
        .annotate(
            added_at=Max("file_added_at"),
            name=Min("name"),
            summary=Min("summary"),
            author_email=Min("author_email"),
        )
        .order_by("-added_at", "name_normalized", "version")[:limit]
    )


def iter_projects(content, repo_ver, limit=PACKAGES_LIMIT):
    """Yield latest newly added projects in the served repository version."""
    qs = annotate_added_at(content, repo_ver)
    return (
        qs.order_by()
        .values("name_normalized")
        .annotate(
            added_at=Max("file_added_at"),
            name=Min("name"),
            summary=Min("summary"),
            author_email=Min("author_email"),
        )
        .order_by("-added_at", "name_normalized")[:limit]
    )


def _item_dict(title, link, description, author_email, pubdate):
    return {
        "title": sanitize_xml_text(title),
        "link": link,
        "description": sanitize_xml_text(description),
        "author_email": format_author(author_email),
        "pubdate": pubdate,
        "unique_id": f"{link}#{pubdate.isoformat()}",
    }


def render_rss(title, link, description, items):
    """Render an RSS 2.0 document from item dicts produced by `_item_dict`."""
    feed = Rss201rev2Feed(
        title=sanitize_xml_text(title),
        link=link,
        description=sanitize_xml_text(description),
        language="en",
    )
    for item in items:
        feed.add_item(
            title=item["title"],
            link=item["link"],
            description=item["description"],
            author_email=item["author_email"],
            pubdate=item["pubdate"],
            unique_id=item["unique_id"],
            unique_id_is_permalink=False,
        )
    return feed.writeString("utf-8")


def _release_link(index_url, name_normalized, version):
    return urljoin(index_url, f"pypi/{name_normalized}/{version}/json")


def _project_link(index_url, name_normalized):
    return urljoin(index_url, f"pypi/{name_normalized}/json")


def render_updates_feed(index_url, releases):
    items = [
        _item_dict(
            title=f"{release['name']} {release['version']}",
            link=_release_link(index_url, release["name_normalized"], release["version"]),
            description=release["summary"],
            author_email=release["author_email"],
            pubdate=release["added_at"],
        )
        for release in releases
    ]
    return render_rss(
        title="Recent updates",
        link=index_url,
        description="Recent updates to this Python package index",
        items=items,
    )


def render_packages_feed(index_url, projects):
    items = [
        _item_dict(
            title=f"{project['name']} added to index",
            link=_project_link(index_url, project["name_normalized"]),
            description=project["summary"],
            author_email=project["author_email"],
            pubdate=project["added_at"],
        )
        for project in projects
    ]
    return render_rss(
        title="Newest packages",
        link=index_url,
        description="Newest packages registered on this Python package index",
        items=items,
    )


def render_project_releases_feed(index_url, project_name, releases):
    project_link = _project_link(index_url, canonicalize_name(project_name))
    items = [
        _item_dict(
            title=release["version"],
            link=_release_link(index_url, release["name_normalized"], release["version"]),
            description=release["summary"],
            author_email=release["author_email"],
            pubdate=release["added_at"],
        )
        for release in releases
    ]
    return render_rss(
        title=f"Recent updates for {project_name}",
        link=project_link,
        description=f"Recent updates to {project_name} on this Python package index",
        items=items,
    )


class FeedView(PyPIMixin, ViewSet):
    """View for PyPI-compatible RSS feeds on a distribution."""

    endpoint_name = "rss"
    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["updates", "packages", "project_releases"],
                "principal": "*",
                "effect": "allow",
            },
        ],
    }

    def _index_url(self, path):
        return urljoin(self.base_api_url, f"{path}/")

    def _rss_response(self, xml):
        return HttpResponse(xml, content_type=RSS_CONTENT_TYPE)

    @extend_schema(summary="Get latest updates RSS feed")
    @method_decorator(cache_control(max_age=600, public=True))
    @method_decorator(condition(etag_func=_etag_func))
    @PythonApiCache(base_key=find_base_path_cached)
    def updates(self, request, path):
        """Latest releases added to this index, analogous to PyPI `/rss/updates.xml`."""
        repo_ver, content = self.get_rvc()
        index_url = self._index_url(path)
        releases = list(iter_releases(content, repo_ver)) if content is not None else []
        return self._rss_response(render_updates_feed(index_url, releases))

    @extend_schema(summary="Get newest packages RSS feed")
    @method_decorator(cache_control(max_age=600, public=True))
    @method_decorator(condition(etag_func=_etag_func))
    @PythonApiCache(base_key=find_base_path_cached)
    def packages(self, request, path):
        """Latest newly added projects, analogous to PyPI `/rss/packages.xml`."""
        repo_ver, content = self.get_rvc()
        index_url = self._index_url(path)
        projects = list(iter_projects(content, repo_ver)) if content is not None else []
        return self._rss_response(render_packages_feed(index_url, projects))

    @extend_schema(summary="Get project releases RSS feed")
    @method_decorator(cache_control(max_age=600, public=True))
    @method_decorator(condition(etag_func=_etag_func))
    @PythonApiCache(base_key=find_base_path_cached)
    def project_releases(self, request, path, package):
        """Latest releases for one project, analogous to PyPI `/rss/project/<name>/releases.xml`."""
        repo_ver, content = self.get_rvc()
        normalized = canonicalize_name(package)
        if content is None or not content.filter(name_normalized=normalized).exists():
            return HttpResponseNotFound(f"{normalized} does not exist.")

        index_url = self._index_url(path)
        releases = list(
            iter_releases(
                content, repo_ver, name_normalized=normalized, limit=PROJECT_RELEASES_LIMIT
            )
        )
        project_name = releases[0]["name"] if releases else package
        return self._rss_response(render_project_releases_feed(index_url, project_name, releases))
