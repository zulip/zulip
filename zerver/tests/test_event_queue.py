import time
from typing import Any, Callable, Collection, Dict, List
from unittest import mock

import orjson
from django.http import HttpRequest, HttpResponse

from zerver.actions.streams import do_change_subscription_property
from zerver.actions.user_topics import do_mute_topic
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock, dummy_handler, mock_queue_publish
from zerver.lib.user_groups import create_user_group, remove_user_from_user_group
from zerver.models import Recipient, Stream, Subscription, UserProfile, get_stream
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


class MissedMessageNotificationsTest(ZulipTestCase):
    """Tests the logic for when missed-message notifications
    should be triggered, based on user settings"""

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
                user_id=1, pm_push_notify=True, pm_email_notify=True
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

    def tornado_call(
        self,
        view_func: Callable[[HttpRequest, UserProfile], HttpResponse],
        user_profile: UserProfile,
        post_data: Dict[str, Any],
    ) -> HttpResponse:
        request = HostRequestMock(post_data, user_profile, tornado_handler=dummy_handler)
        return view_func(request, user_profile)

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

    def test_end_to_end_missedmessage_hook(self) -> None:
        """Tests what arguments missedmessage_hook passes into maybe_enqueue_notifications.
        Combined with the previous test, this ensures that the missedmessage_hook is correct"""
        user_profile = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")

        user_profile.enable_online_push_notifications = False
        user_profile.save()

        iago = self.example_user("iago")

        # Fetch the Denmark stream for testing
        stream = get_stream("Denmark", user_profile.realm)
        sub = Subscription.objects.get(
            user_profile=user_profile,
            recipient__type=Recipient.STREAM,
            recipient__type_id=stream.id,
        )

        self.login_user(user_profile)

        def change_subscription_properties(
            user_profile: UserProfile,
            stream: Stream,
            sub: Subscription,
            properties: Dict[str, bool],
        ) -> None:
            for property_name, value in properties.items():
                do_change_subscription_property(
                    user_profile, sub, stream, property_name, value, acting_user=None
                )

        def allocate_event_queue(user: UserProfile) -> ClientDescriptor:
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

        def destroy_event_queue(user: UserProfile, queue_id: str) -> None:
            result = self.tornado_call(cleanup_event_queue, user, {"queue_id": queue_id})
            self.assert_json_success(result)

        def assert_maybe_enqueue_notifications_call_args(
            args_dict: Collection[Any],
            message_id: int,
            user_id: int,
            **kwargs: Any,
        ) -> None:
            expected_args_dict = self.get_maybe_enqueue_notifications_parameters(
                user_id=user_id,
                acting_user_id=iago.id,
                message_id=message_id,
                **kwargs,
            )
            self.assertEqual(args_dict, expected_args_dict)

        client_descriptor = allocate_event_queue(user_profile)
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            # To test the missed_message hook, we first need to send a message
            msg_id = self.send_stream_message(iago, "Denmark")

            # Verify that nothing happens if you call it as not the
            # "last client descriptor", in which case the function
            # short-circuits, since the `missedmessage_hook` handler
            # for garbage-collection is only for the user's last queue.
            missedmessage_hook(user_profile.id, client_descriptor, False)
            mock_enqueue.assert_not_called()

            # Now verify that we called the appropriate enqueue function
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)

        # Test the hook with a private message; this should trigger notifications
        client_descriptor = allocate_event_queue(user_profile)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_personal_message(iago, user_profile)
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                pm_email_notify=True,
                pm_push_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)

        # If `enable_offline_email_notifications` is disabled, email notifications shouldn't
        # be sent even for PMs
        user_profile.enable_offline_email_notifications = False
        user_profile.save()
        client_descriptor = allocate_event_queue(user_profile)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_personal_message(iago, user_profile)
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                pm_email_notify=False,
                pm_push_notify=True,
                already_notified={"email_notified": False, "push_notified": True},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)
        user_profile.enable_offline_email_notifications = True
        user_profile.save()

        # Test the hook with a mention; this should trigger notifications
        client_descriptor = allocate_event_queue(user_profile)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_stream_message(
            self.example_user("iago"), "Denmark", content="@**King Hamlet** what's up?"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                mention_push_notify=True,
                mention_email_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)

        # If `enable_offline_push_notifications` is disabled, push notifications shouldn't
        # be sent even for mentions
        user_profile.enable_offline_push_notifications = False
        user_profile.save()
        client_descriptor = allocate_event_queue(user_profile)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_personal_message(iago, user_profile)
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                pm_email_notify=True,
                pm_push_notify=False,
                already_notified={"email_notified": True, "push_notified": False},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)
        user_profile.enable_offline_push_notifications = True
        user_profile.save()

        # Test the hook with a wildcard mention; this should trigger notifications
        client_descriptor = allocate_event_queue(user_profile)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_stream_message(iago, "Denmark", content="@**all** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                wildcard_mention_email_notify=True,
                wildcard_mention_push_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)

        # Wildcard mentions in muted streams don't notify.
        change_subscription_properties(user_profile, stream, sub, {"is_muted": True})
        client_descriptor = allocate_event_queue(user_profile)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_stream_message(iago, "Denmark", content="@**all** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                wildcard_mention_email_notify=False,
                wildcard_mention_push_notify=False,
                message_id=msg_id,
                user_id=user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)
        change_subscription_properties(user_profile, stream, sub, {"is_muted": False})

        # With wildcard_mentions_notify=False, we treat the user as not mentioned.
        user_profile.wildcard_mentions_notify = False
        user_profile.save()
        client_descriptor = allocate_event_queue(user_profile)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_stream_message(iago, "Denmark", content="@**all** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                wildcard_mention_email_notify=False,
                wildcard_mention_push_notify=False,
                already_notified={"email_notified": False, "push_notified": False},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)
        user_profile.wildcard_mentions_notify = True
        user_profile.save()

        # If wildcard_mentions_notify=True for a stream and False for a user, we treat the user
        # as mentioned for that stream.
        user_profile.wildcard_mentions_notify = False
        sub.wildcard_mentions_notify = True
        user_profile.save()
        sub.save()
        client_descriptor = allocate_event_queue(user_profile)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_stream_message(iago, "Denmark", content="@**all** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                wildcard_mention_email_notify=True,
                wildcard_mention_push_notify=True,
                already_notified={"email_notified": True, "push_notified": True},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)
        user_profile.wildcard_mentions_notify = True
        sub.wildcard_mentions_notify = None
        user_profile.save()
        sub.save()

        # If notifications for personal mentions themselves have been turned off,
        # even turning on `wildcard_mentions_notify` should not send notifications
        user_profile.enable_offline_email_notifications = False
        user_profile.wildcard_mentions_notify = True
        user_profile.save()
        client_descriptor = allocate_event_queue(user_profile)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_stream_message(iago, "Denmark", content="@**all** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            # We've turned off email notifications for personal mentions, but push notifications
            # for personal mentions are still on.
            # Because `wildcard_mentions_notify` is True, a message with `@all` should follow the
            # personal mention settings
            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                wildcard_mention_email_notify=False,
                wildcard_mention_push_notify=True,
                already_notified={"email_notified": False, "push_notified": True},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)
        user_profile.enable_offline_email_notifications = True
        user_profile.wildcard_mentions_notify = True
        user_profile.save()

        # Test with a user group mention
        hamlet_and_cordelia = create_user_group(
            "hamlet_and_cordelia", [user_profile, cordelia], cordelia.realm
        )
        client_descriptor = allocate_event_queue(user_profile)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_stream_message(
            iago, "Denmark", content="@*hamlet_and_cordelia* what's up?"
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                mention_push_notify=True,
                mention_email_notify=True,
                mentioned_user_group_id=hamlet_and_cordelia.id,
                already_notified={"email_notified": True, "push_notified": True},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)
        remove_user_from_user_group(user_profile, hamlet_and_cordelia)
        remove_user_from_user_group(cordelia, hamlet_and_cordelia)

        # Test the hook with a stream message with stream_push_notify
        change_subscription_properties(user_profile, stream, sub, {"push_notifications": True})
        client_descriptor = allocate_event_queue(user_profile)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_stream_message(iago, "Denmark", content="what's up everyone?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                stream_push_notify=True,
                stream_email_notify=False,
                already_notified={"email_notified": False, "push_notified": True},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)

        # Test the hook with a stream message with stream_email_notify
        client_descriptor = allocate_event_queue(user_profile)
        change_subscription_properties(
            user_profile, stream, sub, {"push_notifications": False, "email_notifications": True}
        )
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_stream_message(iago, "Denmark", content="what's up everyone?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                stream_push_notify=False,
                stream_email_notify=True,
                already_notified={"email_notified": True, "push_notified": False},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)

        # Test the hook with stream message with stream_push_notify on
        # a muted topic, which we should not push notify for
        client_descriptor = allocate_event_queue(user_profile)
        change_subscription_properties(
            user_profile, stream, sub, {"push_notifications": True, "email_notifications": False}
        )

        self.assertTrue(client_descriptor.event_queue.empty())
        do_mute_topic(user_profile, stream, "mutingtest")
        msg_id = self.send_stream_message(
            iago,
            "Denmark",
            content="what's up everyone?",
            topic_name="mutingtest",
        )
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)

        # Test the hook with stream message with stream_email_notify on
        # a muted stream, which we should not push notify for
        client_descriptor = allocate_event_queue(user_profile)
        change_subscription_properties(
            user_profile, stream, sub, {"push_notifications": False, "email_notifications": True}
        )

        self.assertTrue(client_descriptor.event_queue.empty())
        change_subscription_properties(user_profile, stream, sub, {"is_muted": True})
        msg_id = self.send_stream_message(iago, "Denmark", content="what's up everyone?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                already_notified={"email_notified": False, "push_notified": False},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)

        # Clean up the state we just changed (not necessary unless we add more test code below)
        change_subscription_properties(
            user_profile, stream, sub, {"push_notifications": True, "is_muted": False}
        )

        # Test the hook when the sender has been muted
        result = self.api_post(user_profile, f"/api/v1/users/me/muted_users/{iago.id}")
        self.assert_json_success(result)
        client_descriptor = allocate_event_queue(user_profile)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_personal_message(iago, user_profile)
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            assert_maybe_enqueue_notifications_call_args(
                args_dict=args_dict,
                message_id=msg_id,
                user_id=user_profile.id,
                sender_is_muted=True,
                pm_email_notify=True,
                pm_push_notify=True,
                already_notified={"email_notified": False, "push_notified": False},
            )
        destroy_event_queue(user_profile, client_descriptor.event_queue.id)
        result = self.api_delete(user_profile, f"/api/v1/users/me/muted_users/{iago.id}")
        self.assert_json_success(result)

        # Test that bots don't receive any notifications
        bot_info = {
            "full_name": "The Bot of Hamlet",
            "short_name": "hambot",
            "bot_type": "1",
        }
        result = self.client_post("/json/bots", bot_info)
        response_dict = self.assert_json_success(result)
        hambot = UserProfile.objects.get(id=response_dict["user_id"])
        client_descriptor = allocate_event_queue(hambot)
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_personal_message(iago, hambot)
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(hambot.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_dict = mock_enqueue.call_args_list[0][1]

            # Defaults are all False
            assert_maybe_enqueue_notifications_call_args(
                user_id=hambot.id,
                args_dict=args_dict,
                message_id=msg_id,
            )
        destroy_event_queue(hambot, client_descriptor.event_queue.id)
        self.assert_json_success(result)


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
            wildcard_mention_user_ids=[cordelia.id],
            muted_sender_user_ids=[],
        )
        with mock.patch("zerver.tornado.event_queue.process_message_event") as m:
            process_notification(notice)
            m.assert_called_once()
            self.assertDictEqual(m.call_args[0][0], expected_current_format_event)
            self.assertEqual(m.call_args[0][1], expected_current_format_users)
