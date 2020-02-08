from collections import defaultdict

import datetime
import itertools
import time

from django.utils.timezone import now as timezone_now

from typing import Any, Dict, List, Set

from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import (
    query_for_ids,
    PushDeviceToken,
    Realm,
    UserPresence,
    UserProfile,
)

def get_status_dicts_for_rows(all_rows: List[Dict[str, Any]],
                              mobile_user_ids: Set[int],
                              slim_presence: bool) -> Dict[str, Dict[str, Any]]:

    # Note that datetime values have sub-second granularity, which is
    # mostly important for avoiding test flakes, but it's also technically
    # more precise for real users.
    # We could technically do this sort with the database, but doing it
    # here prevents us from having to assume the caller is playing nice.
    all_rows = sorted(
        all_rows,
        key = lambda row: (row['user_profile__id'], row['timestamp'])
    )

    # For now slim_presence just means that we will use
    # user_id as a key instead of email.  We will eventually
    # do other things based on this flag to make things simpler
    # for the clients.
    if slim_presence:
        # Stringify user_id here, since it's gonna be turned
        # into a string anyway by JSON, and it keeps mypy happy.
        get_user_key = lambda row: str(row['user_profile__id'])
    else:
        get_user_key = lambda row: row['user_profile__email']

    user_statuses = dict()  # type: Dict[str, Dict[str, Any]]

    for user_key, presence_rows in itertools.groupby(all_rows, get_user_key):
        info = get_legacy_user_info(
            list(presence_rows),
            mobile_user_ids
        )
        user_statuses[user_key] = info

    return user_statuses

def get_legacy_user_info(presence_rows: List[Dict[str, Any]],
                         mobile_user_ids: Set[int]) -> Dict[str, Any]:

    # The format of data here is for legacy users of our API,
    # including old versions of the mobile app.
    info_rows = []
    for row in presence_rows:
        client_name = row['client__name']
        status = UserPresence.status_to_string(row['status'])
        dt = row['timestamp']
        timestamp = datetime_to_timestamp(dt)
        push_enabled = row['user_profile__enable_offline_push_notifications']
        has_push_devices = row['user_profile__id'] in mobile_user_ids
        pushable = (push_enabled and has_push_devices)

        info = dict(
            client=client_name,
            status=status,
            timestamp=timestamp,
            pushable=pushable,
        )

        info_rows.append(info)

    most_recent_info = info_rows[-1]

    result = dict()

    # The word "aggegrated" here is possibly misleading.
    # It's really just the most recent client's info.
    result['aggregated'] = dict(
        client=most_recent_info['client'],
        status=most_recent_info['status'],
        timestamp=most_recent_info['timestamp'],
    )

    # Build a dictionary of client -> info.  There should
    # only be one row per client, but to be on the safe side,
    # we always overwrite with rows that are later in our list.
    for info in info_rows:
        result[info['client']] = info

    return result

def get_presence_for_user(user_profile_id: int,
                          slim_presence: bool=False) -> Dict[str, Dict[str, Any]]:
    query = UserPresence.objects.filter(user_profile_id=user_profile_id).values(
        'client__name',
        'status',
        'timestamp',
        'user_profile__email',
        'user_profile__id',
        'user_profile__enable_offline_push_notifications',
    )
    presence_rows = list(query)

    mobile_user_ids = set()  # type: Set[int]
    if PushDeviceToken.objects.filter(user_id=user_profile_id).exists():  # nocoverage
        # TODO: Add a test, though this is low priority, since we don't use mobile_user_ids yet.
        mobile_user_ids.add(user_profile_id)

    return get_status_dicts_for_rows(presence_rows, mobile_user_ids, slim_presence)


def get_status_dict_by_realm(realm_id: int, slim_presence: bool = False) -> Dict[str, Dict[str, Any]]:
    user_profile_ids = UserProfile.objects.filter(
        realm_id=realm_id,
        is_active=True,
        is_bot=False
    ).order_by('id').values_list('id', flat=True)

    user_profile_ids = list(user_profile_ids)
    if not user_profile_ids:  # nocoverage
        # This conditional is necessary because query_for_ids
        # throws an exception if passed an empty list.
        #
        # It's not clear this condition is actually possible,
        # though, because it shouldn't be possible to end up with
        # a realm with 0 active users.
        return {}

    two_weeks_ago = timezone_now() - datetime.timedelta(weeks=2)
    query = UserPresence.objects.filter(
        realm_id=realm_id,
        timestamp__gte=two_weeks_ago,
        user_profile__is_active=True,
        user_profile__is_bot=False,
    ).values(
        'client__name',
        'status',
        'timestamp',
        'user_profile__email',
        'user_profile__id',
        'user_profile__enable_offline_push_notifications',
    )

    presence_rows = list(query)

    mobile_query = PushDeviceToken.objects.distinct(
        'user_id'
    ).values_list(
        'user_id',
        flat=True
    )

    mobile_query = query_for_ids(
        query=mobile_query,
        user_ids=user_profile_ids,
        field='user_id'
    )
    mobile_user_ids = set(mobile_query)

    return get_status_dicts_for_rows(presence_rows, mobile_user_ids, slim_presence)

def get_presences_for_realm(realm: Realm,
                            slim_presence: bool) -> Dict[str, Dict[str, Dict[str, Any]]]:

    if realm.presence_disabled:
        # Return an empty dict if presence is disabled in this realm
        return defaultdict(dict)

    return get_status_dict_by_realm(realm.id, slim_presence)

def get_presence_response(requesting_user_profile: UserProfile,
                          slim_presence: bool) -> Dict[str, Any]:
    realm = requesting_user_profile.realm
    server_timestamp = time.time()
    presences = get_presences_for_realm(realm, slim_presence)
    return dict(presences=presences, server_timestamp=server_timestamp)
