import datetime


class TimeZoneNotUTCError(Exception):
    pass


def verify_UTC(dt: datetime.datetime) -> None:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) != datetime.timezone.utc.utcoffset(dt):
        raise TimeZoneNotUTCError(f"Datetime {dt} does not have a UTC time zone.")


def convert_to_UTC(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def floor_to_hour(dt: datetime.datetime) -> datetime.datetime:
    verify_UTC(dt)
    return datetime.datetime(*dt.timetuple()[:4], tzinfo=datetime.timezone.utc)


def floor_to_day(dt: datetime.datetime) -> datetime.datetime:
    verify_UTC(dt)
    return datetime.datetime(*dt.timetuple()[:3], tzinfo=datetime.timezone.utc)


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
    return datetime.datetime.fromtimestamp(float(timestamp), tz=datetime.timezone.utc)


def datetime_to_timestamp(dt: datetime.datetime) -> int:
    verify_UTC(dt)
    return int(dt.timestamp())
