import os
from gettext import gettext as _
import pkginfo
import shutil
import tempfile

from django.db import transaction
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from pulpcore.plugin import viewsets as platform
from pulpcore.plugin.models import Artifact, RepositoryVersion
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.tasking import enqueue_with_reservation

from pulp_python.app import models as python_models
from pulp_python.app import serializers as python_serializers
from pulp_python.app import tasks
from pulp_python.app.utils import parse_project_metadata

DIST_EXTENSIONS = {
    ".whl": "bdist_wheel",
    ".exe": "bdist_wininst",
    ".egg": "bdist_egg",
    ".tar.bz2": "sdist",
    ".tar.gz": "sdist",
    ".zip": "sdist",
}

DIST_TYPES = {
    "bdist_wheel": pkginfo.Wheel,
    "bdist_wininst": pkginfo.Distribution,
    "bdist_egg": pkginfo.BDist,
    "sdist": pkginfo.SDist,
}


class PythonPackageContentFilter(platform.ContentFilter):
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


class PythonPackageContentViewSet(platform.ContentViewSet):
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

    @transaction.atomic
    def create(self, request):
        """
        <!-- User-facing documentation, rendered as html-->
        This endpoint is part of the <a href="workflows/upload.html">Upload workflow.</a> Create
        a PythonPackageContent here by specifying an uploaded Artifact. `pulp-python` will inspect
        parse the metadata directly from the file.

        """
        try:
            artifact = self.get_resource(request.data['_artifact'], Artifact)
        except KeyError:
            raise serializers.ValidationError(detail={'_artifact': _('This field is required')})

        try:
            filename = request.data['filename']
        except KeyError:
            raise serializers.ValidationError(detail={'filename': _('This field is required')})

        # iterate through extensions since splitext does not support things like .tar.gz
        for ext, packagetype in DIST_EXTENSIONS.items():
            if filename.endswith(ext):

                # Copy file to a temp directory under the user provided filename, we do this
                # because pkginfo validates that the filename has a valid extension before
                # reading it
                with tempfile.TemporaryDirectory() as td:
                    temp_path = os.path.join(td, filename)
                    shutil.copy2(artifact.file.path, temp_path)
                    metadata = DIST_TYPES[packagetype](temp_path)
                    metadata.packagetype = packagetype
                    break
        else:
            raise serializers.ValidationError(_(
                "Extension on {} is not a valid python extension "
                "(.whl, .exe, .egg, .tar.gz, .tar.bz2, .zip)").format(filename)
            )

        data = parse_project_metadata(vars(metadata))
        data['classifiers'] = [{'name': classifier} for classifier in metadata.classifiers]
        data['packagetype'] = metadata.packagetype
        data['version'] = metadata.version
        data['filename'] = filename
        data['_artifact'] = request.data['_artifact']
        data['_relative_path'] = filename

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        headers = self.get_success_headers(request.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class PythonRemoteFilter(platform.RemoteFilter):
    """
    FilterSet for PythonRemote.
    """

    class Meta:
        model = python_models.PythonRemote
        fields = []


class PythonRemoteViewSet(platform.RemoteViewSet):
    """
    <!-- User-facing documentation, rendered as html-->
    Python Remotes are representations of an <b>external repository</b> of Python content, eg.
    PyPI.  Fields include upstream repository config. Python Remotes are also used to `sync` from
    upstream repositories, and contains sync settings.

    """

    endpoint_name = 'python'
    queryset = python_models.PythonRemote.objects.all()
    serializer_class = python_serializers.PythonRemoteSerializer
    filterset_class = PythonRemoteFilter

    @swagger_auto_schema(
        responses={202: AsyncOperationResponseSerializer}
    )
    @action(detail=True, methods=('post',), serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        <!-- User-facing documentation, rendered as html-->
        Trigger an asynchronous task to sync python content. The sync task will retrieve Python
        content from the specified `Remote` and " update the specified `Respository`, creating a
        new  `RepositoryVersion`.
        """
        remote = self.get_object()
        serializer = RepositorySyncURLSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data.get('repository')
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
        return platform.OperationPostponedResponse(result, request)


class PythonPublicationViewSet(platform.PublicationViewSet):
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
        return platform.OperationPostponedResponse(result, request)
