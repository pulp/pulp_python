# Generated by Django 4.2.10 on 2024-07-08 00:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('python', '0013_add_rbac_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='pythonpackagecontent',
            name='dynamic',
            field=models.JSONField(null=True),
        ),
        migrations.AddField(
            model_name='pythonpackagecontent',
            name='provides_extra',
            field=models.JSONField(null=True),
        ),
    ]