from zerver.lib.test_classes import ZulipTestCase


class TestNotificationData(ZulipTestCase):
    def test_is_push_notifiable(self) -> None:
        sender_id = self.example_user("cordelia").id

        # Boring case
        user_data = self.create_user_notifications_data_object()
        self.assertFalse(
            user_data.is_push_notifiable(private_message=False, sender_id=sender_id, idle=True)
        )

        # Notifiable cases for PMs, mentions, stream notifications
        user_data = self.create_user_notifications_data_object()
        self.assertTrue(
            user_data.is_push_notifiable(private_message=True, sender_id=sender_id, idle=True)
        )

        user_data = self.create_user_notifications_data_object(flags=["mentioned"], mentioned=True)
        self.assertTrue(
            user_data.is_push_notifiable(private_message=False, sender_id=sender_id, idle=True)
        )

        user_data = self.create_user_notifications_data_object(
            flags=["wildcard_mentioned"], wildcard_mention_notify=True
        )
        self.assertTrue(
            user_data.is_push_notifiable(private_message=False, sender_id=sender_id, idle=True)
        )

        user_data = self.create_user_notifications_data_object(stream_push_notify=True)
        self.assertTrue(
            user_data.is_push_notifiable(private_message=False, sender_id=sender_id, idle=True)
        )

        # Now, test the `online_push_enabled` property
        # Test no notifications when not idle
        user_data = self.create_user_notifications_data_object()
        self.assertFalse(
            user_data.is_push_notifiable(private_message=True, sender_id=sender_id, idle=False)
        )

        # Test notifications are sent when not idle but `online_push_enabled = True`
        user_data = self.create_user_notifications_data_object(online_push_enabled=True)
        self.assertTrue(
            user_data.is_push_notifiable(private_message=True, sender_id=sender_id, idle=False)
        )

        # The following are hypothetical cases, since a private message can never have `stream_push_notify = True`.
        # We just want to test the early (False) return patterns in these special cases:
        # Message sender is muted.
        user_data = self.create_user_notifications_data_object(
            sender_is_muted=True,
            flags=["mentioned", "wildcard_mentioned"],
            wildcard_mention_notify=True,
            mentioned=True,
            stream_email_notify=True,
            stream_push_notify=True,
        )
        self.assertFalse(
            user_data.is_push_notifiable(private_message=True, sender_id=sender_id, idle=True)
        )

        # Message sender is the user the object corresponds to.
        user_data = self.create_user_notifications_data_object(
            id=sender_id,
            sender_is_muted=False,
            flags=["mentioned", "wildcard_mentioned"],
            wildcard_mention_notify=True,
            mentioned=True,
            stream_email_notify=True,
            stream_push_notify=True,
        )
        self.assertFalse(
            user_data.is_push_notifiable(private_message=True, sender_id=sender_id, idle=True)
        )

    def test_is_email_notifiable(self) -> None:
        sender_id = self.example_user("cordelia").id

        # Boring case
        user_data = self.create_user_notifications_data_object()
        self.assertFalse(
            user_data.is_email_notifiable(private_message=False, sender_id=sender_id, idle=True)
        )

        # Notifiable cases for PMs, mentions, stream notifications
        user_data = self.create_user_notifications_data_object()
        self.assertTrue(
            user_data.is_email_notifiable(private_message=True, sender_id=sender_id, idle=True)
        )

        user_data = self.create_user_notifications_data_object(flags=["mentioned"], mentioned=True)
        self.assertTrue(
            user_data.is_email_notifiable(private_message=False, sender_id=sender_id, idle=True)
        )

        user_data = self.create_user_notifications_data_object(
            flags=["wildcard_mentioned"], wildcard_mention_notify=True
        )
        self.assertTrue(
            user_data.is_email_notifiable(private_message=False, sender_id=sender_id, idle=True)
        )

        user_data = self.create_user_notifications_data_object(stream_email_notify=True)
        self.assertTrue(
            user_data.is_email_notifiable(private_message=False, sender_id=sender_id, idle=True)
        )

        # Test no notifications when not idle
        user_data = self.create_user_notifications_data_object()
        self.assertFalse(
            user_data.is_email_notifiable(private_message=True, sender_id=sender_id, idle=False)
        )

        # The following are hypothetical cases, since a private message can never have `stream_email_notify = True`.
        # We just want to test the early (False) return patterns in these special cases:
        # Message sender is muted.
        user_data = self.create_user_notifications_data_object(
            sender_is_muted=True,
            flags=["mentioned", "wildcard_mentioned"],
            wildcard_mention_notify=True,
            mentioned=True,
            stream_email_notify=True,
            stream_push_notify=True,
        )
        self.assertFalse(
            user_data.is_email_notifiable(private_message=True, sender_id=sender_id, idle=True)
        )

        # Message sender is the user the object corresponds to.
        user_data = self.create_user_notifications_data_object(
            id=sender_id,
            sender_is_muted=False,
            flags=["mentioned", "wildcard_mentioned"],
            wildcard_mention_notify=True,
            mentioned=True,
            stream_email_notify=True,
            stream_push_notify=True,
        )
        self.assertFalse(
            user_data.is_email_notifiable(private_message=True, sender_id=sender_id, idle=True)
        )

    def test_is_notifiable(self) -> None:
        # This is just for coverage purposes. We've already tested all scenarios above,
        # and `is_notifiable` is a simple OR of the email and push functions.
        sender_id = self.example_user("cordelia").id
        user_data = self.create_user_notifications_data_object()
        self.assertTrue(
            user_data.is_notifiable(private_message=True, sender_id=sender_id, idle=True)
        )
