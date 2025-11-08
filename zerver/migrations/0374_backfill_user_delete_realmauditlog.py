from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def backfill_user_deleted_logs(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
    RealmAuditLog.USER_DELETED = 106

    UserProfile = apps.get_model("zerver", "UserProfile")

    objects_to_create = []
    for user_profile in UserProfile.objects.filter(
        is_mirror_dummy=True, is_active=False, delivery_email__regex=r"^deleteduser\d+@.+"
    ):
        entry = RealmAuditLog(
            realm_id=user_profile.realm_id,
            modified_user=user_profile,
            acting_user=user_profile,
            event_type=RealmAuditLog.USER_DELETED,
            # For old dummy users, the date_joined is the time of the deletion.
            event_time=user_profile.date_joined,
            backfilled=True,
        )
        objects_to_create.append(entry)
    RealmAuditLog.objects.bulk_create(objects_to_create)


def reverse_code(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
    RealmAuditLog.USER_DELETED = 106

    RealmAuditLog.objects.filter(event_type=RealmAuditLog.USER_DELETED, backfilled=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0373_fix_deleteduser_dummies"),
    ]

    operations = [
        migrations.RunPython(
            backfill_user_deleted_logs,
            reverse_code=reverse_code,
            elidable=True,
        )
    ]
