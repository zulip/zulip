# Generated by Django 4.1.6 on 2023-02-17 12:06
import json

from django.db import migrations
from django.db.backends.postgresql.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def fix_audit_log_objects_for_group_based_stream_settings(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """
    This adds the property_name field to any STREAM_GROUP_BASED_SETTING_CHANGED
    audit log entries that were created before the previous commit.
    """
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")

    STREAM_GROUP_BASED_SETTING_CHANGED = 608
    OLD_VALUE = "1"
    NEW_VALUE = "2"

    for audit_log_object in RealmAuditLog.objects.filter(
        event_type=STREAM_GROUP_BASED_SETTING_CHANGED
    ):
        extra_data = json.loads(audit_log_object.extra_data)
        old_value = extra_data[OLD_VALUE]
        new_value = extra_data[NEW_VALUE]

        audit_log_object.extra_data = json.dumps(
            {
                OLD_VALUE: old_value,
                NEW_VALUE: new_value,
                "property": "can_remove_subscribers_group",
            }
        )
        audit_log_object.save(update_fields=["extra_data"])


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0429_user_topic_case_insensitive_unique_toghether"),
    ]

    operations = [
        migrations.RunPython(
            fix_audit_log_objects_for_group_based_stream_settings,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
