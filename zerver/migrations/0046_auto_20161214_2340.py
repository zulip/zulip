# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0045_userprofile_hide_private_message_desktop_notifications'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userprofile',
            name='hide_private_message_desktop_notifications',
        ),
        migrations.AddField(
            model_name='userprofile',
            name='include_content_of_private_messages_in_desktop_notifications',
            field=models.BooleanField(default=False),
        ),
    ]
