import datetime
from typing import List

from django.utils.timezone import now as timezone_now

from zerver.lib.actions import get_active_presence_idle_user_ids
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    Message,
    UserPresence,
    UserProfile,
    bulk_get_huddle_user_ids,
    get_client,
    get_huddle_user_ids,
)


class MissedMessageTest(ZulipTestCase):
    def test_presence_idle_user_ids(self) -> None:
        UserPresence.objects.all().delete()

        sender = self.example_user("cordelia")
        realm = sender.realm
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        user_data_objects = [
            self.create_user_notifications_data_object(user_id=hamlet.id),
            self.create_user_notifications_data_object(user_id=othello.id),
        ]
        message_type = "private"

        def assert_missing(user_ids: List[int]) -> None:
            presence_idle_user_ids = get_active_presence_idle_user_ids(
                realm=realm,
                sender_id=sender.id,
                message_type=message_type,
                active_users_data=user_data_objects,
            )
            self.assertEqual(sorted(user_ids), sorted(presence_idle_user_ids))

        def set_presence(user: UserProfile, client_name: str, ago: int) -> None:
            when = timezone_now() - datetime.timedelta(seconds=ago)
            UserPresence.objects.create(
                user_profile_id=user.id,
                realm_id=user.realm_id,
                client=get_client(client_name),
                timestamp=when,
            )

        message_type = "private"
        assert_missing([hamlet.id, othello.id])

        # We have already thoroughly tested the `is_notifiable` function elsewhere,
        # so we needn't test all cases here. This test exists mainly to avoid a bug
        # which existed earlier with `get_active_presence_idle_user_ids` only looking
        # at `private_message` and the `mentioned` flag, not stream level notifications.
        # Simulate Hamlet has turned on notifications for the stream, and test that he's
        # in the list.
        message_type = "stream"
        user_data_objects[0].stream_email_notify = True
        assert_missing([hamlet.id])

        # We don't currently send push or email notifications for alert words -- only
        # desktop notifications, so `is_notifiable` will return False even if the flags contain
        # alert words. Test that `get_active_presence_idle_user_ids` correctly includes even
        # the alert word case in the list.
        user_data_objects[0].stream_email_notify = False
        user_data_objects[0].flags = ["has_alert_word"]
        assert_missing([hamlet.id])

        # Hamlet is idle (and the message has an alert word), so he should be in the list.
        set_presence(hamlet, "iPhone", ago=5000)
        assert_missing([hamlet.id])

        # If Hamlet is active, don't include him in the `presence_idle` list.
        set_presence(hamlet, "website", ago=15)
        assert_missing([])

        # Hamlet is active now, so only Othello should be in the list for a huddle
        # message.
        message_type = "private"
        assert_missing([othello.id])


class TestBulkGetHuddleUserIds(ZulipTestCase):
    def test_bulk_get_huddle_user_ids(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        iago = self.example_user("iago")
        message_ids = [
            self.send_huddle_message(hamlet, [cordelia, othello], "test"),
            self.send_huddle_message(cordelia, [hamlet, othello, iago], "test"),
        ]

        messages = Message.objects.filter(id__in=message_ids).order_by("id")
        first_huddle_recipient = messages[0].recipient
        first_huddle_user_ids = list(get_huddle_user_ids(first_huddle_recipient))
        second_huddle_recipient = messages[1].recipient
        second_huddle_user_ids = list(get_huddle_user_ids(second_huddle_recipient))

        huddle_user_ids = bulk_get_huddle_user_ids(
            [first_huddle_recipient, second_huddle_recipient]
        )
        self.assertEqual(huddle_user_ids[first_huddle_recipient.id], first_huddle_user_ids)
        self.assertEqual(huddle_user_ids[second_huddle_recipient.id], second_huddle_user_ids)

    def test_bulk_get_huddle_user_ids_empty_list(self) -> None:
        self.assertEqual(bulk_get_huddle_user_ids([]), {})
