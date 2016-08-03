from __future__ import absolute_import

from datetime import datetime
import calendar
from django.utils.timezone import utc

from typing import Tuple

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
