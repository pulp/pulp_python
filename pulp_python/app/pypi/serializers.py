from gettext import gettext as _

from rest_framework import serializers


class SummarySerializer(serializers.Serializer):
    """
    A Serializer for summary information of an index.
    """

    projects = serializers.IntegerField(help_text=_("Number of Python projects in index"))
    releases = serializers.IntegerField(help_text=_("Number of Python distributions in index"))
    files = serializers.IntegerField(help_text=_("Number of files for all distributions in index"))


class PackageMetadataSerializer(serializers.Serializer):
    """
    A Serializer for a package's metadata.
    """

    last_serial = serializers.IntegerField(help_text=_("Cache value from last PyPI sync"))
    info = serializers.JSONField(help_text=_("Core metadata of the package"))
    releases = serializers.JSONField(help_text=_("List of all the releases of the package"))
    urls = serializers.JSONField()
