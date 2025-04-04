import time
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.utils.timezone import now as timezone_now

from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.users import check_user_can_access_all_users, get_accessible_user_ids
from zerver.models import Realm, UserPresence, UserProfile


def get_presence_dicts_for_rows(
    all_rows: Sequence[Mapping[str, Any]], slim_presence: bool
) -> dict[str, dict[str, Any]]:
    if slim_presence:
        # Stringify user_id here, since it's gonna be turned
        # into a string anyway by JSON, and it keeps mypy happy.
        get_user_key = lambda row: str(row["user_profile_id"])
        get_user_presence_info = get_modern_user_presence_info
    else:
        get_user_key = lambda row: row["user_profile__email"]
        get_user_presence_info = get_legacy_user_presence_info

    user_statuses: dict[str, dict[str, Any]] = {}

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
    dt: datetime | None, date_joined: datetime
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
) -> dict[str, Any]:
    # TODO: Do further bandwidth optimizations to this structure.
    result = {}
    result["active_timestamp"] = datetime_to_timestamp(last_active_time)
    result["idle_timestamp"] = datetime_to_timestamp(last_connected_time)
    return result


def get_legacy_user_presence_info(
    last_active_time: datetime, last_connected_time: datetime
) -> dict[str, Any]:
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
) -> dict[str, Any]:
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
) -> dict[str, dict[str, Any]]:
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
    realm: Realm,
    slim_presence: bool = False,
    last_update_id_fetched_by_client: int | None = None,
    history_limit_days: int | None = None,
    requesting_user_profile: UserProfile | None = None,
) -> tuple[dict[str, dict[str, Any]], int]:
    now = timezone_now()
    if history_limit_days is not None:
        fetch_since_datetime = now - timedelta(days=history_limit_days)
    else:
        # The original behavior for this API was to return last two weeks
        # of data at most, so we preserve that when the history_limit_days
        # param is not provided.
        fetch_since_datetime = now - timedelta(days=14)

    kwargs: dict[str, object] = dict()
    if last_update_id_fetched_by_client is not None:
        kwargs["last_update_id__gt"] = last_update_id_fetched_by_client

    if last_update_id_fetched_by_client is None or last_update_id_fetched_by_client <= 0:
        # If the client already has fetched some presence data, as indicated by
        # last_update_id_fetched_by_client, then filtering by last_connected_time
        # is redundant, as it shouldn't affect the results.
        kwargs["last_connected_time__gte"] = fetch_since_datetime

    if history_limit_days != 0:
        query = UserPresence.objects.filter(
            realm_id=realm.id,
            user_profile__is_active=True,
            user_profile__is_bot=False,
            **kwargs,
        )
    else:
        # If history_limit_days is 0, the client doesn't want any presence data.
        # Explicitly return an empty QuerySet to avoid a query or races which
        # might cause a UserPresence row to get fetched if it gets updated
        # during the execution of this function.
        query = UserPresence.objects.none()

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
            "last_update_id",
        )
    )
    # Get max last_update_id from the list.
    if presence_rows:
        last_update_id_fetched_by_server: int | None = max(
            row["last_update_id"] for row in presence_rows
        )
    elif last_update_id_fetched_by_client is not None:
        # If there are no results, that means that are no new updates to presence
        # since what the client has last seen. Therefore, returning the same
        # last_update_id that the client provided is correct.
        last_update_id_fetched_by_server = last_update_id_fetched_by_client
    else:
        # If the client didn't specify a last_update_id, we return -1 to indicate
        # the lack of any data fetched, while sticking to the convention of
        # returning an integer.
        last_update_id_fetched_by_server = -1

    assert last_update_id_fetched_by_server is not None
    return get_presence_dicts_for_rows(
        presence_rows, slim_presence
    ), last_update_id_fetched_by_server


def get_presences_for_realm(
    realm: Realm,
    slim_presence: bool,
    last_update_id_fetched_by_client: int | None,
    history_limit_days: int | None,
    requesting_user_profile: UserProfile,
) -> tuple[dict[str, dict[str, dict[str, Any]]], int]:
    if realm.presence_disabled:
        # Return an empty dict if presence is disabled in this realm
        return defaultdict(dict), -1

    return get_presence_dict_by_realm(
        realm,
        slim_presence,
        last_update_id_fetched_by_client,
        history_limit_days,
        requesting_user_profile=requesting_user_profile,
    )


def get_presence_response(
    requesting_user_profile: UserProfile,
    slim_presence: bool,
    last_update_id_fetched_by_client: int | None = None,
    history_limit_days: int | None = None,
) -> dict[str, Any]:
    realm = requesting_user_profile.realm
    server_timestamp = time.time()
    presences, last_update_id_fetched_by_server = get_presences_for_realm(
        realm,
        slim_presence,
        last_update_id_fetched_by_client,
        history_limit_days,
        requesting_user_profile=requesting_user_profile,
    )

    response_dict = dict(
        presences=presences,
        server_timestamp=server_timestamp,
        presence_last_update_id=last_update_id_fetched_by_server,
    )

    return response_dict
