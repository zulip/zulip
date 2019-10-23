# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def convert_bots_to_system_bots(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    REALM_INTERNAL_BOTS = [
        'reminder-bot@zulip.com',
    ]
    UserProfile = apps.get_model('zerver', 'UserProfile')
    internal_bots = UserProfile.objects.filter(
        email__in=REALM_INTERNAL_BOTS,
        bot_type=1
    )
    for bot in internal_bots:
        bot.bot_type = 5
        bot.save(update_fields=['bot_type'])


class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0154_fix_invalid_bot_owner'),
    ]

    operations = [
        migrations.RunPython(convert_bots_to_system_bots),
    ]
