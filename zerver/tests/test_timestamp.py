from __future__ import absolute_import

from django.utils import timezone

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import floor_to_hour, floor_to_day, ceiling_to_hour, \
    ceiling_to_day, timestamp_to_datetime, datetime_to_timestamp, \
    TimezoneNotUTCException

from datetime import datetime, timedelta
from dateutil import parser
import pytz

from six.moves import zip

class TestTimestamp(ZulipTestCase):
    def test_datetime_and_timestamp_conversions(self):
        # type: () -> None
        timestamp = 1483228800
        for dt in [
                parser.parse('2017-01-01 00:00:00.123 UTC'),
                parser.parse('2017-01-01 00:00:00.123').replace(tzinfo=timezone.utc),
                parser.parse('2017-01-01 00:00:00.123').replace(tzinfo=pytz.utc)]:
            self.assertEqual(timestamp_to_datetime(timestamp), dt-timedelta(microseconds=123000))
            self.assertEqual(datetime_to_timestamp(dt), timestamp)

        for dt in [
                parser.parse('2017-01-01 00:00:00.123+01:00'),
                parser.parse('2017-01-01 00:00:00.123')]:
            with self.assertRaises(TimezoneNotUTCException):
                datetime_to_timestamp(dt)
