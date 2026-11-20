import hashlib
from unittest import mock

from django.core.files.base import ContentFile
from django.test import TestCase

from pulpcore.plugin.files import PulpTemporaryUploadedFile
from pulpcore.plugin.util import get_domain

from pulp_python.app.pypi.serializers import PackageUploadSerializer


class TestPackageUploadSerializer(TestCase):
    def test_filename_survives_a_storage_that_renames_the_upload(self):
        filename = "shelf_reader-0.1-py2-none-any.whl"
        payload = b"not a real wheel"
        storage = get_domain().get_storage()
        original_save = storage._save

        def save_and_rename(name, content):
            # The Google Cloud Storage backend renames the saved file to its storage path.
            saved = original_save(name, content)
            content.name = saved
            return saved

        serializer = PackageUploadSerializer(
            data={
                "content": PulpTemporaryUploadedFile.from_file(ContentFile(payload, name=filename)),
                "sha256_digest": hashlib.sha256(payload).hexdigest(),
            }
        )
        with mock.patch.object(storage, "_save", side_effect=save_and_rename):
            self.assertTrue(serializer.is_valid(), serializer.errors)

        artifact, uploaded_filename = serializer.validated_data["content"]
        self.assertEqual(uploaded_filename, filename)
        self.assertNotEqual(artifact.file.name, filename)
