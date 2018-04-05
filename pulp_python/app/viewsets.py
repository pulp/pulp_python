from gettext import gettext as _

from pulpcore.plugin import viewsets as platform
from pulpcore.plugin.models import Repository, RepositoryVersion
from rest_framework import decorators
from rest_framework.exceptions import ValidationError

from pulp_python.app import models as python_models
from pulp_python.app import serializers as python_serializers
from pulp_python.app.tasks import sync, publish


class PythonPackageContentViewSet(platform.ContentViewSet):
    """
    The ViewSet for PythonPackageContent.
    """

    endpoint_name = 'python'
    queryset = python_models.PythonPackageContent.objects.all()
    serializer_class = python_serializers.PythonPackageContentSerializer


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

        if not remote.feed_url:
            raise ValidationError(detail=_("A remote must have a 'feed_url' attribute to sync."))

        async_result = sync.apply_async_with_reservation(
            [repository, remote],
            kwargs={
                'remote_pk': remote.pk,
                'repository_pk': repository.pk
            }
        )
        return platform.OperationPostponedResponse([async_result], request)


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
        return platform.OperationPostponedResponse([result], request)
