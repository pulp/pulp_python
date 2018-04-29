import pkginfo
import tempfile, shutil, os

from gettext import gettext as _

from django.db import transaction
from pulpcore.plugin import viewsets as platform
from pulpcore.plugin.models import Repository, RepositoryVersion, Artifact
from rest_framework import decorators, status, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from pulp_python.app import models as python_models
from pulp_python.app import serializers as python_serializers
from pulp_python.app.tasks import sync, publish
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


class PythonPackageContentViewSet(platform.ContentViewSet):
    """
    The ViewSet for PythonPackageContent.
    """

    endpoint_name = 'python/packages'
    queryset = python_models.PythonPackageContent.objects.all()
    serializer_class = python_serializers.PythonPackageContentSerializer

    @transaction.atomic
    def create(self, request):
        try:
            artifact = self.get_resource(request.data['artifact'], Artifact)
        except KeyError:
            raise serializers.ValidationError(detail={'artifact': _('This field is required')})

        filename = request.data['filename']

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
            raise serializers.ValidationError(_("Extension on {} is not a valid python"
                                                " extension (.whl, .exe, .egg, .tar.gz, .tar.bz2, "
                                                ".zip)").format(filename))

        data = parse_project_metadata(vars(metadata))
        data['classifiers'] = [{'name': classifier} for classifier in metadata.classifiers]
        data['packagetype'] = metadata.packagetype
        data['version'] = metadata.version
        data['filename'] = filename
        data['artifact'] = request.data['artifact']

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        headers = self.get_success_headers(request.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class PythonRemoteViewSet(platform.RemoteViewSet):
    """
    A ViewSet for PythonRemote.

    Similar to the PythonContentViewSet above, define endpoint_name,
    queryset and serializer, at a minimum.
    """

    endpoint_name = 'python'
    queryset = python_models.PythonRemote.objects.all()
    serializer_class = python_serializers.PythonRemoteSerializer

    @decorators.detail_route(methods=('post',))
    def sync(self, request, pk):
        """
        Dispatches a sync task.
        """
        remote = self.get_object()
        repository = self.get_resource(request.data['repository'], Repository)

        async_result = sync.apply_async_with_reservation(
            [repository, remote],
            kwargs={
                'remote_pk': remote.pk,
                'repository_pk': repository.pk
            }
        )
        return platform.OperationPostponedResponse(async_result, request)


class PythonPublisherViewSet(platform.PublisherViewSet):
    """
    A ViewSet for PythonPublisher.

    Similar to the PythonContentViewSet above, define endpoint_name,
    queryset and serializer, at a minimum.
    """

    endpoint_name = 'python'
    queryset = python_models.PythonPublisher.objects.all()
    serializer_class = python_serializers.PythonPublisherSerializer

    @decorators.detail_route(methods=('post',))
    def publish(self, request, pk):
        """
        Dispatches a publish task.
        """
        publisher = self.get_object()
        repository = None
        repository_version = None

        if 'repository' not in request.data and 'repository_version' not in request.data:
            raise ValidationError("Either the 'repository' or 'repository_version' "
                                  "need to be specified.")

        if 'repository' in request.data and request.data['repository']:
            repository = self.get_resource(request.data['repository'], Repository)

        if 'repository_version' in request.data and request.data['repository_version']:
            repository_version = self.get_resource(request.data['repository_version'],
                                                   RepositoryVersion)

        if repository and repository_version:
            raise ValidationError("Either the 'repository' or 'repository_version' "
                                  "can be specified - not both.")

        if not repository_version:
            repository_version = RepositoryVersion.latest(repository)

        result = publish.apply_async_with_reservation(
            [repository_version.repository, publisher],
            kwargs={
                'publisher_pk': publisher.pk,
                'repository_version_pk': repository_version.pk
            }
        )
        return platform.OperationPostponedResponse(result, request)
