# Generated by Django 3.2.6 on 2021-09-17 17:08

from django.db import migrations
from django.db.backends.postgresql.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import F


def migrate_twenty_four_hour_time_to_realmuserdefault(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    RealmUserDefault = apps.get_model("zerver", "RealmUserDefault")
    realm_user_default_objects = RealmUserDefault.objects.exclude(
        twenty_four_hour_time=F("realm__default_twenty_four_hour_time")
    )
    for realm_user_default in realm_user_default_objects:
        realm = realm_user_default.realm
        realm_user_default.twenty_four_hour_time = realm.default_twenty_four_hour_time
        realm_user_default.save(update_fields=["twenty_four_hour_time"])


def reverse_migrate_twenty_four_hour_time_to_realmuserdefault(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    RealmUserDefault = apps.get_model("zerver", "RealmUserDefault")
    realm_user_default_objects = RealmUserDefault.objects.exclude(
        realm__default_twenty_four_hour_time=F("twenty_four_hour_time")
    )
    for realm_user_default in realm_user_default_objects:
        realm = realm_user_default.realm
        realm.default_twenty_four_hour_time = realm_user_default.twenty_four_hour_time
        realm.save(update_fields=["default_twenty_four_hour_time"])


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0351_user_topic_visibility_indexes"),
    ]

    operations = [
        migrations.RunPython(
            migrate_twenty_four_hour_time_to_realmuserdefault,
            reverse_code=reverse_migrate_twenty_four_hour_time_to_realmuserdefault,
            elidable=True,
        ),
    ]
