from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def rename_populate_db_client(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Renames the 'populate_db' client to 'ZulipDataImport' to
    better reflect its use in production, which is messages imported
    into Zulip via official data import tools.
    """
    Client = apps.get_model("zerver", "Client")

    Client.objects.filter(name="populate_db").update(name="ZulipDataImport")


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0701_merge"),
    ]

    operations = [
        migrations.RunPython(
            rename_populate_db_client,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
