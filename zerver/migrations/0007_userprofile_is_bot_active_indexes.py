# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0006_zerver_userprofile_email_upper_idx'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userprofile',
            name='is_active',
            field=models.BooleanField(default=True, db_index=True),
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='is_bot',
            field=models.BooleanField(default=False, db_index=True),
        ),
    ]
