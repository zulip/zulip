from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import OuterRef


def set_default_value_for_can_change_own_name_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Realm = apps.get_model("zerver", "Realm")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")

    Realm.objects.filter(can_change_own_name_group=None, name_changes_disabled=True).update(
        can_change_own_name_group=NamedUserGroup.objects.filter(
            name="role:administrators", realm_for_sharding=OuterRef("id"), is_system_group=True
        ).values("pk")
    )
    Realm.objects.filter(can_change_own_name_group=None, name_changes_disabled=False).update(
        can_change_own_name_group=NamedUserGroup.objects.filter(
            name="role:everyone", realm_for_sharding=OuterRef("id"), is_system_group=True
        ).values("pk")
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0801_realm_can_change_own_name_group"),
    ]

    operations = [
        migrations.RunPython(
            set_default_value_for_can_change_own_name_group,
            elidable=True,
            reverse_code=migrations.RunPython.noop,
        )
    ]
