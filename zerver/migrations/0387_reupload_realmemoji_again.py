from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

from zerver.lib.queue import queue_json_publish


def reupload_realm_emoji(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """As detailed in https://github.com/zulip/zulip/issues/21608, it is
    possible for the deferred_work queue from Zulip 4.x to have been
    started up by puppet during the deployment before migrations were
    run on Zulip 5.0.

    This means that the deferred_work events originally produced by
    migration 0376 might have been processed and discarded without
    effect.

    That code has been removed from the 0376 migration, and we run it
    here, after the upgrade code has been fixed; servers which already
    processed that migration might at worst do this work twice, which
    is harmless aside from being a small waste of resources.
    """

    Realm = apps.get_model("zerver", "Realm")
    if settings.TEST_SUITE:
        # There are no custom emoji in the test suite data set, and
        # the below code won't work because RabbitMQ isn't enabled for
        # the test suite.
        return

    for realm_id in Realm.objects.order_by("id").values_list("id", flat=True):
        event = {
            "type": "reupload_realm_emoji",
            "realm_id": realm_id,
        }
        queue_json_publish("deferred_work", event)


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0386_fix_attachment_caches"),
    ]

    operations = [
        migrations.RunPython(reupload_realm_emoji, reverse_code=migrations.RunPython.noop),
    ]
