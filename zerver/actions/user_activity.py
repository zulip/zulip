from datetime import datetime

from zerver.lib.queue import queue_json_publish_rollback_unsafe
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import UserActivityInterval, UserProfile


def do_update_user_activity_interval(user_profile: UserProfile, log_time: datetime) -> None:
    effective_end = log_time + UserActivityInterval.MIN_INTERVAL_LENGTH
    # This code isn't perfect, because with various races we might end
    # up creating two overlapping intervals, but that shouldn't happen
    # often, and can be corrected for in post-processing
    try:
        last = UserActivityInterval.objects.filter(user_profile=user_profile).order_by("-end")[0]
        # Two intervals overlap iff each interval ends after the other
        # begins.  In this case, we just extend the old interval to
        # include the new interval.
        if log_time <= last.end and effective_end >= last.start:
            last.end = max(last.end, effective_end)
            last.start = min(last.start, log_time)
            last.save(update_fields=["start", "end"])
            return
    except IndexError:
        pass

    # Otherwise, the intervals don't overlap, so we should make a new one
    UserActivityInterval.objects.create(
        user_profile=user_profile, start=log_time, end=effective_end
    )


def update_user_activity_interval(user_profile: UserProfile, log_time: datetime) -> None:
    event = {"user_profile_id": user_profile.id, "time": datetime_to_timestamp(log_time)}
    queue_json_publish_rollback_unsafe("user_activity_interval", event)
