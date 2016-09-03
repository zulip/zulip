# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import bitfield.models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0028_userprofile_tos_version'),
    ]

    operations = [
        migrations.AddField(
            model_name='stream',
            name='default_permissions',
            field=bitfield.models.BitField([b'can_read', b'can_write', b'can_moderate', b'can_add_remove_users'], default=1),
        ),
        migrations.AddField(
            model_name='subscription',
            name='permissions',
            field=bitfield.models.BitField([b'can_read', b'can_write', b'can_moderate', b'can_add_remove_users'], default=None),
        ),
    ]
