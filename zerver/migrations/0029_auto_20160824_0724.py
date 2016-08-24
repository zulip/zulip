# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0028_userprofile_tos_version'),
    ]

    operations = [
        migrations.AlterField(
            model_name='realm',
            name='default_language',
            field=models.CharField(default='en', max_length=10),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='default_language',
            field=models.CharField(default='en', max_length=10),
        ),
    ]
