# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0044_reaction'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='hide_private_message_desktop_notifications',
            field=models.BooleanField(default=True),
        ),
    ]
