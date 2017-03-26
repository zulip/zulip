# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0013_realmemoji'),
    ]

    operations = [
        migrations.AlterField(
            model_name='realmemoji',
            name='img_url',
            field=models.URLField(max_length=1000),
        ),
    ]
