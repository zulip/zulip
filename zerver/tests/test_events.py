# -*- coding: utf-8 -*-
# See http://zulip.readthedocs.io/en/latest/events-system.html for
# high-level documentation on how this system works.
from __future__ import absolute_import
from __future__ import print_function
from typing import Any, Callable, Dict, List, Optional, Union, Text, Tuple
import os
import shutil

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.test import TestCase
from django.utils.timezone import now as timezone_now

from zerver.models import (
    get_client, get_realm, get_recipient, get_stream, get_user,
    Message, RealmDomain, Recipient, UserMessage, UserPresence, UserProfile,
    Realm, Subscription, Stream,
)

from zerver.lib.actions import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    check_add_realm_emoji,
    check_send_typing_notification,
    do_add_alert_words,
    do_add_default_stream,
    do_add_reaction,
    do_add_realm_domain,
    do_add_realm_filter,
    do_change_avatar_fields,
    do_change_bot_owner,
    do_change_default_all_public_streams,
    do_change_default_events_register_stream,
    do_change_default_sending_stream,
    do_change_full_name,
    do_change_icon_source,
    do_change_is_admin,
    do_change_notification_settings,
    do_change_realm_domain,
    do_change_stream_description,
    do_change_subscription_property,
    do_create_user,
    do_deactivate_stream,
    do_deactivate_user,
    do_delete_message,
    do_mark_hotspot_as_read,
    do_mute_topic,
    do_reactivate_user,
    do_regenerate_api_key,
    do_remove_alert_words,
    do_remove_default_stream,
    do_remove_reaction,
    do_remove_realm_domain,
    do_remove_realm_emoji,
    do_remove_realm_filter,
    do_rename_stream,
    do_set_realm_authentication_methods,
    do_set_realm_message_editing,
    do_set_realm_property,
    do_set_user_display_setting,
    do_set_realm_notifications_stream,
    do_unmute_topic,
    do_update_embedded_data,
    do_update_message,
    do_update_message_flags,
    do_update_pointer,
    do_update_user_presence,
    log_event,
    notify_realm_custom_profile_fields,
)
from zerver.lib.events import (
    apply_events,
    fetch_initial_state_data,
)
from zerver.lib.message import render_markdown
from zerver.lib.test_helpers import POSTRequestMock, get_subscription, \
    stub_event_queue_user_events
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.topic_mutes import (
    add_topic_mute,
)
from zerver.lib.validator import (
    check_bool, check_dict, check_dict_only, check_float, check_int, check_list, check_string,
    equals, check_none_or, Validator
)

from zerver.views.events_register import _default_all_public_streams, _default_narrow

from zerver.tornado.event_queue import allocate_client_descriptor, EventQueue
from zerver.tornado.views import get_events_backend

from collections import OrderedDict
import mock
import time
import ujson
from six.moves import range


class LogEventsTest(ZulipTestCase):
    def test_with_missing_event_log_dir_setting(self):
        # type: () -> None
        with self.settings(EVENT_LOG_DIR=None):
            log_event(dict())

    def test_log_event_mkdir(self):
        # type: () -> None
        dir_name = 'var/test-log-dir'

        try:
            shutil.rmtree(dir_name)
        except OSError:  # nocoverage
            # assume it doesn't exist already
            pass

        self.assertFalse(os.path.exists(dir_name))
        with self.settings(EVENT_LOG_DIR=dir_name):
            event = {}  # type: Dict[str, int]
            log_event(event)
        self.assertTrue(os.path.exists(dir_name))


class EventsEndpointTest(ZulipTestCase):
    def test_events_register_endpoint(self):
        # type: () -> None

        # This test is intended to get minimal coverage on the
        # events_register code paths
        email = self.example_email("hamlet")
        with mock.patch('zerver.views.events_register.do_events_register', return_value={}):
            result = self.client_post('/json/register', **self.api_auth(email))
        self.assert_json_success(result)

        with mock.patch('zerver.lib.events.request_event_queue', return_value=None):
            result = self.client_post('/json/register', **self.api_auth(email))
        self.assert_json_error(result, "Could not allocate event queue")

        return_event_queue = '15:11'
        return_user_events = []  # type: (List[Any])

        # Test that call is made to deal with a returning soft deactivated user.
        with mock.patch('zerver.lib.events.maybe_catch_up_soft_deactivated_user') as fa:
            with stub_event_queue_user_events(return_event_queue, return_user_events):
                result = self.client_post('/json/register', dict(event_types=ujson.dumps(['pointer'])),
                                          **self.api_auth(email))
                self.assertEqual(fa.call_count, 1)

        with stub_event_queue_user_events(return_event_queue, return_user_events):
            result = self.client_post('/json/register', dict(event_types=ujson.dumps(['pointer'])),
                                      **self.api_auth(email))
        self.assert_json_success(result)
        result_dict = result.json()
        self.assertEqual(result_dict['last_event_id'], -1)
        self.assertEqual(result_dict['queue_id'], '15:11')

        return_event_queue = '15:12'
        return_user_events = [
            {
                'id': 6,
                'type': 'pointer',
                'pointer': 15,
            }
        ]
        with stub_event_queue_user_events(return_event_queue, return_user_events):
            result = self.client_post('/json/register', dict(event_types=ujson.dumps(['pointer'])),
                                      **self.api_auth(email))

        self.assert_json_success(result)
        result_dict = result.json()
        self.assertEqual(result_dict['last_event_id'], 6)
        self.assertEqual(result_dict['pointer'], 15)
        self.assertEqual(result_dict['queue_id'], '15:12')

        # Now test with `fetch_event_types` not matching the event
        return_event_queue = '15:13'
        with stub_event_queue_user_events(return_event_queue, return_user_events):
            result = self.client_post('/json/register',
                                      dict(event_types=ujson.dumps(['pointer']),
                                           fetch_event_types=ujson.dumps(['message'])),
                                      **self.api_auth(email))
        self.assert_json_success(result)
        result_dict = result.json()
        self.assertEqual(result_dict['last_event_id'], 6)
        # Check that the message event types data is in there
        self.assertIn('max_message_id', result_dict)
        # Check that the pointer event types data is not in there
        self.assertNotIn('pointer', result_dict)
        self.assertEqual(result_dict['queue_id'], '15:13')

        # Now test with `fetch_event_types` matching the event
        with stub_event_queue_user_events(return_event_queue, return_user_events):
            result = self.client_post('/json/register',
                                      dict(fetch_event_types=ujson.dumps(['pointer']),
                                           event_types=ujson.dumps(['message'])),
                                      **self.api_auth(email))
        self.assert_json_success(result)
        result_dict = result.json()
        self.assertEqual(result_dict['last_event_id'], 6)
        # Check that we didn't fetch the messages data
        self.assertNotIn('max_message_id', result_dict)
        # Check that the pointer data is in there, and is correctly
        # updated (presering our atomicity guaranteed), though of
        # course any future pointer events won't be distributed
        self.assertIn('pointer', result_dict)
        self.assertEqual(result_dict['pointer'], 15)
        self.assertEqual(result_dict['queue_id'], '15:13')

    def test_tornado_endpoint(self):
        # type: () -> None

        # This test is mostly intended to get minimal coverage on
        # the /notify_tornado endpoint, so we can have 100% URL coverage,
        # but it does exercise a little bit of the codepath.
        post_data = dict(
            data=ujson.dumps(
                dict(
                    event=dict(
                        type='other'
                    ),
                    users=[self.example_user('hamlet').id],
                ),
            ),
        )
        req = POSTRequestMock(post_data, user_profile=None)
        req.META['REMOTE_ADDR'] = '127.0.0.1'
        result = self.client_post_request('/notify_tornado', req)
        self.assert_json_error(result, 'Access denied', status_code=403)

        post_data['secret'] = settings.SHARED_SECRET
        req = POSTRequestMock(post_data, user_profile=None)
        req.META['REMOTE_ADDR'] = '127.0.0.1'
        result = self.client_post_request('/notify_tornado', req)
        self.assert_json_success(result)

class GetEventsTest(ZulipTestCase):
    def tornado_call(self, view_func, user_profile, post_data):
        # type: (Callable[[HttpRequest, UserProfile], HttpResponse], UserProfile, Dict[str, Any]) -> HttpResponse
        request = POSTRequestMock(post_data, user_profile)
        return view_func(request, user_profile)

    def test_get_events(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        recipient_user_profile = self.example_user('othello')
        recipient_email = recipient_user_profile.email
        self.login(email)

        result = self.tornado_call(get_events_backend, user_profile,
                                   {"apply_markdown": ujson.dumps(True),
                                    "event_types": ujson.dumps(["message"]),
                                    "user_client": "website",
                                    "dont_block": ujson.dumps(True),
                                    })
        self.assert_json_success(result)
        queue_id = ujson.loads(result.content)["queue_id"]

        recipient_result = self.tornado_call(get_events_backend, recipient_user_profile,
                                             {"apply_markdown": ujson.dumps(True),
                                              "event_types": ujson.dumps(["message"]),
                                              "user_client": "website",
                                              "dont_block": ujson.dumps(True),
                                              })
        self.assert_json_success(recipient_result)
        recipient_queue_id = ujson.loads(recipient_result.content)["queue_id"]

        result = self.tornado_call(get_events_backend, user_profile,
                                   {"queue_id": queue_id,
                                    "user_client": "website",
                                    "last_event_id": -1,
                                    "dont_block": ujson.dumps(True),
                                    })
        events = ujson.loads(result.content)["events"]
        self.assert_json_success(result)
        self.assert_length(events, 0)

        local_id = 10.01
        self.send_message(email, recipient_email, Recipient.PERSONAL, "hello", local_id=local_id, sender_queue_id=queue_id)

        result = self.tornado_call(get_events_backend, user_profile,
                                   {"queue_id": queue_id,
                                    "user_client": "website",
                                    "last_event_id": -1,
                                    "dont_block": ujson.dumps(True),
                                    })
        events = ujson.loads(result.content)["events"]
        self.assert_json_success(result)
        self.assert_length(events, 1)
        self.assertEqual(events[0]["type"], "message")
        self.assertEqual(events[0]["message"]["sender_email"], email)
        self.assertEqual(events[0]["local_message_id"], local_id)
        self.assertEqual(events[0]["message"]["display_recipient"][0]["is_mirror_dummy"], False)
        self.assertEqual(events[0]["message"]["display_recipient"][1]["is_mirror_dummy"], False)

        last_event_id = events[0]["id"]
        local_id += 0.01

        self.send_message(email, recipient_email, Recipient.PERSONAL, "hello", local_id=local_id, sender_queue_id=queue_id)

        result = self.tornado_call(get_events_backend, user_profile,
                                   {"queue_id": queue_id,
                                    "user_client": "website",
                                    "last_event_id": last_event_id,
                                    "dont_block": ujson.dumps(True),
                                    })
        events = ujson.loads(result.content)["events"]
        self.assert_json_success(result)
        self.assert_length(events, 1)
        self.assertEqual(events[0]["type"], "message")
        self.assertEqual(events[0]["message"]["sender_email"], email)
        self.assertEqual(events[0]["local_message_id"], local_id)

        # Test that the received message in the receiver's event queue
        # exists and does not contain a local id
        recipient_result = self.tornado_call(get_events_backend, recipient_user_profile,
                                             {"queue_id": recipient_queue_id,
                                              "user_client": "website",
                                              "last_event_id": -1,
                                              "dont_block": ujson.dumps(True),
                                              })
        recipient_events = ujson.loads(recipient_result.content)["events"]
        self.assert_json_success(recipient_result)
        self.assertEqual(len(recipient_events), 2)
        self.assertEqual(recipient_events[0]["type"], "message")
        self.assertEqual(recipient_events[0]["message"]["sender_email"], email)
        self.assertTrue("local_message_id" not in recipient_events[0])
        self.assertEqual(recipient_events[1]["type"], "message")
        self.assertEqual(recipient_events[1]["message"]["sender_email"], email)
        self.assertTrue("local_message_id" not in recipient_events[1])

    def test_get_events_narrow(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        self.login(email)

        result = self.tornado_call(get_events_backend, user_profile,
                                   {"apply_markdown": ujson.dumps(True),
                                    "event_types": ujson.dumps(["message"]),
                                    "narrow": ujson.dumps([["stream", "denmark"]]),
                                    "user_client": "website",
                                    "dont_block": ujson.dumps(True),
                                    })
        self.assert_json_success(result)
        queue_id = ujson.loads(result.content)["queue_id"]

        result = self.tornado_call(get_events_backend, user_profile,
                                   {"queue_id": queue_id,
                                    "user_client": "website",
                                    "last_event_id": -1,
                                    "dont_block": ujson.dumps(True),
                                    })
        events = ujson.loads(result.content)["events"]
        self.assert_json_success(result)
        self.assert_length(events, 0)

        self.send_message(email, self.example_email("othello"), Recipient.PERSONAL, "hello")
        self.send_message(email, "Denmark", Recipient.STREAM, "hello")

        result = self.tornado_call(get_events_backend, user_profile,
                                   {"queue_id": queue_id,
                                    "user_client": "website",
                                    "last_event_id": -1,
                                    "dont_block": ujson.dumps(True),
                                    })
        events = ujson.loads(result.content)["events"]
        self.assert_json_success(result)
        self.assert_length(events, 1)
        self.assertEqual(events[0]["type"], "message")
        self.assertEqual(events[0]["message"]["display_recipient"], "Denmark")

class EventsRegisterTest(ZulipTestCase):

    def setUp(self):
        # type: () -> None
        super(EventsRegisterTest, self).setUp()
        self.user_profile = self.example_user('hamlet')
        self.user_profile.tutorial_status = UserProfile.TUTORIAL_WAITING
        self.user_profile.save(update_fields=['tutorial_status'])

    def create_bot(self, email):
        # type: (str) -> UserProfile
        return do_create_user(email, '123',
                              get_realm('zulip'), 'Test Bot', 'test',
                              bot_type=UserProfile.DEFAULT_BOT, bot_owner=self.user_profile)

    def realm_bot_schema(self, field_name, check):
        # type: (str, Validator) -> Validator
        return self.check_events_dict([
            ('type', equals('realm_bot')),
            ('op', equals('update')),
            ('bot', check_dict_only([
                ('email', check_string),
                ('user_id', check_int),
                (field_name, check),
            ])),
        ])

    def do_test(self, action, event_types=None, include_subscribers=True, state_change_expected=True,
                num_events=1):
        # type: (Callable[[], Any], Optional[List[str]], bool, bool, int) -> List[Dict[str, Any]]
        client = allocate_client_descriptor(
            dict(user_profile_id = self.user_profile.id,
                 user_profile_email = self.user_profile.email,
                 realm_id = self.user_profile.realm_id,
                 event_types = event_types,
                 client_type_name = "website",
                 apply_markdown = True,
                 all_public_streams = False,
                 queue_timeout = 600,
                 last_connection_time = time.time(),
                 narrow = [])
        )
        # hybrid_state = initial fetch state + re-applying events triggered by our action
        # normal_state = do action then fetch at the end (the "normal" code path)
        hybrid_state = fetch_initial_state_data(self.user_profile, event_types, "", include_subscribers=include_subscribers)
        action()
        events = client.event_queue.contents()
        self.assertTrue(len(events) == num_events)

        before = ujson.dumps(hybrid_state)
        apply_events(hybrid_state, events, self.user_profile, include_subscribers=include_subscribers)
        after = ujson.dumps(hybrid_state)

        if state_change_expected:
            if before == after:
                print(events)  # nocoverage
                raise AssertionError('Test does not exercise enough code -- events do not change state.')
        else:
            if before != after:
                raise AssertionError('Test is invalid--state actually does change here.')

        normal_state = fetch_initial_state_data(self.user_profile, event_types, "", include_subscribers=include_subscribers)
        self.match_states(hybrid_state, normal_state)
        return events

    def assert_on_error(self, error):
        # type: (Optional[str]) -> None
        if error:
            raise AssertionError(error)

    def match_states(self, state1, state2):
        # type: (Dict[str, Any], Dict[str, Any]) -> None
        def normalize(state):
            # type: (Dict[str, Any]) -> None
            state['realm_users'] = {u['email']: u for u in state['realm_users']}
            for u in state['never_subscribed']:
                if 'subscribers' in u:
                    u['subscribers'].sort()
            for u in state['subscriptions']:
                if 'subscribers' in u:
                    u['subscribers'].sort()
            state['subscriptions'] = {u['name']: u for u in state['subscriptions']}
            state['unsubscribed'] = {u['name']: u for u in state['unsubscribed']}
            if 'realm_bots' in state:
                state['realm_bots'] = {u['email']: u for u in state['realm_bots']}
        normalize(state1)
        normalize(state2)
        self.assertEqual(state1, state2)

    def check_events_dict(self, required_keys):
        # type: (List[Tuple[str, Validator]]) -> Validator
        required_keys.append(('id', check_int))
        return check_dict_only(required_keys)

    def test_mentioned_send_message_events(self):
        # type: () -> None
        user = self.example_user('hamlet')

        for i in range(3):
            content = 'mentioning... @**' + user.full_name + '** hello ' + str(i)
            self.do_test(
                lambda: self.send_message(self.example_email('cordelia'),
                                          "Verona",
                                          Recipient.STREAM,
                                          content)

            )

    def test_pm_send_message_events(self):
        # type: () -> None
        self.do_test(
            lambda: self.send_message(self.example_email('cordelia'),
                                      self.example_email('hamlet'),
                                      Recipient.PERSONAL,
                                      'hola')

        )

    def test_huddle_send_message_events(self):
        # type: () -> None
        huddle = [
            self.example_email('hamlet'),
            self.example_email('othello'),
        ]
        self.do_test(
            lambda: self.send_message(self.example_email('cordelia'),
                                      huddle,
                                      Recipient.HUDDLE,
                                      'hola')

        )

    def test_stream_send_message_events(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('message')),
            ('flags', check_list(None)),
            ('message', self.check_events_dict([
                ('avatar_url', check_string),
                ('client', check_string),
                ('content', check_string),
                ('content_type', equals('text/html')),
                ('display_recipient', check_string),
                ('is_mentioned', check_bool),
                ('is_me_message', check_bool),
                ('reactions', check_list(None)),
                ('recipient_id', check_int),
                ('sender_realm_str', check_string),
                ('sender_email', check_string),
                ('sender_full_name', check_string),
                ('sender_id', check_int),
                ('sender_short_name', check_string),
                ('stream_id', check_int),
                ('subject', check_string),
                ('subject_links', check_list(None)),
                ('timestamp', check_int),
                ('type', check_string),
            ])),
        ])

        events = self.do_test(
            lambda: self.send_message(self.example_email("hamlet"), "Verona", Recipient.STREAM, "hello"),
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Verify message editing
        schema_checker = self.check_events_dict([
            ('type', equals('update_message')),
            ('flags', check_list(None)),
            ('content', check_string),
            ('edit_timestamp', check_int),
            ('flags', check_list(None)),
            ('message_id', check_int),
            ('message_ids', check_list(check_int)),
            ('orig_content', check_string),
            ('orig_rendered_content', check_string),
            ('orig_subject', check_string),
            ('prev_rendered_content_version', check_int),
            ('propagate_mode', check_string),
            ('rendered_content', check_string),
            ('sender', check_string),
            ('stream_id', check_int),
            ('subject', check_string),
            ('subject_links', check_list(None)),
            ('user_id', check_int),
        ])

        message = Message.objects.order_by('-id')[0]
        topic = 'new_topic'
        propagate_mode = 'change_all'
        content = 'new content'
        rendered_content = render_markdown(message, content)
        events = self.do_test(
            lambda: do_update_message(self.user_profile, message, topic,
                                      propagate_mode, content, rendered_content),
            state_change_expected=True,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Verify do_update_embedded_data
        schema_checker = self.check_events_dict([
            ('type', equals('update_message')),
            ('flags', check_list(None)),
            ('content', check_string),
            ('flags', check_list(None)),
            ('message_id', check_int),
            ('message_ids', check_list(check_int)),
            ('rendered_content', check_string),
            ('sender', check_string),
        ])

        events = self.do_test(
            lambda: do_update_embedded_data(self.user_profile, message,
                                            u"embed_content", "<p>embed_content</p>"),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_update_message_flags(self):
        # type: () -> None
        # Test message flag update events
        schema_checker = self.check_events_dict([
            ('all', check_bool),
            ('type', equals('update_message_flags')),
            ('flag', check_string),
            ('messages', check_list(check_int)),
            ('operation', equals("add")),
        ])

        message = self.send_message(self.example_email("cordelia"), self.example_email("hamlet"), Recipient.PERSONAL, "hello")
        user_profile = self.example_user('hamlet')
        events = self.do_test(
            lambda: do_update_message_flags(user_profile, 'add', 'starred', [message]),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)
        schema_checker = self.check_events_dict([
            ('all', check_bool),
            ('type', equals('update_message_flags')),
            ('flag', check_string),
            ('messages', check_list(check_int)),
            ('operation', equals("remove")),
        ])
        events = self.do_test(
            lambda: do_update_message_flags(user_profile, 'remove', 'starred', [message]),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_update_read_flag_removes_unread_msg_ids(self):
        # type: () -> None

        user_profile = self.example_user('hamlet')
        mention = '@**' + user_profile.full_name + '**'

        for content in ['hello', mention]:
            message = self.send_message(
                self.example_email('cordelia'),
                "Verona",
                Recipient.STREAM,
                content
            )

            self.do_test(
                lambda: do_update_message_flags(user_profile, 'add', 'read', [message]),
                state_change_expected=True,
            )

    def test_send_message_to_existing_recipient(self):
        # type: () -> None
        self.send_message(
            self.example_email('cordelia'),
            "Verona",
            Recipient.STREAM,
            "hello 1"
        )
        self.do_test(
            lambda: self.send_message("cordelia@zulip.com", "Verona", Recipient.STREAM, "hello 2"),
            state_change_expected=True,
        )

    def test_send_reaction(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('reaction')),
            ('op', equals('add')),
            ('message_id', check_int),
            ('emoji_name', check_string),
            ('emoji_code', check_string),
            ('reaction_type', check_string),
            ('user', check_dict_only([
                ('email', check_string),
                ('full_name', check_string),
                ('user_id', check_int)
            ])),
        ])

        message_id = self.send_message(self.example_email("hamlet"), "Verona", Recipient.STREAM, "hello")
        message = Message.objects.get(id=message_id)
        events = self.do_test(
            lambda: do_add_reaction(
                self.user_profile, message, "tada"),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_remove_reaction(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('reaction')),
            ('op', equals('remove')),
            ('message_id', check_int),
            ('emoji_name', check_string),
            ('emoji_code', check_string),
            ('reaction_type', check_string),
            ('user', check_dict_only([
                ('email', check_string),
                ('full_name', check_string),
                ('user_id', check_int)
            ])),
        ])

        message_id = self.send_message(self.example_email("hamlet"), "Verona", Recipient.STREAM, "hello")
        message = Message.objects.get(id=message_id)
        do_add_reaction(self.user_profile, message, "tada")
        events = self.do_test(
            lambda: do_remove_reaction(
                self.user_profile, message, "tada"),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_typing_events(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('typing')),
            ('op', equals('start')),
            ('sender', check_dict_only([
                ('email', check_string),
                ('user_id', check_int)])),
            ('recipients', check_list(check_dict_only([
                ('email', check_string),
                ('user_id', check_int),
            ]))),
        ])

        events = self.do_test(
            lambda: check_send_typing_notification(
                self.user_profile, [self.example_email("cordelia")], "start"),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_custom_profile_fields_events(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('custom_profile_fields')),
            ('fields', check_list(check_dict_only([
                ('type', check_int),
                ('name', check_string),
            ]))),
        ])

        events = self.do_test(
            lambda: notify_realm_custom_profile_fields(
                self.user_profile.realm),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_presence_events(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('presence')),
            ('email', check_string),
            ('server_timestamp', check_float),
            ('presence', check_dict_only([
                ('website', check_dict_only([
                    ('status', equals('active')),
                    ('timestamp', check_int),
                    ('client', check_string),
                    ('pushable', check_bool),
                ])),
            ])),
        ])
        events = self.do_test(lambda: do_update_user_presence(
            self.user_profile, get_client("website"), timezone_now(), UserPresence.ACTIVE))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_presence_events_multiple_clients(self):
        # type: () -> None
        schema_checker_android = self.check_events_dict([
            ('type', equals('presence')),
            ('email', check_string),
            ('server_timestamp', check_float),
            ('presence', check_dict_only([
                ('ZulipAndroid/1.0', check_dict_only([
                    ('status', equals('idle')),
                    ('timestamp', check_int),
                    ('client', check_string),
                    ('pushable', check_bool),
                ])),
            ])),
        ])
        self.client_post("/api/v1/users/me/presence", {'status': 'idle'},
                         HTTP_USER_AGENT="ZulipAndroid/1.0",
                         **self.api_auth(self.user_profile.email))
        self.do_test(lambda: do_update_user_presence(
            self.user_profile, get_client("website"), timezone_now(), UserPresence.ACTIVE))
        events = self.do_test(lambda: do_update_user_presence(
            self.user_profile, get_client("ZulipAndroid/1.0"), timezone_now(), UserPresence.IDLE))
        error = schema_checker_android('events[0]', events[0])
        self.assert_on_error(error)

    def test_pointer_events(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('pointer')),
            ('pointer', check_int)
        ])
        events = self.do_test(lambda: do_update_pointer(self.user_profile, 1500))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_register_events(self):
        # type: () -> None
        realm_user_add_checker = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('add')),
            ('person', check_dict_only([
                ('user_id', check_int),
                ('email', check_string),
                ('avatar_url', check_string),
                ('full_name', check_string),
                ('is_admin', check_bool),
                ('is_bot', check_bool),
                ('timezone', check_string),
            ])),
        ])

        events = self.do_test(lambda: self.register("test1@zulip.com", "test1"))
        self.assert_length(events, 1)
        error = realm_user_add_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_alert_words_events(self):
        # type: () -> None
        alert_words_checker = self.check_events_dict([
            ('type', equals('alert_words')),
            ('alert_words', check_list(check_string)),
        ])

        events = self.do_test(lambda: do_add_alert_words(self.user_profile, ["alert_word"]))
        error = alert_words_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_remove_alert_words(self.user_profile, ["alert_word"]))
        error = alert_words_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_default_streams_events(self):
        # type: () -> None
        default_streams_checker = self.check_events_dict([
            ('type', equals('default_streams')),
            ('default_streams', check_list(check_dict_only([
                ('description', check_string),
                ('invite_only', check_bool),
                ('name', check_string),
                ('stream_id', check_int),
            ]))),
        ])

        stream = get_stream("Scotland", self.user_profile.realm)
        events = self.do_test(lambda: do_add_default_stream(stream))
        error = default_streams_checker('events[0]', events[0])
        events = self.do_test(lambda: do_remove_default_stream(stream))
        error = default_streams_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_muted_topics_events(self):
        # type: () -> None
        muted_topics_checker = self.check_events_dict([
            ('type', equals('muted_topics')),
            ('muted_topics', check_list(check_list(check_string, 2))),
        ])
        stream = get_stream('Denmark', self.user_profile.realm)
        recipient = get_recipient(Recipient.STREAM, stream.id)
        events = self.do_test(lambda: do_mute_topic(
            self.user_profile, stream, recipient, "topic"))
        error = muted_topics_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_unmute_topic(
            self.user_profile, stream, "topic"))
        error = muted_topics_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_avatar_fields(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict_only([
                ('email', check_string),
                ('user_id', check_int),
                ('avatar_url', check_string),
            ])),
        ])
        events = self.do_test(
            lambda: do_change_avatar_fields(self.user_profile, UserProfile.AVATAR_FROM_USER),
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_full_name(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict_only([
                ('email', check_string),
                ('full_name', check_string),
                ('user_id', check_int),
            ])),
        ])
        events = self.do_test(lambda: do_change_full_name(self.user_profile, 'Sir Hamlet', self.user_profile))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def do_set_realm_property_test(self, name):
        # type: (str) -> None
        bool_tests = [True, False, True]  # type: List[bool]
        test_values = dict(
            default_language=[u'es', u'de', u'en'],
            description=[u'Realm description', u'New description'],
            message_retention_days=[10, 20],
            name=[u'Zulip', u'New Name'],
            waiting_period_threshold=[10, 20],
        )  # type: Dict[str, Any]

        vals = test_values.get(name)
        property_type = Realm.property_types[name]
        if property_type is bool:
            validator = check_bool
            vals = bool_tests
        elif property_type is Text:
            validator = check_string
        elif property_type is int:
            validator = check_int
        elif property_type == (int, type(None)):
            validator = check_int
        else:
            raise AssertionError("Unexpected property type %s" % (property_type,))
        schema_checker = self.check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update')),
            ('property', equals(name)),
            ('value', validator),
        ])

        if vals is None:
            raise AssertionError('No test created for %s' % (name))
        do_set_realm_property(self.user_profile.realm, name, vals[0])
        for val in vals[1:]:
            events = self.do_test(
                lambda: do_set_realm_property(self.user_profile.realm, name, val))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_realm_property(self):
        # type: () -> None

        for prop in Realm.property_types:
            self.do_set_realm_property_test(prop)

    def test_change_realm_authentication_methods(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update_dict')),
            ('property', equals('default')),
            ('data', check_dict_only([
                ('authentication_methods', check_dict([]))
            ])),
        ])

        def fake_backends():
            # type: () -> Any
            backends = (
                'zproject.backends.DevAuthBackend',
                'zproject.backends.EmailAuthBackend',
                'zproject.backends.GitHubAuthBackend',
                'zproject.backends.GoogleMobileOauth2Backend',
                'zproject.backends.ZulipLDAPAuthBackend',
            )
            return self.settings(AUTHENTICATION_BACKENDS=backends)

        # Test transitions; any new backends should be tested with T/T/T/F/T
        for (auth_method_dict) in \
                ({'Google': True, 'Email': True, 'GitHub': True, 'LDAP': False, 'Dev': False},
                 {'Google': True, 'Email': True, 'GitHub': False, 'LDAP': False, 'Dev': False},
                 {'Google': True, 'Email': False, 'GitHub': False, 'LDAP': False, 'Dev': False},
                 {'Google': True, 'Email': False, 'GitHub': True, 'LDAP': False, 'Dev': False},
                 {'Google': False, 'Email': False, 'GitHub': False, 'LDAP': False, 'Dev': True},
                 {'Google': False, 'Email': False, 'GitHub': True, 'LDAP': False, 'Dev': True},
                 {'Google': False, 'Email': True, 'GitHub': True, 'LDAP': True, 'Dev': False}):
            with fake_backends():
                events = self.do_test(
                    lambda: do_set_realm_authentication_methods(
                        self.user_profile.realm,
                        auth_method_dict))

            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_pin_stream(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('subscription')),
            ('op', equals('update')),
            ('property', equals('pin_to_top')),
            ('stream_id', check_int),
            ('value', check_bool),
            ('name', check_string),
            ('email', check_string),
        ])
        stream = get_stream("Denmark", self.user_profile.realm)
        sub = get_subscription(stream.name, self.user_profile)
        do_change_subscription_property(self.user_profile, sub, stream, "pin_to_top", False)
        for pinned in (True, False):
            events = self.do_test(lambda: do_change_subscription_property(self.user_profile, sub, stream, "pin_to_top", pinned))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_realm_message_edit_settings(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update_dict')),
            ('property', equals('default')),
            ('data', check_dict_only([
                ('allow_message_editing', check_bool),
                ('message_content_edit_limit_seconds', check_int),
            ])),
        ])
        # Test every transition among the four possibilities {T,F} x {0, non-0}
        for (allow_message_editing, message_content_edit_limit_seconds) in \
            ((True, 0), (False, 0), (True, 0), (False, 1234), (True, 0), (True, 1234), (True, 0),
             (False, 0), (False, 1234), (False, 0), (True, 1234), (False, 0),
             (True, 1234), (True, 600), (False, 600), (False, 1234), (True, 600)):
            events = self.do_test(
                lambda: do_set_realm_message_editing(self.user_profile.realm,
                                                     allow_message_editing,
                                                     message_content_edit_limit_seconds))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_realm_notifications_stream(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update')),
            ('property', equals('notifications_stream_id')),
            ('value', check_int),
        ])

        stream = get_stream("Rome", self.user_profile.realm)

        for notifications_stream, notifications_stream_id in ((stream, stream.id), (None, -1)):
            events = self.do_test(
                lambda: do_set_realm_notifications_stream(self.user_profile.realm,
                                                          notifications_stream,
                                                          notifications_stream_id))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_is_admin(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict_only([
                ('email', check_string),
                ('is_admin', check_bool),
                ('user_id', check_int),
            ])),
        ])
        do_change_is_admin(self.user_profile, False)
        for is_admin in [True, False]:
            events = self.do_test(lambda: do_change_is_admin(self.user_profile, is_admin))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def do_set_user_display_settings_test(self, setting_name):
        # type: (str) -> None
        """Test updating each setting in UserProfile.property_types dict."""

        bool_change = [True, False, True]  # type: List[bool]
        test_changes = dict(
            emojiset = [u'apple', u'twitter'],
            default_language = [u'es', u'de', u'en'],
            timezone = [u'US/Mountain', u'US/Samoa', u'Pacific/Galapogos', u'']
        )  # type: Dict[str, Any]

        property_type = UserProfile.property_types[setting_name]
        if property_type is bool:
            validator = check_bool
        elif property_type is Text:
            validator = check_string
        else:
            raise AssertionError("Unexpected property type %s" % (property_type,))

        num_events = 1
        if setting_name == "timezone":
            num_events = 2
        values = test_changes.get(setting_name)
        if property_type is bool:
            values = bool_change
        if values is None:
            raise AssertionError('No test created for %s' % (setting_name))

        for value in values:
            events = self.do_test(lambda: do_set_user_display_setting(
                self.user_profile, setting_name, value), num_events=num_events)

            schema_checker = self.check_events_dict([
                ('type', equals('update_display_settings')),
                ('setting_name', equals(setting_name)),
                ('user', check_string),
                ('setting', validator),
            ])
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

            timezone_schema_checker = self.check_events_dict([
                ('type', equals('realm_user')),
                ('op', equals('update')),
                ('person', check_dict_only([
                    ('email', check_string),
                    ('user_id', check_int),
                    ('timezone', check_string),
                ])),
            ])
            if setting_name == "timezone":
                error = timezone_schema_checker('events[1]', events[1])

    def test_set_user_display_settings(self):
        # type: () -> None
        for prop in UserProfile.property_types:
            self.do_set_user_display_settings_test(prop)

    def test_change_notification_settings(self):
        # type: () -> None
        for notification_setting, v in self.user_profile.notification_setting_types.items():
            schema_checker = self.check_events_dict([
                ('type', equals('update_global_notifications')),
                ('notification_name', equals(notification_setting)),
                ('user', check_string),
                ('setting', check_bool),
            ])
            do_change_notification_settings(self.user_profile, notification_setting, False)
            for setting_value in [True, False]:
                events = self.do_test(lambda: do_change_notification_settings(
                    self.user_profile, notification_setting, setting_value, log=False))
                error = schema_checker('events[0]', events[0])
                self.assert_on_error(error)

    def test_realm_emoji_events(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('realm_emoji')),
            ('op', equals('update')),
            ('realm_emoji', check_dict([])),
        ])
        events = self.do_test(lambda: check_add_realm_emoji(get_realm("zulip"), "my_emoji",
                                                            "https://realm.com/my_emoji"))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_remove_realm_emoji(get_realm("zulip"), "my_emoji"))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_realm_filter_events(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('realm_filters')),
            ('realm_filters', check_list(None)),  # TODO: validate tuples in the list
        ])
        events = self.do_test(lambda: do_add_realm_filter(get_realm("zulip"), "#(?P<id>[123])",
                                                          "https://realm.com/my_realm_filter/%(id)s"))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        self.do_test(lambda: do_remove_realm_filter(get_realm("zulip"), "#(?P<id>[123])"))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_realm_domain_events(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('realm_domains')),
            ('op', equals('add')),
            ('realm_domain', check_dict_only([
                ('domain', check_string),
                ('allow_subdomains', check_bool),
            ])),
        ])
        realm = get_realm('zulip')
        events = self.do_test(lambda: do_add_realm_domain(realm, 'zulip.org', False))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        schema_checker = self.check_events_dict([
            ('type', equals('realm_domains')),
            ('op', equals('change')),
            ('realm_domain', check_dict_only([
                ('domain', equals('zulip.org')),
                ('allow_subdomains', equals(True)),
            ])),
        ])
        test_domain = RealmDomain.objects.get(realm=realm, domain='zulip.org')
        events = self.do_test(lambda: do_change_realm_domain(test_domain, True))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        schema_checker = self.check_events_dict([
            ('type', equals('realm_domains')),
            ('op', equals('remove')),
            ('domain', equals('zulip.org')),
        ])
        events = self.do_test(lambda: do_remove_realm_domain(test_domain))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_create_bot(self):
        # type: () -> None
        bot_created_checker = self.check_events_dict([
            ('type', equals('realm_bot')),
            ('op', equals('add')),
            ('bot', check_dict_only([
                ('email', check_string),
                ('user_id', check_int),
                ('bot_type', check_int),
                ('full_name', check_string),
                ('is_active', check_bool),
                ('api_key', check_string),
                ('default_sending_stream', check_none_or(check_string)),
                ('default_events_register_stream', check_none_or(check_string)),
                ('default_all_public_streams', check_bool),
                ('avatar_url', check_string),
                ('owner', check_string),
            ])),
        ])
        action = lambda: self.create_bot('test-bot@zulip.com')
        events = self.do_test(action, num_events=2)
        error = bot_created_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_change_bot_full_name(self):
        # type: () -> None
        bot = self.create_bot('test-bot@zulip.com')
        action = lambda: do_change_full_name(bot, 'New Bot Name', self.user_profile)
        events = self.do_test(action, num_events=2)
        error = self.realm_bot_schema('full_name', check_string)('events[1]', events[1])
        self.assert_on_error(error)

    def test_regenerate_bot_api_key(self):
        # type: () -> None
        bot = self.create_bot('test-bot@zulip.com')
        action = lambda: do_regenerate_api_key(bot, self.user_profile)
        events = self.do_test(action)
        error = self.realm_bot_schema('api_key', check_string)('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_avatar_source(self):
        # type: () -> None
        bot = self.create_bot('test-bot@zulip.com')
        action = lambda: do_change_avatar_fields(bot, bot.AVATAR_FROM_USER)
        events = self.do_test(action, num_events=2)
        error = self.realm_bot_schema('avatar_url', check_string)('events[0]', events[0])
        self.assertEqual(events[1]['type'], 'realm_user')
        self.assert_on_error(error)

    def test_change_realm_icon_source(self):
        # type: () -> None
        realm = get_realm('zulip')
        action = lambda: do_change_icon_source(realm, realm.ICON_FROM_GRAVATAR)
        events = self.do_test(action, state_change_expected=False)
        schema_checker = self.check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update_dict')),
            ('property', equals('icon')),
            ('data', check_dict_only([
                ('icon_url', check_string),
                ('icon_source', check_string),
            ])),
        ])
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_default_all_public_streams(self):
        # type: () -> None
        bot = self.create_bot('test-bot@zulip.com')
        action = lambda: do_change_default_all_public_streams(bot, True)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_all_public_streams', check_bool)('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_default_sending_stream(self):
        # type: () -> None
        bot = self.create_bot('test-bot@zulip.com')
        stream = get_stream("Rome", bot.realm)

        action = lambda: do_change_default_sending_stream(bot, stream)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_sending_stream', check_string)('events[0]', events[0])
        self.assert_on_error(error)

        action = lambda: do_change_default_sending_stream(bot, None)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_sending_stream', equals(None))('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_default_events_register_stream(self):
        # type: () -> None
        bot = self.create_bot('test-bot@zulip.com')
        stream = get_stream("Rome", bot.realm)

        action = lambda: do_change_default_events_register_stream(bot, stream)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_events_register_stream', check_string)('events[0]', events[0])
        self.assert_on_error(error)

        action = lambda: do_change_default_events_register_stream(bot, None)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_events_register_stream', equals(None))('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_owner(self):
        # type: () -> None
        change_bot_owner_checker = self.check_events_dict([
            ('type', equals('realm_bot')),
            ('op', equals('update')),
            ('bot', check_dict_only([
                ('email', check_string),
                ('user_id', check_int),
                ('owner_id', check_int),
            ])),
        ])
        self.user_profile = self.example_user('iago')
        owner = self.example_user('hamlet')
        bot = self.create_bot('test-bot@zulip.com')
        action = lambda: do_change_bot_owner(bot, owner, self.user_profile)
        events = self.do_test(action)
        error = change_bot_owner_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_do_deactivate_user(self):
        # type: () -> None
        bot_deactivate_checker = self.check_events_dict([
            ('type', equals('realm_bot')),
            ('op', equals('remove')),
            ('bot', check_dict_only([
                ('email', check_string),
                ('full_name', check_string),
                ('user_id', check_int),
            ])),
        ])
        bot = self.create_bot('foo-bot@zulip.com')
        action = lambda: do_deactivate_user(bot)
        events = self.do_test(action, num_events=2)
        error = bot_deactivate_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_do_reactivate_user(self):
        # type: () -> None
        bot_reactivate_checker = self.check_events_dict([
            ('type', equals('realm_bot')),
            ('op', equals('add')),
            ('bot', check_dict_only([
                ('email', check_string),
                ('user_id', check_int),
                ('bot_type', check_int),
                ('full_name', check_string),
                ('is_active', check_bool),
                ('api_key', check_string),
                ('default_sending_stream', check_none_or(check_string)),
                ('default_events_register_stream', check_none_or(check_string)),
                ('default_all_public_streams', check_bool),
                ('avatar_url', check_string),
                ('owner', check_none_or(check_string)),
            ])),
        ])
        bot = self.create_bot('foo-bot@zulip.com')
        do_deactivate_user(bot)
        action = lambda: do_reactivate_user(bot)
        events = self.do_test(action, num_events=2)
        error = bot_reactivate_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_do_mark_hotspot_as_read(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('hotspots')),
            ('hotspots', check_list(check_dict_only([
                ('name', check_string),
                ('title', check_string),
                ('description', check_string),
                ('delay', check_float),
            ]))),
        ])
        events = self.do_test(lambda: do_mark_hotspot_as_read(self.user_profile, 'intro_reply'))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_rename_stream(self):
        # type: () -> None
        stream = self.make_stream('old_name')
        new_name = u'stream with a brand new name'
        self.subscribe(self.user_profile, stream.name)

        action = lambda: do_rename_stream(stream, new_name)
        events = self.do_test(action, num_events=2)

        schema_checker = self.check_events_dict([
            ('type', equals('stream')),
            ('op', equals('update')),
            ('property', equals('email_address')),
            ('value', check_string),
            ('stream_id', check_int),
            ('name', equals('old_name')),
        ])
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)
        schema_checker = self.check_events_dict([
            ('type', equals('stream')),
            ('op', equals('update')),
            ('property', equals('name')),
            ('value', equals(new_name)),
            ('name', equals('old_name')),
            ('stream_id', check_int),
        ])
        error = schema_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_deactivate_stream_neversubscribed(self):
        # type: () -> None
        stream = self.make_stream('old_name')

        action = lambda: do_deactivate_stream(stream)
        events = self.do_test(action)

        schema_checker = self.check_events_dict([
            ('type', equals('stream')),
            ('op', equals('delete')),
            ('streams', check_list(check_dict([]))),
        ])
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_subscribe_other_user_never_subscribed(self):
        # type: () -> None
        action = lambda: self.subscribe(self.example_user("othello"), u"test_stream")
        events = self.do_test(action, num_events=2)
        peer_add_schema_checker = self.check_events_dict([
            ('type', equals('subscription')),
            ('op', equals('peer_add')),
            ('user_id', check_int),
            ('subscriptions', check_list(check_string)),
        ])
        error = peer_add_schema_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_subscribe_events(self):
        # type: () -> None
        self.do_test_subscribe_events(include_subscribers=True)

    def test_subscribe_events_no_include_subscribers(self):
        # type: () -> None
        self.do_test_subscribe_events(include_subscribers=False)

    def do_test_subscribe_events(self, include_subscribers):
        # type: (bool) -> None
        subscription_fields = [
            ('color', check_string),
            ('description', check_string),
            ('email_address', check_string),
            ('invite_only', check_bool),
            ('in_home_view', check_bool),
            ('name', check_string),
            ('desktop_notifications', check_bool),
            ('push_notifications', check_bool),
            ('audible_notifications', check_bool),
            ('stream_id', check_int),
        ]
        if include_subscribers:
            subscription_fields.append(('subscribers', check_list(check_int)))  # type: ignore
        subscription_schema_checker = check_list(
            check_dict(subscription_fields),  # TODO: Can this be converted to check_dict_only?
        )
        stream_create_schema_checker = self.check_events_dict([
            ('type', equals('stream')),
            ('op', equals('create')),
            ('streams', check_list(check_dict_only([
                ('name', check_string),
                ('stream_id', check_int),
                ('invite_only', check_bool),
                ('description', check_string),
            ]))),
        ])
        add_schema_checker = self.check_events_dict([
            ('type', equals('subscription')),
            ('op', equals('add')),
            ('subscriptions', subscription_schema_checker),
        ])
        remove_schema_checker = self.check_events_dict([
            ('type', equals('subscription')),
            ('op', equals('remove')),
            ('subscriptions', check_list(
                check_dict_only([
                    ('name', equals('test_stream')),
                    ('stream_id', check_int),
                ]),
            )),
        ])
        peer_add_schema_checker = self.check_events_dict([
            ('type', equals('subscription')),
            ('op', equals('peer_add')),
            ('user_id', check_int),
            ('subscriptions', check_list(check_string)),
        ])
        peer_remove_schema_checker = self.check_events_dict([
            ('type', equals('subscription')),
            ('op', equals('peer_remove')),
            ('user_id', check_int),
            ('subscriptions', check_list(check_string)),
        ])
        stream_update_schema_checker = self.check_events_dict([
            ('type', equals('stream')),
            ('op', equals('update')),
            ('property', equals('description')),
            ('value', check_string),
            ('stream_id', check_int),
            ('name', check_string),
        ])

        # Subscribe to a totally new stream, so it's just Hamlet on it
        action = lambda: self.subscribe(self.example_user("hamlet"), "test_stream")  # type: Callable
        events = self.do_test(action, event_types=["subscription", "realm_user"],
                              include_subscribers=include_subscribers)
        error = add_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Add another user to that totally new stream
        action = lambda: self.subscribe(self.example_user("othello"), "test_stream")
        events = self.do_test(action,
                              include_subscribers=include_subscribers,
                              state_change_expected=include_subscribers,
                              )
        error = peer_add_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        stream = get_stream("test_stream", self.user_profile.realm)

        # Now remove the first user, to test the normal unsubscribe flow
        action = lambda: bulk_remove_subscriptions(
            [self.example_user('othello')],
            [stream])
        events = self.do_test(action,
                              include_subscribers=include_subscribers,
                              state_change_expected=include_subscribers,
                              )
        error = peer_remove_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Now remove the second user, to test the 'vacate' event flow
        action = lambda: bulk_remove_subscriptions(
            [self.example_user('hamlet')],
            [stream])
        events = self.do_test(action,
                              include_subscribers=include_subscribers,
                              num_events=2)
        error = remove_schema_checker('events[1]', events[1])
        self.assert_on_error(error)

        # Now resubscribe a user, to make sure that works on a vacated stream
        action = lambda: self.subscribe(self.example_user("hamlet"), "test_stream")
        events = self.do_test(action,
                              include_subscribers=include_subscribers,
                              num_events=2)
        error = add_schema_checker('events[1]', events[1])
        self.assert_on_error(error)

        action = lambda: do_change_stream_description(stream, u'new description')
        events = self.do_test(action,
                              include_subscribers=include_subscribers)
        error = stream_update_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Subscribe to a totally new invite-only stream, so it's just Hamlet on it
        stream = self.make_stream("private", get_realm("zulip"), invite_only=True)
        user_profile = self.example_user('hamlet')
        action = lambda: bulk_add_subscriptions([stream], [user_profile])
        events = self.do_test(action, include_subscribers=include_subscribers,
                              num_events=2)
        error = stream_create_schema_checker('events[0]', events[0])
        error = add_schema_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_do_delete_message(self):
        # type: () -> None
        schema_checker = self.check_events_dict([
            ('type', equals('delete_message')),
            ('message_id', check_int),
            ('sender', check_string),
        ])
        msg_id = self.send_message("hamlet@zulip.com", "Verona", Recipient.STREAM)
        message = Message.objects.get(id=msg_id)
        events = self.do_test(
            lambda: do_delete_message(self.user_profile, message),
            state_change_expected=True,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_do_delete_message_no_max_id(self):
        # type: () -> None
        user_profile = self.example_user('aaron')
        # Delete all historical messages for this user
        user_profile = self.example_user('hamlet')
        UserMessage.objects.filter(user_profile=user_profile).delete()
        msg_id = self.send_message("hamlet@zulip.com", "Verona", Recipient.STREAM)
        message = Message.objects.get(id=msg_id)
        self.do_test(
            lambda: do_delete_message(self.user_profile, message),
            state_change_expected=True,
        )
        result = fetch_initial_state_data(user_profile, None, "")
        self.assertEqual(result['max_message_id'], -1)

class FetchInitialStateDataTest(ZulipTestCase):
    # Non-admin users don't have access to all bots
    def test_realm_bots_non_admin(self):
        # type: () -> None
        user_profile = self.example_user('cordelia')
        self.assertFalse(user_profile.is_realm_admin)
        result = fetch_initial_state_data(user_profile, None, "")
        self.assert_length(result['realm_bots'], 0)

        # additionally the API key for a random bot is not present in the data
        api_key = self.notification_bot().api_key
        self.assertNotIn(api_key, str(result))

    # Admin users have access to all bots in the realm_bots field
    def test_realm_bots_admin(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        do_change_is_admin(user_profile, True)
        self.assertTrue(user_profile.is_realm_admin)
        result = fetch_initial_state_data(user_profile, None, "")
        self.assertTrue(len(result['realm_bots']) > 5)

    def test_max_message_id_with_no_history(self):
        # type: () -> None
        user_profile = self.example_user('aaron')
        # Delete all historical messages for this user
        UserMessage.objects.filter(user_profile=user_profile).delete()
        result = fetch_initial_state_data(user_profile, None, "")
        self.assertEqual(result['max_message_id'], -1)

    def test_unread_msgs(self):
        # type: () -> None
        def mute_stream(user_profile, stream):
            # type: (UserProfile, Stream) -> None
            recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
            subscription = Subscription.objects.get(
                user_profile=user_profile,
                recipient=recipient
            )
            subscription.in_home_view = False
            subscription.save()

        def mute_topic(user_profile, stream_name, topic_name):
            # type: (UserProfile, Text, Text) -> None
            stream = get_stream(stream_name, realm)
            recipient = get_recipient(Recipient.STREAM, stream.id)

            add_topic_mute(
                user_profile=user_profile,
                stream_id=stream.id,
                recipient_id=recipient.id,
                topic_name='muted-topic',
            )

        cordelia = self.example_user('cordelia')
        sender_id = cordelia.id
        sender_email = cordelia.email
        user_profile = self.example_user('hamlet')
        othello = self.example_user('othello')

        realm = user_profile.realm

        # our tests rely on order
        assert(sender_email < user_profile.email)
        assert(user_profile.email < othello.email)

        pm1_message_id = self.send_message(sender_email, user_profile.email, Recipient.PERSONAL, "hello1")
        pm2_message_id = self.send_message(sender_email, user_profile.email, Recipient.PERSONAL, "hello2")

        muted_stream = self.subscribe(user_profile, 'Muted Stream')
        mute_stream(user_profile, muted_stream)
        mute_topic(user_profile, 'Denmark', 'muted-topic')

        stream_message_id = self.send_message(sender_email, "Denmark", Recipient.STREAM, "hello")
        muted_stream_message_id = self.send_message(sender_email, "Muted Stream", Recipient.STREAM, "hello")
        muted_topic_message_id = self.send_message(sender_email, "Denmark", Recipient.STREAM,
                                                   subject="muted-topic", content="hello")

        huddle_message_id = self.send_message(sender_email,
                                              [user_profile.email, othello.email],
                                              Recipient.HUDDLE,
                                              'hello3')

        def get_unread_data():
            # type: () -> Dict[str, Any]
            result = fetch_initial_state_data(user_profile, None, "")['unread_msgs']
            return result

        result = get_unread_data()

        # The count here reflects the count of unread messages that we will
        # report to users in the bankruptcy dialog, and for now it excludes unread messages
        # from muted treams, but it doesn't exclude unread messages from muted topics yet.
        self.assertEqual(result['count'], 4)

        unread_pm = result['pms'][0]
        self.assertEqual(unread_pm['sender_id'], sender_id)
        self.assertEqual(unread_pm['unread_message_ids'], [pm1_message_id, pm2_message_id])

        unread_stream = result['streams'][0]
        self.assertEqual(unread_stream['stream_id'], get_stream('Denmark', user_profile.realm).id)
        self.assertEqual(unread_stream['topic'], 'muted-topic')
        self.assertEqual(unread_stream['unread_message_ids'], [muted_topic_message_id])

        unread_stream = result['streams'][1]
        self.assertEqual(unread_stream['stream_id'], get_stream('Denmark', user_profile.realm).id)
        self.assertEqual(unread_stream['topic'], 'test')
        self.assertEqual(unread_stream['unread_message_ids'], [stream_message_id])

        unread_stream = result['streams'][2]
        self.assertEqual(unread_stream['stream_id'], get_stream('Muted Stream', user_profile.realm).id)
        self.assertEqual(unread_stream['topic'], 'test')
        self.assertEqual(unread_stream['unread_message_ids'], [muted_stream_message_id])

        huddle_string = ','.join(str(uid) for uid in sorted([sender_id, user_profile.id, othello.id]))

        unread_huddle = result['huddles'][0]
        self.assertEqual(unread_huddle['user_ids_string'], huddle_string)
        self.assertEqual(unread_huddle['unread_message_ids'], [huddle_message_id])

        self.assertEqual(result['mentions'], [])

        um = UserMessage.objects.get(
            user_profile_id=user_profile.id,
            message_id=stream_message_id
        )
        um.flags |= UserMessage.flags.mentioned
        um.save()

        result = get_unread_data()
        self.assertEqual(result['mentions'], [stream_message_id])

class EventQueueTest(TestCase):
    def test_one_event(self):
        # type: () -> None
        queue = EventQueue("1")
        queue.push({"type": "pointer",
                    "pointer": 1,
                    "timestamp": "1"})
        self.assertFalse(queue.empty())
        self.assertEqual(queue.contents(),
                         [{'id': 0,
                           'type': 'pointer',
                           "pointer": 1,
                           "timestamp": "1"}])

    def test_event_collapsing(self):
        # type: () -> None
        queue = EventQueue("1")
        for pointer_val in range(1, 10):
            queue.push({"type": "pointer",
                        "pointer": pointer_val,
                        "timestamp": str(pointer_val)})
        self.assertEqual(queue.contents(),
                         [{'id': 8,
                           'type': 'pointer',
                           "pointer": 9,
                           "timestamp": "9"}])

        queue = EventQueue("2")
        for pointer_val in range(1, 10):
            queue.push({"type": "pointer",
                        "pointer": pointer_val,
                        "timestamp": str(pointer_val)})
        queue.push({"type": "unknown"})
        queue.push({"type": "restart", "server_generation": "1"})
        for pointer_val in range(11, 20):
            queue.push({"type": "pointer",
                        "pointer": pointer_val,
                        "timestamp": str(pointer_val)})
        queue.push({"type": "restart", "server_generation": "2"})
        self.assertEqual(queue.contents(),
                         [{"type": "unknown",
                           "id": 9},
                          {'id': 19,
                           'type': 'pointer',
                           "pointer": 19,
                           "timestamp": "19"},
                          {"id": 20,
                           "type": "restart",
                           "server_generation": "2"}])
        for pointer_val in range(21, 23):
            queue.push({"type": "pointer",
                        "pointer": pointer_val,
                        "timestamp": str(pointer_val)})
        self.assertEqual(queue.contents(),
                         [{"type": "unknown",
                           "id": 9},
                          {'id': 19,
                           'type': 'pointer',
                           "pointer": 19,
                           "timestamp": "19"},
                          {"id": 20,
                           "type": "restart",
                           "server_generation": "2"},
                          {'id': 22,
                           'type': 'pointer',
                           "pointer": 22,
                           "timestamp": "22"},
                          ])

    def test_flag_add_collapsing(self):
        # type: () -> None
        queue = EventQueue("1")
        queue.push({"type": "update_message_flags",
                    "flag": "read",
                    "operation": "add",
                    "all": False,
                    "messages": [1, 2, 3, 4],
                    "timestamp": "1"})
        queue.push({"type": "update_message_flags",
                    "flag": "read",
                    "all": False,
                    "operation": "add",
                    "messages": [5, 6],
                    "timestamp": "1"})
        self.assertEqual(queue.contents(),
                         [{'id': 1,
                           'type': 'update_message_flags',
                           "all": False,
                           "flag": "read",
                           "operation": "add",
                           "messages": [1, 2, 3, 4, 5, 6],
                           "timestamp": "1"}])

    def test_flag_remove_collapsing(self):
        # type: () -> None
        queue = EventQueue("1")
        queue.push({"type": "update_message_flags",
                    "flag": "collapsed",
                    "operation": "remove",
                    "all": False,
                    "messages": [1, 2, 3, 4],
                    "timestamp": "1"})
        queue.push({"type": "update_message_flags",
                    "flag": "collapsed",
                    "all": False,
                    "operation": "remove",
                    "messages": [5, 6],
                    "timestamp": "1"})
        self.assertEqual(queue.contents(),
                         [{'id': 1,
                           'type': 'update_message_flags',
                           "all": False,
                           "flag": "collapsed",
                           "operation": "remove",
                           "messages": [1, 2, 3, 4, 5, 6],
                           "timestamp": "1"}])

    def test_collapse_event(self):
        # type: () -> None
        queue = EventQueue("1")
        queue.push({"type": "pointer",
                    "pointer": 1,
                    "timestamp": "1"})
        queue.push({"type": "unknown",
                    "timestamp": "1"})
        self.assertEqual(queue.contents(),
                         [{'id': 0,
                           'type': 'pointer',
                           "pointer": 1,
                           "timestamp": "1"},
                          {'id': 1,
                           'type': 'unknown',
                           "timestamp": "1"}])

class TestEventsRegisterAllPublicStreamsDefaults(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email

    def test_use_passed_all_public_true_default_false(self):
        # type: () -> None
        self.user_profile.default_all_public_streams = False
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, True)
        self.assertTrue(result)

    def test_use_passed_all_public_true_default(self):
        # type: () -> None
        self.user_profile.default_all_public_streams = True
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, True)
        self.assertTrue(result)

    def test_use_passed_all_public_false_default_false(self):
        # type: () -> None
        self.user_profile.default_all_public_streams = False
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, False)
        self.assertFalse(result)

    def test_use_passed_all_public_false_default_true(self):
        # type: () -> None
        self.user_profile.default_all_public_streams = True
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, False)
        self.assertFalse(result)

    def test_use_true_default_for_none(self):
        # type: () -> None
        self.user_profile.default_all_public_streams = True
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, None)
        self.assertTrue(result)

    def test_use_false_default_for_none(self):
        # type: () -> None
        self.user_profile.default_all_public_streams = False
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, None)
        self.assertFalse(result)

class TestEventsRegisterNarrowDefaults(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email
        self.stream = get_stream('Verona', self.user_profile.realm)

    def test_use_passed_narrow_no_default(self):
        # type: () -> None
        self.user_profile.default_events_register_stream_id = None
        self.user_profile.save()
        result = _default_narrow(self.user_profile, [[u'stream', u'my_stream']])
        self.assertEqual(result, [[u'stream', u'my_stream']])

    def test_use_passed_narrow_with_default(self):
        # type: () -> None
        self.user_profile.default_events_register_stream_id = self.stream.id
        self.user_profile.save()
        result = _default_narrow(self.user_profile, [[u'stream', u'my_stream']])
        self.assertEqual(result, [[u'stream', u'my_stream']])

    def test_use_default_if_narrow_is_empty(self):
        # type: () -> None
        self.user_profile.default_events_register_stream_id = self.stream.id
        self.user_profile.save()
        result = _default_narrow(self.user_profile, [])
        self.assertEqual(result, [[u'stream', u'Verona']])

    def test_use_narrow_if_default_is_none(self):
        # type: () -> None
        self.user_profile.default_events_register_stream_id = None
        self.user_profile.save()
        result = _default_narrow(self.user_profile, [])
        self.assertEqual(result, [])
