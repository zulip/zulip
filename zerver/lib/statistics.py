# -*- coding: utf-8 -*-

from zerver.models import UserProfile, UserActivity, UserActivityInterval, Message

from django.utils.timezone import utc
from typing import Any, Dict, List, Sequence, Set

from datetime import datetime, timedelta

# Return the amount of Zulip usage for this user between the two
# given dates
def seconds_usage_between(user_profile: UserProfile, begin: datetime, end: datetime) -> timedelta:
    intervals = UserActivityInterval.objects.filter(user_profile=user_profile,
                                                    end__gte=begin,
                                                    start__lte=end)
    duration = timedelta(0)
    for interval in intervals:
        start = max(begin, interval.start)
        finish = min(end, interval.end)
        duration += finish-start
    return duration
