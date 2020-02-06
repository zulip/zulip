from collections import defaultdict

import datetime
import time

from django.utils.timezone import now as timezone_now

from typing import Any, Dict
from zerver.models import (
    query_for_ids,
    PushDeviceToken,
    UserPresence,
    UserProfile,
)

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
        timestamp__gte=two_weeks_ago
    ).values(
        'client__name',
        'status',
        'timestamp',
        'user_profile__email',
        'user_profile__id',
        'user_profile__enable_offline_push_notifications',
    )

    query = query_for_ids(
        query=query,
        user_ids=user_profile_ids,
        field='user_profile_id'
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

    return UserPresence.get_status_dicts_for_rows(presence_rows, mobile_user_ids, slim_presence)

def get_status_dict(requesting_user_profile: UserProfile,
                    slim_presence: bool) -> Dict[str, Dict[str, Dict[str, Any]]]:

    if requesting_user_profile.realm.presence_disabled:
        # Return an empty dict if presence is disabled in this realm
        return defaultdict(dict)

    return get_status_dict_by_realm(requesting_user_profile.realm_id, slim_presence)

def get_presence_response(requesting_user_profile: UserProfile,
                          slim_presence: bool) -> Dict[str, Any]:
    server_timestamp = time.time()
    presences = get_status_dict(requesting_user_profile, slim_presence)
    return dict(presences=presences, server_timestamp=server_timestamp)
