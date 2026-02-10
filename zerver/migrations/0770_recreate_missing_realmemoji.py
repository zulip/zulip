from typing import Any

from django.db import connection, migrations, transaction
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
            first_owner = None
            sql = """
                WITH distinct_emoji AS (
                    SELECT DISTINCT emoji.value AS e
                    FROM zerver_realmauditlog
                    CROSS JOIN LATERAL jsonb_each(
                        zerver_realmauditlog.extra_data->'realm_emoji'
                    ) AS emoji(key, value)
                    WHERE zerver_realmauditlog.realm_id = %s
                    AND zerver_realmauditlog.event_type = %s
                )
                SELECT * FROM distinct_emoji
                LEFT JOIN zerver_realmemoji
                    ON zerver_realmemoji.id = (e->>'id')::integer
                    OR (zerver_realmemoji.name = e->>'name'
                        AND zerver_realmemoji.realm_id = %s)
                WHERE zerver_realmemoji.id IS NULL
            """
            with connection.cursor() as cursor:
                cursor.execute(sql, [realm.id, REALM_EMOJI_ADDED, realm.id])
                for (orphaned_emoji,) in cursor.fetchall():
                    print(
                        f"Creating missing emoji {orphaned_emoji['id']} = {realm.string_id} / {orphaned_emoji['name']}"
                    )
                    file_name = orphaned_emoji["source_url"][
                        1 + orphaned_emoji["source_url"].rfind("/") :
                    ]
                    if first_owner is None:
                        first_owner = get_first_human_owner_user(realm)

                    RealmEmoji.objects.create(
                        id=int(orphaned_emoji["id"]),
                        realm_id=realm.id,
                        name=orphaned_emoji["name"],
                        author_id=first_owner.id,
                        file_name=file_name,
                        deactivated=orphaned_emoji["deactivated"],
                        is_animated=orphaned_emoji["still_url"] is not None,
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
