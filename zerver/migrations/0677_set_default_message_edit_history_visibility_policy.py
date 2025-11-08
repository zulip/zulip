from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def set_value_for_message_edit_history_visibility_policy(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    VISIBILITY_ALL = 1
    VISIBILITY_NONE = 3

    Realm = apps.get_model("zerver", "Realm")
    Realm.objects.filter(allow_edit_history=True).update(
        message_edit_history_visibility_policy=VISIBILITY_ALL
    )
    Realm.objects.filter(allow_edit_history=False).update(
        message_edit_history_visibility_policy=VISIBILITY_NONE
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0676_realm_message_edit_history_visibility_policy"),
    ]

    operations = [
        migrations.RunPython(set_value_for_message_edit_history_visibility_policy),
    ]
