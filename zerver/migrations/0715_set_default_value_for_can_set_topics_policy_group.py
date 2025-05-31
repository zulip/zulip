from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import OuterRef


def set_default_value_for_can_set_topics_policy_group(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Realm = apps.get_model("zerver", "Realm")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")

    MEMBERS_GROUP_NAME = "role:members"

    Realm.objects.filter(can_set_topics_policy_group=None).update(
        can_set_topics_policy_group=NamedUserGroup.objects.filter(
            name=MEMBERS_GROUP_NAME, realm=OuterRef("id"), is_system_group=True
        ).values("pk")
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0714_realm_can_set_topics_policy_group"),
    ]

    operations = [
        migrations.RunPython(
            set_default_value_for_can_set_topics_policy_group,
            elidable=True,
            reverse_code=migrations.RunPython.noop,
        )
    ]
