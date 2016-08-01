from __future__ import absolute_import

from datetime import datetime, timedelta
import calendar
from django.utils.timezone import utc

def timestamp_to_datetime(timestamp):
    # type: (float) -> datetime
    return datetime.utcfromtimestamp(float(timestamp)).replace(tzinfo=utc)

def datetime_to_timestamp(datetime_object):
    # type: (datetime) -> int
    return calendar.timegm(datetime_object.timetuple())

def datetime_to_string(datetime_object):
    # type: (datetime) -> text_type
    return datetime_object.strftime('%Y-%m-%d %H:%M:%S')

def string_to_datetime(datetime_str):
    # type: (text_type) -> datetime
    return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')

def interval_boundary_floor(datetime_object, interval):
    # type: (datetime, text_type) -> datetime
    # don't have to worry about leap seconds, since datetime doesn't support it
    # datetime objects are (year, month, day, hour, minutes, seconds, microseconds)
    if interval == 'hour':
        return datetime(*datetime_object.timetuple()[:4])
    elif interval == 'day':
        return datetime(*datetime_object.timetuple()[:3])
    else:
        raise ValueError("Unknown interval", interval)

def interval_boundary_next(datetime_object, interval):
    # type: (datetime, text_type) -> datetime
    # don't have to worry about leap seconds, since datetime doesn't support it
    # datetime objects are (year, month, day, hour, minutes, seconds, microseconds)
    last = interval_boundary_floor(datetime_object, interval)
    if interval == 'hour':
        return last + timedelta(hour = 1)
    elif interval == 'day':
        return last + timedelta(day = 1)
    else:
        raise ValueError("Unknown interval", interval)

def interval_boundary_lastfloor(datetime_object, interval):
    # type: (datetime, text_type) -> datetime
    last = interval_boundary_floor(datetime_object, interval)
    return interval_boundary_lastfloor(last - timedelta(microseconds = 1), interval)
