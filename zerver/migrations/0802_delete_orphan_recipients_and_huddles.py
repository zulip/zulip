from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Exists, OuterRef

STREAM = 2
DIRECT_MESSAGE_GROUP = 3
BATCH_SIZE = 1000


def delete_orphan_recipients_and_huddles(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Recipient = apps.get_model("zerver", "Recipient")
    Subscription = apps.get_model("zerver", "Subscription")
    DirectMessageGroup = apps.get_model("zerver", "DirectMessageGroup")
    UserProfile = apps.get_model("zerver", "UserProfile")
    Stream = apps.get_model("zerver", "Stream")

    # Stream has no FK from Recipient (only a type_id int); when
    # realm.delete() cascades the Stream, its Recipient row is left
    # behind.  Orphans are those whose type_id no longer points at
    # a live Stream.
    orphan_stream_recipient_ids = list(
        Recipient.objects.filter(type=STREAM)
        .exclude(type_id__in=Stream.objects.values_list("id", flat=True))
        .values_list("id", flat=True)
    )
    print()
    print(f"Deleting {len(orphan_stream_recipient_ids)} orphan stream recipients...")
    for chunk_start in range(0, len(orphan_stream_recipient_ids), BATCH_SIZE):
        chunk = orphan_stream_recipient_ids[chunk_start : chunk_start + BATCH_SIZE]
        Recipient.objects.filter(id__in=chunk).delete()
        print(
            f"  Deleted {chunk_start + len(chunk)}/{len(orphan_stream_recipient_ids)} orphan stream recipients."
        )

    # A DMG Recipient is orphan when its only remaining Subscriptions
    # are from cross-realm system bots, or when none remain.
    crossrealm_bot_ids = set(
        UserProfile.objects.filter(
            delivery_email__in=settings.CROSS_REALM_BOT_EMAILS,
        ).values_list("id", flat=True)
    )
    has_human_subscriber = Exists(
        Subscription.objects.filter(recipient_id=OuterRef("id")).exclude(
            user_profile_id__in=crossrealm_bot_ids,
        )
    )
    orphan_dmg_recipient_ids = list(
        Recipient.objects.filter(type=DIRECT_MESSAGE_GROUP)
        .annotate(has_human=has_human_subscriber)
        .filter(has_human=False)
        .values_list("id", flat=True)
    )
    print(f"Deleting {len(orphan_dmg_recipient_ids)} orphan direct message groups...")
    for chunk_start in range(0, len(orphan_dmg_recipient_ids), BATCH_SIZE):
        chunk = orphan_dmg_recipient_ids[chunk_start : chunk_start + BATCH_SIZE]
        chunk_huddle_ids = list(
            Recipient.objects.filter(id__in=chunk).values_list("type_id", flat=True)
        )
        # Recipient.delete() cascades Subscription and Message;
        # DirectMessageGroup.recipient is SET_NULL, so the DMG row
        # needs an explicit delete.
        Recipient.objects.filter(id__in=chunk).delete()
        DirectMessageGroup.objects.filter(id__in=chunk_huddle_ids).delete()
        print(
            f"  Deleted {chunk_start + len(chunk)}/{len(orphan_dmg_recipient_ids)} orphan direct message groups."
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0801_realmexport_backfill_export_from_prior_server_status"),
    ]

    operations = [
        migrations.RunPython(
            delete_orphan_recipients_and_huddles,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
