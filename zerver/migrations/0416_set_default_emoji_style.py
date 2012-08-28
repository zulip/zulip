from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def update_deprecated_emoji_style(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """
    This migration updates the emoji style for users who are using the
    deprecated Google blob style. Unless they are part of an organization
    which has Google blob as an organization default, these users will
    now use the modern Google emoji style.
    """

    UserProfile = apps.get_model("zerver", "UserProfile")
    RealmUserDefault = apps.get_model("zerver", "RealmUserDefault")

    UserProfile.objects.filter(emojiset="google-blob").exclude(
        realm__in=RealmUserDefault.objects.filter(emojiset="google-blob").values("realm")
    ).update(emojiset="google")


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0415_delete_scimclient"),
    ]

    operations = [
        migrations.RunPython(update_deprecated_emoji_style, elidable=True),
    ]
