from django.urls import path

from pulp_python.app.pypi.views import SimpleView, MetadataView, PyPIView, UploadView

PYPI_API_URL = 'pypi/<path:path>/'
# TODO: Implement remaining PyPI endpoints
# path("project/", PackageProject.as_view()), # Endpoints to nicely see contents of index
# path("search/", PackageSearch.as_view()),

urlpatterns = [
    path(PYPI_API_URL + "legacy/", UploadView.as_view({"post": "create"}), name="upload"),
    path(
        PYPI_API_URL + "pypi/<path:meta>/",
        MetadataView.as_view({"get": "retrieve"}),
        name="pypi-metadata"
    ),
    path(
        PYPI_API_URL + "simple/<str:package>/",
        SimpleView.as_view({"get": "retrieve"}),
        name="simple-package-detail"
    ),
    path(
        PYPI_API_URL + 'simple/',
        SimpleView.as_view({"get": "list", "post": "create"}),
        name="simple-detail"
    ),
    path(PYPI_API_URL, PyPIView.as_view({"get": "retrieve"}), name="pypi-detail"),
]
