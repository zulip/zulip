from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def backfill_remote_zulip_server_creation_log_events(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    RemoteZulipServer = apps.get_model("zilencer", "RemoteZulipServer")
    RemoteZulipServerAuditLog = apps.get_model("zilencer", "RemoteZulipServerAuditLog")
    RemoteZulipServerAuditLog.REMOTE_SERVER_CREATED = 10215

    objects_to_create = []
    for remote_server in RemoteZulipServer.objects.all():
        entry = RemoteZulipServerAuditLog(
            server=remote_server,
            event_type=RemoteZulipServerAuditLog.REMOTE_SERVER_CREATED,
            event_time=remote_server.last_updated,
            backfilled=True,
        )
        objects_to_create.append(entry)
    RemoteZulipServerAuditLog.objects.bulk_create(objects_to_create)


def reverse_code(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    RemoteZulipServerAuditLog = apps.get_model("zilencer", "RemoteZulipServerAuditLog")
    RemoteZulipServerAuditLog.REMOTE_SERVER_CREATED = 10215
    RemoteZulipServerAuditLog.objects.filter(
        event_type=RemoteZulipServerAuditLog.REMOTE_SERVER_CREATED, backfilled=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("zilencer", "0021_alter_remotezulipserver_uuid"),
    ]

    operations = [
        migrations.RunPython(
            backfill_remote_zulip_server_creation_log_events,
            reverse_code=reverse_code,
            elidable=True,
        )
    ]
