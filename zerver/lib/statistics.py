# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import division

from zerver.models import UserProfile, UserActivity, UserActivityInterval, Message

from django.utils.timezone import utc
from typing import Any, Dict, List, Sequence, Set

from datetime import datetime, timedelta

from itertools import chain
from six.moves import range
import six

def median(data):
    # type: (Sequence[float]) -> float
    data = sorted(data)

    size = len(data)
    if size % 2 == 1:
        return data[size//2]
    else:
        before = size//2 - 1
        after = size//2
        return (data[before] + data[after]) / 2.0

users_who_sent_query = Message.objects.select_related("sender") \
        .exclude(sending_client__name__contains="mirror") \
        .exclude(sending_client__name__contains="API")

def active_users():
    # type: () -> Sequence[UserProfile]
    # Return a list of active users we want to count towards various
    # statistics.
    return UserProfile.objects.filter(is_bot=False, is_active=True).select_related()

def users_who_sent_between(begin, end):
    # type: (datetime, datetime) -> Set[int]
    sender_objs = users_who_sent_query.filter(pub_date__gt=begin, pub_date__lt=end) \
        .values("sender__id")
    return set(s["sender__id"] for s in sender_objs)

def users_who_sent_ever():
    # type: () -> Set[int]
    return set(s["sender__id"] for s in users_who_sent_query.values("sender__id"))

def active_users_to_measure():
    # type: () -> List[UserProfile]
    senders = users_who_sent_ever()
    return [u for u in active_users() if u.id in senders]

def active_users_who_sent_between(begin, end):
    # type: (datetime, datetime) -> List[UserProfile]
    senders = users_who_sent_between(begin, end)
    return [u for u in active_users() if u.id in senders]

# Return the amount of Zulip usage for this user between the two
# given dates
def seconds_usage_between(user_profile, begin, end):
    # type: (UserProfile, datetime, datetime) -> timedelta
    intervals = UserActivityInterval.objects.filter(user_profile=user_profile, end__gte=begin, start__lte=end)
    duration = timedelta(0)
    for interval in intervals:
        start = max(begin, interval.start)
        finish = min(end, interval.end)
        duration += finish-start
    return duration

# Return a list of how many seconds each user has been engaging with the app on a given day
def seconds_active_during_day(day):
    # type: (datetime) -> List[float]
    begin_day = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=utc)
    end_day = day.replace(hour=23, minute=59, second=59, microsecond=0, tzinfo=utc)
    active_users = active_users_to_measure()

    return [seconds_usage_between(user, begin_day, end_day).total_seconds() for user in active_users]

def users_active_nosend_during_day(day):
    # type: (datetime) -> List[UserProfile]
    begin_day = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=utc)
    end_day = day.replace(hour=23, minute=59, second=59, microsecond=0, tzinfo=utc)
    active_users = active_users_to_measure()
    today_senders = users_who_sent_between(begin_day, end_day)

    today_users = [] # type: List[UserProfile]
    for user_profile in active_users:
        intervals = UserActivityInterval.objects.filter(user_profile=user_profile,
                                                        end__gte=begin_day,
                                                        start__lte=end_day)
        if len(intervals) != 0:
            today_users.append(user_profile)
    return [u for u in today_users if u.id not in today_senders]

def calculate_stats(data, all_users):
    # type: (Sequence[float], Sequence[UserProfile]) -> Dict[str, Any]
    if len(data) == 0:
        return {"# data points": 0}

    active_user_count = len([x for x in data if x > 1])
    mean_data = sum(data) // active_user_count
    median_data = median([x for x in data if x > 1])

    return {'active users': active_user_count,
            'total users': len(all_users),
            'mean': str(timedelta(seconds=mean_data)),
            'median': str(timedelta(seconds=median_data)),
            '# data points': len(data)}

# Return an info dict {mean: , median} containing the mean/median seconds users were active on a given day
def activity_averages_during_day(day):
    # type: (datetime) -> Dict[str, Any]
    users_to_measure = active_users_to_measure()
    seconds_active = seconds_active_during_day(day)
    return calculate_stats(seconds_active, all_users=users_to_measure)

# Returns an info dict {mean: , median} with engagement numbers for all users according
# to active_users_to_measure.
def activity_averages_between(begin, end, by_day=True):
    # type: (datetime, datetime, bool) -> Dict[str, Any]
    seconds_active = {}
    users_to_measure = active_users_to_measure()
    for i in range((end - begin).days):
        day = begin + timedelta(days=i)

        # Ignore weekends
        if day.weekday() in [5, 6]:
            continue

        seconds_active[day] = seconds_active_during_day(day)

    if by_day:
        return dict((str(day), calculate_stats(values, all_users=users_to_measure))
                    for day, values in six.iteritems(seconds_active))
    else:
        return calculate_stats(list(chain.from_iterable(seconds_active.values())), # type: ignore # chain.from_iterable needs overload
                               all_users=users_to_measure)
