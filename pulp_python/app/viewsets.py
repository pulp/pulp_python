from gettext import gettext as _

from pulpcore.plugin import viewsets as platform
from pulpcore.plugin.models import Repository
from rest_framework import decorators
from rest_framework.exceptions import ValidationError

from . import models, serializers, tasks


class PythonPackageContentViewSet(platform.ContentViewSet):
    """
    The ViewSet for PythonPackageContent.
    """

    endpoint_name = 'python'
    queryset = models.PythonPackageContent.objects.all()
    serializer_class = serializers.PythonPackageContentSerializer


class PythonImporterViewSet(platform.ImporterViewSet):
    """
    A ViewSet for PythonImporter.

    Similar to the PythonContentViewSet above, define endpoint_name,
    queryset and serializer, at a minimum.
    """

    endpoint_name = 'python'
    queryset = models.PythonImporter.objects.all()
    serializer_class = serializers.PythonImporterSerializer

    @decorators.detail_route(methods=('post',))
    def sync(self, request, pk):
        """
        Dispatches a sync task.
        """
        importer = self.get_object()
        repository = self.get_resource(request.data['repository'], Repository)

        if not importer.feed_url:
            raise ValidationError(detail=_("An importer must have a 'feed_url' attribute to sync."))

        async_result = tasks.sync.apply_async_with_reservation(
            [repository, importer],
            kwargs={
                'importer_pk': importer.pk,
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
    queryset = models.PythonPublisher.objects.all()
    serializer_class = serializers.PythonPublisherSerializer
