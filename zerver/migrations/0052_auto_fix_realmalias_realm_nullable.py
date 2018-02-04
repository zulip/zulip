# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-02-11 03:07

import django.db.models.deletion
from django.db import migrations, models

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
