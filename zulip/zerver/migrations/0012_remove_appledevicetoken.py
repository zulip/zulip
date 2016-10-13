# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0011_remove_guardian'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='appledevicetoken',
            name='user',
        ),
        migrations.DeleteModel(
            name='AppleDeviceToken',
        ),
    ]
