from django.db import migrations
from django.db.backends.postgresql.schema import DatabaseSchemaEditor
from django.db.migrations.state import StateApps


def set_emoji_author(apps: StateApps, schema_editor: DatabaseSchemaEditor) -> None:
    """
    This migration establishes the invariant that all RealmEmoji objects have .author set
    and queues events for reuploading all RealmEmoji.
    """

    RealmEmoji = apps.get_model("zerver", "RealmEmoji")
    UserProfile = apps.get_model("zerver", "UserProfile")
    ROLE_REALM_OWNER = 100

    realm_emoji_to_update = []
    for realm_emoji in RealmEmoji.objects.all():
        if realm_emoji.author_id is None:
            user_profile = (
                UserProfile.objects.filter(
                    realm_id=realm_emoji.realm_id, is_active=True, role=ROLE_REALM_OWNER
                )
                .order_by("id")
                .first()
            )
            realm_emoji.author_id = user_profile.id
            realm_emoji_to_update.append(realm_emoji)

    RealmEmoji.objects.bulk_update(realm_emoji_to_update, ["author_id"])

    # Previously, this also pushed `reupload_realm_emoji` events onto
    # the `deferred_work` queue; however,
    # https://github.com/zulip/zulip/issues/21608 made those possibly
    # run too early, and that work was repeated in migration 0387 to
    # ensure it ran.  As such, the work has been removed from this
    # migration, so it does not unnecessarily run twice.


class Migration(migrations.Migration):

    dependencies = [
        ("zerver", "0375_invalid_characters_in_stream_names"),
    ]

    operations = [
        migrations.RunPython(set_emoji_author, reverse_code=migrations.RunPython.noop),
    ]
