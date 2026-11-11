"""Unit tests for the repository package index helpers."""

import uuid
from datetime import datetime, timedelta

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
    PythonRepositoryVersionViewSet,
    PythonRepositoryViewSet,
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

    for field in (
        "description",
        "license_expression",
        "classifiers",
        "requires_dist",
        "project_urls",
        "license_file",
    ):
        assert f'"{field}"' not in page_queries[0]["sql"]
    description_queries = [
        query for query in queries if '"description"' in query["sql"].split(" FROM ", 1)[0]
    ]
    assert len(description_queries) == 1


@pytest.mark.django_db
@pytest.mark.parametrize("has_sdist", [True, False])
def test_package_list_representative_file(has_sdist, django_assert_num_queries):
    """Metadata prefers an sdist, but update times use the newest file in the snapshot."""
    repository = PythonRepository.objects.create(name=str(uuid.uuid4()))
    units = []
    if has_sdist:
        units.append(_create_package("alpha", "1.0"))
    for platform in ("linux", "macos"):
        units.append(
            _create_package(
                "alpha",
                "1.0",
                filename=f"alpha-1.0-{platform}.whl",
                packagetype="bdist_wheel",
                description=f"{platform} wheel description",
            )
        )
    outside = _create_package("alpha", "1.0")
    PythonPackageContent.objects.filter(pk=outside.pk).update(
        pulp_created=units[-1].pulp_created + timedelta(days=1)
    )
    with repository.new_version() as version:
        version.add_content(PythonPackageContent.objects.filter(pk__in=[unit.pk for unit in units]))
    content = repository.latest_version().get_content(PythonPackageContent.objects.all())

    with django_assert_num_queries(2):
        rows = assemble_package_index(list(package_catalog_queryset(content)))
    assert len(rows[0]["versions"]) == 1
    version = rows[0]["versions"][0]
    assert set(version) == {"version", "last_updated"}
    assert version["version"] == "1.0"
    assert datetime.fromisoformat(version["last_updated"]) == units[-1].pulp_created
    assert rows[0]["description"] == (
        "alpha 1.0 description" if has_sdist else "macos wheel description"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("explicit", [True, False])
def test_package_list_incomplete_version(django_user_model, explicit):
    """An incomplete version returns 404 and is ignored by the repository action."""
    repository = PythonRepository.objects.create(name=str(uuid.uuid4()))
    incomplete = RepositoryVersion.objects.create(repository=repository, number=1, complete=False)
    user = django_user_model.objects.create(username=str(uuid.uuid4()), is_superuser=True)
    request = APIRequestFactory().get("/")
    request.pulp_domain = repository.pulp_domain
    force_authenticate(request, user=user)
    viewset = PythonRepositoryVersionViewSet if explicit else PythonRepositoryViewSet
    kwargs = (
        {"repository_pk": str(repository.pk), "number": incomplete.number}
        if explicit
        else {"pk": str(repository.pk)}
    )
    response = viewset.as_view({"get": "packages"}, **viewset.packages.kwargs)(request, **kwargs)
    assert response.status_code == (404 if explicit else 200)
    if not explicit:
        assert response.data["count"] == 0
        assert response.data["results"] == []


def test_package_content_viewset_registration():
    """The catalog must not compete with the package content resource's viewset."""
    assert apps.get_app_config("python").named_viewsets[PythonPackageContent] == [
        PythonPackageSingleArtifactContentUploadViewSet
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("version_url", [False, True])
def test_package_list_without_pagination(django_user_model, version_url):
    """Both package actions assemble rows when pagination is disabled."""
    repository = PythonRepository.objects.create(name=str(uuid.uuid4()))
    package = _create_package("alpha", "1.0")
    with repository.new_version() as version:
        version.add_content(PythonPackageContent.objects.filter(pk=package.pk))
    user = django_user_model.objects.create(username=str(uuid.uuid4()), is_superuser=True)
    request = APIRequestFactory().get("/")
    request.pulp_domain = repository.pulp_domain
    force_authenticate(request, user=user)
    viewset = PythonRepositoryVersionViewSet if version_url else PythonRepositoryViewSet
    kwargs = (
        {"repository_pk": str(repository.pk), "number": repository.latest_version().number}
        if version_url
        else {"pk": str(repository.pk)}
    )
    response = viewset.as_view(
        {"get": "packages"}, pagination_class=None, **viewset.packages.kwargs
    )(request, **kwargs)
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]["description"] == "alpha 1.0 description"
    version = response.data[0]["versions"][0]
    assert set(version) == {"version", "last_updated"}
    assert version["version"] == "1.0"
    assert datetime.fromisoformat(version["last_updated"]) == package.pulp_created
