import orjson
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def update_twitter_to_x(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    CustomProfileField = apps.get_model("zerver", "CustomProfileField")
    EXTERNAL_ACCOUNT = 7

    old_value = orjson.dumps({"subtype": "twitter"}).decode()
    new_value = orjson.dumps({"subtype": "x"}).decode()

    CustomProfileField.objects.filter(
        name="Twitter username", field_type=EXTERNAL_ACCOUNT, field_data=old_value
    ).update(name="X username", field_data=new_value)


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0768_realmauditlog_scrubbed"),
    ]

    operations = [
        migrations.RunPython(
            update_twitter_to_x,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
