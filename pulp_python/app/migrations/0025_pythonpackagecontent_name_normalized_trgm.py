from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import AddIndexConcurrently, TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):
    atomic = False  # required for CONCURRENTLY

    dependencies = [
        ("python", "0024_pythonrepository_error_on_reject"),
    ]

    operations = [
        TrigramExtension(),
        AddIndexConcurrently(
            model_name="pythonpackagecontent",
            index=GinIndex(
                fields=["name_normalized"],
                name="python_name_normalized_trgm",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
