# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0029_realm_subdomain'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='starred_users',
            field=models.ManyToManyField(related_name='buddies', to=settings.AUTH_USER_MODEL),
        ),
    ]
