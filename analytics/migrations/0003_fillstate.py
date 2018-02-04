# -*- coding: utf-8 -*-
from django.db import migrations, models

import zerver.lib.str_utils

class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0002_remove_huddlecount'),
    ]

    operations = [
        migrations.CreateModel(
            name='FillState',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('property', models.CharField(unique=True, max_length=40)),
                ('end_time', models.DateTimeField()),
                ('state', models.PositiveSmallIntegerField()),
                ('last_modified', models.DateTimeField(auto_now=True)),
            ],
            bases=(zerver.lib.str_utils.ModelReprMixin, models.Model),
        ),
    ]
