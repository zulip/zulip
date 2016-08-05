from __future__ import absolute_import

import datetime
import calendar
from django.utils.timezone import utc

def timestamp_to_datetime(timestamp):
    # type: (float) -> datetime.datetime
    return datetime.datetime.utcfromtimestamp(float(timestamp)).replace(tzinfo=utc)

def datetime_to_timestamp(datetime_object):
    # type: (datetime.datetime) -> int
    return calendar.timegm(datetime_object.timetuple())

def datetime_to_string(datetime_object):
    # type: (datetime.datetime) -> text_type
    return datetime_object.strftime('%Y-%m-%d %H:%M:%S')

def string_to_datetime(datetime_str):
    # type: (text_type) -> datetime.datetime
    return datetime.datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
