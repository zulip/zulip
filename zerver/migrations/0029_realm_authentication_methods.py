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
            model_name='realm',
            name='authentication_methods',
            field=bitfield.models.BitField([b'Google', b'Email', b'GitHub'], default=7),
        ),
    ]
