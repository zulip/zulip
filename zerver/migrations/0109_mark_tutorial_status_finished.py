from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def set_tutorial_status_to_finished(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    UserProfile = apps.get_model("zerver", "UserProfile")
    UserProfile.objects.update(tutorial_status="F")


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0108_fix_default_string_id"),
    ]

    operations = [
        migrations.RunPython(set_tutorial_status_to_finished, elidable=True),
    ]
