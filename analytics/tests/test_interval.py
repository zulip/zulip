from django.test import TestCase
from django.utils import timezone

from analytics.lib.interval import TimeInterval, floor_to_interval_boundary, subtract_interval, timeinterval_range

from datetime import datetime, timedelta

class TimeIntervalTest(TestCase):
    def test_time_interval_creation(self):
        # type: () -> None
        time_interval = TimeInterval('day', datetime(2016, 4, 29, 3, 14, 15, 926535).replace(tzinfo=timezone.utc))
        self.assertEqual(time_interval.start, datetime(2016, 4, 28, 3, 0, 0).replace(tzinfo=timezone.utc))
        self.assertEqual(time_interval.end, datetime(2016, 4, 29, 3, 0, 0).replace(tzinfo=timezone.utc))

    def test_datetime_leap_second(self):
        # type: () -> None
        after_leap = datetime(2015, 7, 1)
        self.assertEqual(subtract_interval(after_leap, 'hour'), datetime(2015, 6, 30, 23))

    def test_timeinterval_range(self):
        # type: () -> None
        first = datetime(2016, 4, 29, 3, 14, 15, 926535).replace(tzinfo=timezone.utc)
        self.assertEqual(len(timeinterval_range(first, first + timedelta(days = 1), 'day', 'hour')), 24)
        first_hour = floor_to_interval_boundary(first, 'hour')
        self.assertEqual(len(timeinterval_range(first_hour, first_hour + timedelta(days = 1), 'day', 'hour')), 25)
        self.assertEqual(len(timeinterval_range(first_hour, first_hour + timedelta(days = 1), 'day', 'day')), 1)

        # TODO: test UTC / timezone flooring stuff
