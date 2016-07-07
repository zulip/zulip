# -*- coding: utf-8 -*-
from __future__ import unicode_literals

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
        ('zerver', '0025_message_is_me_message'),
    ]

    operations = [
        migrations.RunPython(forward_migration, backward_migration),
    ]
