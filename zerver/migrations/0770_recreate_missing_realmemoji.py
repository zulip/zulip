from typing import Any

from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Exists, OuterRef

ROLE_REALM_OWNER = 100
REALM_EMOJI_ADDED = 226


def recreate_missing_realmemoji(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    RealmEmoji = apps.get_model("zerver", "RealmEmoji")
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
    Realm = apps.get_model("zerver", "Realm")
    UserProfile = apps.get_model("zerver", "UserProfile")

    def get_first_human_owner_user(realm: Any) -> Any:
        first_active_human_owner = UserProfile.objects.filter(
            realm=realm, is_bot=False, role=ROLE_REALM_OWNER, is_active=True
        ).first()
        if first_active_human_owner is not None:
            return first_active_human_owner

        fallback_owner_user = UserProfile.objects.filter(
            realm=realm, is_bot=False, role=ROLE_REALM_OWNER, is_active=False
        ).first()
        if fallback_owner_user is None:
            raise AssertionError(f"No human owner users in realm {realm.string_id}")
        return fallback_owner_user

    emoji_add_log_queryset = RealmAuditLog.objects.filter(
        realm=OuterRef("pk"),
        event_type=REALM_EMOJI_ADDED,
    )
    for realm in (
        Realm.objects.annotate(has_emoji_add_log=Exists(emoji_add_log_queryset))
        .filter(has_emoji_add_log=True)
        .iterator()
    ):
        with transaction.atomic():
            emoji_add_records = RealmAuditLog.objects.filter(
                realm=realm,
                event_type=REALM_EMOJI_ADDED,
            ).order_by("-id")
            first_owner = get_first_human_owner_user(realm)
            for emoji_add in emoji_add_records.iterator():
                emoji = list(emoji_add.extra_data["realm_emoji"].values())
                for e in emoji:
                    if RealmEmoji.objects.filter(id=int(e["id"])).exists():
                        continue
                    file_name = e["source_url"][1 + e["source_url"].rfind("/") :]
                    print(f"Creating missing emoji {e['name']}")
                    RealmEmoji.objects.create(
                        id=int(e["id"]),
                        realm_id=realm.id,
                        name=e["name"],
                        author_id=first_owner.id,
                        file_name=file_name,
                        deactivated=e["deactivated"],
                        is_animated=e["still_url"] is not None,
                    )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0769_rename_profile_field_twitter_to_x"),
    ]

    operations = [
        migrations.RunPython(
            recreate_missing_realmemoji,
            elidable=True,
        ),
    ]
