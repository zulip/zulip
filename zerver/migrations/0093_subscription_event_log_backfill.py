from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Max
from django.utils.timezone import now as timezone_now


def backfill_subscription_log_events(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    migration_time = timezone_now()
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
    Subscription = apps.get_model("zerver", "Subscription")
    Message = apps.get_model("zerver", "Message")
    objects_to_create = []

    subs_query = Subscription.objects.select_related(
        "user_profile", "user_profile__realm", "recipient"
    ).filter(recipient__type=2)
    for sub in subs_query:
        entry = RealmAuditLog(
            realm=sub.user_profile.realm,
            modified_user=sub.user_profile,
            modified_stream_id=sub.recipient.type_id,
            event_last_message_id=0,
            event_type="subscription_created",
            event_time=migration_time,
            backfilled=True,
        )
        objects_to_create.append(entry)
    RealmAuditLog.objects.bulk_create(objects_to_create)
    objects_to_create = []

    event_last_message_id = Message.objects.aggregate(Max("id"))["id__max"]
    migration_time_for_deactivation = timezone_now()
    for sub in subs_query.filter(active=False):
        entry = RealmAuditLog(
            realm=sub.user_profile.realm,
            modified_user=sub.user_profile,
            modified_stream_id=sub.recipient.type_id,
            event_last_message_id=event_last_message_id,
            event_type="subscription_deactivated",
            event_time=migration_time_for_deactivation,
            backfilled=True,
        )
        objects_to_create.append(entry)
    RealmAuditLog.objects.bulk_create(objects_to_create)
    objects_to_create = []


def reverse_code(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
    RealmAuditLog.objects.filter(event_type="subscription_created").delete()
    RealmAuditLog.objects.filter(event_type="subscription_deactivated").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0092_create_scheduledemail"),
    ]

    operations = [
        migrations.AddField(
            model_name="realmauditlog",
            name="event_last_message_id",
            field=models.IntegerField(null=True),
        ),
        migrations.RunPython(
            backfill_subscription_log_events, reverse_code=reverse_code, elidable=True
        ),
    ]
