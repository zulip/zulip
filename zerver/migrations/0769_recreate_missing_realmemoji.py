from typing import Any

from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps

ROLE_REALM_OWNER = 100
REALM_EMOJI_ADDED = 226


def recreate_missing_realmemoji(apps: StateApps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    RealmEmoji = apps.get_model("zerver", "RealmEmoji")
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
    Realm = apps.get_model("zerver", "Realm")
    UserProfile = apps.get_model("zerver", "UserProfile")

    def get_human_owner_users(realm: Any) -> Any:
        return UserProfile.objects.filter(
            realm=realm, is_bot=False, role=ROLE_REALM_OWNER, is_active=True
        )

    for realm in Realm.objects.all().iterator():
        with transaction.atomic():
            emoji_add_records = RealmAuditLog.objects.filter(
                realm=realm,
                event_type=REALM_EMOJI_ADDED,
            ).order_by("-id")
            first_owner = get_human_owner_users(realm).order_by("id").first()
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

    # TODO: flushing the cache would be helpful. perhaps just add flush-memcached to suggested instructions?


class Migration(migrations.Migration):
    dependencies = [
        ("zerver", "0768_realmauditlog_scrubbed"),
    ]

    operations = [
        migrations.RunPython(
            recreate_missing_realmemoji,
            elidable=True,
        ),
    ]
