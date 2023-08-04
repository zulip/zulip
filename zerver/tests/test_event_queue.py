import time
from typing import Any, Callable, Collection, Dict, List
from unittest import mock

import orjson
from django.http import HttpRequest, HttpResponse

from zerver.actions.message_send import internal_send_private_message
from zerver.actions.muted_users import do_mute_user
from zerver.actions.streams import do_change_subscription_property
from zerver.actions.user_groups import check_add_user_group
from zerver.actions.user_settings import do_change_user_setting
from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.lib.cache import cache_delete, get_muting_users_cache_key
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock, dummy_handler, mock_queue_publish
from zerver.models import Recipient, Subscription, UserProfile, UserTopic, get_stream
from zerver.tornado.event_queue import (
    ClientDescriptor,
    access_client_descriptor,
    allocate_client_descriptor,
    maybe_enqueue_notifications,
    missedmessage_hook,
    persistent_queue_filename,
    process_notification,
)
from zerver.tornado.views import cleanup_event_queue, get_events


class MaybeEnqueueNotificationsTest(ZulipTestCase):
    def test_maybe_enqueue_notifications(self) -> None:
        # We've already tested the "when to send notifications" logic as part of the
        # notification_data module.
        # This test is for verifying whether `maybe_enqueue_notifications` returns the
        # `already_notified` data correctly.
        params = self.get_maybe_enqueue_notifications_parameters(
            message_id=1, user_id=1, acting_user_id=2
        )

        with mock_queue_publish(
            "zerver.tornado.event_queue.queue_json_publish"
        ) as mock_queue_json_publish:
            notified = maybe_enqueue_notifications(**params)
            mock_queue_json_publish.assert_not_called()

        with mock_queue_publish(
            "zerver.tornado.event_queue.queue_json_publish"
        ) as mock_queue_json_publish:
            params["user_notifications_data"] = self.create_user_notifications_data_object(
                user_id=1, dm_push_notify=True, dm_email_notify=True
            )
            notified = maybe_enqueue_notifications(**params)
            self.assertTrue(mock_queue_json_publish.call_count, 2)

            queues_pushed = [entry[0][0] for entry in mock_queue_json_publish.call_args_list]
            self.assertIn("missedmessage_mobile_notifications", queues_pushed)
            self.assertIn("missedmessage_emails", queues_pushed)

            self.assertTrue(notified["email_notified"])
            self.assertTrue(notified["push_notified"])

        with mock_queue_publish(
            "zerver.tornado.event_queue.queue_json_publish"
        ) as mock_queue_json_publish:
            params = self.get_maybe_enqueue_notifications_parameters(
                message_id=1,
                acting_user_id=2,
                user_id=3,
                mention_push_notify=True,
                mention_email_notify=True,
                mentioned_user_group_id=33,
            )
            notified = maybe_enqueue_notifications(**params)
            self.assertTrue(mock_queue_json_publish.call_count, 2)

            push_notice = mock_queue_json_publish.call_args_list[0][0][1]
            self.assertEqual(push_notice["mentioned_user_group_id"], 33)

            email_notice = mock_queue_json_publish.call_args_list[1][0][1]
            self.assertEqual(email_notice["mentioned_user_group_id"], 33)


class StreamWatchersTest(ZulipTestCase):
    def test_stream_watchers(self) -> None:
        """
        We used to have a bug with stream_watchers, where we set their flags to
        None.
        """
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm
        stream_name = "Denmark"

        self.subscribe(cordelia, stream_name)
        self.unsubscribe(hamlet, stream_name)

        queue_data = dict(
            all_public_streams=True,
            apply_markdown=True,
            client_gravatar=True,
            client_type_name="home grown API program",
            event_types=["message"],
            last_connection_time=time.time(),
            queue_timeout=0,
            realm_id=realm.id,
            user_profile_id=hamlet.id,
        )

        client = allocate_client_descriptor(queue_data)

        self.send_stream_message(cordelia, stream_name)

        self.assert_length(client.event_queue.contents(), 1)

        # This next line of code should silently succeed and basically do
        # nothing under the covers.  This test is here to prevent a bug
        # from re-appearing.
        missedmessage_hook(
            user_profile_id=hamlet.id,
            client=client,
            last_for_client=True,
        )


class MissedMessageHookTest(ZulipTestCase):
    """Tests what arguments missedmessage_hook passes into maybe_enqueue_notifications.
    Combined with the previous test, this ensures that the missedmessage_hook is correct"""

    def tornado_call(
        self,
        view_func: Callable[[HttpRequest, UserProfile], HttpResponse],
        user_profile: UserProfile,
        post_data: Dict[str, Any],
    ) -> HttpResponse:
        request = HostRequestMock(post_data, user_profile, tornado_handler=dummy_handler)
        return view_func(request, user_profile)

    def allocate_event_queue(self, user: UserProfile) -> ClientDescriptor:
        result = self.tornado_call(
            get_events,
            user,
            {
                "apply_markdown": orjson.dumps(True).decode(),
                "client_gravatar": orjson.dumps(True).decode(),
                "event_types": orjson.dumps(["message"]).decode(),
                "user_client": "website",
                "dont_block": orjson.dumps(True).decode(),
            },
        )
        self.assert_json_success(result)
        queue_id = orjson.loads(result.content)["queue_id"]
        return access_client_descriptor(user.id, queue_id)

    def destroy_event_queue(self, user: UserProfile, queue_id: str) -> None:
        result = self.tornado_call(cleanup_event_queue, user, {"queue_id": queue_id})
        self.assert_json_success(result)

    def assert_maybe_enqueue_notifications_call_args(
        self,
        args_dict: Collection[Any],
        message_id: int,
        user_id: int,
        **kwargs: Any,
    ) -> None:
        expected_args_dict = self.get_maybe_enqueue_notifications_parameters(
            user_id=user_id,
            acting_user_id=self.example_user("iago").id,
            message_id=message_id,
            **kwargs,
        )
        self.assertEqual(args_dict, expected_args_dict)

    def change_subscription_properties(self, properties: Dict[str, bool]) -> None:
        stream = get_stream("Denmark", self.user_profile.realm)
        sub = Subscription.objects.get(
            user_profile=self.user_profile,
            recipient__type=Recipient.STREAM,
            recipient__type_id=stream.id,
        )
        for property_name, value in properties.items():
            do_change_subscription_property(
                self.user_profile, sub, stream, property_name, value, acting_user=None
            )

    def setUp(self) -> None:
        self.user_profile = self.example_user("hamlet")
        self.cordelia = self.example_user("cordelia")
        do_change_user_setting(
            self.user_profile, "enable_online_push_notifications", False, acting_user=None
        )
        self.iago = self.example_user("iago")
        self.client_descriptor = self.allocate_event_queue(self.user_profile)
        self.assertTrue(self.client_descriptor.event_queue.empty())

        self.login_user(self.user_profile)

    def tearDown(self) -> None:
        self.destroy_event_queue(self.user_profile, self.client_descriptor.event_queue.id)

    def test_basic(self) -> None:
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            # To test the missed_message hook, we first need to send a message
            msg_id = self.send_stream_message(self.iago, "Denmark")

            # Verify that nothing happens if you call it as not the
            # "last client descriptor", in which case the function
            # short-circuits, since the `missedmessage_hook` handler
            # for garbage-collection is only for the user's last queue.
            missedmessage_hook(self.user_profile.id, self.client_descriptor, False)
            mock_enqueue.assert_not_called()

            # Now verify that we called the appropriate enqueue function
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_direct_message(self) -> None:
        # By default, email and push notifications should be sent for direct messages
        msg_id = self.send_personal_message(self.iago, self.user_profile)
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                dm_email_notify=True,
                dm_push_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_enable_offline_email_notifications_setting(self) -> None:
        # When `enable_offline_email_notifications` is off, email notifications
        # should not be sent for direct messages
        do_change_user_setting(
            self.user_profile, "enable_offline_email_notifications", False, acting_user=None
        )
        msg_id = self.send_personal_message(self.iago, self.user_profile)
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                dm_email_notify=False,
                dm_push_notify=True,
                already_notified={"email_notified": False, "push_notified": True},
            )

    def test_mention(self) -> None:
        # By default, email and push notifications should be sent for mentions
        msg_id = self.send_stream_message(
            self.example_user("iago"), "Denmark", content="@**King Hamlet** what's up?"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                mention_push_notify=True,
                mention_email_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_enable_offline_push_notifications_setting(self) -> None:
        # When `enable_offline_push_notifications` is off, push notifications should not be sent for mentions
        do_change_user_setting(
            self.user_profile, "enable_offline_push_notifications", False, acting_user=None
        )
        msg_id = self.send_personal_message(self.iago, self.user_profile)
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                dm_email_notify=True,
                dm_push_notify=False,
                already_notified={"email_notified": True, "push_notified": False},
            )

    def test_topic_wildcard_mention(self) -> None:
        # By default, topic wildcard mentions should send notifications, just like regular mentions
        self.send_stream_message(self.user_profile, "Denmark")
        msg_id = self.send_stream_message(self.iago, "Denmark", content="@**topic** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called()
            args_dict = mock_enqueue.call_args_list[1][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                topic_wildcard_mention_email_notify=True,
                topic_wildcard_mention_push_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_topic_wildcard_mention_in_muted_stream(self) -> None:
        # Topic wildcard mentions in muted streams don't notify.
        self.change_subscription_properties({"is_muted": True})
        self.send_stream_message(self.user_profile, "Denmark")
        msg_id = self.send_stream_message(self.iago, "Denmark", content="@**topic** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called()
            args_dict = mock_enqueue.call_args_list[1][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                topic_wildcard_mention_email_notify=False,
                topic_wildcard_mention_push_notify=False,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_topic_wildcard_mention_in_muted_topic(self) -> None:
        # Topic wildcard mentions in muted topics don't notify.
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "mutingtest",
            visibility_policy=UserTopic.VisibilityPolicy.MUTED,
        )
        self.send_stream_message(self.user_profile, "Denmark")
        msg_id = self.send_stream_message(
            self.iago, "Denmark", topic_name="mutingtest", content="@**topic** what's up?"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called()
            args_dict = mock_enqueue.call_args_list[1][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                topic_wildcard_mention_email_notify=False,
                topic_wildcard_mention_push_notify=False,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_stream_wildcard_mention(self) -> None:
        # By default, stream wildcard mentions should send notifications, just like regular mentions
        msg_id = self.send_stream_message(self.iago, "Denmark", content="@**all** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_wildcard_mention_email_notify=True,
                stream_wildcard_mention_push_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_stream_wildcard_mention_in_muted_stream(self) -> None:
        # stream wildcard mentions in muted streams don't notify.
        self.change_subscription_properties({"is_muted": True})
        msg_id = self.send_stream_message(self.iago, "Denmark", content="@**all** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                stream_wildcard_mention_email_notify=False,
                stream_wildcard_mention_push_notify=False,
                message_id=msg_id,
                user_id=self.user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_stream_wildcard_mention_in_muted_topic(self) -> None:
        # stream wildcard mentions in muted topics don't notify.
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "mutingtest",
            visibility_policy=UserTopic.VisibilityPolicy.MUTED,
        )
        msg_id = self.send_stream_message(
            self.iago, "Denmark", topic_name="mutingtest", content="@**all** what's up?"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                stream_wildcard_mention_email_notify=False,
                stream_wildcard_mention_push_notify=False,
                message_id=msg_id,
                user_id=self.user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_wildcard_mentions_notify_global_setting(self) -> None:
        # With wildcard_mentions_notify=False for a user, we treat the user as not mentioned.
        do_change_user_setting(
            self.user_profile, "wildcard_mentions_notify", False, acting_user=None
        )
        msg_id = self.send_stream_message(self.iago, "Denmark", content="@**all** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_wildcard_mention_email_notify=False,
                stream_wildcard_mention_push_notify=False,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_wildcard_mentions_notify_stream_specific_setting(
        self,
    ) -> None:
        # If wildcard_mentions_notify=True for a stream and False for a user, we treat the user
        # as mentioned for that stream.
        do_change_user_setting(
            self.user_profile, "wildcard_mentions_notify", False, acting_user=None
        )
        self.change_subscription_properties({"wildcard_mentions_notify": True})
        msg_id = self.send_stream_message(self.iago, "Denmark", content="@**all** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_wildcard_mention_email_notify=True,
                stream_wildcard_mention_push_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_wildcard_mentions_notify_global_setting_is_a_wrapper(self) -> None:
        # If email notifications for direct messages and mentions themselves have been turned off,
        # even turning on `wildcard_mentions_notify` should not send email notifications
        do_change_user_setting(
            self.user_profile, "enable_offline_email_notifications", False, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "wildcard_mentions_notify", True, acting_user=None
        )
        msg_id = self.send_stream_message(self.iago, "Denmark", content="@**all** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            # We've turned off email notifications for personal mentions, but push notifications
            # for personal mentions are still on.
            # Because `wildcard_mentions_notify` is True, a message with `@all` should follow the
            # personal mention settings
            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_wildcard_mention_email_notify=False,
                stream_wildcard_mention_push_notify=True,
                already_notified={"email_notified": False, "push_notified": True},
            )

    def test_wildcard_mentions_notify_stream_specific_setting_is_a_wrapper(self) -> None:
        # Similar to the above test, but for the stream-specific version of the setting
        self.change_subscription_properties({"wildcard_mentions_notify": True})
        do_change_user_setting(
            self.user_profile, "enable_offline_email_notifications", False, acting_user=None
        )
        msg_id = self.send_stream_message(self.iago, "Denmark", content="@**all** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_wildcard_mention_email_notify=False,
                stream_wildcard_mention_push_notify=True,
                already_notified={"email_notified": False, "push_notified": True},
            )

    def test_user_group_mention(self) -> None:
        hamlet_and_cordelia = check_add_user_group(
            self.cordelia.realm,
            "hamlet_and_cordelia",
            [self.user_profile, self.cordelia],
            acting_user=None,
        )
        msg_id = self.send_stream_message(
            self.iago, "Denmark", content="@*hamlet_and_cordelia* what's up?"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                mention_push_notify=True,
                mention_email_notify=True,
                mentioned_user_group_id=hamlet_and_cordelia.id,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_stream_push_notify_global_setting(self) -> None:
        do_change_user_setting(
            self.user_profile, "enable_stream_push_notifications", True, acting_user=None
        )
        msg_id = self.send_stream_message(self.iago, "Denmark", content="what's up everyone?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_push_notify=True,
                stream_email_notify=False,
                already_notified={"email_notified": False, "push_notified": True},
            )

    def test_stream_email_notify_global_setting(self) -> None:
        do_change_user_setting(
            self.user_profile, "enable_stream_email_notifications", True, acting_user=None
        )
        msg_id = self.send_stream_message(self.iago, "Denmark", content="what's up everyone?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_push_notify=False,
                stream_email_notify=True,
                already_notified={"email_notified": True, "push_notified": False},
            )

    def test_stream_push_notify_global_setting_with_muted_stream(self) -> None:
        # Push notification should not be sent
        do_change_user_setting(
            self.user_profile, "enable_stream_push_notifications", True, acting_user=None
        )
        self.change_subscription_properties({"is_muted": True})
        msg_id = self.send_stream_message(self.iago, "Denmark", content="what's up everyone?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_stream_email_notify_global_setting_with_muted_topic(self) -> None:
        # Email notification should not be sent
        do_change_user_setting(
            self.user_profile, "enable_stream_email_notifications", True, acting_user=None
        )
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "mutingtest",
            visibility_policy=UserTopic.VisibilityPolicy.MUTED,
        )
        msg_id = self.send_stream_message(
            self.iago, "Denmark", topic_name="mutingtest", content="what's up everyone?"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_stream_push_notify_stream_specific_setting(self) -> None:
        self.change_subscription_properties({"push_notifications": True})
        msg_id = self.send_stream_message(self.iago, "Denmark", content="what's up everyone?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_push_notify=True,
                stream_email_notify=False,
                already_notified={"email_notified": False, "push_notified": True},
            )

    def test_stream_email_notify_stream_specific_setting(self) -> None:
        self.change_subscription_properties({"email_notifications": True})
        msg_id = self.send_stream_message(self.iago, "Denmark", content="what's up everyone?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_push_notify=False,
                stream_email_notify=True,
                already_notified={"email_notified": True, "push_notified": False},
            )

    def test_stream_push_notify_stream_specific_setting_with_muted_topic(self) -> None:
        # Push notification should not be sent
        self.change_subscription_properties({"push_notifications": True})
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "mutingtest",
            visibility_policy=UserTopic.VisibilityPolicy.MUTED,
        )
        msg_id = self.send_stream_message(
            self.iago,
            "Denmark",
            content="what's up everyone?",
            topic_name="mutingtest",
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_stream_email_notify_stream_specific_setting_with_muted_stream(self) -> None:
        # Email notification should not be sent
        self.change_subscription_properties({"email_notifications": True, "is_muted": True})
        msg_id = self.send_stream_message(self.iago, "Denmark", content="what's up everyone?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_stream_email_and_push_notify_unmuted_topic_muted_stream_with_all_notifications_turned_off(
        self,
    ) -> None:
        # Both push and email notifications should not be sent
        self.change_subscription_properties({"is_muted": True})
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "unmutingtest",
            visibility_policy=UserTopic.VisibilityPolicy.UNMUTED,
        )
        msg_id = self.send_stream_message(
            self.iago,
            "Denmark",
            content="what's up everyone?",
            topic_name="unmutingtest",
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_stream_email_and_push_notify_unmuted_topic_muted_stream_with_global_setting_turned_on(
        self,
    ) -> None:
        # Both push and email notifications should be sent
        do_change_user_setting(
            self.user_profile, "enable_stream_push_notifications", True, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "enable_stream_email_notifications", True, acting_user=None
        )
        self.change_subscription_properties({"is_muted": True})
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "unmutingtest",
            visibility_policy=UserTopic.VisibilityPolicy.UNMUTED,
        )
        msg_id = self.send_stream_message(
            self.iago,
            "Denmark",
            content="what's up everyone?",
            topic_name="unmutingtest",
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_push_notify=True,
                stream_email_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_stream_email_and_push_notify_unmuted_topic_muted_stream_with_stream_setting_turned_on(
        self,
    ) -> None:
        # Both push and email notifications should be sent
        self.change_subscription_properties(
            {"push_notifications": True, "email_notifications": True, "is_muted": True}
        )
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "unmutingtest",
            visibility_policy=UserTopic.VisibilityPolicy.UNMUTED,
        )
        msg_id = self.send_stream_message(
            self.iago,
            "Denmark",
            content="what's up everyone?",
            topic_name="unmutingtest",
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_push_notify=True,
                stream_email_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_stream_email_and_push_notify_unmuted_topic_and_unmuted_stream(
        self,
    ) -> None:
        # Both push and email notifications should be not sent
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "unmutingtest",
            visibility_policy=UserTopic.VisibilityPolicy.UNMUTED,
        )
        msg_id = self.send_stream_message(
            self.iago,
            "Denmark",
            content="what's up everyone?",
            topic_name="unmutingtest",
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_followed_topic_email_and_push_notify(self) -> None:
        # messages sent in followed topics should send both email and push notifications.
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_email_notifications", True, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_push_notifications", True, acting_user=None
        )
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "followed_topic_test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        msg_id = self.send_stream_message(
            self.iago, "Denmark", content="what's up everyone?", topic_name="followed_topic_test"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                followed_topic_email_notify=True,
                followed_topic_push_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_followed_topic_email_notify_global_setting(self) -> None:
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_email_notifications", False, acting_user=None
        )
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "followed_topic_test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        msg_id = self.send_stream_message(
            self.iago, "Denmark", content="what's up everyone?", topic_name="followed_topic_test"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                followed_topic_email_notify=False,
                followed_topic_push_notify=True,
                already_notified={"email_notified": False, "push_notified": True},
            )

    def test_followed_topic_push_notify_global_setting(self) -> None:
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_push_notifications", False, acting_user=None
        )
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "followed_topic_test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        msg_id = self.send_stream_message(
            self.iago, "Denmark", content="what's up everyone?", topic_name="followed_topic_test"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                followed_topic_email_notify=True,
                followed_topic_push_notify=False,
                already_notified={"email_notified": True, "push_notified": False},
            )

    def test_topic_wildcard_mention_in_followed_topic_notify(self) -> None:
        do_change_user_setting(
            self.user_profile, "wildcard_mentions_notify", False, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_email_notifications", False, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_push_notifications", False, acting_user=None
        )

        # By default, wildcard mentions in followed topics should send notifications, just like regular mentions.
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "followed_topic_test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        self.send_stream_message(self.user_profile, "Denmark", topic_name="followed_topic_test")
        msg_id = self.send_stream_message(
            self.iago, "Denmark", content="@**topic** what's up?", topic_name="followed_topic_test"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called()
            args_dict = mock_enqueue.call_args_list[1][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                topic_wildcard_mention_in_followed_topic_email_notify=True,
                topic_wildcard_mention_in_followed_topic_push_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_stream_wildcard_mention_in_followed_topic_notify(self) -> None:
        do_change_user_setting(
            self.user_profile, "wildcard_mentions_notify", False, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_email_notifications", False, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_push_notifications", False, acting_user=None
        )

        # By default, wildcard mentions in followed topics should send notifications, just like regular mentions.
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "followed_topic_test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        msg_id = self.send_stream_message(
            self.iago, "Denmark", content="@**all** what's up?", topic_name="followed_topic_test"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_wildcard_mention_in_followed_topic_email_notify=True,
                stream_wildcard_mention_in_followed_topic_push_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_topic_wildcard_mention_in_followed_topic_muted_stream(self) -> None:
        # By default, topic wildcard mentions in a followed topic with muted stream DO notify.
        do_change_user_setting(
            self.user_profile, "wildcard_mentions_notify", False, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_email_notifications", False, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_push_notifications", False, acting_user=None
        )

        self.change_subscription_properties({"is_muted": True})
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        self.send_stream_message(self.user_profile, "Denmark")

        msg_id = self.send_stream_message(self.iago, "Denmark", content="@**topic** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called()
            args_dict = mock_enqueue.call_args_list[1][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                topic_wildcard_mention_in_followed_topic_email_notify=True,
                topic_wildcard_mention_in_followed_topic_push_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_stream_wildcard_mention_in_followed_topic_muted_stream(self) -> None:
        # By default, stream wildcard mentions in a followed topic with muted stream DO notify.
        do_change_user_setting(
            self.user_profile, "wildcard_mentions_notify", False, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_email_notifications", False, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_push_notifications", False, acting_user=None
        )

        self.change_subscription_properties({"is_muted": True})
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        self.send_stream_message(self.user_profile, "Denmark")

        msg_id = self.send_stream_message(self.iago, "Denmark", content="@**all** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called()
            args_dict = mock_enqueue.call_args_list[1][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                stream_wildcard_mention_in_followed_topic_email_notify=True,
                stream_wildcard_mention_in_followed_topic_push_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )

    def test_followed_topic_wildcard_mentions_notify_global_setting(self) -> None:
        do_change_user_setting(
            self.user_profile, "wildcard_mentions_notify", False, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_email_notifications", False, acting_user=None
        )
        do_change_user_setting(
            self.user_profile, "enable_followed_topic_push_notifications", False, acting_user=None
        )

        # Now, disabling `enable_followed_topic_wildcard_mentions_notify` should result in no notifications.
        do_change_user_setting(
            self.user_profile,
            "enable_followed_topic_wildcard_mentions_notify",
            False,
            acting_user=None,
        )
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "followed_topic_test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        msg_id = self.send_stream_message(
            self.iago, "Denmark", content="@**all** what's up?", topic_name="followed_topic_test"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )

    def test_muted_sender(self) -> None:
        do_mute_user(self.user_profile, self.iago)
        msg_id = self.send_personal_message(self.iago, self.user_profile)
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                dm_push_notify=True,
                dm_email_notify=True,
                sender_is_muted=True,
                already_notified={"email_notified": False, "push_notified": False},
            )
        # Sending messages with muted users makes use of caching.
        # Cleanup the cache so that we don't mess up other tests.
        cache_delete(key=get_muting_users_cache_key(muted_user_id=self.iago.id))

    def test_bot_recipient(self) -> None:
        # Test that bots don't receive any notifications
        bot_info = {
            "full_name": "The Bot of Hamlet",
            "short_name": "hambot",
            "bot_type": "1",
        }
        result = self.client_post("/json/bots", bot_info)
        response_dict = self.assert_json_success(result)
        hambot = UserProfile.objects.get(id=response_dict["user_id"])

        # Our setUp and tearDown methods handle client descriptor for Hamlet,
        # but we need one for hambot
        hamlet_client_descriptor = self.client_descriptor
        self.client_descriptor = self.allocate_event_queue(hambot)
        msg_id = self.send_personal_message(self.iago, hambot)
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(hambot.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            # Defaults are all False
            self.assert_maybe_enqueue_notifications_call_args(
                user_id=hambot.id,
                args_dict=args_dict,
                message_id=msg_id,
            )
        self.destroy_event_queue(hambot, self.client_descriptor.event_queue.id)
        self.client_descriptor = hamlet_client_descriptor

    # Internal direct messages
    def test_disable_external_notifications(self) -> None:
        # The disable_external_notifications parameter, used for messages sent by welcome bot,
        # should result in no email/push notifications being sent regardless of the message type.
        msg_id = internal_send_private_message(
            self.iago, self.user_profile, "Test Content", disable_external_notifications=True
        )
        assert msg_id is not None
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(self.user_profile.id, self.client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            self.assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=self.user_profile.id,
                dm_email_notify=True,
                dm_push_notify=True,
                disable_external_notifications=True,
                # disable_external_notifications parameter set to False would have resulted in
                # already_notified={"email_notified": True, "push_notified": True}
                already_notified={"email_notified": False, "push_notified": False},
            )


class FileReloadLogicTest(ZulipTestCase):
    def test_persistent_queue_filename(self) -> None:
        with self.settings(
            JSON_PERSISTENT_QUEUE_FILENAME_PATTERN="/home/zulip/tornado/event_queues%s.json"
        ):
            self.assertEqual(
                persistent_queue_filename(9800), "/home/zulip/tornado/event_queues.json"
            )
            self.assertEqual(
                persistent_queue_filename(9800, last=True),
                "/home/zulip/tornado/event_queues.json.last",
            )
        with self.settings(
            JSON_PERSISTENT_QUEUE_FILENAME_PATTERN="/home/zulip/tornado/event_queues%s.json",
            TORNADO_PROCESSES=4,
        ):
            self.assertEqual(
                persistent_queue_filename(9800), "/home/zulip/tornado/event_queues.9800.json"
            )
            self.assertEqual(
                persistent_queue_filename(9800, last=True),
                "/home/zulip/tornado/event_queues.9800.last.json",
            )


class PruneInternalDataTest(ZulipTestCase):
    def test_prune_internal_data(self) -> None:
        user_profile = self.example_user("hamlet")
        queue_data = dict(
            all_public_streams=True,
            apply_markdown=True,
            client_gravatar=True,
            client_type_name="website",
            event_types=["message"],
            last_connection_time=time.time(),
            queue_timeout=600,
            realm_id=user_profile.realm.id,
            user_profile_id=user_profile.id,
        )
        client = allocate_client_descriptor(queue_data)
        self.assertTrue(client.event_queue.empty())

        self.send_stream_message(
            self.example_user("iago"), "Denmark", content="@**King Hamlet** what's up?"
        )
        self.send_stream_message(
            self.example_user("iago"), "Denmark", content="@**all** what's up?"
        )
        self.send_personal_message(self.example_user("iago"), user_profile)

        events = client.event_queue.contents()
        self.assert_length(events, 3)
        self.assertFalse("internal_data" in events[0])
        self.assertFalse("internal_data" in events[1])
        self.assertFalse("internal_data" in events[2])

        events = client.event_queue.contents(include_internal_data=True)
        self.assertTrue("internal_data" in events[0])
        self.assertTrue("internal_data" in events[1])
        self.assertTrue("internal_data" in events[2])


class EventQueueTest(ZulipTestCase):
    def get_client_descriptor(self) -> ClientDescriptor:
        hamlet = self.example_user("hamlet")
        realm = hamlet.realm
        queue_data = dict(
            all_public_streams=False,
            apply_markdown=False,
            client_gravatar=True,
            client_type_name="website",
            event_types=None,
            last_connection_time=time.time(),
            queue_timeout=0,
            realm_id=realm.id,
            user_profile_id=hamlet.id,
        )

        client = allocate_client_descriptor(queue_data)
        return client

    def verify_to_dict_end_to_end(self, client: ClientDescriptor) -> None:
        client_dict = client.to_dict()
        new_client = ClientDescriptor.from_dict(client_dict)
        self.assertEqual(client.to_dict(), new_client.to_dict())

        client_dict = client.to_dict()
        del client_dict["event_queue"]["newest_pruned_id"]
        new_client = ClientDescriptor.from_dict(client_dict)
        self.assertEqual(client_dict, new_client.to_dict())

    def test_one_event(self) -> None:
        client = self.get_client_descriptor()
        queue = client.event_queue
        in_dict = dict(
            type="arbitrary",
            x="foo",
            y=42,
            z=False,
            timestamp="1",
        )
        out_dict = dict(
            id=0,
            **in_dict,
        )
        queue.push(in_dict)
        self.assertFalse(queue.empty())
        self.verify_to_dict_end_to_end(client)
        self.assertEqual(queue.contents(), [out_dict])
        self.verify_to_dict_end_to_end(client)

    def test_event_collapsing(self) -> None:
        client = self.get_client_descriptor()
        queue = client.event_queue

        """
        The update_message_flags events are special, because
        they can be collapsed together.  Given two umfe's, we:
            * use the latest timestamp
            * concatenate the messages
        """

        def umfe(timestamp: int, messages: List[int]) -> Dict[str, Any]:
            return dict(
                type="update_message_flags",
                operation="add",
                flag="read",
                all=False,
                timestamp=timestamp,
                messages=messages,
            )

        events = [
            umfe(timestamp=1, messages=[101]),
            umfe(timestamp=2, messages=[201, 202]),
            dict(type="unknown"),
            dict(type="restart", server_generation="1"),
            umfe(timestamp=3, messages=[301, 302, 303]),
            dict(type="restart", server_generation="2"),
            umfe(timestamp=4, messages=[401, 402, 403, 404]),
        ]

        for event in events:
            queue.push(event)

        self.verify_to_dict_end_to_end(client)

        self.assertEqual(
            queue.contents(),
            [
                dict(id=2, type="unknown"),
                dict(id=5, type="restart", server_generation="2"),
                dict(
                    id=6,
                    type="update_message_flags",
                    operation="add",
                    flag="read",
                    all=False,
                    timestamp=4,
                    messages=[101, 201, 202, 301, 302, 303, 401, 402, 403, 404],
                ),
            ],
        )

        """
        Note that calling queue.contents() has the side
        effect that we will no longer be able to collapse
        the previous events, so the next event will just
        get added to the queue, rather than collapsed.
        """
        queue.push(
            umfe(timestamp=5, messages=[501, 502, 503, 504, 505]),
        )
        self.assertEqual(
            queue.contents(),
            [
                dict(id=2, type="unknown"),
                dict(id=5, type="restart", server_generation="2"),
                dict(
                    id=6,
                    type="update_message_flags",
                    operation="add",
                    flag="read",
                    all=False,
                    timestamp=4,
                    messages=[101, 201, 202, 301, 302, 303, 401, 402, 403, 404],
                ),
                dict(
                    id=7,
                    type="update_message_flags",
                    operation="add",
                    flag="read",
                    all=False,
                    timestamp=5,
                    messages=[501, 502, 503, 504, 505],
                ),
            ],
        )

    def test_flag_add_collapsing(self) -> None:
        client = self.get_client_descriptor()
        queue = client.event_queue
        queue.push(
            {
                "type": "update_message_flags",
                "flag": "read",
                "operation": "add",
                "all": False,
                "messages": [1, 2, 3, 4],
                "timestamp": "1",
            }
        )
        self.verify_to_dict_end_to_end(client)
        queue.push(
            {
                "type": "update_message_flags",
                "flag": "read",
                "all": False,
                "operation": "add",
                "messages": [5, 6],
                "timestamp": "1",
            }
        )
        self.verify_to_dict_end_to_end(client)
        self.assertEqual(
            queue.contents(),
            [
                {
                    "id": 1,
                    "type": "update_message_flags",
                    "all": False,
                    "flag": "read",
                    "operation": "add",
                    "messages": [1, 2, 3, 4, 5, 6],
                    "timestamp": "1",
                }
            ],
        )
        self.verify_to_dict_end_to_end(client)

    def test_flag_remove_collapsing(self) -> None:
        client = self.get_client_descriptor()
        queue = client.event_queue
        queue.push(
            {
                "type": "update_message_flags",
                "flag": "collapsed",
                "operation": "remove",
                "all": False,
                "messages": [1, 2, 3, 4],
                "timestamp": "1",
            }
        )
        self.verify_to_dict_end_to_end(client)
        queue.push(
            {
                "type": "update_message_flags",
                "flag": "collapsed",
                "all": False,
                "operation": "remove",
                "messages": [5, 6],
                "timestamp": "1",
            }
        )
        self.verify_to_dict_end_to_end(client)
        self.assertEqual(
            queue.contents(),
            [
                {
                    "id": 1,
                    "type": "update_message_flags",
                    "all": False,
                    "flag": "collapsed",
                    "operation": "remove",
                    "messages": [1, 2, 3, 4, 5, 6],
                    "timestamp": "1",
                }
            ],
        )
        self.verify_to_dict_end_to_end(client)

    def test_collapse_event(self) -> None:
        """
        This mostly focuses on the internals of
        how we store "virtual_events" that we
        can collapse if subsequent events are
        of the same form.  See the code in
        EventQueue.push for more context.
        """
        client = self.get_client_descriptor()
        queue = client.event_queue
        queue.push({"type": "restart", "server_generation": 1, "timestamp": "1"})
        # Verify the server_generation event is stored as a virtual event
        self.assertEqual(
            queue.virtual_events,
            {"restart": {"id": 0, "type": "restart", "server_generation": 1, "timestamp": "1"}},
        )
        # And we can reconstruct newest_pruned_id etc.
        self.verify_to_dict_end_to_end(client)

        queue.push({"type": "unknown", "timestamp": "1"})
        self.assertEqual(list(queue.queue), [{"id": 1, "type": "unknown", "timestamp": "1"}])
        self.assertEqual(
            queue.virtual_events,
            {"restart": {"id": 0, "type": "restart", "server_generation": 1, "timestamp": "1"}},
        )
        # And we can still reconstruct newest_pruned_id etc. correctly
        self.verify_to_dict_end_to_end(client)

        # Verify virtual events are converted to real events by .contents()
        self.assertEqual(
            queue.contents(),
            [
                {"id": 0, "type": "restart", "server_generation": 1, "timestamp": "1"},
                {"id": 1, "type": "unknown", "timestamp": "1"},
            ],
        )

        # And now verify to_dict after pruning
        queue.prune(0)
        self.verify_to_dict_end_to_end(client)

        queue.prune(1)
        self.verify_to_dict_end_to_end(client)


class SchemaMigrationsTests(ZulipTestCase):
    def test_reformat_legacy_send_message_event(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        old_format_event = dict(
            type="message",
            message=1,
            message_dict={},
            presence_idle_user_ids=[hamlet.id, othello.id],
        )
        old_format_users = [
            dict(
                id=hamlet.id,
                flags=["mentioned"],
                mentioned=True,
                online_push_enabled=True,
                stream_push_notify=False,
                stream_email_notify=True,
                wildcard_mention_notify=False,
                sender_is_muted=False,
            ),
            dict(
                id=cordelia.id,
                flags=["wildcard_mentioned"],
                mentioned=False,
                online_push_enabled=True,
                stream_push_notify=True,
                stream_email_notify=False,
                wildcard_mention_notify=True,
                sender_is_muted=False,
            ),
        ]
        notice = dict(event=old_format_event, users=old_format_users)

        expected_current_format_users = [
            dict(
                id=hamlet.id,
                flags=["mentioned"],
            ),
            dict(
                id=cordelia.id,
                flags=["wildcard_mentioned"],
            ),
        ]

        expected_current_format_event = dict(
            type="message",
            message=1,
            message_dict={},
            presence_idle_user_ids=[hamlet.id, othello.id],
            online_push_user_ids=[hamlet.id, cordelia.id],
            stream_push_user_ids=[cordelia.id],
            stream_email_user_ids=[hamlet.id],
            stream_wildcard_mention_user_ids=[cordelia.id],
            muted_sender_user_ids=[],
        )
        with mock.patch("zerver.tornado.event_queue.process_message_event") as m:
            process_notification(notice)
            m.assert_called_once()
            self.assertDictEqual(m.call_args[0][0], expected_current_format_event)
            self.assertEqual(m.call_args[0][1], expected_current_format_users)
