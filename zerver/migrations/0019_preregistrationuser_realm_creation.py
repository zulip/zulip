# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0018_realm_emoji_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='preregistrationuser',
            name='realm_creation',
            field=models.BooleanField(default=False),
        ),
    ]
