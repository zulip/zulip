# -*- coding: utf-8 -*-
# Generated by Django 1.10.4 on 2016-12-20 07:02

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0045_realm_waiting_period_threshold'),
    ]

    operations = [
        migrations.AddField(
            model_name='realmemoji',
            name='author',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]
