# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0004_userprofile_left_side_userlist'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='realm',
            options={'permissions': (('administer', 'Administer a realm'), ('api_super_user', 'Can send messages as other users for mirroring'))},
        ),
    ]
