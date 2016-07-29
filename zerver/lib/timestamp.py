from __future__ import absolute_import

import datetime
import calendar
from django.utils.timezone import utc

def assert_timezone_aware(datetime):
    # type: (datetime.datetime) -> None
    if datetime.tzinfo is None:
        raise ValueError("datetime object should be timezone aware.")

def timestamp_to_datetime(timestamp):
    # type: (float) -> datetime.datetime
    return datetime.datetime.utcfromtimestamp(float(timestamp)).replace(tzinfo=utc)

def datetime_to_timestamp(datetime_object):
    # type: (datetime.datetime) -> int
    return calendar.timegm(datetime_object.timetuple())

def datetime_to_string(datetime_object):
    # type: (datetime.datetime) -> str
    assert_timezone_aware(datetime_object)
    date_string = datetime_object.strftime('%Y-%m-%d %H:%M:%S%z')
    return date_string
