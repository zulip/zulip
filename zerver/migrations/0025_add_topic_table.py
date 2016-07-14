# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import zerver.lib.str_utils


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0024_realm_allow_message_editing'),
    ]

    operations = [
        migrations.CreateModel(
            name='Topic',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=60, db_index=True)),
                ('recipient', models.ForeignKey(to='zerver.Recipient')),
            ],
            bases=(zerver.lib.str_utils.ModelReprMixin, models.Model),
        ),
        migrations.AddField(
            model_name='message',
            name='topic',
            field=models.ForeignKey(to='zerver.Topic', null=True),
        ),
        migrations.RunSQL("""
            insert into zerver_topic (recipient_id, name)
            select distinct recipient_id, subject from zerver_message where subject != ''
            """
        )
    ]
