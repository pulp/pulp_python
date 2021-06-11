# Generated by Django 2.2.23 on 2021-06-10 01:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('python', '0007_pythonpackagecontent_mv-2-1'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pythonpackagecontent',
            name='filename',
            field=models.TextField(db_index=True),
        ),
        migrations.AlterField(
            model_name='pythonpackagecontent',
            name='sha256',
            field=models.CharField(db_index=True, max_length=64, unique=True),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterUniqueTogether(
                    name='pythonpackagecontent',
                    unique_together={('sha256',)},
                ),
            ],
        ),
    ]