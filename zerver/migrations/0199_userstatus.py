# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2018-12-17 18:49
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0198_preregistrationuser_invited_as'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserStatus',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField()),
                ('status', models.PositiveSmallIntegerField(default=1)),
                ('client', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='zerver.Client')),
                ('user_profile', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
