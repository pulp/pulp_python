# Generated by Django 2.2.3 on 2020-08-12 22:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("python", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="pythonpackagecontent",
            name="python_version",
            field=models.TextField(default=""),
            preserve_default=False,
        ),
    ]
