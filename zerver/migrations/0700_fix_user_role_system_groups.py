from collections import defaultdict
from typing import Any

from django.conf import settings
from django.db import migrations, transaction
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models import Count
from django.utils.timezone import now as timezone_now

ROLE_REALM_OWNER = 100
ROLE_REALM_ADMINISTRATOR = 200
ROLE_MODERATOR = 300
ROLE_MEMBER = 400
ROLE_GUEST = 600


class SystemGroups:
    FULL_MEMBERS = "role:fullmembers"
    EVERYONE_ON_INTERNET = "role:internet"
    OWNERS = "role:owners"
    ADMINISTRATORS = "role:administrators"
    MODERATORS = "role:moderators"
    MEMBERS = "role:members"
    EVERYONE = "role:everyone"
    NOBODY = "role:nobody"


def fix_system_group_memberships_based_on_role(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
) -> None:
    """
    Our ldap integration supports syncing the user's .role based on their
    LDAP groups. It had a bug, updating only the .role value, without updating
    the system group memberships for the user accordingly. Additionally,
    the RealmAuditLog USER_ROLE_CHANGED entry was not created either.

    This migration fixes the group memberships for users whose .role
    doesn't match them, additionally also creating the missing RealmAuditLog
    object.
    """
    UserProfile = apps.get_model("zerver", "UserProfile")
    Realm = apps.get_model("zerver", "Realm")
    RealmAuditLog = apps.get_model("zerver", "RealmAuditLog")
    NamedUserGroup = apps.get_model("zerver", "NamedUserGroup")
    UserGroupMembership = apps.get_model("zerver", "UserGroupMembership")

    if settings.CORPORATE_ENABLED:
        # Zulip Cloud doesn't support LDAP, and this migration isn't
        # entirely race-safe, so it's better to not run in there.
        #
        # Self-hosted systems generally stop the server to apply
        # migrations, so rare races between role changes and this
        # migration are quite unlikely to impact anyone.
        return

    def get_system_user_group_by_name(group_name: str, realm_id: int) -> Any:
        return NamedUserGroup.objects.get(name=group_name, realm_id=realm_id, is_system_group=True)

    def realm_user_count_by_role(realm: Any) -> dict[str, Any]:
        """
        Code copied from the implementation in zerver.lib.user_counts
        """
        ROLE_COUNT_HUMANS = "11"
        ROLE_COUNT_BOTS = "12"

        human_counts = {
            str(ROLE_REALM_ADMINISTRATOR): 0,
            str(ROLE_REALM_OWNER): 0,
            str(ROLE_MODERATOR): 0,
            str(ROLE_MEMBER): 0,
            str(ROLE_GUEST): 0,
        }
        for value_dict in (
            UserProfile.objects.filter(realm=realm, is_bot=False, is_active=True)
            .values("role")
            .annotate(Count("role"))
        ):
            human_counts[str(value_dict["role"])] = value_dict["role__count"]
        bot_count = UserProfile.objects.filter(realm=realm, is_bot=True, is_active=True).count()
        return {
            ROLE_COUNT_HUMANS: human_counts,
            ROLE_COUNT_BOTS: bot_count,
        }

    def fix_user_memberships_if_needed(
        user_profile: Any,
        direct_memberships: list[Any],
        fullmembers_membership: Any | None,
        guest_group: Any,
        member_group: Any,
        fullmember_group: Any,
        moderator_group: Any,
        admin_group: Any,
        owner_group: Any,
    ) -> tuple[list[Any], list[Any], list[Any]]:
        new_memberships: list[Any] = []
        delete_memberships: list[Any] = []
        new_realmauditlogs: list[Any] = []

        group_id_to_group_name = {
            guest_group.id: "Guests",
            member_group.id: "Members",
            moderator_group.id: "Moderators",
            admin_group.id: "Administrators",
            owner_group.id: "Owners",
        }
        role_to_group = {
            ROLE_GUEST: guest_group,
            ROLE_MEMBER: member_group,
            ROLE_MODERATOR: moderator_group,
            ROLE_REALM_ADMINISTRATOR: admin_group,
            ROLE_REALM_OWNER: owner_group,
        }
        group_id_to_role = {v.id: k for k, v in role_to_group.items()}

        role = user_profile.role
        group_implied_by_role = role_to_group[role]

        if len(direct_memberships) == 0:
            print(
                f"User {user_profile.id} has no role group memberships. This is unexpected. Skipping."
            )
            return [], [], []

        if len(direct_memberships) > 1:
            group_names = [group_id_to_group_name[m.user_group_id] for m in direct_memberships]
            print(
                f"User {user_profile.id} has more than one role group membership: {group_names}. "
                f"Expected group based on role value of {role}: {group_id_to_group_name[group_implied_by_role.id]}. Skipping."
            )
            return [], [], []

        assert len(direct_memberships) == 1
        role_membership = direct_memberships[0]

        if role_membership.user_group_id == group_implied_by_role.id:
            # This user's state is correct.
            return [], [], []

        print(f"User {user_profile.id} will be fixed.")

        # We can determine what the user's previous role was based on the current incorrect membership.
        old_role = group_id_to_role[role_membership.user_group_id]

        # Fix the membership to point to the correct group for the user's role.
        memberships_to_delete.append(role_membership)
        new_memberships.append(
            UserGroupMembership(user_profile=user_profile, user_group=group_implied_by_role)
        )

        if role != ROLE_MEMBER and fullmembers_membership is not None:
            memberships_to_delete.append(fullmembers_membership)
        elif (
            role == ROLE_MEMBER
            and fullmembers_membership is None
            and realm.waiting_period_threshold == 0
        ):
            # For realms without waiting_period_threshold=0, this will get calculated correctly
            # by the promote_new_full_members cronjob.
            new_memberships.append(
                UserGroupMembership(user_profile=user_profile, user_group=fullmember_group)
            )

        # Create the RealmAuditLog that must be missing in these situations as well.
        USER_ROLE_CHANGED = 105
        OLD_VALUE = "1"
        NEW_VALUE = "2"
        ROLE_COUNT = "10"
        new_realmauditlogs.append(
            RealmAuditLog(
                backfilled=True,
                realm=user_profile.realm,
                modified_user=user_profile,
                acting_user=None,
                event_type=USER_ROLE_CHANGED,
                event_time=timezone_now(),
                extra_data={
                    OLD_VALUE: old_role,
                    NEW_VALUE: role,
                    # This could be done much more efficiently than
                    # calling the function that re-calculates all
                    # counts for every user we process, but we expect
                    # this fixup code path to only be relevant for a
                    # very small number of users.
                    ROLE_COUNT: realm_user_count_by_role(user_profile.realm),
                },
            )
        )

        return new_memberships, delete_memberships, new_realmauditlogs

    print()
    for realm in Realm.objects.exclude(string_id=settings.SYSTEM_BOT_REALM):
        print(f"Processing realm {realm.id}")
        guest_group = get_system_user_group_by_name(SystemGroups.EVERYONE, realm.id)
        member_group = get_system_user_group_by_name(SystemGroups.MEMBERS, realm.id)
        moderator_group = get_system_user_group_by_name(SystemGroups.MODERATORS, realm.id)
        admin_group = get_system_user_group_by_name(SystemGroups.ADMINISTRATORS, realm.id)
        owner_group = get_system_user_group_by_name(SystemGroups.OWNERS, realm.id)

        fullmember_group = get_system_user_group_by_name(SystemGroups.FULL_MEMBERS, realm.id)

        role_group_ids = [
            guest_group.id,
            member_group.id,
            moderator_group.id,
            admin_group.id,
            owner_group.id,
        ]

        direct_memberships = UserGroupMembership.objects.filter(user_group_id__in=role_group_ids)
        user_id_to_group_memberships = defaultdict(list)
        for membership in direct_memberships:
            user_id_to_group_memberships[membership.user_profile_id].append(membership)

        # Full members work differently than other roles - membership in this group is not mutually
        # exclusive with membership in other groups. More concretely, a user can be in the Members
        # group and Fullmembers group simultaneously.
        # Due to this trait, it requires different handling and the info will be kept in a separate
        # structure.
        fullmembers_memberships = UserGroupMembership.objects.filter(user_group=fullmember_group)
        user_id_fullmembers_membership: dict[int, Any] = defaultdict(lambda: None)
        for membership in fullmembers_memberships:
            user_id_fullmembers_membership[membership.user_profile_id] = membership

        memberships_to_create: list[Any] = []
        memberships_to_delete: list[Any] = []
        realmauditlogs_to_create: list[Any] = []
        for user_profile in UserProfile.objects.filter(realm=realm):
            new_memberships, delete_memberships, new_realmauditlogs = (
                fix_user_memberships_if_needed(
                    user_profile,
                    user_id_to_group_memberships[user_profile.id],
                    user_id_fullmembers_membership[user_profile.id],
                    guest_group=guest_group,
                    member_group=member_group,
                    fullmember_group=fullmember_group,
                    moderator_group=moderator_group,
                    admin_group=admin_group,
                    owner_group=owner_group,
                )
            )
            memberships_to_create += new_memberships
            memberships_to_delete + delete_memberships
            realmauditlogs_to_create += new_realmauditlogs

        with transaction.atomic(durable=True):
            UserGroupMembership.objects.filter(
                id__in=[m.id for m in memberships_to_delete]
            ).delete()
            UserGroupMembership.objects.bulk_create(memberships_to_create)
            RealmAuditLog.objects.bulk_create(realmauditlogs_to_create)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("zerver", "0699_scheduledmessage_reminder_target_message_id"),
    ]

    operations = [
        migrations.RunPython(
            fix_system_group_memberships_based_on_role,
            reverse_code=migrations.RunPython.noop,
            elidable=True,
        ),
    ]
