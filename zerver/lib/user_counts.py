from typing import Any, Dict

from django.db.models import Count

from zerver.models import Realm, RealmAuditLog, UserProfile


def realm_user_count(realm: Realm) -> int:
    return UserProfile.objects.filter(realm=realm, is_active=True, is_bot=False).count()


def realm_user_count_by_role(realm: Realm) -> Dict[str, Any]:
    human_counts = {
        str(UserProfile.ROLE_REALM_ADMINISTRATOR): 0,
        str(UserProfile.ROLE_REALM_OWNER): 0,
        str(UserProfile.ROLE_MODERATOR): 0,
        str(UserProfile.ROLE_MEMBER): 0,
        str(UserProfile.ROLE_GUEST): 0,
    }
    for value_dict in (
        UserProfile.objects.filter(realm=realm, is_bot=False, is_active=True)
        .values("role")
        .annotate(Count("role"))
    ):
        human_counts[str(value_dict["role"])] = value_dict["role__count"]
    bot_count = UserProfile.objects.filter(realm=realm, is_bot=True, is_active=True).count()
    return {
        RealmAuditLog.ROLE_COUNT_HUMANS: human_counts,
        RealmAuditLog.ROLE_COUNT_BOTS: bot_count,
    }
