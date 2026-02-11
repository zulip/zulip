import django.db.models.deletion
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def set_can_change_name_group(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """
    Migrate existing realm_name_changes_disabled boolean to can_change_name_group.
    - name_changes_disabled=True → role:administrators
    - name_changes_disabled=False → role:everyone
    """
    Realm = apps.get_model("zerver", "Realm")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")

    for realm in Realm.objects.all().iterator():
        if realm.name_changes_disabled:
            # name_changes_disabled=True means only admins can change names
            administrators_group = NamedUserGroup.objects.get(
                name="role:administrators",
                realm=realm,
                is_system_group=True,
            )
            realm.can_change_name_group = administrators_group.usergroup_ptr
        else:
            # name_changes_disabled=False means everyone can change names
            everyone_group = NamedUserGroup.objects.get(
                name="role:everyone",
                realm=realm,
                is_system_group=True,
            )
            realm.can_change_name_group = everyone_group.usergroup_ptr
        realm.save(update_fields=["can_change_name_group"])


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0776_realm_default_avatar_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="realm",
            name="can_change_name_group",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
        migrations.RunPython(
            set_can_change_name_group,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
        migrations.AlterField(
            model_name="realm",
            name="can_change_name_group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="+",
                to="zerver.usergroup",
            ),
        ),
    ]
