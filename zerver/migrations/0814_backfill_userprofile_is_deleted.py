from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Exists, OuterRef


def backfill_userprofile_is_deleted(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """Sets is_deleted=True for users who were deleted before the
    is_deleted field was added in 0797_userprofile_is_deleted.

    Deleted users are identified by their USER_DELETED or
    USER_DELETED_PRESERVING_MESSAGES RealmAuditLog entries; these
    were backfilled for older deleted users in
    0374_backfill_user_delete_realmauditlog.
    """

    Realm = apps.get_model("zerver", "Realm")
    UserProfile = apps.get_model("zerver", "UserProfile")
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")

    USER_DELETED = 106
    USER_DELETED_PRESERVING_MESSAGES = 107

    for realm_id in Realm.objects.order_by("id").values_list("id", flat=True).iterator():
        has_user_deleted_event = Exists(
            RealmAuditLog.objects.filter(
                realm_id=realm_id,
                event_type__in=[USER_DELETED, USER_DELETED_PRESERVING_MESSAGES],
                modified_user_id=OuterRef("id"),
            )
        )
        num_updated = (
            UserProfile.objects.filter(
                realm_id=realm_id, is_mirror_dummy=True, is_active=False, is_deleted=False
            )
            .filter(has_user_deleted_event)
            .update(is_deleted=True)
        )
        if num_updated > 0:
            print(f"Realm {realm_id}: set is_deleted=True for {num_updated} deleted users.")


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        # Because this will be backported to 12.x, we only depend on the last migration in 12.x
        ("zerver", "0801_realmexport_backfill_export_from_prior_server_status"),
    ]

    operations = [
        migrations.RunPython(
            backfill_userprofile_is_deleted,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
