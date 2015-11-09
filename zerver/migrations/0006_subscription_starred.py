# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0005_auto_20150920_1340'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='starred',
            field=models.BooleanField(default=False),
        ),
    ]
