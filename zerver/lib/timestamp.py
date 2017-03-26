from __future__ import absolute_import

import datetime
import calendar
from django.utils import timezone

def floor_to_hour(dt):
    # type: (datetime.datetime) -> datetime.datetime
    return datetime.datetime(*dt.timetuple()[:4]) \
                   .replace(tzinfo=dt.tzinfo)

def floor_to_day(dt):
    # type: (datetime.datetime) -> datetime.datetime
    return datetime.datetime(*dt.timetuple()[:3]) \
                   .replace(tzinfo=dt.tzinfo)

def ceiling_to_hour(dt):
    # type: (datetime.datetime) -> datetime.datetime
    floor = floor_to_hour(dt)
    if floor == dt:
        return floor
    return floor + datetime.timedelta(hours=1)

def ceiling_to_day(dt):
    # type: (datetime.datetime) -> datetime.datetime
    floor = floor_to_day(dt)
    if floor == dt:
        return floor
    return floor + datetime.timedelta(days=1)

def timestamp_to_datetime(timestamp):
    # type: (float) -> datetime.datetime
    return datetime.datetime.fromtimestamp(float(timestamp), tz=timezone.utc)

class TimezoneNotUTCException(Exception):
    pass

def datetime_to_timestamp(dt):
    # type: (datetime.datetime) -> int
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) != timezone.utc.utcoffset(dt):
        raise TimezoneNotUTCException("Datetime %s to be converted does not have a UTC timezone." % (dt,))
    return calendar.timegm(dt.timetuple())
