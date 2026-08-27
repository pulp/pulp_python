from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("python", "0024_pythonrepository_error_on_reject"),
    ]

    operations = [
        migrations.AddField(
            model_name="pythonremote",
            name="vulnerabilities",
            field=models.BooleanField(default=False),
        ),
    ]
