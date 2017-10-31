from pulpcore.plugin import viewsets as platform

from . import models, serializers


class PythonContentViewSet(platform.ContentViewSet):
    """
    A ViewSet for PythonContent.

    Define endpoint name which will appear in the API endpoint for this content type.
    For example::
        http://pulp.example.com/api/v3/content/python/

    Also specify queryset and serializer for PythonContent.
    """

    endpoint_name = 'python'
    queryset = models.PythonContent.objects.all()
    serializer_class = serializers.PythonContentSerializer


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
