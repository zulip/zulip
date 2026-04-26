from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import F, Func, Value


def remove_realm_emoji_from_audit_log_extra_data(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """The REALM_EMOJI_ADDED and REALM_EMOJI_REMOVED audit log entries
    used to store the full realm-wide emoji dictionary in a
    "realm_emoji" key inside extra_data.  The "added_emoji" and
    "deactivated_emoji" keys already record the actually-changed
    emoji, so drop the redundant "realm_emoji" key from historical
    rows.
    """
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")

    # AuditLogEventType values (inlined because migrations should not
    # import from zerver.models):
    REALM_EMOJI_ADDED = 226
    REALM_EMOJI_REMOVED = 227

    RealmAuditLog.objects.filter(
        event_type__in=[REALM_EMOJI_ADDED, REALM_EMOJI_REMOVED],
        extra_data__has_key="realm_emoji",
    ).update(
        extra_data=Func(
            F("extra_data"),
            Value("realm_emoji"),
            function="",
            arg_joiner=" - ",
        ),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0798_remove_userprofile_recipient_and_personal_recipients"),
    ]

    operations = [
        migrations.RunPython(
            remove_realm_emoji_from_audit_log_extra_data,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
