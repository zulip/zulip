from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def fix_old_realm_reactivation_confirmations(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """
    Migration 0400_realmreactivationstatus changed REALM_REACTIVATION Confirmation
    to have a RealmReactivationStatus instance as .content_object. Now we need to migrate
    pre-existing REALM_REACTIVATION Confirmations to follow this format.

    The process is a bit fiddly because Confirmation.content_object is a GenericForeignKey,
    which can't be directly accessed in migration code, so changing it involves manually
    updating the .object_id and .content_type attributes underpinning it.

    For these old Confirmation we don't have a mechanism for tracking which have been used,
    so it's safest to just revoke them all. If any users need a realm reactivation link, it
    can just be re-generated.
    """
    REALM_REACTIVATION = 8

    RealmReactivationStatus = apps.get_model("zerver", "RealmReactivationStatus")
    Realm = apps.get_model("zerver", "Realm")
    Confirmation = apps.get_model("confirmation", "Confirmation")
    ContentType = apps.get_model("contenttypes", "ContentType")

    if not Confirmation.objects.filter(type=REALM_REACTIVATION).exists():
        # No relevant Confirmations so nothing to do, and the database may actually
        # no be provisioned yet, which would make the code below break.
        return

    # .content_type of these old Confirmation will be changed to this.
    realm_reactivation_status_content_type, created = ContentType.objects.get_or_create(
        model="realmreactivationstatus", app_label="zerver"
    )

    for confirmation in Confirmation.objects.filter(type=REALM_REACTIVATION):
        if confirmation.content_type_id == realm_reactivation_status_content_type.id:
            # This Confirmation is already in the new format.
            continue

        assert confirmation.content_type.model == "realm"
        realm_object_id = confirmation.object_id

        # Sanity check that the realm exists.
        try:
            Realm.objects.get(id=realm_object_id)
        except Realm.DoesNotExist:
            print(
                f"Confirmation {confirmation.id} is tied to realm_id {realm_object_id} which doesn't exist. "
                "This is unexpected! Skipping migrating it."
            )
            continue

        # We create the object with STATUS_REVOKED.
        new_content_object = RealmReactivationStatus(realm_id=realm_object_id, status=2)
        new_content_object.save()

        # Now we can finally change the .content_object. This is done by setting
        # .content_type to the correct ContentType as mentioned above and the object_id
        # to the id of the RealmReactivationStatus instance that's supposed to be
        # the content_object. This works because .content_object is dynamically
        # derived by django from the .content_type and object_id values.
        confirmation.content_type_id = realm_reactivation_status_content_type
        confirmation.object_id = new_content_object.id
        confirmation.save()


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0400_realmreactivationstatus"),
    ]

    operations = [
        migrations.RunPython(fix_old_realm_reactivation_confirmations, elidable=True),
    ]
