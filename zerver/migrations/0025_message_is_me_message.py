# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0024_realm_allow_message_editing'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='is_me_message',
            field=models.BooleanField(default=False),
        ),
    ]
