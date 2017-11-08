from rest_framework import serializers
from pulpcore.plugin import serializers as platform

from . import models


class PythonContentSerializer(platform.ContentSerializer):
    """
    A Serializer for PythonContent.

    Add serializers for the new fields defined in PythonContent and
    add those fields to the Meta class keeping fields from the parent class as well.

    For example::

    field1 = serializers.TextField()
    field2 = serializers.IntegerField()
    field3 = serializers.CharField()

    class Meta:
        fields = platform.ContentSerializer.Meta.fields + ('field1', 'field2', 'field3')
        model = models.PythonContent
    """

    class Meta:
        fields = platform.ContentSerializer.Meta.fields
        model = models.PythonContent


class PythonImporterSerializer(platform.ImporterSerializer):
    """
    A Serializer for PythonImporter.

    Add any new fields if defined on PythonImporter.
    Similar to the example above, in PythonContentSerializer.
    Additional validators can be added to the parent validators list

    For example::

    class Meta:
        validators = platform.ImporterSerializer.Meta.validators + [myValidator1, myValidator2]
    """

    class Meta:
        fields = platform.ImporterSerializer.Meta.fields
        model = models.PythonImporter
        validators = platform.ImporterSerializer.Meta.validators


class PythonPublisherSerializer(platform.PublisherSerializer):
    """
    A Serializer for PythonPublisher.

    Add any new fields if defined on PythonPublisher.
    Similar to the example above, in PythonContentSerializer.
    Additional validators can be added to the parent validators list

    For example::

    class Meta:
        validators = platform.PublisherSerializer.Meta.validators + [myValidator1, myValidator2]
    """

    class Meta:
        fields = platform.PublisherSerializer.Meta.fields
        model = models.PythonPublisher
        validators = platform.PublisherSerializer.Meta.validators
