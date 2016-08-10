# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0027_realm_default_language'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='tos_version',
            field=models.CharField(max_length=10, null=True),
        ),
    ]
