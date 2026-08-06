from datetime import datetime

from django.conf import settings
from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.utils.timezone import now as timezone_now

ROLE_REALM_OWNER = 100
ROLE_REALM_ADMINISTRATOR = 200
ROLE_MODERATOR = 300
ROLE_MEMBER = 400
ROLE_GUEST = 600

# Values of AuditLogEventType; see zerver/models/realm_audit_logs.py.
USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED = 703
USER_GROUP_DIRECT_USER_MEMBERSHIP_REMOVED = 704

FULL_MEMBERS_GROUP_NAME = "role:fullmembers"
MEMBERS_GROUP_NAME = "role:members"


def bot_should_be_full_member(
    owner_role: int, owner_date_joined: datetime, waiting_period_threshold: int
) -> bool:
    # Mirrors the inverse of UserProfile.determine_is_provisional_member for a
    # member-role bot: it follows its owner, and is never a full member while
    # owned by a guest.
    if owner_role == ROLE_GUEST:
        return False
    if owner_role in (ROLE_REALM_OWNER, ROLE_REALM_ADMINISTRATOR, ROLE_MODERATOR):
        return True
    return (timezone_now() - owner_date_joined).days >= waiting_period_threshold


def backfill_bot_full_member_status(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """A member-role bot's full-member status now follows its owner rather than
    the bot's own date_joined (issue #32468). Existing bots were placed in the
    FULL_MEMBERS system group under the old rule, and in realms with
    waiting_period_threshold=0 the promote_new_full_members cronjob never runs
    to recompute them. Reconcile every member-role bot's FULL_MEMBERS
    membership with its owner once, so the invariant holds on existing data.
    """
    Realm = apps.get_model("zerver", "Realm")
    UserProfile = apps.get_model("zerver", "UserProfile")
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")
    UserGroupMembership = apps.get_model("zerver", "UserGroupMembership")

    for realm in Realm.objects.exclude(string_id=settings.SYSTEM_BOT_REALM):
        try:
            full_members_group = NamedUserGroup.objects.get(
                name=FULL_MEMBERS_GROUP_NAME, realm_id=realm.id, is_system_group=True
            )
            members_group = NamedUserGroup.objects.get(
                name=MEMBERS_GROUP_NAME, realm_id=realm.id, is_system_group=True
            )
        except NamedUserGroup.DoesNotExist:
            # A realm without role-based system groups is fixed up by earlier
            # migrations; there is nothing to reconcile here.
            continue

        bot_rows = list(
            UserProfile.objects.filter(
                realm_id=realm.id,
                is_bot=True,
                role=ROLE_MEMBER,
                bot_owner__isnull=False,
            ).values_list("id", "bot_owner__role", "bot_owner__date_joined")
        )
        if not bot_rows:
            continue

        bot_ids = [row[0] for row in bot_rows]
        currently_full_member_ids = set(
            UserGroupMembership.objects.filter(
                user_group=full_members_group, user_profile_id__in=bot_ids
            ).values_list("user_profile_id", flat=True)
        )
        # A bot can only join FULL_MEMBERS if it is in MEMBERS, matching how
        # update_users_in_full_members_system_group promotes members.
        member_group_bot_ids = set(
            UserGroupMembership.objects.filter(
                user_group=members_group, user_profile_id__in=bot_ids
            ).values_list("user_profile_id", flat=True)
        )

        memberships_to_add = []
        ids_to_remove = []
        for bot_id, owner_role, owner_date_joined in bot_rows:
            should_be_full = bot_should_be_full_member(
                owner_role, owner_date_joined, realm.waiting_period_threshold
            )
            currently_full = bot_id in currently_full_member_ids
            if should_be_full and not currently_full and bot_id in member_group_bot_ids:
                memberships_to_add.append(
                    UserGroupMembership(user_profile_id=bot_id, user_group=full_members_group)
                )
            elif not should_be_full and currently_full:
                ids_to_remove.append(bot_id)

        if not memberships_to_add and not ids_to_remove:
            continue

        now = timezone_now()
        audit_logs = [
            RealmAuditLog(
                realm_id=realm.id,
                modified_user_id=membership.user_profile_id,
                modified_user_group=full_members_group,
                event_type=USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
                event_time=now,
                acting_user=None,
                backfilled=True,
            )
            for membership in memberships_to_add
        ] + [
            RealmAuditLog(
                realm_id=realm.id,
                modified_user_id=bot_id,
                modified_user_group=full_members_group,
                event_type=USER_GROUP_DIRECT_USER_MEMBERSHIP_REMOVED,
                event_time=now,
                acting_user=None,
                backfilled=True,
            )
            for bot_id in ids_to_remove
        ]

        with transaction.atomic(durable=True):
            if ids_to_remove:
                UserGroupMembership.objects.filter(
                    user_group=full_members_group, user_profile_id__in=ids_to_remove
                ).delete()
            if memberships_to_add:
                UserGroupMembership.objects.bulk_create(memberships_to_add)
            RealmAuditLog.objects.bulk_create(audit_logs)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0805_fix_deleteduser_email"),
    ]

    operations = [
        migrations.RunPython(
            backfill_bot_full_member_status,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
