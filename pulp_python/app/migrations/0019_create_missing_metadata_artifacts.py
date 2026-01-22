# Generated manually on 2025-12-15 14:00 for creating missing metadata artifacts
from django.db import migrations


def set_metadata_sha256_null(apps, schema_editor):
    # We can't easily create the metadata artifacts in this migration, so just set the metadata_sha256
    # to null and we will introduce a new command later to create them.
    PythonPackageContent = apps.get_model("python", "PythonPackageContent")
    PythonPackageContent.objects.filter(metadata_sha256__isnull=False).update(metadata_sha256=None)


class Migration(migrations.Migration):

    dependencies = [
        ("python", "0018_packageprovenance"),
    ]

    operations = [
        migrations.RunPython(
            set_metadata_sha256_null,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
