from pathlib import Path

from bandersnatch.configuration import BandersnatchConfig
from django.db import transaction
from django_filters import CharFilter
from django_filters.rest_framework import filters as drf_filters
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.utils import canonicalize_name
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
)
from rest_framework.response import Response
from rest_framework.serializers import IntegerField, URLField, ValidationError

from pulpcore.plugin import viewsets as core_viewsets
from pulpcore.plugin.actions import ModifyRepositoryActionMixin
from pulpcore.plugin.models import RepositoryVersion
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositoryAddRemoveContentSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.tasking import check_content, dispatch
from pulpcore.plugin.util import extract_pk

from pulp_python.app import models as python_models
from pulp_python.app import serializers as python_serializers
from pulp_python.app import tasks
from pulp_python.app.catalog import (
    apply_package_prefix_filters,
    assemble_package_index,
    collapse_python_builds,
    distinct_package_names_qs,
    python_packages_in_version,
    repository_metrics,
)
from pulp_python.app.versions import (
    BUILD_SUFFIX_PATTERN,
    normalize_name_normalized_search,
    normalize_package_index_ordering,
)


class PythonRepositoryViewSet(
    core_viewsets.RepositoryViewSet, ModifyRepositoryActionMixin, core_viewsets.RolesMixin
):
    """
    PythonRepository represents a single Python repository, to which content can be
    synced, added, or removed.
    """

    endpoint_name = "python"
    queryset = python_models.PythonRepository.objects.all()
    serializer_class = python_serializers.PythonRepositorySerializer
    queryset_filtering_required_permission = "python.view_pythonrepository"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "my_permissions"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_perms:python.add_pythonrepository",
                    "has_remote_param_model_or_domain_or_obj_perms:python.view_pythonremote",
                ],
            },
            {
                "action": ["retrieve", "packages", "metrics"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_domain_or_obj_perms:python.view_pythonrepository",
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_or_obj_perms:python.delete_pythonrepository",
                    "has_model_or_domain_or_obj_perms:python.view_pythonrepository",
                ],
            },
            {
                "action": ["update", "partial_update", "set_label", "unset_label"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_or_obj_perms:python.change_pythonrepository",
                    "has_model_or_domain_or_obj_perms:python.view_pythonrepository",
                    "has_remote_param_model_or_domain_or_obj_perms:python.view_pythonremote",
                ],
            },
            {
                "action": ["sync"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_or_obj_perms:python.sync_pythonrepository",
                    "has_remote_param_model_or_domain_or_obj_perms:python.view_pythonremote",
                    "has_model_or_domain_or_obj_perms:python.view_pythonrepository",
                ],
            },
            {
                "action": ["modify", "repair_metadata"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_or_obj_perms:python.modify_pythonrepository",
                    "has_model_or_domain_or_obj_perms:python.view_pythonrepository",
                ],
            },
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_or_obj_perms:python.manage_roles_pythonrepository"
                ],
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {"roles": "python.pythonrepository_owner"},
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }
    LOCKED_ROLES = {
        "python.pythonrepository_creator": ["python.add_pythonrepository"],
        "python.pythonrepository_owner": [
            "python.view_pythonrepository",
            "python.change_pythonrepository",
            "python.delete_pythonrepository",
            "python.modify_pythonrepository",
            "python.sync_pythonrepository",
            "python.manage_roles_pythonrepository",
            "python.repair_pythonrepository",
        ],
        "python.pythonrepository_viewer": ["python.view_pythonrepository"],
    }

    def filter_queryset(self, queryset):
        """Do not apply the repository FilterSet to package-index query params."""
        if getattr(self, "action", None) in ("packages", "metrics"):
            return queryset
        return super().filter_queryset(queryset)

    def _requested_repository_version(self, repository):
        """Resolve optional ``repository_version`` href/PRN, else latest complete version."""
        href = self.request.query_params.get("repository_version")
        if not href:
            return repository.latest_version()
        repo_version = self.get_resource(href, RepositoryVersion)
        if repo_version.repository_id != repository.pk:
            raise ValidationError({"repository_version": "Must be a version of this repository."})
        return repo_version

    @extend_schema(
        description="Trigger an asynchronous task to create a new repository version.",
        summary="Modify Repository Content",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=RepositoryAddRemoveContentSerializer)
    def modify(self, request, pk, **kwargs):
        """
        Queues a task that creates a new RepositoryVersion by adding and removing content units.

        If allow_package_substitution is False, error_on_reject is True, and the request is
        **only** adding packages, then a package substitution check is performed to provide a
        quicker error response. Otherwise, the check is delegated to the task.

        Also performs an early blocklist check on added packages when error_on_reject is True.
        When error_on_reject is False, rejected packages are skipped during task finalization.
        """
        repository = self.get_object()
        add_content_units = request.data.get("add_content_units", [])
        content_ids = [extract_pk(x) for x in add_content_units]

        if repository.error_on_reject:
            self._early_blocklist_check(repository, content_ids)

        if not repository.allow_package_substitution and repository.error_on_reject:
            remove_content_units = request.data.get("remove_content_units", [])
            if remove_content_units or "base_version" in request.data:
                return super().modify(request, pk)
            rvc = repository.latest_version().content
            packages = (
                python_models.PythonPackageContent.objects.filter(pk__in=content_ids)
                .exclude(pk__in=rvc)
                .values("filename")
            )
            conflicting_packages = python_models.PythonPackageContent.objects.filter(
                filename__in=packages, pk__in=rvc
            )
            if conflicting_packages.exists():
                raise ValidationError(
                    "Found duplicate packages being added with the same filename but different checksums. "  # noqa: E501
                    f"Existing conflicting packages: {conflicting_packages.values('filename', 'sha256', 'pk')}"  # noqa: E501
                )
        return super().modify(request, pk)

    def _early_blocklist_check(self, repository, content_ids):
        """
        Raise early if any added packages match a blocklist entry.
        """
        if not content_ids:
            return
        packages = python_models.PythonPackageContent.objects.filter(pk__in=content_ids).only(
            "filename", "name_normalized", "version"
        )
        blocked = repository.find_blocklisted_packages(packages)
        if blocked:
            raise ValidationError(
                "Blocklisted packages cannot be added to this repository: {}".format(
                    ", ".join(pkg.filename for pkg in blocked)
                )
            )

    @extend_schema(
        summary="Repair metadata",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=None)
    def repair_metadata(self, request, pk, **kwargs):
        """
        Trigger an asynchronous task to repair Python metadata. This task will repair metadata
        of all packages for the specified `Repository`, without creating a new `RepositoryVersion`.
        """
        repository = self.get_object()

        result = dispatch(
            tasks.repair,
            exclusive_resources=[repository],
            kwargs={"repository_pk": str(repository.pk)},
        )
        return core_viewsets.OperationPostponedResponse(result, request)

    @extend_schema(summary="Sync from remote", responses={202: AsyncOperationResponseSerializer})
    @action(detail=True, methods=["post"], serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk, **kwargs):
        """
        <!-- User-facing documentation, rendered as html-->
        Trigger an asynchronous task to sync python content. The sync task will retrieve Python
        content from the specified `Remote` and update the specified `Respository`, creating a
        new  `RepositoryVersion`.
        """
        repository = self.get_object()
        serializer = RepositorySyncURLSerializer(
            data=request.data, context={"request": request, "repository_pk": pk}
        )
        serializer.is_valid(raise_exception=True)
        remote = serializer.validated_data.get("remote", repository.remote)
        mirror = serializer.validated_data.get("mirror")

        result = dispatch(
            tasks.sync,
            exclusive_resources=[repository],
            shared_resources=[remote],
            kwargs={
                "remote_pk": str(remote.pk),
                "repository_pk": str(repository.pk),
                "mirror": mirror,
            },
        )
        return core_viewsets.OperationPostponedResponse(result, request)

    @extend_schema(
        summary="List packages",
        description=(
            "Return one row per distinct package name in a repository version "
            "(latest complete version if repository_version is omitted). "
            "Pagination count is the number of distinct packages, not files. "
            "Each row includes last_updated (newest membership among any rebuild), "
            "versions (logical version keys after rebuild-suffix strip, newest first), "
            "and latest_releases (newest rebuild per logical version, same order). "
            "set(versions) === set(latest_releases[].version)."
        ),
        parameters=[
            OpenApiParameter(
                name="repository_version",
                type=OpenApiTypes.URI,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                    "HREF or PRN of a version of this repository. "
                    "Defaults to the latest complete version."
                ),
            ),
            OpenApiParameter(
                name="name_normalized__istartswith",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    "Case-insensitive prefix on the PEP 503 normalized package name."
                    "At least 3 characters required."
                ),
            ),
            OpenApiParameter(
                name="name_normalized__icontains",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description=(
                    "Case-insensitive substring on the PEP 503 normalized package name."
                    "At least 3 characters required."
                ),
            ),
            OpenApiParameter(
                name="name__istartswith",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description="Case-insensitive prefix on the original package name.",
            ),
            OpenApiParameter(
                name="ordering",
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                many=True,
                description=(
                    "Order catalog rows. Allowed: name, name_normalized, last_updated. "
                    "Prefix with '-' for descending. Default is name."
                ),
            ),
        ],
        responses={
            200: inline_serializer(
                name="PaginatedPythonRepositoryPackageList",
                fields={
                    "count": IntegerField(),
                    "next": URLField(allow_null=True),
                    "previous": URLField(allow_null=True),
                    "results": python_serializers.PythonRepositoryPackageSerializer(many=True),
                },
            )
        },
    )
    @action(
        detail=True,
        methods=["get"],
        serializer_class=python_serializers.PythonRepositoryPackageSerializer,
    )
    def packages(self, request, pk):
        """List distinct packages in a repository version."""
        repository = self.get_object()
        repo_version = self._requested_repository_version(repository)
        content_qs = python_packages_in_version(repo_version)
        search_errors = {}
        try:
            name_normalized_prefix = normalize_name_normalized_search(
                request.query_params.get("name_normalized__istartswith")
            )
        except ValueError as exc:
            search_errors["name_normalized__istartswith"] = str(exc)
            name_normalized_prefix = None
        try:
            name_normalized_contains = normalize_name_normalized_search(
                request.query_params.get("name_normalized__icontains")
            )
        except ValueError as exc:
            search_errors["name_normalized__icontains"] = str(exc)
            name_normalized_contains = None
        if search_errors:
            raise ValidationError(search_errors)
        content_qs = apply_package_prefix_filters(
            content_qs,
            name_normalized_prefix=name_normalized_prefix,
            name_prefix=request.query_params.get("name__istartswith"),
            name_normalized_contains=name_normalized_contains,
        )
        try:
            ordering = normalize_package_index_ordering(request.query_params.getlist("ordering"))
        except ValueError as exc:
            raise ValidationError({"ordering": str(exc)}) from exc
        names_qs = distinct_package_names_qs(
            content_qs, repository, repo_version, ordering=ordering
        )
        page = self.paginate_queryset(names_qs)
        rows = assemble_package_index(
            content_qs,
            page if page is not None else list(names_qs),
            repository,
            repo_version,
        )
        serializer = self.get_serializer(rows, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @extend_schema(
        summary="Repository metrics",
        description=(
            "Distinct counts for Python package content in a repository version "
            "(latest complete version if repository_version is omitted). "
            "package_count is distinct name_normalized. version_count is distinct "
            "(name_normalized, base_version) after rebuild-suffix strip. build_count is "
            "distinct (name_normalized, full version). Counts are not filtered by "
            "packagetype. Until rebuild suffixes exist, version_count equals build_count."
        ),
        parameters=[
            OpenApiParameter(
                name="repository_version",
                type=OpenApiTypes.URI,
                location=OpenApiParameter.QUERY,
                required=False,
                description=(
                    "HREF or PRN of a version of this repository. "
                    "Defaults to the latest complete version."
                ),
            ),
        ],
        responses={200: python_serializers.PythonRepositoryMetricsSerializer},
    )
    @action(
        detail=True,
        methods=["get"],
        serializer_class=python_serializers.PythonRepositoryMetricsSerializer,
    )
    def metrics(self, request, pk):
        """Return package / version / build counts for a repository version."""
        repository = self.get_object()
        repo_version = self._requested_repository_version(repository)
        serializer = self.get_serializer(
            repository_metrics(python_packages_in_version(repo_version))
        )
        return Response(serializer.data)


class PythonBlocklistEntryViewSet(
    core_viewsets.NamedModelViewSet,
    CreateModelMixin,
    RetrieveModelMixin,
    ListModelMixin,
    DestroyModelMixin,
):
    """
    ViewSet for managing blocklist entries on a PythonRepository.

    Blocklist entries prevent packages from being added to the repository.
    Entries can match by package `name` (all versions), package `name` + `version`,
    or exact `filename`. Exactly one of `name` or `filename` must be provided.
    """

    endpoint_name = "blocklist_entries"
    router_lookup = "pythonblocklistentry"
    parent_viewset = PythonRepositoryViewSet
    parent_lookup_kwargs = {"repository_pk": "repository__pk"}
    serializer_class = python_serializers.PythonBlocklistEntrySerializer
    queryset = python_models.PythonBlocklistEntry.objects.all()
    filterset_fields = {"name": ["exact"], "version": ["exact", "isnull"], "filename": ["exact"]}
    ordering = ("-pulp_created",)

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_repository_model_or_domain_or_obj_perms:python.view_pythonrepository",  # noqa: E501
            },
            {
                "action": ["create", "destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repository_model_or_domain_or_obj_perms:python.modify_pythonrepository",
                    "has_repository_model_or_domain_or_obj_perms:python.view_pythonrepository",
                ],
            },
        ],
    }

    def get_serializer_context(self):
        """
        Inject the parent repository into the serializer context so that `validate()` can check for
        duplicate entries. The guard on `repository_pk` prevents errors during schema generation.
        """
        context = super().get_serializer_context()
        if self.kwargs.get("repository_pk"):
            context["repository"] = self.get_parent_object()
        return context


class PythonRepositoryVersionViewSet(core_viewsets.RepositoryVersionViewSet):
    """
    PythonRepositoryVersion represents a single Python repository version.
    """

    parent_viewset = PythonRepositoryViewSet

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_repository_model_or_domain_or_obj_perms:python.view_pythonrepository",  # noqa: E501
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repository_model_or_domain_or_obj_perms:python.delete_pythonrepository",
                    "has_repository_model_or_domain_or_obj_perms:python.view_pythonrepository",
                ],
            },
            {
                "action": ["repair"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repository_model_or_domain_or_obj_perms:python.repair_pythonrepository",
                    "has_repository_model_or_domain_or_obj_perms:python.view_pythonrepository",
                ],
            },
            {
                "action": ["scan"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repository_model_or_domain_or_obj_perms:python.view_pythonrepository",
                ],
            },
        ],
    }

    @extend_schema(
        summary="Generate vulnerability report", responses={202: AsyncOperationResponseSerializer}
    )
    @action(detail=True, methods=["post"], serializer_class=None)
    def scan(self, request, repository_pk, **kwargs):
        """
        Scan a repository version for vulnerabilities.
        """
        repository_version = self.get_object()
        func = (
            f"{tasks.get_repo_version_content.__module__}.{tasks.get_repo_version_content.__name__}"
        )
        task = dispatch(
            check_content,
            shared_resources=[repository_version.repository],
            args=[func, [repository_version.pk]],
        )
        return core_viewsets.OperationPostponedResponse(task, request)


class PythonDistributionViewSet(core_viewsets.DistributionViewSet, core_viewsets.RolesMixin):
    """
    <!-- User-facing documentation, rendered as html-->
    Pulp Python Distributions are used to distribute Python content from
    <a href="./#tag/Repositories:-Python">Python Repositories</a> or
    <a href="./#tag/Publications:-Pypi">Python Publications.</a> <b> Pulp Python
    Distributions should not be confused with "Python Distribution" as defined by the Python
    community.</b> In Pulp usage, Python content is referred to as <a
    href="./#tag/Content:-Packages">Python Package Content.</a>
    """

    endpoint_name = "pypi"
    queryset = python_models.PythonDistribution.objects.all()
    serializer_class = python_serializers.PythonDistributionSerializer
    queryset_filtering_required_permission = "python.view_pythondistribution"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "my_permissions"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_perms:python.add_pythondistribution",
                    "has_repo_or_repo_ver_param_model_or_domain_or_obj_perms:"
                    "python.view_pythonrepository",
                    "has_publication_param_model_or_domain_or_obj_perms:"
                    "python.view_pythonpublication",
                ],
            },
            {
                "action": ["retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_domain_or_obj_perms:python.view_pythondistribution",
            },
            {
                "action": ["update", "partial_update", "set_label", "unset_label"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_or_obj_perms:python.change_pythondistribution",
                    "has_model_or_domain_or_obj_perms:python.view_pythondistribution",
                    "has_repo_or_repo_ver_param_model_or_domain_or_obj_perms:"
                    "python.view_pythonrepository",
                    "has_publication_param_model_or_domain_or_obj_perms:"
                    "python.view_pythonpublication",
                ],
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_or_obj_perms:python.delete_pythondistribution",
                    "has_model_or_domain_or_obj_perms:python.view_pythondistribution",
                ],
            },
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_or_obj_perms:python.manage_roles_pythondistribution"
                ],
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {"roles": "python.pythondistribution_owner"},
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }
    LOCKED_ROLES = {
        "python.pythondistribution_creator": ["python.add_pythondistribution"],
        "python.pythondistribution_owner": [
            "python.view_pythondistribution",
            "python.change_pythondistribution",
            "python.delete_pythondistribution",
            "python.manage_roles_pythondistribution",
        ],
        "python.pythondistribution_viewer": ["python.view_pythondistribution"],
    }


class NormalizedNameFilter(CharFilter):
    """Filter that normalizes the input and queries name_normalized."""

    def filter(self, qs, value):
        if value:
            if isinstance(value, list):
                value = [canonicalize_name(v) for v in value]
            else:
                value = canonicalize_name(value)
        return super().filter(qs, value)


class NormalizedNameInFilter(drf_filters.BaseInFilter, NormalizedNameFilter):
    """In-filter that normalizes each input value and queries name_normalized."""


class VersionSpecifierFilter(CharFilter):
    """Filter that matches versions against a PEP 440 specifier string."""

    def filter(self, qs, value):
        if not value:
            return qs
        try:
            spec = SpecifierSet(value, prereleases=True)
        except InvalidSpecifier:
            raise ValidationError(
                {"version_specifier": f"Invalid PEP 440 version specifier: {value}"}
            )
        matching_pks = []
        for pk, version in qs.values_list("pk", self.field_name):
            if spec.contains(version):
                matching_pks.append(pk)
        return qs.filter(pk__in=matching_pks)


class PythonPackageContentFilter(core_viewsets.ContentFilter):
    """
    FilterSet for PythonPackageContent.
    """

    name = NormalizedNameFilter(field_name="name_normalized", lookup_expr="exact")
    name__in = NormalizedNameInFilter(field_name="name_normalized", lookup_expr="in")
    name__contains = CharFilter(field_name="name", lookup_expr="contains")
    version_specifier = VersionSpecifierFilter(
        field_name="version",
        help_text="Filter by PEP 440 version specifier (e.g., >=2.4,<3.0 or ~=1.26)",
    )
    collapse_builds = drf_filters.BooleanFilter(
        method="filter_collapse_builds",
        help_text=(
            "When true, collapse rebuilds of the same logical version: strip a trailing "
            f"suffix matching {BUILD_SUFFIX_PATTERN} from version, then keep one content unit "
            "per (name_normalized, base_version) with the latest pulp_created. "
            "Pass packagetype=sdist so wheel and sdist files are not collapsed together. "
            "Default false."
        ),
    )

    def filter_collapse_builds(self, qs, name, value):
        """Documented on the FilterSet; applied in the viewset after ordering.

        DISTINCT ON requires ORDER BY to start with the distinct columns. The
        viewset applies collapse after other filter backends so that ordering
        cannot break it.
        """
        return qs

    class Meta:
        model = python_models.PythonPackageContent
        fields = {
            "author": ["exact", "in", "contains"],
            "packagetype": ["exact", "in"],
            "requires_python": ["exact", "in", "contains"],
            "filename": ["exact", "in", "contains"],
            "keywords": ["in", "contains"],
            "sha256": ["exact", "in"],
            "version": ["exact", "gt", "lt", "gte", "lte"],
        }


class PythonPackageSingleArtifactContentUploadViewSet(
    core_viewsets.SingleArtifactContentUploadViewSet
):
    """
    <!-- User-facing documentation, rendered as html-->
    PythonPackageContent represents each individually installable Python package. In the Python
    ecosystem, this is called a <i>Python Distribution</i>, sometimes (ambiguously) refered to as a
    package. In Pulp Python, we refer to it as <i>PythonPackageContent</i>. Each
    PythonPackageContent corresponds to a single filename, for example
    `pulpcore-3.0.0rc1-py3-none-any.whl` or `pulpcore-3.0.0rc1.tar.gz`.

    """

    endpoint_name = "packages"
    queryset = python_models.PythonPackageContent.objects.all()
    serializer_class = python_serializers.PythonPackageContentSerializer
    minimal_serializer_class = python_serializers.MinimalPythonPackageContentSerializer
    filterset_class = PythonPackageContentFilter

    def filter_queryset(self, queryset):
        """Apply ``collapse_builds`` after other backends so DISTINCT ON stays valid."""
        queryset = super().filter_queryset(queryset)
        if getattr(self, "action", "") != "list":
            return queryset
        raw = self.request.query_params.get("collapse_builds")
        if raw is None or raw == "":
            return queryset
        if str(raw).lower() in ("true", "t", "yes", "y", "1"):
            return collapse_python_builds(queryset)
        return queryset

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_required_repo_perms_on_upload:python.modify_pythonrepository",
                    "has_required_repo_perms_on_upload:python.view_pythonrepository",
                    "has_upload_param_model_or_domain_or_obj_perms:core.change_upload",
                ],
            },
            {
                "action": ["upload"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_perms:python.upload_python_packages",
                ],
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }

    LOCKED_ROLES = {
        "python.python_package_uploader": [
            "python.upload_python_packages",
        ],
    }

    @extend_schema(
        summary="Synchronous Python package upload",
        request=python_serializers.PythonPackageContentUploadSerializer,
        responses={201: python_serializers.PythonPackageContentSerializer},
    )
    @action(
        detail=False,
        methods=["post"],
        serializer_class=python_serializers.PythonPackageContentUploadSerializer,
    )
    def upload(self, request, **kwargs):
        """
        Create a Python package.
        """
        serializer = self.get_serializer(data=request.data)

        with transaction.atomic():
            # Create the artifact
            serializer.is_valid(raise_exception=True)
            # Create the package
            serializer.save()

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class PackageProvenanceFilter(core_viewsets.ContentFilter):
    """
    FilterSet for PackageProvenance.
    """

    class Meta:
        model = python_models.PackageProvenance
        fields = {
            "package": ["exact", "in"],
            "sha256": ["exact", "in"],
        }


class PackageProvenanceViewSet(core_viewsets.NoArtifactContentUploadViewSet):
    """
    PackageProvenance represents a PEP 740 provenance object for a Python package.

    Use ?minimal=true to get a human readable representation of the provenance.
    """

    endpoint_name = "provenance"
    queryset = python_models.PackageProvenance.objects.all()
    serializer_class = python_serializers.PackageProvenanceSerializer
    filterset_class = PackageProvenanceFilter

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_required_repo_perms_on_upload:python.modify_pythonrepository",
                    "has_required_repo_perms_on_upload:python.view_pythonrepository",
                    "has_upload_param_model_or_domain_or_obj_perms:core.change_upload",
                ],
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }


class PackageYankViewSet(core_viewsets.ReadOnlyContentViewSet):
    """
    Read-only viewset for PackageYank content units (PEP 592).
    PackageYank markers indicate that a package version has been yanked in a repository.
    Use the /yank/ and /unyank/ PyPI endpoints to create or remove these markers.
    """

    endpoint_name = "yanks"
    queryset = python_models.PackageYank.objects.all()
    serializer_class = python_serializers.PackageYankSerializer

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }


class PythonRemoteViewSet(core_viewsets.RemoteViewSet, core_viewsets.RolesMixin):
    """
    <!-- User-facing documentation, rendered as html-->
    Python Remotes are representations of an <b>external repository</b> of Python content, eg.
    PyPI.  Fields include upstream repository config. Python Remotes are also used to `sync` from
    upstream repositories, and contains sync settings.

    """

    endpoint_name = "python"
    queryset = python_models.PythonRemote.objects.all()
    serializer_class = python_serializers.PythonRemoteSerializer
    queryset_filtering_required_permission = "python.view_pythonremote"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "my_permissions"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["create", "from_bandersnatch"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_domain_perms:python.add_pythonremote",
            },
            {
                "action": ["retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_domain_or_obj_perms:python.view_pythonremote",
            },
            {
                "action": ["update", "partial_update", "set_label", "unset_label"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_or_obj_perms:python.change_pythonremote",
                    "has_model_or_domain_or_obj_perms:python.view_pythonremote",
                ],
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_or_obj_perms:python.delete_pythonremote",
                    "has_model_or_domain_or_obj_perms:python.view_pythonremote",
                ],
            },
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": ["has_model_or_domain_or_obj_perms:python.manage_roles_pythonremote"],
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {"roles": "python.pythonremote_owner"},
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }
    LOCKED_ROLES = {
        "python.pythonremote_creator": ["python.add_pythonremote"],
        "python.pythonremote_owner": [
            "python.view_pythonremote",
            "python.change_pythonremote",
            "python.delete_pythonremote",
            "python.manage_roles_pythonremote",
        ],
        "python.pythonremote_viewer": ["python.view_pythonremote"],
    }

    @extend_schema(
        summary="Create from Bandersnatch",
        responses={201: python_serializers.PythonRemoteSerializer},
    )
    @action(
        detail=False,
        methods=["post"],
        serializer_class=python_serializers.PythonBanderRemoteSerializer,
    )
    def from_bandersnatch(self, request, **kwargs):
        """
        <!-- User-facing documentation, rendered as html-->
        Takes the fields specified in the Bandersnatch config and creates a Python Remote from it.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bander_config_file = serializer.validated_data.get("config")
        name = serializer.validated_data.get("name")
        policy = serializer.validated_data.get("policy")
        bander_config = BandersnatchConfig(Path(bander_config_file.file.name))
        data = {
            "name": name,
            "policy": policy,
            "url": bander_config.get("mirror", "master"),
            "download_concurrency": bander_config.get("mirror", "workers"),
        }
        enabled = bander_config.get("plugins", "enabled")
        enabled_all = "all" in enabled
        data["prereleases"] = not (enabled_all or "prerelease_release" in enabled)
        # TODO refactor to use a translation object
        plugin_filters = {  # plugin : (section_name, bander_option, pulp_option)
            "allowlist_project": ("allowlist", "packages", "includes"),
            "blocklist_project": ("blocklist", "packages", "excludes"),
            "regex_release_file_metadata": (
                "regex_release_file_metadata",
                "any:release_file.packagetype",
                "package_types",
            ),
            "latest_release": ("latest_release", "keep", "keep_latest_packages"),
            "exclude_platform": ("blocklist", "platforms", "exclude_platforms"),
        }
        for plugin, options in plugin_filters.items():
            if (enabled_all or plugin in enabled) and bander_config.has_option(
                options[0], options[1]
            ):
                data[options[2]] = bander_config.get(options[0], options[1]).split()
        remote = python_serializers.PythonRemoteSerializer(data=data, context={"request": request})
        remote.is_valid(raise_exception=True)
        remote.save()
        headers = self.get_success_headers(remote.data)
        return Response(remote.data, status=status.HTTP_201_CREATED, headers=headers)


@extend_schema_view(
    list=extend_schema(deprecated=True),
    add_role=extend_schema(deprecated=True),
    remove_role=extend_schema(deprecated=True),
    list_roles=extend_schema(deprecated=True),
    my_permissions=extend_schema(deprecated=True),
)
class PythonPublicationViewSet(core_viewsets.PublicationViewSet, core_viewsets.RolesMixin):
    """
    Python Publications refer to the Python Package content in a repository version, and include
    metadata about that content. [Deprecated] See
    https://pulpproject.org/pulp_python/docs/user/guides/host/#migrating-off-publications for more
    information.

    Use a repository or repository-version to serve content instead.

    """

    endpoint_name = "pypi"
    queryset = python_models.PythonPublication.objects.exclude(complete=False)
    serializer_class = python_serializers.PythonPublicationSerializer
    queryset_filtering_required_permission = "python.view_pythonpublication"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "my_permissions"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_perms:python.add_pythonpublication",
                    "has_repo_or_repo_ver_param_model_or_domain_or_obj_perms:"
                    "python.view_pythonrepository",
                ],
            },
            {
                "action": ["retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_domain_or_obj_perms:python.view_pythonpublication",
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_or_obj_perms:python.delete_pythonpublication",
                    "has_model_or_domain_or_obj_perms:python.view_pythonpublication",
                ],
            },
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_domain_or_obj_perms:python.manage_roles_pythonpublication"
                ],
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {"roles": "python.pythonpublication_owner"},
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }
    LOCKED_ROLES = {
        "python.pythonpublication_creator": ["python.add_pythonpublication"],
        "python.pythonpublication_owner": [
            "python.view_pythonpublication",
            "python.delete_pythonpublication",
            "python.manage_roles_pythonpublication",
        ],
        "python.pythonpublication_viewer": ["python.view_pythonpublication"],
    }

    @extend_schema(responses={202: AsyncOperationResponseSerializer}, deprecated=True)
    def create(self, request, **kwargs):
        """
        <!-- User-facing documentation, rendered as html-->
        Dispatches a publish task, which generates metadata that will be used by pip.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repository_version = serializer.validated_data.get("repository_version")

        # Safe because version OR repository is enforced by serializer.
        if not repository_version:
            repository = serializer.validated_data.get("repository")
            repository_version = RepositoryVersion.latest(repository)

        result = dispatch(
            tasks.publish,
            shared_resources=[repository_version.repository],
            kwargs={"repository_version_pk": str(repository_version.pk)},
        )
        return core_viewsets.OperationPostponedResponse(result, request)

    @extend_schema(deprecated=True)
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(deprecated=True)
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)
