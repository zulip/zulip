# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-13 23:32
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0060_move_avatars_to_be_uid_based'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='realm',
            name='domain',
        ),
    ]
