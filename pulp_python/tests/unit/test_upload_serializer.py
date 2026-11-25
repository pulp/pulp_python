import hashlib
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile

from pulpcore.plugin.models import Artifact

from pulp_python.app.pypi.serializers import PackageUploadSerializer


def test_upload_keeps_package_filename_when_saving_the_artifact_renames_the_file():
    filename = "shelf_reader-0.1-py2-none-any.whl"
    payload = b"not a real wheel"
    upload = SimpleUploadedFile(filename, payload)
    artifact = mock.Mock()
    # The Google Cloud Storage backend renames the file when the artifact is saved.
    artifact.save.side_effect = lambda: setattr(upload, "name", "artifact/ab/cdef")

    serializer = PackageUploadSerializer(
        data={"content": upload, "sha256_digest": hashlib.sha256(payload).hexdigest()}
    )
    with mock.patch.object(Artifact, "init_and_validate", return_value=artifact):
        assert serializer.is_valid(), serializer.errors

    artifact.save.assert_called_once()
    assert serializer.validated_data["content"] == (artifact, filename)
