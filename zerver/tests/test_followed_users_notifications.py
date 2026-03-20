from zerver.lib.test_classes import ZulipTestCase
from zerver.models import FollowedUser
from zerver.lib.followed_users import add_user_follow, get_followers_who_can_see_stream_message
from django.utils.timezone import now


class FollowedUserNotificationTest(ZulipTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.follower = self.example_user("hamlet")
        self.followed = self.example_user("othello")

    # Verify that adding a follow relationship creates a DB record
    def test_add_follow(self) -> None:
        add_user_follow(self.follower, self.followed, now())

        self.assertTrue(
            FollowedUser.objects.filter(
                user_profile=self.follower,
                followed_user=self.followed,
            ).exists()
        )

    # Followers without stream subscription should not receive notifications
    def test_non_subscriber_not_notified(self) -> None:
        stream = self.make_stream("test-stream")

        self.follower.enable_followed_user_push_notifications = True
        self.follower.save()

        add_user_follow(self.follower, self.followed, now())

        result = get_followers_who_can_see_stream_message(
            followed_user_id=self.followed.id,
            stream_id=stream.id,
            realm_id=self.follower.realm.id,
        )

        self.assertNotIn(self.follower.id, result)

    # Followers who are subscribed and have push enabled should be notified
    def test_follower_with_push_and_subscription_notified(self) -> None:
        stream = self.subscribe(self.follower, "test-stream")
        self.subscribe(self.followed, stream.name)

        self.follower.enable_followed_user_push_notifications = True
        self.follower.save()

        add_user_follow(self.follower, self.followed, now())

        result = get_followers_who_can_see_stream_message(
            followed_user_id=self.followed.id,
            stream_id=stream.id,
            realm_id=self.follower.realm.id,
        )

        self.assertIn(self.follower.id, result)

    # Followers with push disabled should NOT receive notifications
    def test_push_disabled_not_notified(self) -> None:
        stream = self.subscribe(self.follower, "test-stream")

        # Push notifications disabled
        self.follower.enable_followed_user_push_notifications = False
        self.follower.save()

        add_user_follow(self.follower, self.followed, now())

        result = get_followers_who_can_see_stream_message(
            followed_user_id=self.followed.id,
            stream_id=stream.id,
            realm_id=self.follower.realm.id,
        )

        self.assertNotIn(self.follower.id, result)

    # Verify that a follower actually receives the message in the stream
    def test_followed_user_message_visible_to_follower(self) -> None:
        stream = self.subscribe(self.follower, "test-stream")
        self.subscribe(self.followed, stream.name)

        self.follower.enable_followed_user_push_notifications = True
        self.follower.save()

        add_user_follow(self.follower, self.followed, now())

        self.send_stream_message(
            self.followed,
            stream.name,
            "test",
            "hello"
        )

        from zerver.models import UserMessage
        messages = UserMessage.objects.filter(
            user_profile=self.follower,
            message__sender=self.followed
        )
        self.assertTrue(messages.exists())