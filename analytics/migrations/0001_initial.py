# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import zerver.lib.str_utils


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0026_delete_mituser'),
    ]

    operations = [
        migrations.CreateModel(
            name='RealmCount',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('domain', models.CharField(max_length=40, db_index=True)),
                ('property', models.CharField(max_length=40)),
                ('value', models.BigIntegerField()),
                ('start_time', models.DateTimeField()),
                ('interval', models.CharField(max_length=20)),
                ('anomaly_id', models.BigIntegerField(null=True)),
                ('realm', models.ForeignKey(to='zerver.Realm')),
            ],
            bases=(zerver.lib.str_utils.ModelReprMixin, models.Model),
        ),
    ]
