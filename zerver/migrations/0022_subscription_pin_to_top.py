# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0021_migrate_attachment_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscription',
            name='pin_to_top',
            field=models.BooleanField(default=False),
        ),
    ]
