# -*- coding: utf-8 -*-
# Generated by Django 1.11.26 on 2020-01-27 04:32
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0013_remove_anomaly'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='fillstate',
            name='last_modified',
        ),
    ]
