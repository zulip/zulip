# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import zerver.lib.str_utils


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0027_topics_backfill'),
    ]

    operations = [
        migrations.AddField(
            model_name='message',
            name='topic',
            field=models.ForeignKey(to='zerver.Topic', null=True),
        ),
    ]
