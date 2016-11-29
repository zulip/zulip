# -*- coding: utf-8 -*-
# Generated by Django 1.10.5 on 2017-03-28 08:23
from __future__ import unicode_literals

import bitfield.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0069_realmauditlog_extra_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='archivedusermessage',
            name='flags',
            field=bitfield.models.BitField(['read', 'starred', 'collapsed', 'mentioned', 'wildcard_mentioned', 'summarize_in_home', 'summarize_in_stream', 'force_expand', 'force_collapse', 'has_alert_word', 'historical', 'is_me_message', 'online_mentioned'], default=0),
        ),
        migrations.AlterField(
            model_name='usermessage',
            name='flags',
            field=bitfield.models.BitField(['read', 'starred', 'collapsed', 'mentioned', 'wildcard_mentioned', 'summarize_in_home', 'summarize_in_stream', 'force_expand', 'force_collapse', 'has_alert_word', 'historical', 'is_me_message', 'online_mentioned'], default=0),
        ),
    ]
