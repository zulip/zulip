# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0009_add_missing_migrations'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='streamcolor',
            name='subscription',
        ),
        migrations.DeleteModel(
            name='StreamColor',
        ),
    ]
