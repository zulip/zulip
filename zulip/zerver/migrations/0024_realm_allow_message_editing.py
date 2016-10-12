# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0023_userprofile_default_language'),
    ]

    operations = [
        migrations.AddField(
            model_name='realm',
            name='allow_message_editing',
            field=models.BooleanField(default=True),
        ),
    ]
