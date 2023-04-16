# Generated by Django 4.2 on 2023-04-13 23:45

import django.db.models.deletion
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def fill_RealmAuthenticationMethod_data(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    Realm = apps.get_model("zerver", "Realm")
    RealmAuthenticationMethod = apps.get_model("zerver", "RealmAuthenticationMethod")
    for realm in Realm.objects.order_by("id"):
        rows_to_create = []
        for key, value in realm.authentication_methods.iteritems():
            if value:
                rows_to_create.append(RealmAuthenticationMethod(name=key, realm_id=realm.id))
        RealmAuthenticationMethod.objects.bulk_create(rows_to_create)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0435_scheduledmessage_rendered_content"),
    ]

    operations = [
        migrations.CreateModel(
            name="RealmAuthenticationMethod",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("name", models.CharField(max_length=80)),
                (
                    "realm",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="zerver.realm"
                    ),
                ),
            ],
            options={
                "unique_together": {("realm", "name")},
            },
        ),
        migrations.RunPython(fill_RealmAuthenticationMethod_data),
    ]
