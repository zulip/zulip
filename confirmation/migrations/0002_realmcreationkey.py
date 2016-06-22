# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('confirmation', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RealmCreationKey',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('creation_key', models.CharField(max_length=40, verbose_name='activation key')),
                ('date_created', models.DateTimeField(default=django.utils.timezone.now, verbose_name='created')),
            ],
        ),
    ]
