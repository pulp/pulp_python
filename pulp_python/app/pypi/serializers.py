import logging
from gettext import gettext as _

from rest_framework import serializers
from pulp_python.app.tasks.upload import DIST_EXTENSIONS
from pulpcore.plugin.models import Artifact
from django.db.utils import IntegrityError

log = logging.getLogger(__name__)


class SummarySerializer(serializers.Serializer):
    """
    A Serializer for summary information of an index.
    """

    projects = serializers.IntegerField(help_text=_("Number of Python projects in index"))
    releases = serializers.IntegerField(
        help_text=_("Number of Python distribution releases in index")
    )
    files = serializers.IntegerField(help_text=_("Number of files for all distributions in index"))


class PackageMetadataSerializer(serializers.Serializer):
    """
    A Serializer for a package's metadata.
    """

    last_serial = serializers.IntegerField(help_text=_("Cache value from last PyPI sync"))
    info = serializers.JSONField(help_text=_("Core metadata of the package"))
    releases = serializers.JSONField(help_text=_("List of all the releases of the package"))
    urls = serializers.JSONField()


class PackageUploadSerializer(serializers.Serializer):
    """
    A Serializer for Python packages being uploaded to the index.
    """

    content = serializers.FileField(
        help_text=_("A Python package release file to upload to the index."),
        required=True,
        write_only=True,
    )
    action = serializers.CharField(
        help_text=_("Defaults to `file_upload`, don't change it or request will fail!"),
        default="file_upload",
        source=":action"
    )
    sha256_digest = serializers.CharField(
        help_text=_("SHA256 of package to validate upload integrity."),
        required=True,
        min_length=64,
        max_length=64,
    )

    def validate(self, data):
        """Validates the request."""
        action = data.get(":action")
        if action != "file_upload":
            raise serializers.ValidationError(
                _("We do not support the :action {}").format(action)
            )
        file = data.get("content")
        for ext, packagetype in DIST_EXTENSIONS.items():
            if file.name.endswith(ext):
                break
        else:
            raise serializers.ValidationError(_(
                "Extension on {} is not a valid python extension "
                "(.whl, .exe, .egg, .tar.gz, .tar.bz2, .zip)").format(file.name)
            )
        sha256 = data.get("sha256_digest")
        digests = {"sha256": sha256} if sha256 else None
        artifact = Artifact.init_and_validate(file, expected_digests=digests)
        try:
            artifact.save()
        except IntegrityError:
            artifact = Artifact.objects.get(sha256=artifact.sha256)
            artifact.touch()
            log.info(f"Artifact for {file.name} already existed in database")
        data["content"] = (artifact, file.name)
        return data


class PackageUploadTaskSerializer(serializers.Serializer):
    """
    A Serializer for responding to a package upload task.
    """

    session = serializers.CharField()
    task = serializers.CharField()
    task_start_time = serializers.DateTimeField()
