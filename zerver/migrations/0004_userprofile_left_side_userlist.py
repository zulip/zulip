# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0003_custom_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='left_side_userlist',
            field=models.BooleanField(default=False),
        ),
    ]
