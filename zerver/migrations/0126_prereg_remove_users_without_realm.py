# Generated by Django 1.11.6 on 2017-11-30 04:58

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def remove_prereg_users_without_realm(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    prereg_model = apps.get_model("zerver", "PreregistrationUser")
    prereg_model.objects.filter(realm=None, realm_creation=False).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0125_realm_max_invites"),
    ]

    operations = [
        migrations.RunPython(
            remove_prereg_users_without_realm, reverse_code=migrations.RunPython.noop, elidable=True
        ),
    ]
