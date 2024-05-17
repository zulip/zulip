from datetime import timedelta

from zerver.lib.test_classes import ZulipTestCase
from zilencer.management.commands.populate_db import choose_date_sent


class TestChoosePubDate(ZulipTestCase):
    def test_choose_date_sent_large_tot_messages(self) -> None:
        """
        Test for a bug that was present, where specifying a large amount of messages to generate
        would cause each message to have date_sent set to timezone_now(), instead of the date_sents
        being distributed across the span of several days.
        """
        tot_messages = 1000000
        datetimes_list = [
            choose_date_sent(i, tot_messages, 5, 1)
            for i in range(1, tot_messages, tot_messages // 100)
        ]

        # Verify there is a meaningful difference between elements.
        for i in range(1, len(datetimes_list)):
            self.assertTrue(datetimes_list[i] - datetimes_list[i - 1] > timedelta(minutes=5))


class TestUserTimeZones(ZulipTestCase):
    def test_timezones_assigned_to_users(self) -> None:
        othello = self.example_user("othello")
        self.assertEqual(othello.timezone, "US/Pacific")
        shiva = self.example_user("shiva")
        self.assertEqual(shiva.timezone, "Asia/Kolkata")
        cordelia = self.example_user("cordelia")
        self.assertEqual(cordelia.timezone, "UTC")
