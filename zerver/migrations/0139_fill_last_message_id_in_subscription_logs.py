# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def fill_last_message_id_in_subscription_logs(
    apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    event_type = ['subscription_created', 'subscription_deactivated', 'subscription_activated']
    RealmAuditLog = apps.get_model('zerver', 'RealmAuditLog')
    subscription_logs = RealmAuditLog.objects.filter(
        event_last_message_id__isnull=True, event_type__in=event_type)

    for log in subscription_logs:
        log.event_last_message_id = -1
        log.save(update_fields=['event_last_message_id'])

def reverse_code(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0138_userprofile_realm_name_in_notifications'),
    ]

    operations = [
        migrations.RunPython(fill_last_message_id_in_subscription_logs,
                             reverse_code=reverse_code),
    ]
