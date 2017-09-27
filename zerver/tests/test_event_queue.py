import mock

from typing import Any, Callable, Dict, Tuple

from zerver.lib.test_classes import ZulipTestCase
from zerver.tornado.event_queue import maybe_enqueue_notifications

class MissedMessageNotificationsTest(ZulipTestCase):
    """Tests the logic for when missed-message notifications
    should be triggered, based on user settings"""
    def check_will_notify(self, *args, **kwargs):
        # type: (*Any, **Any) -> Tuple[str, str]
        email_notice = None
        mobile_notice = None
        with mock.patch("zerver.tornado.event_queue.queue_json_publish") as mock_queue_publish:
            notified = maybe_enqueue_notifications(*args, **kwargs)
            if notified is None:
                notified = {}
            for entry in mock_queue_publish.call_args_list:
                args = entry[0]
                if args[0] == "missedmessage_mobile_notifications":
                    mobile_notice = args[1]
                if args[0] == "missedmessage_emails":
                    email_notice = args[1]

            # Now verify the return value matches the queue actions
            if email_notice:
                self.assertTrue(notified['email_notified'])
            else:
                self.assertFalse(notified.get('email_notified', False))
            if mobile_notice:
                self.assertTrue(notified['push_notified'])
            else:
                self.assertFalse(notified.get('push_notified', False))
        return email_notice, mobile_notice

    def test_enqueue_notifications(self):
        # type: () -> None
        user_profile = self.example_user("hamlet")
        message_id = 32

        # Boring message doesn't send a notice
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=False,
            mentioned=False, stream_push_notify=False, stream_name=None,
            always_push_notify=False, idle=True)
        self.assertTrue(email_notice is None)
        self.assertTrue(mobile_notice is None)

        # Private message sends a notice
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=True,
            mentioned=False, stream_push_notify=False, stream_name=None,
            always_push_notify=False, idle=True)
        self.assertTrue(email_notice is not None)
        self.assertTrue(mobile_notice is not None)

        # Mention sends a notice
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=False,
            mentioned=True, stream_push_notify=False, stream_name=None,
            always_push_notify=False, idle=True)
        self.assertTrue(email_notice is not None)
        self.assertTrue(mobile_notice is not None)

        # stream_push_notify pushes but doesn't email
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=False,
            mentioned=False, stream_push_notify=True, stream_name="Denmark",
            always_push_notify=False, idle=True)
        self.assertTrue(email_notice is None)
        self.assertTrue(mobile_notice is not None)

        # Private message doesn't send a notice if not idle
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=True,
            mentioned=False, stream_push_notify=False, stream_name=None,
            always_push_notify=False, idle=False)
        self.assertTrue(email_notice is None)
        self.assertTrue(mobile_notice is None)

        # Private message sends push but not email if not idle but always_push_notify
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=True,
            mentioned=False, stream_push_notify=False, stream_name=None,
            always_push_notify=True, idle=False)
        self.assertTrue(email_notice is None)
        self.assertTrue(mobile_notice is not None)
