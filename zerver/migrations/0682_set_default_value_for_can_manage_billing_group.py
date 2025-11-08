from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def set_default_value_for_can_manage_billing_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Realm = apps.get_model("zerver", "Realm")
    UserProfile = apps.get_model("zerver", "UserProfile")
    UserGroup = apps.get_model("zerver", "UserGroup")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")

    OWNERS_GROUP_NAME = "role:owners"

    for realm in Realm.objects.all():
        if realm.can_manage_billing_group is not None:
            continue

        owners_system_group = NamedUserGroup.objects.get(
            name=OWNERS_GROUP_NAME, realm=realm, is_system_group=True
        )
        billing_admins = UserProfile.objects.filter(
            realm=realm, is_billing_admin=True, is_bot=False, is_active=True
        )

        if billing_admins.exists():
            user_group = UserGroup.objects.create(realm=realm)
            user_group.direct_members.set(list(billing_admins))
            user_group.direct_subgroups.set([owners_system_group])
            realm.can_manage_billing_group = user_group
        else:
            realm.can_manage_billing_group = owners_system_group

        realm.save(update_fields=["can_manage_billing_group"])


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0681_realm_can_manage_billing_group"),
    ]

    operations = [
        migrations.RunPython(
            set_default_value_for_can_manage_billing_group,
            elidable=True,
            reverse_code=migrations.RunPython.noop,
        )
    ]
