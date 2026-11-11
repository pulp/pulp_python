from django.conf import settings
from django.urls import path

from pulp_python.app.pypi.feeds import FeedView
from pulp_python.app.pypi.views import (
    MetadataView,
    ProvenanceView,
    PyPIView,
    SimpleView,
    UploadView,
    YankView,
)

if settings.DOMAIN_ENABLED:
    PYPI_API_URL = "/<slug:pulp_domain>/<path:path>/"
else:
    PYPI_API_URL = "/<path:path>/"
PYPI_API_URL = settings.PYPI_PATH_PREFIX.strip("/") + PYPI_API_URL
# TODO: Implement remaining PyPI endpoints
# path("project/", PackageProject.as_view()), # Endpoints to nicely see contents of index
# path("search/", PackageSearch.as_view()),

urlpatterns = [
    path(PYPI_API_URL + "legacy/", UploadView.as_view({"post": "create"}), name="upload"),
    path(
        PYPI_API_URL + "integrity/<str:package>/<str:version>/<str:filename>/provenance/",
        ProvenanceView.as_view({"get": "retrieve"}),
        name="integrity-provenance",
    ),
    path(
        PYPI_API_URL + "pypi/<path:meta>/",
        MetadataView.as_view({"get": "retrieve"}),
        name="pypi-metadata",
    ),
    path(
        PYPI_API_URL + "simple/<str:package>/",
        SimpleView.as_view({"get": "retrieve"}),
        name="simple-package-detail",
    ),
    path(
        PYPI_API_URL + "simple/",
        SimpleView.as_view({"get": "list", "post": "create"}),
        name="simple-detail",
    ),
    path(PYPI_API_URL + "yank/", YankView.as_view({"post": "yank"}), name="yank"),
    path(PYPI_API_URL + "unyank/", YankView.as_view({"post": "unyank"}), name="unyank"),
    path(
        PYPI_API_URL + "rss/updates.xml",
        FeedView.as_view({"get": "updates"}),
        name="rss-updates",
    ),
    path(
        PYPI_API_URL + "rss/packages.xml",
        FeedView.as_view({"get": "packages"}),
        name="rss-packages",
    ),
    path(
        PYPI_API_URL + "rss/project/<str:package>/releases.xml",
        FeedView.as_view({"get": "project_releases"}),
        name="rss-project-releases",
    ),
    path(PYPI_API_URL, PyPIView.as_view({"get": "retrieve"}), name="pypi-detail"),
]
