from django.utils.timezone import get_fixed_timezone
from zerver.lib.test_classes import ZulipTestCase

from analytics.lib.counts import CountStat
from analytics.views import time_range

from datetime import datetime, timedelta

class TestTimeRange(ZulipTestCase):
    def test_time_range(self):
        # type: () -> None
        HOUR = timedelta(hours=1)
        DAY = timedelta(days=1)
        TZINFO = get_fixed_timezone(-100) # 100 minutes west of UTC

        # Using 22:59 so that converting to UTC and applying ceiling_to_{hour,day} do not commute
        a_time = datetime(2016, 3, 14, 22, 59).replace(tzinfo=TZINFO)
        # Round up to hour and day
        ceiling_hour = datetime(2016, 3, 14, 23).replace(tzinfo=TZINFO)
        ceiling_day = datetime(2016, 3, 15).replace(tzinfo=TZINFO)

        # test start == end
        self.assertEqual(time_range(a_time, a_time, CountStat.HOUR, None), [ceiling_hour])
        self.assertEqual(time_range(a_time, a_time, CountStat.DAY, None), [ceiling_day])
        # test start == end == boundary, and min_length == 0
        self.assertEqual(time_range(ceiling_hour, ceiling_hour, CountStat.HOUR, 0), [ceiling_hour])
        self.assertEqual(time_range(ceiling_day, ceiling_day, CountStat.DAY, 0), [ceiling_day])
        # test start and end on different boundaries
        self.assertEqual(time_range(ceiling_hour, ceiling_hour+HOUR, CountStat.HOUR, None),
                         [ceiling_hour, ceiling_hour+HOUR])
        self.assertEqual(time_range(ceiling_day, ceiling_day+DAY, CountStat.DAY, None),
                         [ceiling_day, ceiling_day+DAY])
        # test min_length
        self.assertEqual(time_range(ceiling_hour, ceiling_hour+HOUR, CountStat.HOUR, 4),
                         [ceiling_hour-2*HOUR, ceiling_hour-HOUR, ceiling_hour, ceiling_hour+HOUR])
        self.assertEqual(time_range(ceiling_day, ceiling_day+DAY, CountStat.DAY, 4),
                         [ceiling_day-2*DAY, ceiling_day-DAY, ceiling_day, ceiling_day+DAY])
