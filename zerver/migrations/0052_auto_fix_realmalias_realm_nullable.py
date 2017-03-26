# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-11 03:07
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0051_realmalias_add_allow_subdomains'),
    ]

    operations = [
        migrations.AlterField(
            model_name='realmalias',
            name='realm',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.Realm'),
        ),
    ]
