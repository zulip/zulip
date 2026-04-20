from typing import Any

from django.db.models import Count

from zerver.lib.user_groups import get_recursive_group_members
from zerver.models import Realm, RealmAuditLog, UserProfile
from zerver.models.groups import SystemGroups, get_realm_system_groups_name_dict


def realm_user_count(realm: Realm) -> int:
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False).count()


def get_role_based_system_group_member_count(
    human_counts: dict[str, int],
    system_group_name: str,
) -> int:
    if system_group_name == SystemGroups.NOBODY:
        return 0

    if system_group_name == SystemGroups.OWNERS:
        roles = [UserProfile.ROLE_REALM_OWNER]
    elif system_group_name == SystemGroups.ADMINISTRATORS:
        roles = [UserProfile.ROLE_REALM_OWNER, UserProfile.ROLE_REALM_ADMINISTRATOR]
    elif system_group_name == SystemGroups.MODERATORS:
        roles = [
            UserProfile.ROLE_REALM_OWNER,
            UserProfile.ROLE_REALM_ADMINISTRATOR,
            UserProfile.ROLE_MODERATOR,
        ]
    elif system_group_name == SystemGroups.MEMBERS:
        roles = [
            UserProfile.ROLE_REALM_OWNER,
            UserProfile.ROLE_REALM_ADMINISTRATOR,
            UserProfile.ROLE_MODERATOR,
            UserProfile.ROLE_MEMBER,
        ]
    else:
        assert system_group_name in [SystemGroups.EVERYONE, SystemGroups.EVERYONE_ON_INTERNET]
        roles = UserProfile.ROLE_TYPES

    return sum(human_counts[str(role)] for role in roles)


def realm_user_count_by_role(realm: Realm) -> dict[str, Any]:
    human_counts = {
        str(UserProfile.ROLE_REALM_ADMINISTRATOR): 0,
        str(UserProfile.ROLE_REALM_OWNER): 0,
        str(UserProfile.ROLE_MODERATOR): 0,
        str(UserProfile.ROLE_MEMBER): 0,
        str(UserProfile.ROLE_GUEST): 0,
        "workplace_users": 0,
        "non_workplace_users": 0,
    }
    for value_dict in (
        UserProfile.objects.filter(realm=realm, is_bot=False, is_active=True)
        .values("role")
        .annotate(Count("role"))
    ):
        human_counts[str(value_dict["role"])] = value_dict["role__count"]
    bot_count = UserProfile.objects.filter(realm=realm, is_bot=True, is_active=True).count()

    total_human_count = sum(human_counts[str(role)] for role in UserProfile.ROLE_TYPES)

    system_groups_dict = get_realm_system_groups_name_dict(realm.id)
    if (
        realm.workplace_users_group_id in system_groups_dict
        and system_groups_dict[realm.workplace_users_group_id] != SystemGroups.FULL_MEMBERS
    ):
        # If workplace_users_group is set to a role based group except full members
        # group we can calculate the number of workplace users from already computed
        # role counts.
        system_group_name = system_groups_dict[realm.workplace_users_group_id]
        human_counts["workplace_users"] = get_role_based_system_group_member_count(
            human_counts, system_group_name
        )
    else:
        human_counts["workplace_users"] = (
            get_recursive_group_members(realm.workplace_users_group_id)
            .filter(is_bot=False, is_active=True)
            .count()
        )

    human_counts["non_workplace_users"] = total_human_count - human_counts["workplace_users"]

    return {
        RealmAuditLog.ROLE_COUNT_HUMANS: human_counts,
        RealmAuditLog.ROLE_COUNT_BOTS: bot_count,
    }
