# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0033_migrate_domain_to_realmalias'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='enable_online_push_notifications',
            field=models.BooleanField(default=False),
        ),
    ]
