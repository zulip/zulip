# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0016_realm_create_stream_by_admins_only'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='bot_type',
            field=models.PositiveSmallIntegerField(null=True, db_index=True),
        ),
    ]
