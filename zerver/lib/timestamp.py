import datetime
import calendar
import re
from dateutil.parser import parse as dateparser
from django.utils.timezone import utc as timezone_utc
from django.utils.timezone import now as timezone_now
from typing import Optional
from zerver.lib.timezone import get_timezone

class TimezoneNotUTCException(Exception):
    pass

def verify_UTC(dt: datetime.datetime) -> None:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) != timezone_utc.utcoffset(dt):
        raise TimezoneNotUTCException("Datetime %s does not have a UTC timezone." % (dt,))

def convert_to_UTC(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone_utc)
    return dt.astimezone(timezone_utc)

def floor_to_hour(dt: datetime.datetime) -> datetime.datetime:
    verify_UTC(dt)
    return datetime.datetime(*dt.timetuple()[:4]) \
                   .replace(tzinfo=timezone_utc)

def floor_to_day(dt: datetime.datetime) -> datetime.datetime:
    verify_UTC(dt)
    return datetime.datetime(*dt.timetuple()[:3]) \
                   .replace(tzinfo=timezone_utc)

def ceiling_to_hour(dt: datetime.datetime) -> datetime.datetime:
    floor = floor_to_hour(dt)
    if floor == dt:
        return floor
    return floor + datetime.timedelta(hours=1)

def ceiling_to_day(dt: datetime.datetime) -> datetime.datetime:
    floor = floor_to_day(dt)
    if floor == dt:
        return floor
    return floor + datetime.timedelta(days=1)

def timestamp_to_datetime(timestamp: float) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(float(timestamp), tz=timezone_utc)

def datetime_to_timestamp(dt: datetime.datetime) -> int:
    verify_UTC(dt)
    return calendar.timegm(dt.timetuple())

def parse_generic_time(timestr: str, local_tz: str='UTC') -> Optional[datetime.datetime]:
    timestr = timestr.lower()
    cur_datetime = timezone_now().astimezone(tz=get_timezone(local_tz))

    def patch_timestr(lookup_str: str, timedelta: datetime.timedelta) -> str:
        lookup = re.search(lookup_str, timestr)
        if lookup:
            lookup_datetime = cur_datetime + timedelta
            lookup_datetime = lookup_datetime.replace(hour=9, minute=0, second=0, microsecond=0)
            lookup_timestr = re.search(r'\d+', timestr)
            replace_str = lookup_datetime.strftime('%d %b %Y %H:%M')
            if lookup_timestr:
                replace_str = lookup_datetime.strftime('%d %b %Y')
            return re.sub(lookup_str, replace_str, timestr)
        return timestr

    timestr = re.sub('next to next', '2', timestr)
    timestr = patch_timestr('next week', datetime.timedelta(days=7 - cur_datetime.weekday()))
    timestr = patch_timestr('tomorrow', datetime.timedelta(days=1))

    try:
        parsed_time = dateparser(timestr)
        return parsed_time
    except ValueError:
        pass

    GENERIC_TIMESTR = re.compile(r'(\d+|an|a)\s(\w+)', re.I)
    generic_time = GENERIC_TIMESTR.search(timestr)
    parsed_time = timezone_now()
    if generic_time:
        try:
            delta = int(generic_time.group(1))
        except ValueError:
            delta = 1
        if delta < 1:
            return None
        delta_type = generic_time.group(2).lower()
        if delta_type in ['min', 'mins', 'minute', 'minutes']:
            parsed_time += datetime.timedelta(minutes=delta)
        if delta_type in ['hour', 'hours']:
            parsed_time += datetime.timedelta(hours=delta)
        if delta_type in ['day', 'days']:
            parsed_time += datetime.timedelta(days=delta)
        if delta_type in ['week', 'weeks']:
            parsed_time += datetime.timedelta(weeks=delta)
        return parsed_time
    return None
