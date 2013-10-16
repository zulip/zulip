# -*- coding: utf-8 -*-
from __future__ import absolute_import

from zerver.models import UserProfile, Realm, UserActivity, UserActivityInterval

from django.utils.timezone import utc

from datetime import timedelta, datetime
from itertools import chain

def median(data):
    data = sorted(data)

    size = len(data)
    if size % 2 == 1:
        return data[size//2]
    else:
        before = size//2 - 1
        after = size//2
        return (data[before] + data[after]) / 2.0

def active_users_to_measure():
    # Return a list of active users we want to count towards various
    # statistics. This eliminates bots, @zulip.com, @customer29.invalid and customer3.invalid
    exclude_realms = ["zulip.com", "customer29.invalid", "customer3.invalid"]
    return UserProfile.objects.filter(is_bot=False, is_active=True) \
                              .exclude(realm__domain__in=exclude_realms) \
                              .select_related()

# Return a set of users who have done some activity in the given timespan--that is,
# we have a UserActivity row for them. This counts pointer moves, flag updates, etc.
def users_active_between(begin, end):
    activities = UserActivity.objects.filter(last_visit__gt=begin, last_visit__lt=end)
    active = set([a.user_profile for a in activities])

    interesting_users = set(active_users_to_measure())
    return active.intersection(interesting_users)

# Return the amount of Zulip usage for this user between the two
# given dates
def seconds_usage_between(user_profile, begin, end):
    intervals = UserActivityInterval.objects.filter(user_profile=user_profile, end__gte=begin, start__lte=end)
    duration = timedelta(0)
    for interval in intervals:
        start = max(begin, interval.start)
        finish = min(end, interval.end)
        duration += finish-start
    return duration

# Return a list of how many seconds each user has been engaging with the app on a given day
def seconds_active_during_day(day):
    begin_day = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=utc)
    end_day = day.replace(hour=23, minute=59, second=59, microsecond=0, tzinfo=utc)
    active_users = users_active_between(begin_day, end_day)

    # Exclude Friday CUSTOMER4 activity numbers
    if day.weekday() == 4:
        active_users = [u for u in active_users if u.realm.domain != 'users.customer4.invalid']

    return [seconds_usage_between(user, begin_day, end_day).total_seconds() for user in active_users]

def calculate_stats(data):
    if len(data) == 0:
        return 0, 0

    mean_data = sum(data) / len(data)
    median_data = median(data)

    return {'mean': str(timedelta(seconds=mean_data)), 'median': str(timedelta(seconds=median_data)), '# data points': len(data)}

# Return an info dict {mean: , median} containing the mean/median seconds users were active on a given day
def activity_averages_during_day(day):
    seconds_active = seconds_active_during_day(day)
    return calculate_stats(seconds_active)

# Returns an info dict {mean: , median} with engagement numbers for all users according
# to active_users_to_measure. This will ignore weekends, and ignore users.customer4.invalid
# on Fridays
def activity_averages_between(begin, end, by_day=True):
    seconds_active = {}
    for i in range((end - begin).days):
        day = begin + timedelta(days=i)

        # Ignore weekends
        if day.weekday() in [5, 6]:
            continue

        seconds_active[day] = seconds_active_during_day(day)

    if by_day:
        return dict((day, calculate_stats(values)) for day, values in seconds_active.iteritems())
    else:
        return calculate_stats(list(chain.from_iterable(seconds_active.values())))
