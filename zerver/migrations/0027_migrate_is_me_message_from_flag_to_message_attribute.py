# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import bitfield
from django.db import migrations, transaction


def forward_migration(apps, schema_editor):
    UserMessage = apps.get_model("zerver", "UserMessage")
    with transaction.atomic():
        for ums in UserMessage.objects.all():
            if ums.flags.is_me_message:
                ums.message.is_me_message = True
                ums.message.save(update_fields=['is_me_message'])


def backward_migration(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0026_message_is_me_message'),
    ]

    operations = [
        migrations.RunPython(forward_migration, backward_migration),
        migrations.AlterField(
            model_name='usermessage',
            name='flags',
            field=bitfield.models.BitField([u'read', u'starred', u'collapsed', u'mentioned', u'wildcard_mentioned', u'summarize_in_home', u'summarize_in_stream', u'force_expand', u'force_collapse', u'has_alert_word', u'historical'], default=0),
        ),
    ]
