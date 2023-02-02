# Generated by Django 1.11.20 on 2019-05-06 13:15

from django.db import migrations
from django.db.backends.postgresql.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def upgrade_create_stream_policy(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    Realm = apps.get_model("zerver", "Realm")
    Realm.CREATE_STREAM_POLICY_MEMBERS = 1
    Realm.CREATE_STREAM_POLICY_ADMINS = 2
    Realm.CREATE_STREAM_POLICY_WAITING_PERIOD = 3
    Realm.objects.filter(waiting_period_threshold__exact=0).filter(
        create_stream_by_admins_only=False
    ).update(create_stream_policy=Realm.CREATE_STREAM_POLICY_MEMBERS)
    Realm.objects.filter(create_stream_by_admins_only=True).update(
        create_stream_policy=Realm.CREATE_STREAM_POLICY_ADMINS
    )
    Realm.objects.filter(waiting_period_threshold__gt=0).filter(
        create_stream_by_admins_only=False
    ).update(create_stream_policy=Realm.CREATE_STREAM_POLICY_WAITING_PERIOD)


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0216_add_create_stream_policy"),
    ]

    operations = [
        migrations.RunPython(
            upgrade_create_stream_policy, reverse_code=migrations.RunPython.noop, elidable=True
        ),
    ]
