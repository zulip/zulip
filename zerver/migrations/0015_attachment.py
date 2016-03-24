# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0014_realm_emoji_url_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='Attachment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('file_name', models.CharField(max_length=100, db_index=True)),
                ('path_id', models.TextField(db_index=True)),
                ('create_time', models.DateTimeField(default=django.utils.timezone.now, db_index=True)),
                ('messages', models.ManyToManyField(to='zerver.Message')),
                ('owner', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
