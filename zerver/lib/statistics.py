from datetime import datetime, timedelta

from zerver.models import UserActivityInterval, UserProfile


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
