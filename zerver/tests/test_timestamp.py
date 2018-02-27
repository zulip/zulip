
from django.utils.timezone import utc as timezone_utc
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import floor_to_hour, floor_to_day, ceiling_to_hour, \
    ceiling_to_day, timestamp_to_datetime, datetime_to_timestamp, \
    TimezoneNotUTCException, convert_to_UTC, parse_generic_time
from zerver.lib.timezone import get_timezone

from datetime import datetime, timedelta
from dateutil import parser
import pytz
import mock

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

    def test_parse_generic_time(self) -> None:
        current_time = timezone_now()
        timestr = 'in a min'
        with mock.patch('zerver.lib.timestamp.timezone_now', return_value=current_time):
            res = parse_generic_time(timestr)
        self.assertEqual(current_time + timedelta(minutes=1), res)

        timestr = 'in 1 min'
        with mock.patch('zerver.lib.timestamp.timezone_now', return_value=current_time):
            res = parse_generic_time(timestr)
        self.assertEqual(current_time + timedelta(minutes=1), res)

        timestr = 'in 0 min'
        with mock.patch('zerver.lib.timestamp.timezone_now', return_value=current_time):
            res = parse_generic_time(timestr)
        self.assertFalse(res)

        timestr = 'in 2 hours'
        with mock.patch('zerver.lib.timestamp.timezone_now', return_value=current_time):
            res = parse_generic_time(timestr)
        self.assertEqual(current_time + timedelta(hours=2), res)

        timestr = 'in an day'
        with mock.patch('zerver.lib.timestamp.timezone_now', return_value=current_time):
            res = parse_generic_time(timestr)
        self.assertEqual(current_time + timedelta(days=1), res)

        timestr = 'in 2 weeks from now'
        with mock.patch('zerver.lib.timestamp.timezone_now', return_value=current_time):
            res = parse_generic_time(timestr)
        self.assertEqual(current_time + timedelta(weeks=2), res)

        current_time = parser.parse('28th Feb 2018, 02:34 AM').replace(tzinfo=get_timezone('UTC'))

        timestr = 'next week'
        expeceted_result_time = parser.parse('5th Mar 2018, 09:00 AM')
        with mock.patch('zerver.lib.timestamp.timezone_now', return_value=current_time):
            res = parse_generic_time(timestr)
        self.assertEqual(expeceted_result_time, res)

        timestr = 'tomorrow'
        expeceted_result_time = parser.parse('1st Mar 2018, 09:00 AM')
        with mock.patch('zerver.lib.timestamp.timezone_now', return_value=current_time):
            res = parse_generic_time(timestr)
        self.assertEqual(expeceted_result_time, res)

        timestr = 'tomorrow at 12 PM'
        expeceted_result_time = parser.parse('1st Mar 2018, 12:00 PM')
        with mock.patch('zerver.lib.timestamp.timezone_now', return_value=current_time):
            res = parse_generic_time(timestr)
        self.assertEqual(expeceted_result_time, res)

        timestr = 'sometime in future'
        with mock.patch('zerver.lib.timestamp.timezone_now', return_value=current_time):
            res = parse_generic_time(timestr)
        self.assertFalse(res)
