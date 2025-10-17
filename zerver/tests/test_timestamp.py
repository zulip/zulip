from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from dateutil import parser
from django.utils.translation import override as override_language

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import (
    TimeZoneNotUTCError,
    ceiling_to_hour,
    convert_to_UTC,
    datetime_to_timestamp,
    floor_to_day,
    floor_to_hour,
    format_datetime_to_string,
    timestamp_to_datetime,
)


class TestTimestamp(ZulipTestCase):
    def test_datetime_and_timestamp_conversions(self) -> None:
        timestamp = 1483228800
        for dt in [
            parser.parse("2017-01-01 00:00:00.123 UTC"),
            parser.parse("2017-01-01 00:00:00.123").replace(tzinfo=timezone.utc),
        ]:
            self.assertEqual(timestamp_to_datetime(timestamp), dt - timedelta(microseconds=123000))
            self.assertEqual(datetime_to_timestamp(dt), timestamp)

        for dt in [
            parser.parse("2017-01-01 00:00:00.123+01:00"),
            parser.parse("2017-01-01 00:00:00.123"),
        ]:
            with self.assertRaises(TimeZoneNotUTCError):
                datetime_to_timestamp(dt)

    def test_convert_to_UTC(self) -> None:
        utc_datetime = parser.parse("2017-01-01 00:00:00.123 UTC")
        for dt in [
            parser.parse("2017-01-01 00:00:00.123").replace(tzinfo=timezone.utc),
            parser.parse("2017-01-01 00:00:00.123"),
            parser.parse("2017-01-01 05:00:00.123+05"),
        ]:
            self.assertEqual(convert_to_UTC(dt), utc_datetime)

    def test_enforce_UTC(self) -> None:
        non_utc_datetime = parser.parse("2017-01-01 00:00:00.123")
        for function in [floor_to_hour, floor_to_day, ceiling_to_hour, ceiling_to_hour]:
            with self.assertRaises(TimeZoneNotUTCError):
                function(non_utc_datetime)

    def test_format_datetime_to_string(self) -> None:
        dt = datetime(2001, 2, 3, 4, 5, 6, tzinfo=timezone.utc)
        self.assertEqual(format_datetime_to_string(dt, True), "Sat, Feb 3, 2001, 04:05 GMT")
        dt = datetime(2001, 2, 3, 4, 5, 6, tzinfo=timezone(timedelta(hours=7, minutes=8)))
        self.assertEqual(format_datetime_to_string(dt, True), "Sat, Feb 3, 2001, 04:05 GMT+7:08")
        dt = datetime(2001, 2, 3, 4, 5, 6, tzinfo=timezone(-timedelta(hours=7, minutes=8)))
        self.assertEqual(format_datetime_to_string(dt, True), "Sat, Feb 3, 2001, 04:05 GMT-7:08")
        dt = datetime(2001, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("America/Los_Angeles"))
        self.assertEqual(format_datetime_to_string(dt, True), "Sat, Feb 3, 2001, 04:05 PST")
        self.assertRegex(
            format_datetime_to_string(dt, False), r"^Sat, Feb 3, 2001, 4:05[ \u202f]AM PST$"
        )
        with override_language("ja-JP"):
            self.assertEqual(format_datetime_to_string(dt, True), "2001年2月3日(土) 4:05 GMT-8")
            self.assertEqual(
                format_datetime_to_string(dt, False), "2001年2月3日(土) 午前4:05 GMT-8"
            )
