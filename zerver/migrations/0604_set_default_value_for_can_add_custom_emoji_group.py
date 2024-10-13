# Generated by Django 4.2.1 on 2023-06-12 10:47

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import OuterRef


def set_default_value_for_can_add_custom_emoji_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Realm = apps.get_model("zerver", "Realm")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")

    add_custom_emoji_policy_to_group_name = {
        1: "role:members",
        2: "role:administrators",
        3: "role:fullmembers",
        4: "role:moderators",
    }

    for id, group_name in add_custom_emoji_policy_to_group_name.items():
        Realm.objects.filter(can_add_custom_emoji_group=None, add_custom_emoji_policy=id).update(
            can_add_custom_emoji_group=NamedUserGroup.objects.filter(
                name=group_name, realm=OuterRef("id"), is_system_group=True
            ).values("pk")
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0603_realm_can_add_custom_emoji_group"),
    ]

    operations = [
        migrations.RunPython(
            set_default_value_for_can_add_custom_emoji_group,
            elidable=True,
            reverse_code=migrations.RunPython.noop,
        )
    ]
