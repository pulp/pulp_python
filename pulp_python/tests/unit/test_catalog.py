"""Unit tests for the repository package index helpers."""

import uuid

import pytest
from django.apps import apps
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory, force_authenticate

from pulpcore.plugin.models import RepositoryVersion

from pulp_python.app.catalog import assemble_package_index, package_catalog_queryset
from pulp_python.app.models import PythonPackageContent, PythonRepository
from pulp_python.app.viewsets import (
    PythonPackageSingleArtifactContentUploadViewSet,
    PythonRepositoryPackageViewSet,
)

_EMPTY_TEXT = (
    "author",
    "author_email",
    "description",
    "home_page",
    "keywords",
    "license",
    "metadata_version",
    "platform",
    "summary",
    "download_url",
    "supported_platform",
    "maintainer",
    "maintainer_email",
    "project_url",
    "requires_python",
    "description_content_type",
    "license_expression",
    "python_version",
)


def _create_package(name, version, **overrides):
    fields = {field: "" for field in _EMPTY_TEXT}
    fields.update(
        name=name,
        version=version,
        filename=f"{name}-{version}.tar.gz",
        packagetype="sdist",
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        description=f"{name} {version} description",
    )
    fields.update(overrides)
    return PythonPackageContent.objects.create(**fields)


@pytest.mark.django_db
@pytest.mark.parametrize("page_size", [1, 2, 4])
def test_package_list_pagination_and_bulk_metadata(django_assert_num_queries, page_size):
    """Page distinct names and load large metadata only for the newest version."""
    repository = PythonRepository.objects.create(name=str(uuid.uuid4()))
    created = [
        _create_package(name, f"1.0.{number}")
        for name in ("alpha", "beta", "gamma", "delta")
        for number in range(5)
    ]
    with repository.new_version() as version:
        version.add_content(
            PythonPackageContent.objects.filter(pk__in=[item.pk for item in created])
        )

    repo_version = repository.latest_version()
    content_qs = repo_version.get_content(PythonPackageContent.objects.all())
    packages = package_catalog_queryset(content_qs)

    with django_assert_num_queries(1):
        assert packages.count() == 4
    with django_assert_num_queries(1), CaptureQueriesContext(connection) as page_queries:
        page = list(packages[:page_size])
    with django_assert_num_queries(1), CaptureQueriesContext(connection) as queries:
        rows = assemble_package_index(page)

    assert [row["name_normalized"] for row in rows] == ["alpha", "beta", "delta", "gamma"][
        :page_size
    ]
    for row in rows:
        assert [item["version"] for item in row["versions"]] == [
            f"1.0.{number}" for number in reversed(range(5))
        ]
        assert row["description"] == f"{row['name_normalized']} 1.0.4 description"

    for field in ("description", "classifiers", "requires_dist", "project_urls", "license_file"):
        assert f'"{field}"' not in page_queries[0]["sql"]
    description_queries = [
        query for query in queries if '"description"' in query["sql"].split(" FROM ", 1)[0]
    ]
    assert len(description_queries) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("has_sdist", [True, False])
def test_package_list_representative_file(has_sdist, django_assert_num_queries):
    """Each version uses an sdist if available, otherwise its newest wheel."""
    repository = PythonRepository.objects.create(name=str(uuid.uuid4()))
    units = []
    if has_sdist:
        units.append(_create_package("alpha", "1.0", license_expression="MIT"))
    for platform in ("linux", "macos"):
        units.append(
            _create_package(
                "alpha",
                "1.0",
                filename=f"alpha-1.0-{platform}.whl",
                packagetype="bdist_wheel",
                license_expression="Apache-2.0",
                description=f"{platform} wheel description",
            )
        )
    with repository.new_version() as version:
        version.add_content(PythonPackageContent.objects.filter(pk__in=[unit.pk for unit in units]))
    content = repository.latest_version().get_content(PythonPackageContent.objects.all())

    with django_assert_num_queries(2):
        rows = assemble_package_index(list(package_catalog_queryset(content)))
    assert rows[0]["versions"] == [
        {"version": "1.0", "license_expression": "MIT" if has_sdist else "Apache-2.0"}
    ]
    assert rows[0]["description"] == (
        "alpha 1.0 description" if has_sdist else "macos wheel description"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("explicit", [True, False])
def test_package_list_incomplete_version(django_user_model, explicit):
    """Reject an explicit incomplete snapshot and ignore it when selecting the latest."""
    repository = PythonRepository.objects.create(name=str(uuid.uuid4()))
    incomplete = RepositoryVersion.objects.create(repository=repository, number=1, complete=False)
    user = django_user_model.objects.create(username=str(uuid.uuid4()), is_superuser=True)
    params = (
        {"repository_version": f"prn:core.repositoryversion:{incomplete.pk}"} if explicit else {}
    )
    request = APIRequestFactory().get("/", params)
    force_authenticate(request, user=user)
    response = PythonRepositoryPackageViewSet.as_view({"get": "list"})(
        request, repository_pk=str(repository.pk)
    )
    assert response.status_code == (400 if explicit else 200)
    if explicit:
        assert "complete" in str(response.data["repository_version"])
    else:
        assert response.data["count"] == 0
        assert response.data["results"] == []


def test_package_content_viewset_registration():
    """The catalog must not compete with the package content resource's viewset."""
    assert apps.get_app_config("python").named_viewsets[PythonPackageContent] == [
        PythonPackageSingleArtifactContentUploadViewSet
    ]


@pytest.mark.django_db
def test_package_list_without_pagination(django_user_model):
    """The standard list action also assembles rows when pagination is disabled."""
    repository = PythonRepository.objects.create(name=str(uuid.uuid4()))
    package = _create_package("alpha", "1.0")
    with repository.new_version() as version:
        version.add_content(PythonPackageContent.objects.filter(pk=package.pk))
    user = django_user_model.objects.create(username=str(uuid.uuid4()), is_superuser=True)
    request = APIRequestFactory().get("/")
    force_authenticate(request, user=user)
    response = PythonRepositoryPackageViewSet.as_view({"get": "list"}, pagination_class=None)(
        request, repository_pk=str(repository.pk)
    )
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["description"] == "alpha 1.0 description"
    assert response.data[0]["versions"] == [{"version": "1.0", "license_expression": ""}]
