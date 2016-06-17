# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings

from zerver.models import Recipient

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0019_preregistrationuser_realm_creation'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachment',
            name='is_realm_public',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='attachment',
            name='realm',
            field=models.ForeignKey(blank=True, to='zerver.Realm', null=True),
        ),
    ]
