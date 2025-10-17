from datetime import datetime, timedelta, timezone
from functools import cache

import icu
from django.utils.translation import get_language


class TimeZoneNotUTCError(Exception):
    pass


def verify_UTC(dt: datetime) -> None:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) != timezone.utc.utcoffset(dt):
        raise TimeZoneNotUTCError(f"Datetime {dt} does not have a UTC time zone.")


def convert_to_UTC(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def floor_to_hour(dt: datetime) -> datetime:
    verify_UTC(dt)
    return datetime(*dt.timetuple()[:4], tzinfo=timezone.utc)


def floor_to_day(dt: datetime) -> datetime:
    verify_UTC(dt)
    return datetime(*dt.timetuple()[:3], tzinfo=timezone.utc)


def ceiling_to_hour(dt: datetime) -> datetime:
    floor = floor_to_hour(dt)
    if floor == dt:
        return floor
    return floor + timedelta(hours=1)


def ceiling_to_day(dt: datetime) -> datetime:
    floor = floor_to_day(dt)
    if floor == dt:
        return floor
    return floor + timedelta(days=1)


def timestamp_to_datetime(timestamp: float) -> datetime:
    return datetime.fromtimestamp(float(timestamp), tz=timezone.utc)


def datetime_to_timestamp(dt: datetime) -> int:
    verify_UTC(dt)
    return int(dt.timestamp())


@cache
def get_date_time_pattern_generator(language: str) -> icu.DateTimePatternGenerator:
    return icu.DateTimePatternGenerator.createInstance(icu.Locale(language))


@cache
def get_icu_time_zone(time_zone: str) -> icu.TimeZone:
    return icu.TimeZone.createTimeZone(time_zone)


@cache
def get_date_time_format(language: str, use_twenty_four_hour_time: bool) -> icu.SimpleDateFormat:
    skeleton = f"yMMMEd{'H' if use_twenty_four_hour_time else 'h'}mz"
    pattern = get_date_time_pattern_generator(language).getBestPattern(skeleton)
    return icu.SimpleDateFormat(pattern, icu.Locale(language))


def format_datetime_to_string(dt: datetime, use_twenty_four_hour_time: bool) -> str:
    assert dt.tzinfo is not None
    time_zone = getattr(dt.tzinfo, "key", None)
    if time_zone is None:
        offset = dt.tzinfo.utcoffset(dt)
        assert offset is not None
        sign = "-" if offset < timedelta(0) else "+"
        hours, rest = divmod(abs(offset), timedelta(hours=1))
        minutes, rest = divmod(rest, timedelta(minutes=1))
        assert rest == timedelta(0)
        time_zone = f"GMT{sign}{hours:02}:{minutes:02}"
    language = get_language()
    calendar = icu.Calendar.createInstance(get_icu_time_zone(time_zone), icu.Locale(language))
    calendar.setTime(dt)
    return get_date_time_format(language, use_twenty_four_hour_time).format(calendar)
