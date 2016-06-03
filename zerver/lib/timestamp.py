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
