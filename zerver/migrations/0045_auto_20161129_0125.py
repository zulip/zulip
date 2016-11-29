# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import bitfield.models


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0044_reaction'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usermessage',
            name='flags',
            field=bitfield.models.BitField(['read', 'starred', 'collapsed', 'mentioned', 'wildcard_mentioned', 'summarize_in_home', 'summarize_in_stream', 'force_expand', 'force_collapse', 'has_alert_word', 'historical', 'is_me_message', 'online_mentioned'], default=0),
        ),
    ]
