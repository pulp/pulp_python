import re

from django.db import migrations, models, transaction


def populate_name_normalized(apps, schema_editor):
    """Populate name_normalized for existing PythonPackageContent rows."""
    PythonPackageContent = apps.get_model("python", "PythonPackageContent")
    package_bulk = []
    normalize_re = re.compile(r"[-_.]+")

    for package in PythonPackageContent.objects.only("pk", "name").iterator():
        package.name_normalized = normalize_re.sub("-", package.name).lower()
        package_bulk.append(package)
        if len(package_bulk) == 100000:
            with transaction.atomic():
                PythonPackageContent.objects.bulk_update(package_bulk, ["name_normalized"])
                package_bulk = []
    if package_bulk:
        with transaction.atomic():
            PythonPackageContent.objects.bulk_update(package_bulk, ["name_normalized"])


class Migration(migrations.Migration):

    dependencies = [
        ("python", "0019_create_missing_metadata_artifacts"),
    ]

    operations = [
        migrations.AddField(
            model_name="pythonpackagecontent",
            name="name_normalized",
            field=models.TextField(db_index=True, default=""),
        ),
        migrations.RunPython(populate_name_normalized, migrations.RunPython.noop, elidable=True),
    ]
