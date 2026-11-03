"""Unit tests for the repository package index helpers."""

import uuid

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIRequestFactory, force_authenticate

from pulpcore.plugin.models import RepositoryVersion

from pulp_python.app.catalog import (
    assemble_package_index,
    distinct_package_names_qs,
    python_packages_in_version,
)
from pulp_python.app.models import PythonPackageContent, PythonRepository
from pulp_python.app.viewsets import PythonRepositoryPackageViewSet

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


def _create_package(name, version):
    fields = {field: "" for field in _EMPTY_TEXT}
    fields.update(
        name=name,
        version=version,
        filename=f"{name}-{version}.tar.gz",
        packagetype="sdist",
        sha256=uuid.uuid4().hex + uuid.uuid4().hex,
        description=f"{name} {version} description",
    )
    return PythonPackageContent.objects.create(**fields)


@pytest.mark.django_db
def test_package_list_pagination_and_deferred_metadata(django_assert_num_queries):
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
    content_qs = python_packages_in_version(repo_version)
    names_qs = distinct_package_names_qs(content_qs)

    with django_assert_num_queries(1):
        assert names_qs.count() == 4
    with django_assert_num_queries(1):
        page = list(names_qs[:2])
    with CaptureQueriesContext(connection) as queries:
        rows = assemble_package_index(content_qs, page, repo_version)

    assert [row["name_normalized"] for row in rows] == ["alpha", "beta"]
    for row in rows:
        assert [item["version"] for item in row["versions"]] == [
            f"1.0.{number}" for number in reversed(range(5))
        ]
        assert row["description"] == f"{row['name_normalized']} 1.0.4 description"

    bulk_select = queries[0]["sql"].split(" FROM ", 1)[0]
    for field in ("description", "classifiers", "requires_dist", "project_urls", "license_file"):
        assert f'"{field}"' not in bulk_select
    description_queries = [
        query for query in queries if '"description"' in query["sql"].split(" FROM ", 1)[0]
    ]
    assert len(description_queries) == len(rows)


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
