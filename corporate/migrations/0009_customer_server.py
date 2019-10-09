# -*- coding: utf-8 -*-
# Generated by Django 1.11.24 on 2019-10-09 16:53
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zilencer', '0018_remoterealmauditlog'),
        ('corporate', '0008_nullable_next_invoice_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='server',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to='zilencer.RemoteZulipServer'),
        ),
        migrations.AlterField(
            model_name='customer',
            name='realm',
            field=models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, to='zerver.Realm'),
        ),
    ]
