# -*- coding: utf-8 -*-
# Generated by Django 1.11.28 on 2020-02-08 05:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0266_userprofile_theme'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='theme',
            field=models.CharField(default='default', max_length=128),
        ),
    ]
