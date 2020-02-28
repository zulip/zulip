# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations

from django.db.backends.postgresql_psycopg2.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps

def change_realm_audit_log_event_type_tense(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    RealmAuditLog = apps.get_model('zerver', 'RealmAuditLog')
    RealmAuditLog.objects.filter(event_type="user_change_password").update(event_type="user_password_changed")
    RealmAuditLog.objects.filter(event_type="user_change_avatar_source").update(event_type="user_avatar_source_changed")
    RealmAuditLog.objects.filter(event_type="bot_owner_changed").update(event_type="user_bot_owner_changed")

class Migration(migrations.Migration):

    dependencies = [
        ('zerver', '0174_userprofile_delivery_email'),
    ]

    operations = [
        migrations.RunPython(change_realm_audit_log_event_type_tense,
                             reverse_code=migrations.RunPython.noop),
    ]
