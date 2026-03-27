from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("python", "0020_pythonpackagecontent_name_normalized"),
    ]

    operations = [
        migrations.AddField(
            model_name="pythonrepository",
            name="allow_package_substitution",
            field=models.BooleanField(default=True),
        ),
    ]
