import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Mapping, Optional, Sequence

from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.users import check_user_can_access_all_users, get_accessible_user_ids
from zerver.models import Realm, UserPresence, UserProfile


def get_presence_dicts_for_rows(
    all_rows: Sequence[Mapping[str, Any]], slim_presence: bool
) -> Dict[str, Dict[str, Any]]:
    if slim_presence:
        # Stringify user_id here, since it's gonna be turned
        # into a string anyway by JSON, and it keeps mypy happy.
        get_user_key = lambda row: str(row["user_profile_id"])
        get_user_presence_info = get_modern_user_presence_info
    else:
        get_user_key = lambda row: row["user_profile__email"]
        get_user_presence_info = get_legacy_user_presence_info

    user_statuses: Dict[str, Dict[str, Any]] = {}

    for presence_row in all_rows:
        user_key = get_user_key(presence_row)

        last_active_time = user_presence_datetime_with_date_joined_default(
            presence_row["last_active_time"], presence_row["user_profile__date_joined"]
        )
        last_connected_time = user_presence_datetime_with_date_joined_default(
            presence_row["last_connected_time"], presence_row["user_profile__date_joined"]
        )

        info = get_user_presence_info(
            last_active_time,
            last_connected_time,
        )
        user_statuses[user_key] = info

    return user_statuses


def user_presence_datetime_with_date_joined_default(
    dt: Optional[datetime], date_joined: datetime
) -> datetime:
    """
    Our data models support UserPresence objects not having None
    values for last_active_time/last_connected_time. The legacy API
    however has always sent timestamps, so for backward
    compatibility we cannot send such values through the API and need
    to default to a sane

    This helper functions expects to take a last_active_time or
    last_connected_time value and the date_joined of the user, which
    will serve as the default value if the first argument is None.
    """
    if dt is None:
        return date_joined

    return dt


def get_modern_user_presence_info(
    last_active_time: datetime, last_connected_time: datetime
) -> Dict[str, Any]:
    # TODO: Do further bandwidth optimizations to this structure.
    result = {}
    result["active_timestamp"] = datetime_to_timestamp(last_active_time)
    result["idle_timestamp"] = datetime_to_timestamp(last_connected_time)
    return result


def get_legacy_user_presence_info(
    last_active_time: datetime, last_connected_time: datetime
) -> Dict[str, Any]:
    """
    Reformats the modern UserPresence data structure so that legacy
    API clients can still access presence data.
    We expect this code to remain mostly unchanged until we can delete it.
    """

    # Now we put things together in the legacy presence format with
    # one client + an `aggregated` field.
    #
    # TODO: Look at whether we can drop to just the "aggregated" field
    # if no clients look at the rest.
    most_recent_info = format_legacy_presence_dict(last_active_time, last_connected_time)

    result = {}

    # The word "aggregated" here is possibly misleading.
    # It's really just the most recent client's info.
    result["aggregated"] = dict(
        client=most_recent_info["client"],
        status=most_recent_info["status"],
        timestamp=most_recent_info["timestamp"],
    )

    result["website"] = most_recent_info

    return result


def format_legacy_presence_dict(
    last_active_time: datetime, last_connected_time: datetime
) -> Dict[str, Any]:
    """
    This function assumes it's being called right after the presence object was updated,
    and is not meant to be used on old presence data.
    """
    if (
        last_active_time
        + timedelta(seconds=settings.PRESENCE_LEGACY_EVENT_OFFSET_FOR_ACTIVITY_SECONDS)
        >= last_connected_time
    ):
        status = UserPresence.LEGACY_STATUS_ACTIVE
        timestamp = datetime_to_timestamp(last_active_time)
    else:
        status = UserPresence.LEGACY_STATUS_IDLE
        timestamp = datetime_to_timestamp(last_connected_time)

    # This field was never used by clients of the legacy API, so we
    # just set it to a fixed value for API format compatibility.
    pushable = False

    return dict(client="website", status=status, timestamp=timestamp, pushable=pushable)


def get_presence_for_user(
    user_profile_id: int, slim_presence: bool = False
) -> Dict[str, Dict[str, Any]]:
    query = UserPresence.objects.filter(user_profile_id=user_profile_id).values(
        "last_active_time",
        "last_connected_time",
        "user_profile__email",
        "user_profile_id",
        "user_profile__enable_offline_push_notifications",
        "user_profile__date_joined",
    )
    presence_rows = list(query)

    return get_presence_dicts_for_rows(presence_rows, slim_presence)


def get_presence_dict_by_realm(
    realm: Realm, slim_presence: bool = False, requesting_user_profile: Optional[UserProfile] = None
) -> Dict[str, Dict[str, Any]]:
    two_weeks_ago = timezone_now() - timedelta(weeks=2)
    query = UserPresence.objects.filter(
        realm_id=realm.id,
        last_connected_time__gte=two_weeks_ago,
        user_profile__is_active=True,
        user_profile__is_bot=False,
    )

    if settings.CAN_ACCESS_ALL_USERS_GROUP_LIMITS_PRESENCE and not check_user_can_access_all_users(
        requesting_user_profile
    ):
        assert requesting_user_profile is not None
        accessible_user_ids = get_accessible_user_ids(realm, requesting_user_profile)
        query = query.filter(user_profile_id__in=accessible_user_ids)

    presence_rows = list(
        query.values(
            "last_active_time",
            "last_connected_time",
            "user_profile__email",
            "user_profile_id",
            "user_profile__enable_offline_push_notifications",
            "user_profile__date_joined",
        )
    )

    return get_presence_dicts_for_rows(presence_rows, slim_presence)


def get_presences_for_realm(
    realm: Realm, slim_presence: bool, requesting_user_profile: UserProfile
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    if realm.presence_disabled:
        # Return an empty dict if presence is disabled in this realm
        return defaultdict(dict)

    return get_presence_dict_by_realm(realm, slim_presence, requesting_user_profile)


def get_presence_response(
    requesting_user_profile: UserProfile, slim_presence: bool
) -> Dict[str, Any]:
    realm = requesting_user_profile.realm
    server_timestamp = time.time()
    presences = get_presences_for_realm(realm, slim_presence, requesting_user_profile)
    return dict(presences=presences, server_timestamp=server_timestamp)
