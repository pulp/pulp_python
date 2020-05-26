from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action

from pulpcore.plugin import viewsets as core_viewsets
from pulpcore.plugin.models import RepositoryVersion
from pulpcore.plugin.actions import ModifyRepositoryActionMixin
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.tasking import enqueue_with_reservation

from pulp_python.app import models as python_models
from pulp_python.app import serializers as python_serializers
from pulp_python.app import tasks


class PythonRepositoryViewSet(core_viewsets.RepositoryViewSet, ModifyRepositoryActionMixin):
    """
    A ViewSet for PythonRepository.
    """

    endpoint_name = 'python'
    queryset = python_models.PythonRepository.objects.all()
    serializer_class = python_serializers.PythonRepositorySerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to sync Python content.",
        operation_summary="Sync from remote",
        responses={202: AsyncOperationResponseSerializer}
    )
    @action(detail=True, methods=['post'], serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        <!-- User-facing documentation, rendered as html-->
        Trigger an asynchronous task to sync python content. The sync task will retrieve Python
        content from the specified `Remote` and " update the specified `Respository`, creating a
        new  `RepositoryVersion`.
        """
        repository = self.get_object()
        serializer = RepositorySyncURLSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        remote = serializer.validated_data.get('remote')
        mirror = serializer.validated_data.get('mirror')

        result = enqueue_with_reservation(
            tasks.sync,
            [repository, remote],
            kwargs={
                'remote_pk': remote.pk,
                'repository_pk': repository.pk,
                'mirror': mirror
            }
        )
        return core_viewsets.OperationPostponedResponse(result, request)


class PythonRepositoryVersionViewSet(core_viewsets.RepositoryVersionViewSet):
    """
    PythonRepositoryVersion represents a single Python repository version.
    """

    parent_viewset = PythonRepositoryViewSet


class PythonDistributionViewSet(core_viewsets.BaseDistributionViewSet):
    """
    <!-- User-facing documentation, rendered as html-->
    Pulp Python Distributions are used to distribute
    <a href="../restapi.html#tag/publications">Python Publications.</a> <b> Pulp Python
    Distributions should not be confused with "Python Distribution" as defined by the Python
    community.</b> In Pulp usage, Python content is refered to as <a
    href="../restapi.html#tag/content">Python Package Content.</a>
    """

    endpoint_name = 'pypi'
    queryset = python_models.PythonDistribution.objects.all()
    serializer_class = python_serializers.PythonDistributionSerializer


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
            'filename': ['exact', 'in', 'contains'],
            'keywords': ['in', 'contains'],
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


class PythonRemoteViewSet(core_viewsets.RemoteViewSet):
    """
    <!-- User-facing documentation, rendered as html-->
    Python Remotes are representations of an <b>external repository</b> of Python content, eg.
    PyPI.  Fields include upstream repository config. Python Remotes are also used to `sync` from
    upstream repositories, and contains sync settings.

    """

    endpoint_name = 'python'
    queryset = python_models.PythonRemote.objects.all()
    serializer_class = python_serializers.PythonRemoteSerializer


class PythonPublicationViewSet(core_viewsets.PublicationViewSet):
    """
    <!-- User-facing documentation, rendered as html-->
    Python Publications refer to the Python Package content in a repository version, and include
    metadata about that content.

    """

    endpoint_name = 'pypi'
    queryset = python_models.PythonPublication.objects.all()
    serializer_class = python_serializers.PythonPublicationSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to publish python content.",
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

        result = enqueue_with_reservation(
            tasks.publish,
            [repository_version.repository],
            kwargs={
                'repository_version_pk': repository_version.pk
            }
        )
        return core_viewsets.OperationPostponedResponse(result, request)
