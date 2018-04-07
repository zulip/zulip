import mock
import time
import ujson

from django.http import HttpRequest, HttpResponse
from typing import Any, Callable, Dict, Tuple

from zerver.lib.actions import do_mute_topic
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import POSTRequestMock
from zerver.models import Recipient, Subscription, UserProfile, get_stream
from zerver.tornado.event_queue import maybe_enqueue_notifications, \
    allocate_client_descriptor, process_message_event, clear_client_event_queues_for_testing, \
    get_client_descriptor, missedmessage_hook
from zerver.tornado.views import get_events_backend

class MissedMessageNotificationsTest(ZulipTestCase):
    """Tests the logic for when missed-message notifications
    should be triggered, based on user settings"""
    def check_will_notify(self, *args: Any, **kwargs: Any) -> Tuple[str, str]:
        email_notice = None
        mobile_notice = None
        with mock.patch("zerver.tornado.event_queue.queue_json_publish") as mock_queue_publish:
            notified = maybe_enqueue_notifications(*args, **kwargs)
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

    def test_enqueue_notifications(self) -> None:
        user_profile = self.example_user("hamlet")
        message_id = 32

        # Boring message doesn't send a notice
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=False,
            mentioned=False, stream_push_notify=False, stream_name=None,
            always_push_notify=False, idle=True, already_notified={})
        self.assertTrue(email_notice is None)
        self.assertTrue(mobile_notice is None)

        # Private message sends a notice
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=True,
            mentioned=False, stream_push_notify=False, stream_name=None,
            always_push_notify=False, idle=True, already_notified={})
        self.assertTrue(email_notice is not None)
        self.assertTrue(mobile_notice is not None)

        # Private message won't double-send either notice if we've
        # already sent notices before.
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=True,
            mentioned=False, stream_push_notify=False, stream_name=None,
            always_push_notify=False, idle=True, already_notified={
                'push_notified': True,
                'email_notified': False,
            })
        self.assertTrue(email_notice is not None)
        self.assertTrue(mobile_notice is None)

        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=True,
            mentioned=False, stream_push_notify=False, stream_name=None,
            always_push_notify=False, idle=True, already_notified={
                'push_notified': False,
                'email_notified': True,
            })
        self.assertTrue(email_notice is None)
        self.assertTrue(mobile_notice is not None)

        # Mention sends a notice
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=False,
            mentioned=True, stream_push_notify=False, stream_name=None,
            always_push_notify=False, idle=True, already_notified={})
        self.assertTrue(email_notice is not None)
        self.assertTrue(mobile_notice is not None)

        # stream_push_notify pushes but doesn't email
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=False,
            mentioned=False, stream_push_notify=True, stream_name="Denmark",
            always_push_notify=False, idle=True, already_notified={})
        self.assertTrue(email_notice is None)
        self.assertTrue(mobile_notice is not None)

        # Private message doesn't send a notice if not idle
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=True,
            mentioned=False, stream_push_notify=False, stream_name=None,
            always_push_notify=False, idle=False, already_notified={})
        self.assertTrue(email_notice is None)
        self.assertTrue(mobile_notice is None)

        # Private message sends push but not email if not idle but always_push_notify
        email_notice, mobile_notice = self.check_will_notify(
            user_profile.id, message_id, private_message=True,
            mentioned=False, stream_push_notify=False, stream_name=None,
            always_push_notify=True, idle=False, already_notified={})
        self.assertTrue(email_notice is None)
        self.assertTrue(mobile_notice is not None)

    def tornado_call(self, view_func: Callable[[HttpRequest, UserProfile], HttpResponse],
                     user_profile: UserProfile, post_data: Dict[str, Any]) -> HttpResponse:
        request = POSTRequestMock(post_data, user_profile)
        return view_func(request, user_profile)

    def test_stream_watchers(self) -> None:
        '''
        We used to have a bug with stream_watchers, where we set their flags to
        None.
        '''
        cordelia = self.example_user('cordelia')
        hamlet = self.example_user('hamlet')
        realm = hamlet.realm
        stream_name = 'Denmark'

        self.unsubscribe(hamlet, stream_name)

        clear_client_event_queues_for_testing()

        queue_data = dict(
            all_public_streams=True,
            apply_markdown=True,
            client_gravatar=True,
            client_type_name='home grown api program',
            event_types=['message'],
            last_connection_time=time.time(),
            queue_timeout=0,
            realm_id=realm.id,
            user_profile_id=hamlet.id,
        )

        client = allocate_client_descriptor(queue_data)

        self.send_stream_message(cordelia.email, stream_name)

        self.assertEqual(len(client.event_queue.contents()), 1)

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
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)

        result = self.tornado_call(get_events_backend, user_profile,
                                   {"apply_markdown": ujson.dumps(True),
                                    "client_gravatar": ujson.dumps(True),
                                    "event_types": ujson.dumps(["message"]),
                                    "user_client": "website",
                                    "dont_block": ujson.dumps(True),
                                    })
        self.assert_json_success(result)
        queue_id = ujson.loads(result.content)["queue_id"]
        client_descriptor = get_client_descriptor(queue_id)

        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            # To test the missed_message hook, we first need to send a message
            msg_id = self.send_stream_message(self.example_email("iago"), "Denmark")

            # Verify that nothing happens if you call it as not the
            # "last client descriptor", in which case the function
            # short-circuits, since the `missedmessage_hook` handler
            # for garbage-collection is only for the user's last queue.
            missedmessage_hook(user_profile.id, client_descriptor, False)
            mock_enqueue.assert_not_called()

            # Now verify that we called the appropriate enqueue function
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_list = mock_enqueue.call_args_list[0][0]

            self.assertEqual(args_list, (user_profile.id, msg_id, False, False, False,
                                         "Denmark", False, True,
                                         {'email_notified': False, 'push_notified': False}))

        # Clear the event queue, before repeating with a private message
        client_descriptor.event_queue.pop()
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_personal_message(self.example_email("iago"), email)
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_list = mock_enqueue.call_args_list[0][0]

            self.assertEqual(args_list, (user_profile.id, msg_id, True, False,
                                         False, None, False, True,
                                         {'email_notified': True, 'push_notified': True}))

        # Clear the event queue, now repeat with a mention
        client_descriptor.event_queue.pop()
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_stream_message(self.example_email("iago"), "Denmark",
                                          content="@**King Hamlet** what's up?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            # Clear the event queue, before repeating with a private message
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_list = mock_enqueue.call_args_list[0][0]

            self.assertEqual(args_list, (user_profile.id, msg_id, False, True,
                                         False, "Denmark", False, True,
                                         {'email_notified': True, 'push_notified': True}))

        # Clear the event queue, now repeat with stream message with stream_push_notify
        stream = get_stream("Denmark", user_profile.realm)
        sub = Subscription.objects.get(user_profile=user_profile, recipient__type=Recipient.STREAM,
                                       recipient__type_id=stream.id)
        sub.push_notifications = True
        sub.save()
        client_descriptor.event_queue.pop()
        self.assertTrue(client_descriptor.event_queue.empty())
        msg_id = self.send_stream_message(self.example_email("iago"), "Denmark",
                                          content="what's up everyone?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            # Clear the event queue, before repeating with a private message
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_list = mock_enqueue.call_args_list[0][0]

            self.assertEqual(args_list, (user_profile.id, msg_id, False, False,
                                         True, "Denmark", False, True,
                                         {'email_notified': False, 'push_notified': False}))

        # Clear the event queue, now repeat with stream message with stream_push_notify
        # on a muted topic, which we should not push notify for
        client_descriptor.event_queue.pop()
        self.assertTrue(client_descriptor.event_queue.empty())
        do_mute_topic(user_profile, stream, sub.recipient, "mutingtest")
        msg_id = self.send_stream_message(self.example_email("iago"), "Denmark",
                                          content="what's up everyone?", topic_name="mutingtest")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            # Clear the event queue, before repeating with a private message
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_list = mock_enqueue.call_args_list[0][0]

            self.assertEqual(args_list, (user_profile.id, msg_id, False, False,
                                         False, "Denmark", False, True,
                                         {'email_notified': False, 'push_notified': False}))

        # Clear the event queue, now repeat with stream message with stream_push_notify
        # on a muted stream, which we should not push notify for
        client_descriptor.event_queue.pop()
        self.assertTrue(client_descriptor.event_queue.empty())
        sub.in_home_view = False
        sub.save()
        msg_id = self.send_stream_message(self.example_email("iago"), "Denmark",
                                          content="what's up everyone?")
        with mock.patch("zerver.tornado.event_queue.maybe_enqueue_notifications") as mock_enqueue:
            # Clear the event queue, before repeating with a private message
            missedmessage_hook(user_profile.id, client_descriptor, True)
            mock_enqueue.assert_called_once()
            args_list = mock_enqueue.call_args_list[0][0]

            self.assertEqual(args_list, (user_profile.id, msg_id, False, False,
                                         False, "Denmark", False, True,
                                         {'email_notified': False, 'push_notified': False}))

        # Clean up the state we just changed (not necessary unless we add more test code below)
        sub.push_notifications = True
        sub.in_home_view = True
        sub.save()
