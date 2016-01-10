# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0008_preregistrationuser_upper_email_idx'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='enable_stream_desktop_notifications',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='enable_stream_sounds',
            field=models.BooleanField(default=False),
        ),
    ]
