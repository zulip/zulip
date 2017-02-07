from django.utils.timezone import get_fixed_timezone
from zerver.lib.test_classes import ZulipTestCase

from analytics.lib.counts import CountStat
from analytics.lib.time_utils import time_range
from analytics.views import rewrite_client_arrays

from datetime import datetime, timedelta

class TestTimeRange(ZulipTestCase):
    def test_time_range(self):
        # type: () -> None
        HOUR = timedelta(hours=1)
        DAY = timedelta(days=1)
        TZINFO = get_fixed_timezone(-100) # 100 minutes west of UTC

        # Using 22:59 so that converting to UTC and applying floor_to_{hour,day} do not commute
        a_time = datetime(2016, 3, 14, 22, 59).replace(tzinfo=TZINFO)
        floor_hour = datetime(2016, 3, 14, 22).replace(tzinfo=TZINFO)
        floor_day = datetime(2016, 3, 14).replace(tzinfo=TZINFO)

        # test start == end
        self.assertEqual(time_range(a_time, a_time, CountStat.HOUR, None), [])
        self.assertEqual(time_range(a_time, a_time, CountStat.DAY, None), [])
        # test start == end == boundary, and min_length == 0
        self.assertEqual(time_range(floor_hour, floor_hour, CountStat.HOUR, 0), [floor_hour])
        self.assertEqual(time_range(floor_day, floor_day, CountStat.DAY, 0), [floor_day])
        # test start and end on different boundaries
        self.assertEqual(time_range(floor_hour, floor_hour+HOUR, CountStat.HOUR, None),
                         [floor_hour, floor_hour+HOUR])
        self.assertEqual(time_range(floor_day, floor_day+DAY, CountStat.DAY, None),
                         [floor_day, floor_day+DAY])
        # test min_length
        self.assertEqual(time_range(floor_hour, floor_hour+HOUR, CountStat.HOUR, 4),
                         [floor_hour-2*HOUR, floor_hour-HOUR, floor_hour, floor_hour+HOUR])
        self.assertEqual(time_range(floor_day, floor_day+DAY, CountStat.DAY, 4),
                         [floor_day-2*DAY, floor_day-DAY, floor_day, floor_day+DAY])

class TestMapArrays(ZulipTestCase):
    def test_map_arrays(self):
        # type: () -> None
        a = {'desktop app 1.0': [1, 2, 3],
             'desktop app 2.0': [10, 12, 13],
             'desktop app 3.0': [21, 22, 23],
             'website': [1, 2, 3],
             'ZulipiOS': [1, 2, 3],
             'ZulipMobile': [1, 5, 7],
             'ZulipPython': [1, 2, 3],
             'API: Python': [1, 2, 3],
             'SomethingRandom': [4, 5, 6],
             'ZulipGitHubWebhook': [7, 7, 9],
             'ZulipAndroid': [64, 63, 65]}
        result = rewrite_client_arrays(a)
        self.assertEqual(result,
                         {'Old desktop app': [32, 36, 39],
                          'Old iOS app': [1, 2, 3],
                          'New iOS app': [1, 5, 7],
                          'Website': [1, 2, 3],
                          'Python API': [2, 4, 6],
                          'SomethingRandom': [4, 5, 6],
                          'GitHub webhook': [7, 7, 9],
                          'Android app': [64, 63, 65]})
