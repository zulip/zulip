from zilencer.management.commands.populate_db import choose_pub_date
from zerver.lib.test_classes import ZulipTestCase

from django.utils.timezone import timedelta as timezone_timedelta

class TestChoosePubDate(ZulipTestCase):
    def test_choose_pub_date_large_tot_messages(self) -> None:
        """
        Test for a bug that was present, where specifying a large amount of messages to generate
        would cause each message to have pub_date set to timezone_now(), instead of the pub_dates
        being distributed across the span of several days.
        """
        tot_messages = 1000000
        datetimes_list = [
            choose_pub_date(i, tot_messages, 1) for i in range(1, tot_messages, tot_messages // 100)
        ]

        # Verify there is a meaningful difference between elements.
        for i in range(1, len(datetimes_list)):
            self.assertTrue(datetimes_list[i] - datetimes_list[i-1] > timezone_timedelta(minutes=5))
