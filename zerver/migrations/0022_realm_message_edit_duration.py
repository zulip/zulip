# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0021_migrate_attachment_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='realm',
            name='allow_message_editing',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='realm',
            name='message_edit_duration_seconds',
            field=models.IntegerField(default=600),
        ),
    ]
