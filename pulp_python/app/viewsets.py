from gettext import gettext as _

from pulpcore.plugin import viewsets as platform
from rest_framework import decorators

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
        importer = self.get_object()
        if not importer.feed_url:
            # TODO(asmacdo) make sure this raises a 400
            raise ValueError(_("An importer must have a 'feed_url' attribute to sync."))

        async_result = tasks.sync.apply_async_with_reservation(
            platform.tags.RESOURCE_REPOSITORY_TYPE, str(importer.repository.pk),
            kwargs={'importer_pk': importer.pk}
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
