from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Exists, OuterRef
from django.utils.timezone import now as timezone_now


def backfill_missing_user_created_deactivated_events(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Backfill USER_CREATED and USER_DEACTIVATED RealmAuditLog entries for
    users that lack them, presumably due to having been imported via a
    third-party importer such as Slack before create_audit_logs_for_users was
    added to the import system.
    """

    Realm = apps.get_model("zerver", "Realm")
    UserProfile = apps.get_model("zerver", "UserProfile")
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")

    USER_CREATED = 101
    USER_ACTIVATED = 102
    USER_DEACTIVATED = 103
    USER_REACTIVATED = 104

    for realm in Realm.objects.all().iterator():
        with transaction.atomic():
            has_user_created_event = Exists(
                RealmAuditLog.objects.filter(
                    realm=realm,
                    event_type=USER_CREATED,
                    modified_user_id=OuterRef("id"),
                )
            )
            users_missing_created_event = list(
                UserProfile.objects.filter(realm=realm)
                .filter(~has_user_created_event)
                .values("id", "date_joined", "is_active")
            )
            if not users_missing_created_event:
                continue

            inactive_user_ids = [
                user["id"] for user in users_missing_created_event if not user["is_active"]
            ]
            if inactive_user_ids:
                # For inactive users, we also need to figure out if they are missing
                # a USER_DEACTIVATED record. We check that by finding the latest event
                # about activations and verifying whether it is a USER_DEACTIVATED
                # event.
                #
                # Note: We are purposely only searching in the subset of users that were
                # already missing the USER_CREATED event - as those are the users affected
                # by the bug in imports from 3rd party tools.
                # This migration is NOT intended to audit the integrity of the activation
                # events sequencing in general. The scope of this backfill is limited
                # to the specific importer bug.
                latest_activation_event_type = {
                    row["modified_user_id"]: row["event_type"]
                    for row in RealmAuditLog.objects.filter(
                        realm=realm,
                        modified_user_id__in=inactive_user_ids,
                        event_type__in=[USER_ACTIVATED, USER_DEACTIVATED, USER_REACTIVATED],
                    )
                    .order_by("modified_user_id", "-event_time", "-id")
                    .distinct("modified_user_id")
                    .values("modified_user_id", "event_type")
                }
            else:
                latest_activation_event_type = {}

            now = timezone_now()
            audit_logs_to_backfill = []
            for user in users_missing_created_event:
                audit_logs_to_backfill.append(
                    RealmAuditLog(
                        realm_id=realm.id,
                        modified_user_id=user["id"],
                        event_type=USER_CREATED,
                        event_time=user["date_joined"],
                        backfilled=True,
                    )
                )
                if user["is_active"]:
                    continue
                if latest_activation_event_type.get(user["id"]) == USER_DEACTIVATED:
                    # If the last activation event is USER_DEACTIVATED, then the state
                    # is correct already.
                    continue
                audit_logs_to_backfill.append(
                    RealmAuditLog(
                        realm_id=realm.id,
                        modified_user_id=user["id"],
                        event_type=USER_DEACTIVATED,
                        event_time=now,
                        backfilled=True,
                    )
                )

            print(
                f"Backfilling {len(audit_logs_to_backfill)} audit log entries for "
                f"{len(users_missing_created_event)} users in realm {realm.string_id}"
            )
            RealmAuditLog.objects.bulk_create(audit_logs_to_backfill, batch_size=1000)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0800_cleanup_case_mismatched_legacy_apns_tokens"),
    ]

    operations = [
        migrations.RunPython(
            backfill_missing_user_created_deactivated_events,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        )
    ]
