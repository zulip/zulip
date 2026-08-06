from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from zerver.lib.queue import queue_json_publish_rollback_unsafe


def reupload_jdenticon_avatars(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """A bug in the import_realm codepath re-generated the Jdenticon avatars
    of every user on the server -- not just the imported realm's -- using
    the imported realm's UUID as salt for Jdenticon's key.
    For users outside the imported realm, that produced an avatar salted
    with the wrong realm's UUID. See #39468.

    We queue a deferred_work event per affected realm, which regenerates
    those avatars with each user's own realm UUID and bumps avatar_version
    so the corrected image is served.
    """
    Realm = apps.get_model("zerver", "Realm")
    if settings.TEST_SUITE:
        # This migration repairs data corrupted by a past bug,
        # not needed for tests.
        return

    non_system_realms = Realm.objects.exclude(string_id=settings.SYSTEM_BOT_REALM)
    if non_system_realms.count() < 2:
        # The bug only affected avatars of realms *other* than the one
        # being imported, so a server that has only ever hosted a single
        # non-system-bot realm has nothing to repair.
        return

    for realm_id in non_system_realms.order_by("id").values_list("id", flat=True):
        event = {"type": "reupload_jdenticon_avatars", "realm_id": realm_id}
        queue_json_publish_rollback_unsafe("deferred_work", event)


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0804_backfill_user_created_audit_logs"),
    ]

    operations = [
        migrations.RunPython(
            reupload_jdenticon_avatars,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
