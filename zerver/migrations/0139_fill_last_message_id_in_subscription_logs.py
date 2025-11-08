from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def backfill_last_message_id(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    event_type = ["subscription_created", "subscription_deactivated", "subscription_activated"]
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
    subscription_logs = RealmAuditLog.objects.filter(
        event_last_message_id__isnull=True, event_type__in=event_type
    )
    subscription_logs.update(event_last_message_id=-1)


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0138_userprofile_realm_name_in_notifications"),
    ]

    operations = [
        migrations.RunPython(
            backfill_last_message_id, reverse_code=migrations.RunPython.noop, elidable=True
        ),
    ]
