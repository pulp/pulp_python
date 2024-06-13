from bandersnatch.configuration import BandersnatchConfig
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from pulpcore.plugin import viewsets as core_viewsets
from pulpcore.plugin.actions import ModifyRepositoryActionMixin
from pulpcore.plugin.models import RepositoryVersion
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.tasking import dispatch

from pulp_python.app import models as python_models
from pulp_python.app import serializers as python_serializers
from pulp_python.app import tasks


class PythonRepositoryViewSet(
    core_viewsets.RepositoryViewSet, ModifyRepositoryActionMixin, core_viewsets.RolesMixin
):
    """
    PythonRepository represents a single Python repository, to which content can be
    synced, added, or removed.
    """

    endpoint_name = 'python'
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
                "action": ["retrieve"],
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
                "action": ["modify"],
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

    @extend_schema(
        summary="Sync from remote",
        responses={202: AsyncOperationResponseSerializer}
    )
    @action(detail=True, methods=['post'], serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        <!-- User-facing documentation, rendered as html-->
        Trigger an asynchronous task to sync python content. The sync task will retrieve Python
        content from the specified `Remote` and update the specified `Respository`, creating a
        new  `RepositoryVersion`.
        """
        repository = self.get_object()
        serializer = RepositorySyncURLSerializer(
            data=request.data,
            context={'request': request, "repository_pk": pk}
        )
        serializer.is_valid(raise_exception=True)
        remote = serializer.validated_data.get('remote', repository.remote)
        mirror = serializer.validated_data.get('mirror')

        result = dispatch(
            tasks.sync,
            exclusive_resources=[repository],
            shared_resources=[remote],
            kwargs={
                'remote_pk': str(remote.pk),
                'repository_pk': str(repository.pk),
                'mirror': mirror
            }
        )
        return core_viewsets.OperationPostponedResponse(result, request)


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
                "condition":
                    "has_repository_model_or_domain_or_obj_perms:python.view_pythonrepository",
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
        ],
    }


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

    endpoint_name = 'pypi'
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


class PythonPackageContentFilter(core_viewsets.ContentFilter):
    """
    FilterSet for PythonPackageContent.
    """

    class Meta:
        model = python_models.PythonPackageContent
        fields = {
            'name': ['exact', 'in'],
            'author': ['exact', 'in'],
            'packagetype': ['exact', 'in'],
            'requires_python': ['exact', 'in', "contains"],
            'filename': ['exact', 'in', 'contains'],
            'keywords': ['in', 'contains'],
            'sha256': ['exact', 'in'],
            'version': ['exact', 'gt', 'lt', 'gte', 'lte']
        }


class PythonPackageSingleArtifactContentUploadViewSet(
        core_viewsets.SingleArtifactContentUploadViewSet):
    """
    <!-- User-facing documentation, rendered as html-->
    PythonPackageContent represents each individually installable Python package. In the Python
    ecosystem, this is called a <i>Python Distribution</i>, sometimes (ambiguously) refered to as a
    package. In Pulp Python, we refer to it as <i>PythonPackageContent</i>. Each
    PythonPackageContent corresponds to a single filename, for example
    `pulpcore-3.0.0rc1-py3-none-any.whl` or `pulpcore-3.0.0rc1.tar.gz`.

    """

    endpoint_name = 'packages'
    queryset = python_models.PythonPackageContent.objects.all()
    serializer_class = python_serializers.PythonPackageContentSerializer
    minimal_serializer_class = python_serializers.MinimalPythonPackageContentSerializer
    filterset_class = PythonPackageContentFilter

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


class PythonRemoteViewSet(core_viewsets.RemoteViewSet, core_viewsets.RolesMixin):
    """
    <!-- User-facing documentation, rendered as html-->
    Python Remotes are representations of an <b>external repository</b> of Python content, eg.
    PyPI.  Fields include upstream repository config. Python Remotes are also used to `sync` from
    upstream repositories, and contains sync settings.

    """

    endpoint_name = 'python'
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
    @action(detail=False, methods=["post"],
            serializer_class=python_serializers.PythonBanderRemoteSerializer)
    def from_bandersnatch(self, request):
        """
        <!-- User-facing documentation, rendered as html-->
        Takes the fields specified in the Bandersnatch config and creates a Python Remote from it.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bander_config_file = serializer.validated_data.get("config")
        name = serializer.validated_data.get("name")
        policy = serializer.validated_data.get("policy")
        bander_config = BandersnatchConfig(bander_config_file.file.name).config
        data = {"name": name,
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
            if (enabled_all or plugin in enabled) and \
                    bander_config.has_option(options[0], options[1]):
                data[options[2]] = bander_config.get(options[0], options[1]).split()
        remote = python_serializers.PythonRemoteSerializer(data=data, context={"request": request})
        remote.is_valid(raise_exception=True)
        remote.save()
        headers = self.get_success_headers(remote.data)
        return Response(remote.data, status=status.HTTP_201_CREATED, headers=headers)


class PythonPublicationViewSet(core_viewsets.PublicationViewSet, core_viewsets.RolesMixin):
    """
    <!-- User-facing documentation, rendered as html-->
    Python Publications refer to the Python Package content in a repository version, and include
    metadata about that content.

    """

    endpoint_name = 'pypi'
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

    @extend_schema(
        responses={202: AsyncOperationResponseSerializer}
    )
    def create(self, request):
        """
        <!-- User-facing documentation, rendered as html-->
        Dispatches a publish task, which generates metadata that will be used by pip.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repository_version = serializer.validated_data.get('repository_version')

        # Safe because version OR repository is enforced by serializer.
        if not repository_version:
            repository = serializer.validated_data.get('repository')
            repository_version = RepositoryVersion.latest(repository)

        result = dispatch(
            tasks.publish,
            shared_resources=[repository_version.repository],
            kwargs={
                'repository_version_pk': str(repository_version.pk)
            }
        )
        return core_viewsets.OperationPostponedResponse(result, request)
