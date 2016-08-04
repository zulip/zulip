from django.test import TestCase

from analytics.lib.interval import TimeInterval, floor_to_interval_boundary, subtract_interval, timeinterval_range

from datetime import datetime, timedelta

class TimeIntervalTest(TestCase):
    def test_time_interval_creation(self):
        time_interval = TimeInterval('day', datetime(2016, 4, 29, 3, 14, 15, 926535))
        self.assertEqual(time_interval.start, datetime(2016, 4, 28, 3, 0, 0))
        self.assertEqual(time_interval.end, datetime(2016, 4, 29, 3, 0, 0))

    def test_leap_second(self):
        after_leap = datetime(2015, 7, 1)
        self.assertEqual(subtract_interval(after_leap, 'hour'), datetime(2015, 6, 30, 23))

    def test_timeinterval_range(self):
        first = datetime(2016, 4, 29, 3, 14, 15, 926535)
        self.assertEqual(len(timeinterval_range(first, first + timedelta(days = 1), 'day', 'hour')), 24)
        first_hour = floor_to_interval_boundary(first, 'hour')
        self.assertEqual(len(timeinterval_range(first_hour, first_hour + timedelta(days = 1), 'day', 'hour')), 25)
        self.assertEqual(len(timeinterval_range(first_hour, first_hour + timedelta(days = 1), 'day', 'day')), 1)
