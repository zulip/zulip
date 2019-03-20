# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-03-17 08:37
from __future__ import unicode_literals

from django.db import migrations, models
import zerver.models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0211_add_users_field_to_scheduled_email'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stream',
            name='email_token',
            field=models.CharField(default=zerver.models.generate_email_token_for_stream, max_length=32, unique=True),
        ),
    ]
