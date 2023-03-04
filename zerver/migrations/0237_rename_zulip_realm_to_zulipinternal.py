from django.conf import settings
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def rename_zulip_realm_to_zulipinternal(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    if not settings.PRODUCTION:
        return

    Realm = apps.get_model("zerver", "Realm")
    UserProfile = apps.get_model("zerver", "UserProfile")

    if Realm.objects.count() == 0:
        # Database not yet populated, do nothing:
        return

    if Realm.objects.filter(string_id="zulipinternal").exists():
        return
    if not Realm.objects.filter(string_id="zulip").exists():
        # If the user renamed the `zulip` system bot realm (or deleted
        # it), there's nothing for us to do.
        return

    internal_realm = Realm.objects.get(string_id="zulip")

    # For safety, as a sanity check, verify that "internal_realm" is indeed the realm for system bots:
    welcome_bot = UserProfile.objects.get(email="welcome-bot@zulip.com")
    assert welcome_bot.realm.id == internal_realm.id

    internal_realm.string_id = "zulipinternal"
    internal_realm.name = "System use only"
    internal_realm.save()


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0236_remove_illegal_characters_email_full"),
    ]

    operations = [
        migrations.RunPython(rename_zulip_realm_to_zulipinternal, elidable=True),
    ]
