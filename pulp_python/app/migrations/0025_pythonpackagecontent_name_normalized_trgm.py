import django.contrib.postgres.indexes
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("python", "0024_pythonrepository_error_on_reject"),
    ]

    operations = [
        TrigramExtension(),
        migrations.AddIndex(
            model_name="pythonpackagecontent",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["name_normalized"],
                name="python_name_normalized_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
