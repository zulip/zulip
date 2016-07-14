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
            name='Topic',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=60, db_index=True)),
                ('recipient', models.ForeignKey(to='zerver.Recipient', db_index=True)),
            ],
            bases=(zerver.lib.str_utils.ModelReprMixin, models.Model),
        ),
        migrations.RunSQL(
            "CREATE UNIQUE INDEX topic_name_recipient ON "
            "zerver_topic ((upper(name)), recipient_id);",
            reverse_sql="DROP INDEX topic_name_recipient;"),
    ]
