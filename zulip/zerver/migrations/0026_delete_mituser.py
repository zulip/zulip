# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0025_realm_message_content_edit_limit'),
    ]

    operations = [
        migrations.DeleteModel(
            name='MitUser',
        ),
    ]
