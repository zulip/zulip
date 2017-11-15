# -*- coding: utf-8 -*-
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0004_add_subgroup'),
    ]

    operations = [
        migrations.AlterField(
            model_name='installationcount',
            name='interval',
            field=models.CharField(max_length=8),
        ),
        migrations.AlterField(
            model_name='installationcount',
            name='property',
            field=models.CharField(max_length=32),
        ),
        migrations.AlterField(
            model_name='realmcount',
            name='interval',
            field=models.CharField(max_length=8),
        ),
        migrations.AlterField(
            model_name='realmcount',
            name='property',
            field=models.CharField(max_length=32),
        ),
        migrations.AlterField(
            model_name='streamcount',
            name='interval',
            field=models.CharField(max_length=8),
        ),
        migrations.AlterField(
            model_name='streamcount',
            name='property',
            field=models.CharField(max_length=32),
        ),
        migrations.AlterField(
            model_name='usercount',
            name='interval',
            field=models.CharField(max_length=8),
        ),
        migrations.AlterField(
            model_name='usercount',
            name='property',
            field=models.CharField(max_length=32),
        ),
    ]
