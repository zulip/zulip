
from django.utils.timezone import utc as timezone_utc

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import floor_to_hour, floor_to_day, ceiling_to_hour, \
    timestamp_to_datetime, datetime_to_timestamp, \
    TimezoneNotUTCException, convert_to_UTC

from datetime import timedelta
from dateutil import parser
import pytz

class TestTimestamp(ZulipTestCase):
    def test_datetime_and_timestamp_conversions(self) -> None:
        timestamp = 1483228800
        for dt in [
                parser.parse('2017-01-01 00:00:00.123 UTC'),
                parser.parse('2017-01-01 00:00:00.123').replace(tzinfo=timezone_utc),
                parser.parse('2017-01-01 00:00:00.123').replace(tzinfo=pytz.utc)]:
            self.assertEqual(timestamp_to_datetime(timestamp), dt-timedelta(microseconds=123000))
            self.assertEqual(datetime_to_timestamp(dt), timestamp)

        for dt in [
                parser.parse('2017-01-01 00:00:00.123+01:00'),
                parser.parse('2017-01-01 00:00:00.123')]:
            with self.assertRaises(TimezoneNotUTCException):
                datetime_to_timestamp(dt)

    def test_convert_to_UTC(self) -> None:
        utc_datetime = parser.parse('2017-01-01 00:00:00.123 UTC')
        for dt in [
                parser.parse('2017-01-01 00:00:00.123').replace(tzinfo=timezone_utc),
                parser.parse('2017-01-01 00:00:00.123'),
                parser.parse('2017-01-01 05:00:00.123+05')]:
            self.assertEqual(convert_to_UTC(dt), utc_datetime)

    def test_enforce_UTC(self) -> None:
        non_utc_datetime = parser.parse('2017-01-01 00:00:00.123')
        for function in [floor_to_hour, floor_to_day, ceiling_to_hour, ceiling_to_hour]:
            with self.assertRaises(TimezoneNotUTCException):
                function(non_utc_datetime)
