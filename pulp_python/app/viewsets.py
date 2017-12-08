from pulpcore.plugin import viewsets as platform

from . import models, serializers


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


class PythonPublisherViewSet(platform.PublisherViewSet):
    """
    A ViewSet for PythonPublisher.

    Similar to the PythonContentViewSet above, define endpoint_name,
    queryset and serializer, at a minimum.
    """

    endpoint_name = 'python'
    queryset = models.PythonPublisher.objects.all()
    serializer_class = serializers.PythonPublisherSerializer
