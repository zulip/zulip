from datetime import datetime, timedelta, timezone


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
