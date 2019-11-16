# Generated by Django 1.11.25 on 2019-11-06 22:40

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0280_userprofile_presence_enabled'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='zoom_token',
            field=django.contrib.postgres.fields.jsonb.JSONField(default=None, null=True),
        ),
    ]
