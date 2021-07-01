from zerver.lib.mention import MentionData
from zerver.lib.notification_data import get_user_group_mentions_data
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import create_user_group


class TestNotificationData(ZulipTestCase):
    def test_is_push_notifiable(self) -> None:
        user_id = self.example_user("hamlet").id
        acting_user_id = self.example_user("cordelia").id

        # Boring case
        user_data = self.create_user_notifications_data_object(user_id=user_id)
        self.assertEqual(
            user_data.get_push_notification_trigger(
                private_message=False, acting_user_id=acting_user_id, idle=True
            ),
            None,
        )
        self.assertFalse(
            user_data.is_push_notifiable(
                private_message=False, acting_user_id=acting_user_id, idle=True
            )
        )

        # Private message
        user_data = self.create_user_notifications_data_object(user_id=user_id)
        self.assertEqual(
            user_data.get_push_notification_trigger(
                private_message=True, acting_user_id=acting_user_id, idle=True
            ),
            "private_message",
        )
        self.assertTrue(
            user_data.is_push_notifiable(
                private_message=True, acting_user_id=acting_user_id, idle=True
            )
        )

        # Mention
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, flags=["mentioned"], mentioned=True
        )
        self.assertEqual(
            user_data.get_push_notification_trigger(
                private_message=False, acting_user_id=acting_user_id, idle=True
            ),
            "mentioned",
        )
        self.assertTrue(
            user_data.is_push_notifiable(
                private_message=False, acting_user_id=acting_user_id, idle=True
            )
        )

        # Wildcard mention
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, flags=["wildcard_mentioned"], wildcard_mention_notify=True
        )
        self.assertEqual(
            user_data.get_push_notification_trigger(
                private_message=False, acting_user_id=acting_user_id, idle=True
            ),
            "wildcard_mentioned",
        )
        self.assertTrue(
            user_data.is_push_notifiable(
                private_message=False, acting_user_id=acting_user_id, idle=True
            )
        )

        # Stream notification
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, stream_push_notify=True
        )
        self.assertEqual(
            user_data.get_push_notification_trigger(
                private_message=False, acting_user_id=acting_user_id, idle=True
            ),
            "stream_push_notify",
        )
        self.assertTrue(
            user_data.is_push_notifiable(
                private_message=False, acting_user_id=acting_user_id, idle=True
            )
        )

        # Now, test the `online_push_enabled` property
        # Test no notifications when not idle
        user_data = self.create_user_notifications_data_object(user_id=user_id)
        self.assertEqual(
            user_data.get_push_notification_trigger(
                private_message=True, acting_user_id=acting_user_id, idle=False
            ),
            None,
        )
        self.assertFalse(
            user_data.is_push_notifiable(
                private_message=True, acting_user_id=acting_user_id, idle=False
            )
        )

        # Test notifications are sent when not idle but `online_push_enabled = True`
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, online_push_enabled=True
        )
        self.assertEqual(
            user_data.get_push_notification_trigger(
                private_message=True, acting_user_id=acting_user_id, idle=False
            ),
            "private_message",
        )
        self.assertTrue(
            user_data.is_push_notifiable(
                private_message=True, acting_user_id=acting_user_id, idle=False
            )
        )

        # The following are hypothetical cases, since a private message can never have `stream_push_notify = True`.
        # We just want to test the early (False) return patterns in these special cases:
        # Message sender is muted.
        user_data = self.create_user_notifications_data_object(
            user_id=user_id,
            sender_is_muted=True,
            flags=["mentioned", "wildcard_mentioned"],
            wildcard_mention_notify=True,
            mentioned=True,
            stream_email_notify=True,
            stream_push_notify=True,
        )
        self.assertEqual(
            user_data.get_push_notification_trigger(
                private_message=True, acting_user_id=acting_user_id, idle=True
            ),
            None,
        )
        self.assertFalse(
            user_data.is_push_notifiable(
                private_message=True, acting_user_id=acting_user_id, idle=True
            )
        )

        # Message sender is the user the object corresponds to.
        user_data = self.create_user_notifications_data_object(
            user_id=acting_user_id,
            sender_is_muted=False,
            flags=["mentioned", "wildcard_mentioned"],
            wildcard_mention_notify=True,
            mentioned=True,
            stream_email_notify=True,
            stream_push_notify=True,
        )
        self.assertEqual(
            user_data.get_push_notification_trigger(
                private_message=True, acting_user_id=acting_user_id, idle=True
            ),
            None,
        )
        self.assertFalse(
            user_data.is_push_notifiable(
                private_message=True, acting_user_id=acting_user_id, idle=True
            )
        )

    def test_is_email_notifiable(self) -> None:
        user_id = self.example_user("hamlet").id
        acting_user_id = self.example_user("cordelia").id

        # Boring case
        user_data = self.create_user_notifications_data_object(user_id=user_id)
        self.assertEqual(
            user_data.get_email_notification_trigger(
                private_message=False, acting_user_id=acting_user_id, idle=True
            ),
            None,
        )
        self.assertFalse(
            user_data.is_email_notifiable(
                private_message=False, acting_user_id=acting_user_id, idle=True
            )
        )

        # Private message
        user_data = self.create_user_notifications_data_object(user_id=user_id)
        self.assertEqual(
            user_data.get_email_notification_trigger(
                private_message=True, acting_user_id=acting_user_id, idle=True
            ),
            "private_message",
        )
        self.assertTrue(
            user_data.is_email_notifiable(
                private_message=True, acting_user_id=acting_user_id, idle=True
            )
        )

        # Mention
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, flags=["mentioned"], mentioned=True
        )
        self.assertEqual(
            user_data.get_email_notification_trigger(
                private_message=False, acting_user_id=acting_user_id, idle=True
            ),
            "mentioned",
        )
        self.assertTrue(
            user_data.is_email_notifiable(
                private_message=False, acting_user_id=acting_user_id, idle=True
            )
        )

        # Wildcard mention
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, flags=["wildcard_mentioned"], wildcard_mention_notify=True
        )
        self.assertEqual(
            user_data.get_email_notification_trigger(
                private_message=False, acting_user_id=acting_user_id, idle=True
            ),
            "wildcard_mentioned",
        )
        self.assertTrue(
            user_data.is_email_notifiable(
                private_message=False, acting_user_id=acting_user_id, idle=True
            )
        )

        # Stream notification
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, stream_email_notify=True
        )
        self.assertEqual(
            user_data.get_email_notification_trigger(
                private_message=False, acting_user_id=acting_user_id, idle=True
            ),
            "stream_email_notify",
        )
        self.assertTrue(
            user_data.is_email_notifiable(
                private_message=False, acting_user_id=acting_user_id, idle=True
            )
        )

        # Test no notifications when not idle
        user_data = self.create_user_notifications_data_object(user_id=user_id)
        self.assertEqual(
            user_data.get_email_notification_trigger(
                private_message=True, acting_user_id=acting_user_id, idle=False
            ),
            None,
        )
        self.assertFalse(
            user_data.is_email_notifiable(
                private_message=True, acting_user_id=acting_user_id, idle=False
            )
        )

        # The following are hypothetical cases, since a private message can never have `stream_email_notify = True`.
        # We just want to test the early (False) return patterns in these special cases:
        # Message sender is muted.
        user_data = self.create_user_notifications_data_object(
            user_id=user_id,
            sender_is_muted=True,
            flags=["mentioned", "wildcard_mentioned"],
            wildcard_mention_notify=True,
            mentioned=True,
            stream_email_notify=True,
            stream_push_notify=True,
        )
        self.assertEqual(
            user_data.get_email_notification_trigger(
                private_message=True, acting_user_id=acting_user_id, idle=True
            ),
            None,
        )
        self.assertFalse(
            user_data.is_email_notifiable(
                private_message=True, acting_user_id=acting_user_id, idle=True
            )
        )

        # Message sender is the user the object corresponds to.
        user_data = self.create_user_notifications_data_object(
            user_id=acting_user_id,
            sender_is_muted=False,
            flags=["mentioned", "wildcard_mentioned"],
            wildcard_mention_notify=True,
            mentioned=True,
            stream_email_notify=True,
            stream_push_notify=True,
        )
        self.assertEqual(
            user_data.get_email_notification_trigger(
                private_message=True, acting_user_id=acting_user_id, idle=True
            ),
            None,
        )
        self.assertFalse(
            user_data.is_email_notifiable(
                private_message=True, acting_user_id=acting_user_id, idle=True
            )
        )

    def test_is_notifiable(self) -> None:
        # This is just for coverage purposes. We've already tested all scenarios above,
        # and `is_notifiable` is a simple OR of the email and push functions.
        user_id = self.example_user("hamlet").id
        acting_user_id = self.example_user("cordelia").id
        user_data = self.create_user_notifications_data_object(user_id=user_id)
        self.assertTrue(
            user_data.is_notifiable(private_message=True, acting_user_id=acting_user_id, idle=True)
        )

    def test_user_group_mentions_map(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        realm = hamlet.realm

        hamlet_only = create_user_group("hamlet_only", [hamlet], realm)
        hamlet_and_cordelia = create_user_group("hamlet_and_cordelia", [hamlet, cordelia], realm)

        # Base case. No user/user group mentions
        result = get_user_group_mentions_data(
            mentioned_user_ids=set(),
            mentioned_user_group_ids=[],
            mention_data=MentionData(realm.id, "no group mentioned"),
        )
        self.assertDictEqual(result, {})

        # Only user group mentions, no personal mentions
        result = get_user_group_mentions_data(
            mentioned_user_ids=set(),
            mentioned_user_group_ids=[hamlet_and_cordelia.id],
            mention_data=MentionData(realm.id, "hey @*hamlet_and_cordelia*!"),
        )
        self.assertDictEqual(
            result,
            {
                hamlet.id: hamlet_and_cordelia.id,
                cordelia.id: hamlet_and_cordelia.id,
            },
        )

        # Hamlet is mentioned in two user groups
        # Test that we consider the smaller user group
        result = get_user_group_mentions_data(
            mentioned_user_ids=set(),
            mentioned_user_group_ids=[hamlet_and_cordelia.id, hamlet_only.id],
            mention_data=MentionData(realm.id, "hey @*hamlet_and_cordelia* and @*hamlet_only*"),
        )
        self.assertDictEqual(
            result,
            {
                hamlet.id: hamlet_only.id,
                cordelia.id: hamlet_and_cordelia.id,
            },
        )

        # To make sure we aren't getting the expected data from over-writing in a loop,
        # test the same setup as above, but with reversed group ids.
        result = get_user_group_mentions_data(
            mentioned_user_ids=set(),
            mentioned_user_group_ids=[hamlet_only.id, hamlet_and_cordelia.id],
            mention_data=MentionData(realm.id, "hey @*hamlet_only* and @*hamlet_and_cordelia*"),
        )
        self.assertDictEqual(
            result,
            {
                hamlet.id: hamlet_only.id,
                cordelia.id: hamlet_and_cordelia.id,
            },
        )

        # Personal and user group mentioned. Test that we don't consider the user
        # group mention for Hamlet in this case.
        result = get_user_group_mentions_data(
            mentioned_user_ids=set([hamlet.id]),
            mentioned_user_group_ids=[hamlet_and_cordelia.id],
            mention_data=MentionData(realm.id, "hey @*hamlet_and_cordelia*!"),
        )
        self.assertDictEqual(
            result,
            {
                cordelia.id: hamlet_and_cordelia.id,
            },
        )
