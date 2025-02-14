from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def set_value_for_message_edit_history_visibility(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    MESSAGE_EDIT_HISTORY_VISIBILITY_ALL = 1
    MESSAGE_EDIT_HISTORY_VISIBILITY_NONE = 3

    Realm = apps.get_model("zerver", "Realm")
    Realm.objects.filter(allow_edit_history=True).update(
        message_edit_history_visibility=MESSAGE_EDIT_HISTORY_VISIBILITY_ALL
    )
    Realm.objects.filter(allow_edit_history=False).update(
        message_edit_history_visibility=MESSAGE_EDIT_HISTORY_VISIBILITY_NONE
    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0672_add_realm_message_edit_history_visibility"),
    ]

    operations = [
        migrations.RunPython(set_value_for_message_edit_history_visibility),
    ]
