# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0026_delete_mituser'),
    ]

    operations = [
        migrations.AddField(
            model_name='realm',
            name='default_language',
            field=models.CharField(default='en', max_length=50),
        ),
    ]
