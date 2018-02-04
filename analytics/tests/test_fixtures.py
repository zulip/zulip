from analytics.lib.counts import CountStat
from analytics.lib.fixtures import generate_time_series_data
from zerver.lib.test_classes import ZulipTestCase

# A very light test suite; the code being tested is not run in production.
class TestFixtures(ZulipTestCase):
    def test_deterministic_settings(self) -> None:
        # test basic business_hour / non_business_hour calculation
        # test we get an array of the right length with frequency=CountStat.DAY
        data = generate_time_series_data(
            days=7, business_hours_base=20, non_business_hours_base=15, spikiness=0)
        self.assertEqual(data, [400, 400, 400, 400, 400, 360, 360])

        data = generate_time_series_data(
            days=1, business_hours_base=2000, non_business_hours_base=1500,
            growth=2, spikiness=0, frequency=CountStat.HOUR)
        # test we get an array of the right length with frequency=CountStat.HOUR
        self.assertEqual(len(data), 24)
        # test that growth doesn't affect the first data point
        self.assertEqual(data[0], 2000)
        # test that the last data point is growth times what it otherwise would be
        self.assertEqual(data[-1], 1500*2)

        # test autocorrelation == 1, since that's the easiest value to test
        data = generate_time_series_data(
            days=1, business_hours_base=2000, non_business_hours_base=2000,
            autocorrelation=1, frequency=CountStat.HOUR)
        self.assertEqual(data[0], data[1])
        self.assertEqual(data[0], data[-1])
