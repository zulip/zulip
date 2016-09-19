# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0028_userprofile_tos_version'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='enable_online_push_notifications',
            field=models.BooleanField(default=False),
        ),
    ]
