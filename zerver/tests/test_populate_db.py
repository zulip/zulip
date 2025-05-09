from collections import defaultdict
from datetime import timedelta

from zerver.lib.stream_subscription import get_active_subscriptions_for_stream_ids
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Stream
from zerver.models.realms import get_realm
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


class TestSubscribeUsers(ZulipTestCase):
    def test_bulk_create_stream_subscriptions(self) -> None:
        """
        This insures bulk_create_stream_subscriptions() ran successfully when test data is loaded via populate_db.py
        """

        realm = get_realm("zulip")
        streams = Stream.objects.filter(realm=realm)
        active_subscriptions = get_active_subscriptions_for_stream_ids(
            {stream.id for stream in streams}
        ).select_related("recipient")

        # Map stream_id to its No. active subscriptions.
        expected_subscriber_count: dict[int, int] = defaultdict(int)

        for sub in active_subscriptions:
            expected_subscriber_count[sub.recipient.type_id] += 1

        for stream in streams:
            self.assertEqual(
                stream.subscriber_count,
                expected_subscriber_count[stream.id],
                msg=f"""
                stream of ID ({stream.id}) should have a subscriber_count of {expected_subscriber_count[stream.id]}.
                """,
            )
