# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0033_migrate_domain_to_realmalias'),
    ]

    operations = [
        migrations.AddField(
            model_name='realm',
            name='message_retention_days',
            field=models.IntegerField(null=True),
        ),
    ]
