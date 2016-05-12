# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0015_attachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='realm',
            name='create_stream_by_admins_only',
            field=models.BooleanField(default=False),
        ),
    ]
