from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import OuterRef


def set_default_value_for_can_create_bots_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Realm = apps.get_model("zerver", "Realm")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")

    bot_creation_policy_to_group_name = {
        1: "role:members",
        2: "role:administrators",
        3: "role:administrators",
    }

    for id, group_name in bot_creation_policy_to_group_name.items():
        Realm.objects.filter(can_create_bots_group=None, bot_creation_policy=id).update(
            can_create_bots_group=NamedUserGroup.objects.filter(
                name=group_name, realm=OuterRef("id"), is_system_group=True
            ).values("pk")
        )


def set_default_value_for_can_create_write_only_bots_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Realm = apps.get_model("zerver", "Realm")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")

    bot_creation_policy_to_group_name = {
        1: "role:members",
        2: "role:members",
        3: "role:administrators",
    }

    for id, group_name in bot_creation_policy_to_group_name.items():
        Realm.objects.filter(can_create_write_only_bots_group=None, bot_creation_policy=id).update(
            can_create_write_only_bots_group=NamedUserGroup.objects.filter(
                name=group_name, realm=OuterRef("id"), is_system_group=True
            ).values("pk")
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0656_realm_can_create_bots_group_and_more"),
    ]

    operations = [
        migrations.RunPython(
            set_default_value_for_can_create_bots_group,
            elidable=True,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            set_default_value_for_can_create_write_only_bots_group,
            elidable=True,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
