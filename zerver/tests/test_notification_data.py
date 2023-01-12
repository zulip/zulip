from zerver.lib.mention import MentionBackend, MentionData
from zerver.lib.notification_data import UserMessageNotificationsData, get_user_group_mentions_data
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.user_groups import create_user_group


class TestNotificationData(ZulipTestCase):
    """
    Because the `UserMessageNotificationsData` does not do any database queries, all user IDs
    used in the following tests are arbitrary, and do not represent real users.
    """

    def test_is_push_notifiable(self) -> None:
        user_id = self.example_user("hamlet").id
        acting_user_id = self.example_user("cordelia").id

        # Boring case
        user_data = self.create_user_notifications_data_object(user_id=user_id)
        self.assertEqual(
            user_data.get_push_notification_trigger(acting_user_id=acting_user_id, idle=True),
            None,
        )
        self.assertFalse(user_data.is_push_notifiable(acting_user_id=acting_user_id, idle=True))

        # Private message
        user_data = self.create_user_notifications_data_object(user_id=user_id, pm_push_notify=True)
        self.assertEqual(
            user_data.get_push_notification_trigger(acting_user_id=acting_user_id, idle=True),
            "private_message",
        )
        self.assertTrue(user_data.is_push_notifiable(acting_user_id=acting_user_id, idle=True))

        # Mention
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, mention_push_notify=True
        )
        self.assertEqual(
            user_data.get_push_notification_trigger(acting_user_id=acting_user_id, idle=True),
            "mentioned",
        )
        self.assertTrue(user_data.is_push_notifiable(acting_user_id=acting_user_id, idle=True))

        # Wildcard mention
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, wildcard_mention_push_notify=True
        )
        self.assertEqual(
            user_data.get_push_notification_trigger(acting_user_id=acting_user_id, idle=True),
            "wildcard_mentioned",
        )
        self.assertTrue(user_data.is_push_notifiable(acting_user_id=acting_user_id, idle=True))

        # Stream notification
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, stream_push_notify=True
        )
        self.assertEqual(
            user_data.get_push_notification_trigger(acting_user_id=acting_user_id, idle=True),
            "stream_push_notify",
        )
        self.assertTrue(user_data.is_push_notifiable(acting_user_id=acting_user_id, idle=True))

        # Now, test the `online_push_enabled` property
        # Test no notifications when not idle
        user_data = self.create_user_notifications_data_object(user_id=user_id, pm_push_notify=True)
        self.assertEqual(
            user_data.get_push_notification_trigger(acting_user_id=acting_user_id, idle=False),
            None,
        )
        self.assertFalse(user_data.is_push_notifiable(acting_user_id=acting_user_id, idle=False))

        # Test notifications are sent when not idle but `online_push_enabled = True`
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, online_push_enabled=True, pm_push_notify=True
        )
        self.assertEqual(
            user_data.get_push_notification_trigger(acting_user_id=acting_user_id, idle=False),
            "private_message",
        )
        self.assertTrue(user_data.is_push_notifiable(acting_user_id=acting_user_id, idle=False))

        # Test the early (False) return patterns in these special cases:
        # Message sender is muted.
        user_data = self.create_user_notifications_data_object(
            user_id=user_id,
            sender_is_muted=True,
            pm_push_notify=True,
            pm_email_notify=True,
            mention_push_notify=True,
            mention_email_notify=True,
            wildcard_mention_push_notify=True,
            wildcard_mention_email_notify=True,
        )
        self.assertEqual(
            user_data.get_push_notification_trigger(acting_user_id=acting_user_id, idle=True),
            None,
        )
        self.assertFalse(user_data.is_push_notifiable(acting_user_id=acting_user_id, idle=True))

        # Message sender is the user the object corresponds to.
        user_data = self.create_user_notifications_data_object(
            user_id=acting_user_id,
            pm_push_notify=True,
            pm_email_notify=True,
            mention_push_notify=True,
            mention_email_notify=True,
            wildcard_mention_push_notify=True,
            wildcard_mention_email_notify=True,
        )
        self.assertEqual(
            user_data.get_push_notification_trigger(acting_user_id=acting_user_id, idle=True),
            None,
        )
        self.assertFalse(user_data.is_push_notifiable(acting_user_id=acting_user_id, idle=True))

    def test_is_email_notifiable(self) -> None:
        user_id = self.example_user("hamlet").id
        acting_user_id = self.example_user("cordelia").id

        # Boring case
        user_data = self.create_user_notifications_data_object(user_id=user_id)
        self.assertEqual(
            user_data.get_email_notification_trigger(acting_user_id=acting_user_id, idle=True),
            None,
        )
        self.assertFalse(user_data.is_email_notifiable(acting_user_id=acting_user_id, idle=True))

        # Private message
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, pm_email_notify=True
        )
        self.assertEqual(
            user_data.get_email_notification_trigger(acting_user_id=acting_user_id, idle=True),
            "private_message",
        )
        self.assertTrue(user_data.is_email_notifiable(acting_user_id=acting_user_id, idle=True))

        # Mention
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, mention_email_notify=True
        )
        self.assertEqual(
            user_data.get_email_notification_trigger(acting_user_id=acting_user_id, idle=True),
            "mentioned",
        )
        self.assertTrue(user_data.is_email_notifiable(acting_user_id=acting_user_id, idle=True))

        # Wildcard mention
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, wildcard_mention_email_notify=True
        )
        self.assertEqual(
            user_data.get_email_notification_trigger(acting_user_id=acting_user_id, idle=True),
            "wildcard_mentioned",
        )
        self.assertTrue(user_data.is_email_notifiable(acting_user_id=acting_user_id, idle=True))

        # Stream notification
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, stream_email_notify=True
        )
        self.assertEqual(
            user_data.get_email_notification_trigger(acting_user_id=acting_user_id, idle=True),
            "stream_email_notify",
        )
        self.assertTrue(user_data.is_email_notifiable(acting_user_id=acting_user_id, idle=True))

        # Test no notifications when not idle
        user_data = self.create_user_notifications_data_object(
            user_id=user_id, pm_email_notify=True
        )
        self.assertEqual(
            user_data.get_email_notification_trigger(acting_user_id=acting_user_id, idle=False),
            None,
        )
        self.assertFalse(user_data.is_email_notifiable(acting_user_id=acting_user_id, idle=False))

        # Test the early (False) return patterns in these special cases:
        # Message sender is muted.
        user_data = self.create_user_notifications_data_object(
            user_id=user_id,
            sender_is_muted=True,
            pm_push_notify=True,
            pm_email_notify=True,
            mention_push_notify=True,
            mention_email_notify=True,
            wildcard_mention_push_notify=True,
            wildcard_mention_email_notify=True,
        )
        self.assertEqual(
            user_data.get_email_notification_trigger(acting_user_id=acting_user_id, idle=True),
            None,
        )
        self.assertFalse(user_data.is_email_notifiable(acting_user_id=acting_user_id, idle=True))

        # Message sender is the user the object corresponds to.
        user_data = self.create_user_notifications_data_object(
            user_id=acting_user_id,
            pm_push_notify=True,
            pm_email_notify=True,
            mention_push_notify=True,
            mention_email_notify=True,
            wildcard_mention_push_notify=True,
            wildcard_mention_email_notify=True,
        )
        self.assertEqual(
            user_data.get_email_notification_trigger(acting_user_id=acting_user_id, idle=True),
            None,
        )
        self.assertFalse(user_data.is_email_notifiable(acting_user_id=acting_user_id, idle=True))

    def test_is_notifiable(self) -> None:
        # This is just for coverage purposes. We've already tested all scenarios above,
        # and `is_notifiable` is a simple OR of the email and push functions.
        user_id = self.example_user("hamlet").id
        acting_user_id = self.example_user("cordelia").id
        user_data = self.create_user_notifications_data_object(user_id=user_id, pm_push_notify=True)
        self.assertTrue(user_data.is_notifiable(acting_user_id=acting_user_id, idle=True))

    def test_bot_user_notifiability(self) -> None:
        # Non-bot user (`user_id=9`) should get notified, while bot user (`user_id=10`) shouldn't
        for user_id, notifiable in [(9, True), (10, False)]:
            user_data = UserMessageNotificationsData.from_user_id_sets(
                user_id=user_id,
                flags=["mentioned"],
                private_message=True,
                online_push_user_ids=set(),
                pm_mention_email_disabled_user_ids=set(),
                pm_mention_push_disabled_user_ids=set(),
                all_bot_user_ids={10, 11, 12},
                muted_sender_user_ids=set(),
                stream_email_user_ids=set(),
                stream_push_user_ids=set(),
                wildcard_mention_user_ids=set(),
            )
            self.assertEqual(user_data.is_notifiable(acting_user_id=1000, idle=True), notifiable)

    def test_user_group_mentions_map(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        realm = hamlet.realm

        hamlet_only = create_user_group("hamlet_only", [hamlet], realm, acting_user=None)
        hamlet_and_cordelia = create_user_group(
            "hamlet_and_cordelia", [hamlet, cordelia], realm, acting_user=None
        )

        mention_backend = MentionBackend(realm.id)

        # Base case. No user/user group mentions
        result = get_user_group_mentions_data(
            mentioned_user_ids=set(),
            mentioned_user_group_ids=[],
            mention_data=MentionData(mention_backend, "no group mentioned"),
        )
        self.assertDictEqual(result, {})

        # Only user group mentions, no personal mentions
        result = get_user_group_mentions_data(
            mentioned_user_ids=set(),
            mentioned_user_group_ids=[hamlet_and_cordelia.id],
            mention_data=MentionData(mention_backend, "hey @*hamlet_and_cordelia*!"),
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
            mention_data=MentionData(
                mention_backend, "hey @*hamlet_and_cordelia* and @*hamlet_only*"
            ),
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
            mention_data=MentionData(
                mention_backend, "hey @*hamlet_only* and @*hamlet_and_cordelia*"
            ),
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
            mentioned_user_ids={hamlet.id},
            mentioned_user_group_ids=[hamlet_and_cordelia.id],
            mention_data=MentionData(mention_backend, "hey @*hamlet_and_cordelia*!"),
        )
        self.assertDictEqual(
            result,
            {
                cordelia.id: hamlet_and_cordelia.id,
            },
        )
