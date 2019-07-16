# See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html for
# high-level documentation on how this system works.
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import copy
import os
import shutil
import sys

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from io import StringIO

from zerver.models import (
    get_client, get_stream, get_realm, get_system_bot,
    Message, RealmDomain, Recipient, UserMessage, UserPresence, UserProfile,
    Realm, Subscription, Stream, flush_per_request_caches, UserGroup, Service,
    Attachment, PreregistrationUser, get_user_by_delivery_email, MultiuseInvite,
    RealmAuditLog
)

from zerver.lib.actions import (
    try_update_realm_custom_profile_field,
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    check_add_realm_emoji,
    check_send_message,
    check_send_typing_notification,
    do_add_alert_words,
    do_add_default_stream,
    do_add_reaction,
    do_add_reaction_legacy,
    do_add_realm_domain,
    do_add_realm_filter,
    do_add_streams_to_default_stream_group,
    do_add_submessage,
    do_change_avatar_fields,
    do_change_bot_owner,
    do_change_default_all_public_streams,
    do_change_default_events_register_stream,
    do_change_default_sending_stream,
    do_change_default_stream_group_description,
    do_change_default_stream_group_name,
    do_change_full_name,
    do_change_icon_source,
    do_change_logo_source,
    do_change_user_role,
    do_change_notification_settings,
    do_change_plan_type,
    do_change_realm_domain,
    do_change_stream_description,
    do_change_stream_invite_only,
    do_change_stream_post_policy,
    do_change_subscription_property,
    do_change_user_delivery_email,
    do_create_user,
    do_create_default_stream_group,
    do_create_multiuse_invite_link,
    do_deactivate_stream,
    do_deactivate_user,
    do_delete_messages,
    do_invite_users,
    do_mark_hotspot_as_read,
    do_mute_topic,
    do_reactivate_user,
    do_regenerate_api_key,
    do_remove_alert_words,
    do_remove_default_stream,
    do_remove_default_stream_group,
    do_remove_reaction,
    do_remove_reaction_legacy,
    do_remove_realm_domain,
    do_remove_realm_emoji,
    do_remove_realm_filter,
    do_remove_streams_from_default_stream_group,
    do_rename_stream,
    do_revoke_multi_use_invite,
    do_revoke_user_invite,
    do_set_realm_authentication_methods,
    do_set_realm_message_editing,
    do_set_realm_property,
    do_set_user_display_setting,
    do_set_realm_notifications_stream,
    do_set_realm_signup_notifications_stream,
    do_unmute_topic,
    do_update_embedded_data,
    do_update_message,
    do_update_message_flags,
    do_update_outgoing_webhook_service,
    do_update_pointer,
    do_update_user_presence,
    do_update_user_status,
    log_event,
    lookup_default_stream_groups,
    notify_realm_custom_profile_fields,
    check_add_user_group,
    do_update_user_group_name,
    do_update_user_group_description,
    bulk_add_members_to_user_group,
    remove_members_from_user_group,
    check_delete_user_group,
    do_update_user_custom_profile_data_if_changed,
)
from zerver.lib.bugdown import MentionData
from zerver.lib.events import (
    apply_events,
    fetch_initial_state_data,
    get_raw_user_data,
    post_process_state,
)
from zerver.lib.message import (
    aggregate_unread_data,
    apply_unread_message_event,
    get_raw_unread_data,
    render_markdown,
    MessageDict,
    UnreadMessagesResult,
)
from zerver.lib.test_helpers import POSTRequestMock, get_subscription, \
    get_test_image_file, stub_event_queue_user_events, queries_captured, \
    create_dummy_file, stdout_suppressed, reset_emails_in_zulip_realm
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.test_runner import slow
from zerver.lib.topic import (
    ORIG_TOPIC,
    TOPIC_NAME,
    TOPIC_LINKS,
)
from zerver.lib.topic_mutes import (
    add_topic_mute,
)
from zerver.lib.validator import (
    check_bool, check_dict, check_dict_only, check_float, check_int, check_list, check_string,
    equals, check_none_or, Validator, check_url, check_int_in
)
from zerver.lib.users import get_api_key

from zerver.views.events_register import _default_all_public_streams, _default_narrow

from zerver.tornado.event_queue import (
    allocate_client_descriptor,
    clear_client_event_queues_for_testing,
    get_client_info_for_message_event,
    process_message_event,
)
from zerver.tornado.views import get_events

from unittest import mock
import time
import ujson


class LogEventsTest(ZulipTestCase):
    def test_with_missing_event_log_dir_setting(self) -> None:
        with self.settings(EVENT_LOG_DIR=None):
            log_event(dict())

    def test_log_event_mkdir(self) -> None:
        dir_name = os.path.join(settings.TEST_WORKER_DIR, "test-log-dir")

        try:
            shutil.rmtree(dir_name)
        except OSError:  # nocoverage
            # assume it doesn't exist already
            pass

        self.assertFalse(os.path.exists(dir_name))
        with self.settings(EVENT_LOG_DIR=dir_name):
            event: Dict[str, int] = {}
            log_event(event)
        self.assertTrue(os.path.exists(dir_name))


class EventsEndpointTest(ZulipTestCase):
    def test_events_register_endpoint(self) -> None:

        # This test is intended to get minimal coverage on the
        # events_register code paths
        user = self.example_user("hamlet")
        with mock.patch('zerver.views.events_register.do_events_register', return_value={}):
            result = self.api_post(user, '/json/register')
        self.assert_json_success(result)

        with mock.patch('zerver.lib.events.request_event_queue', return_value=None):
            result = self.api_post(user, '/json/register')
        self.assert_json_error(result, "Could not allocate event queue")

        return_event_queue = '15:11'
        return_user_events: List[Dict[str, Any]] = []

        # Test that call is made to deal with a returning soft deactivated user.
        with mock.patch('zerver.lib.events.reactivate_user_if_soft_deactivated') as fa:
            with stub_event_queue_user_events(return_event_queue, return_user_events):
                result = self.api_post(user, '/json/register', dict(event_types=ujson.dumps(['pointer'])))
                self.assertEqual(fa.call_count, 1)

        with stub_event_queue_user_events(return_event_queue, return_user_events):
            result = self.api_post(user, '/json/register', dict(event_types=ujson.dumps(['pointer'])))
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
            result = self.api_post(user, '/json/register', dict(event_types=ujson.dumps(['pointer'])))

        self.assert_json_success(result)
        result_dict = result.json()
        self.assertEqual(result_dict['last_event_id'], 6)
        self.assertEqual(result_dict['pointer'], 15)
        self.assertEqual(result_dict['queue_id'], '15:12')

        # Now test with `fetch_event_types` not matching the event
        return_event_queue = '15:13'
        with stub_event_queue_user_events(return_event_queue, return_user_events):
            result = self.api_post(user, '/json/register',
                                   dict(event_types=ujson.dumps(['pointer']),
                                        fetch_event_types=ujson.dumps(['message'])))
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
            result = self.api_post(user, '/json/register',
                                   dict(fetch_event_types=ujson.dumps(['pointer']),
                                        event_types=ujson.dumps(['message'])))
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

    def test_tornado_endpoint(self) -> None:

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
    def tornado_call(self, view_func: Callable[[HttpRequest, UserProfile], HttpResponse],
                     user_profile: UserProfile,
                     post_data: Dict[str, Any]) -> HttpResponse:
        request = POSTRequestMock(post_data, user_profile)
        return view_func(request, user_profile)

    def test_get_events(self) -> None:
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        recipient_user_profile = self.example_user('othello')
        recipient_email = recipient_user_profile.email
        self.login_user(user_profile)

        result = self.tornado_call(get_events, user_profile,
                                   {"apply_markdown": ujson.dumps(True),
                                    "client_gravatar": ujson.dumps(True),
                                    "event_types": ujson.dumps(["message"]),
                                    "user_client": "website",
                                    "dont_block": ujson.dumps(True),
                                    })
        self.assert_json_success(result)
        queue_id = ujson.loads(result.content)["queue_id"]

        recipient_result = self.tornado_call(get_events, recipient_user_profile,
                                             {"apply_markdown": ujson.dumps(True),
                                              "client_gravatar": ujson.dumps(True),
                                              "event_types": ujson.dumps(["message"]),
                                              "user_client": "website",
                                              "dont_block": ujson.dumps(True),
                                              })
        self.assert_json_success(recipient_result)
        recipient_queue_id = ujson.loads(recipient_result.content)["queue_id"]

        result = self.tornado_call(get_events, user_profile,
                                   {"queue_id": queue_id,
                                    "user_client": "website",
                                    "last_event_id": -1,
                                    "dont_block": ujson.dumps(True),
                                    })
        events = ujson.loads(result.content)["events"]
        self.assert_json_success(result)
        self.assert_length(events, 0)

        local_id = '10.01'
        check_send_message(
            sender=user_profile,
            client=get_client('whatever'),
            message_type_name='private',
            message_to=[recipient_email],
            topic_name=None,
            message_content='hello',
            local_id=local_id,
            sender_queue_id=queue_id,
        )

        result = self.tornado_call(get_events, user_profile,
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
        local_id = '10.02'

        check_send_message(
            sender=user_profile,
            client=get_client('whatever'),
            message_type_name='private',
            message_to=[recipient_email],
            topic_name=None,
            message_content='hello',
            local_id=local_id,
            sender_queue_id=queue_id,
        )

        result = self.tornado_call(get_events, user_profile,
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
        recipient_result = self.tornado_call(get_events, recipient_user_profile,
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

    def test_get_events_narrow(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)

        def get_message(apply_markdown: bool, client_gravatar: bool) -> Dict[str, Any]:
            result = self.tornado_call(
                get_events,
                user_profile,
                dict(
                    apply_markdown=ujson.dumps(apply_markdown),
                    client_gravatar=ujson.dumps(client_gravatar),
                    event_types=ujson.dumps(["message"]),
                    narrow=ujson.dumps([["stream", "denmark"]]),
                    user_client="website",
                    dont_block=ujson.dumps(True),
                )
            )

            self.assert_json_success(result)
            queue_id = ujson.loads(result.content)["queue_id"]

            result = self.tornado_call(get_events, user_profile,
                                       {"queue_id": queue_id,
                                        "user_client": "website",
                                        "last_event_id": -1,
                                        "dont_block": ujson.dumps(True),
                                        })
            events = ujson.loads(result.content)["events"]
            self.assert_json_success(result)
            self.assert_length(events, 0)

            self.send_personal_message(user_profile, self.example_user("othello"), "hello")
            self.send_stream_message(user_profile, "Denmark", "**hello**")

            result = self.tornado_call(get_events, user_profile,
                                       {"queue_id": queue_id,
                                        "user_client": "website",
                                        "last_event_id": -1,
                                        "dont_block": ujson.dumps(True),
                                        })
            events = ujson.loads(result.content)["events"]
            self.assert_json_success(result)
            self.assert_length(events, 1)
            self.assertEqual(events[0]["type"], "message")
            return events[0]['message']

        message = get_message(apply_markdown=False, client_gravatar=False)
        self.assertEqual(message["display_recipient"], "Denmark")
        self.assertEqual(message["content"], "**hello**")
        self.assertIn('gravatar.com', message["avatar_url"])

        message = get_message(apply_markdown=True, client_gravatar=False)
        self.assertEqual(message["display_recipient"], "Denmark")
        self.assertEqual(message["content"], "<p><strong>hello</strong></p>")
        self.assertIn('gravatar.com', message["avatar_url"])

        message = get_message(apply_markdown=False, client_gravatar=True)
        self.assertEqual(message["display_recipient"], "Denmark")
        self.assertEqual(message["content"], "**hello**")
        self.assertEqual(message["avatar_url"], None)

        message = get_message(apply_markdown=True, client_gravatar=True)
        self.assertEqual(message["display_recipient"], "Denmark")
        self.assertEqual(message["content"], "<p><strong>hello</strong></p>")
        self.assertEqual(message["avatar_url"], None)

class EventsRegisterTest(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user('hamlet')

    def create_bot(self, email: str, **extras: Any) -> Optional[UserProfile]:
        return self.create_test_bot(email, self.user_profile, **extras)

    def realm_bot_schema(self, field_name: str, check: Validator) -> Validator:
        return self.check_events_dict([
            ('type', equals('realm_bot')),
            ('op', equals('update')),
            ('bot', check_dict_only([
                ('user_id', check_int),
                (field_name, check),
            ])),
        ])

    def do_test(self, action: Callable[[], object], event_types: Optional[List[str]]=None,
                include_subscribers: bool=True, state_change_expected: bool=True,
                notification_settings_null: bool=False,
                client_gravatar: bool=True, slim_presence: bool=False,
                num_events: int=1) -> List[Dict[str, Any]]:
        '''
        Make sure we have a clean slate of client descriptors for these tests.
        If we don't do this, then certain failures will only manifest when you
        run multiple tests within a single test function.

        See also https://zulip.readthedocs.io/en/latest/subsystems/events-system.html#testing
        for details on the design of this test system.
        '''
        clear_client_event_queues_for_testing()

        client = allocate_client_descriptor(
            dict(user_profile_id = self.user_profile.id,
                 realm_id = self.user_profile.realm_id,
                 event_types = event_types,
                 client_type_name = "website",
                 apply_markdown = True,
                 client_gravatar = client_gravatar,
                 slim_presence = slim_presence,
                 all_public_streams = False,
                 queue_timeout = 600,
                 last_connection_time = time.time(),
                 narrow = [])
        )
        # hybrid_state = initial fetch state + re-applying events triggered by our action
        # normal_state = do action then fetch at the end (the "normal" code path)
        hybrid_state = fetch_initial_state_data(
            self.user_profile, event_types, "",
            client_gravatar=client_gravatar,
            slim_presence=slim_presence,
            include_subscribers=include_subscribers
        )
        action()
        events = client.event_queue.contents()
        self.assertEqual(len(events), num_events)

        initial_state = copy.deepcopy(hybrid_state)
        post_process_state(self.user_profile, initial_state, notification_settings_null)
        before = ujson.dumps(initial_state)
        apply_events(hybrid_state, events, self.user_profile,
                     client_gravatar=client_gravatar,
                     slim_presence=slim_presence,
                     include_subscribers=include_subscribers)
        post_process_state(self.user_profile, hybrid_state, notification_settings_null)
        after = ujson.dumps(hybrid_state)

        if state_change_expected:
            if before == after:  # nocoverage
                print(ujson.dumps(initial_state, indent=2))
                print(events)
                raise AssertionError('Test does not exercise enough code -- events do not change state.')
        else:
            try:
                self.match_states(initial_state, copy.deepcopy(hybrid_state), events)
            except AssertionError:  # nocoverage
                raise AssertionError('Test is invalid--state actually does change here.')

        normal_state = fetch_initial_state_data(
            self.user_profile, event_types, "",
            client_gravatar=client_gravatar,
            slim_presence=slim_presence,
            include_subscribers=include_subscribers,
        )
        post_process_state(self.user_profile, normal_state, notification_settings_null)
        self.match_states(hybrid_state, normal_state, events)
        return events

    def assert_on_error(self, error: Optional[str]) -> None:
        if error:
            raise AssertionError(error)

    def match_states(self, state1: Dict[str, Any], state2: Dict[str, Any],
                     events: List[Dict[str, Any]]) -> None:
        def normalize(state: Dict[str, Any]) -> None:
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

        # If this assertions fails, we have unusual problems.
        self.assertEqual(state1.keys(), state2.keys())

        # The far more likely scenario is that some section of
        # our enormous payload does not get updated properly.  We
        # want the diff here to be developer-friendly, hence
        # the somewhat tedious code to provide useful output.
        if state1 != state2:  # nocoverage
            print('\n---States DO NOT MATCH---')
            print('\nEVENTS:\n')

            # Printing out the events is a big help to
            # developers.
            import json
            for event in events:
                print(json.dumps(event, indent=4))

            print('\nMISMATCHES:\n')
            for k in state1:
                if state1[k] != state2[k]:
                    print('\nkey = ' + k)
                    try:
                        self.assertEqual({k: state1[k]}, {k: state2[k]})
                    except AssertionError as e:
                        print(e)
            print('''
                NOTE:

                    This is an advanced test that verifies how
                    we apply events after fetching data.  If you
                    do not know how to debug it, you can ask for
                    help on chat.
                ''')

            sys.stdout.flush()
            raise AssertionError('Mismatching states')

    def check_events_dict(self, required_keys: List[Tuple[str, Validator]]) -> Validator:
        required_keys.append(('id', check_int))
        # Raise AssertionError if `required_keys` contains duplicate items.
        keys = [key[0] for key in required_keys]
        self.assertEqual(len(keys), len(set(keys)), 'Duplicate items found in required_keys.')
        return check_dict_only(required_keys)

    def test_mentioned_send_message_events(self) -> None:
        user = self.example_user('hamlet')

        for i in range(3):
            content = 'mentioning... @**' + user.full_name + '** hello ' + str(i)
            self.do_test(
                lambda: self.send_stream_message(self.example_user('cordelia'),
                                                 "Verona",
                                                 content)

            )

    def test_wildcard_mentioned_send_message_events(self) -> None:
        for i in range(3):
            content = 'mentioning... @**all** hello ' + str(i)
            self.do_test(
                lambda: self.send_stream_message(self.example_user('cordelia'),
                                                 "Verona",
                                                 content)

            )

    def test_pm_send_message_events(self) -> None:
        self.do_test(
            lambda: self.send_personal_message(self.example_user('cordelia'),
                                               self.example_user('hamlet'),
                                               'hola')

        )

    def test_huddle_send_message_events(self) -> None:
        huddle = [
            self.example_user('hamlet'),
            self.example_user('othello'),
        ]
        self.do_test(
            lambda: self.send_huddle_message(self.example_user('cordelia'),
                                             huddle,
                                             'hola')

        )

    def test_stream_send_message_events(self) -> None:
        def get_checker(check_gravatar: Validator) -> Validator:
            schema_checker = self.check_events_dict([
                ('type', equals('message')),
                ('flags', check_list(None)),
                ('message', check_dict_only([
                    ('avatar_url', check_gravatar),
                    ('client', check_string),
                    ('content', check_string),
                    ('content_type', equals('text/html')),
                    ('display_recipient', check_string),
                    ('id', check_int),
                    ('is_me_message', check_bool),
                    ('reactions', check_list(None)),
                    ('recipient_id', check_int),
                    ('sender_realm_str', check_string),
                    ('sender_email', check_string),
                    ('sender_full_name', check_string),
                    ('sender_id', check_int),
                    ('sender_short_name', check_string),
                    ('stream_id', check_int),
                    (TOPIC_NAME, check_string),
                    (TOPIC_LINKS, check_list(None)),
                    ('submessages', check_list(None)),
                    ('timestamp', check_int),
                    ('type', check_string),
                ])),
            ])
            return schema_checker

        events = self.do_test(
            lambda: self.send_stream_message(self.example_user("hamlet"), "Verona", "hello"),
            client_gravatar=False,
        )
        schema_checker = get_checker(check_gravatar=check_string)
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(
            lambda: self.send_stream_message(self.example_user("hamlet"), "Verona", "hello"),
            client_gravatar=True,
        )
        schema_checker = get_checker(check_gravatar=equals(None))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Verify message editing
        schema_checker = self.check_events_dict([
            ('type', equals('update_message')),
            ('flags', check_list(None)),
            ('content', check_string),
            ('edit_timestamp', check_int),
            ('message_id', check_int),
            ('message_ids', check_list(check_int)),
            ('prior_mention_user_ids', check_list(check_int)),
            ('mention_user_ids', check_list(check_int)),
            ('wildcard_mention_user_ids', check_list(check_int)),
            ('presence_idle_user_ids', check_list(check_int)),
            ('stream_push_user_ids', check_list(check_int)),
            ('stream_email_user_ids', check_list(check_int)),
            ('push_notify_user_ids', check_list(check_int)),
            ('orig_content', check_string),
            ('orig_rendered_content', check_string),
            (ORIG_TOPIC, check_string),
            ('prev_rendered_content_version', check_int),
            ('propagate_mode', check_string),
            ('rendered_content', check_string),
            ('stream_id', check_int),
            ('stream_name', check_string),
            (TOPIC_NAME, check_string),
            (TOPIC_LINKS, check_list(None)),
            ('user_id', check_int),
            ('is_me_message', check_bool),
        ])

        message = Message.objects.order_by('-id')[0]
        topic = 'new_topic'
        propagate_mode = 'change_all'
        content = 'new content'
        rendered_content = render_markdown(message, content)
        prior_mention_user_ids: Set[int] = set()
        mentioned_user_ids: Set[int] = set()
        mention_data = MentionData(
            realm_id=self.user_profile.realm_id,
            content=content,
        )

        events = self.do_test(
            lambda: do_update_message(self.user_profile, message, None, topic,
                                      propagate_mode, content, rendered_content,
                                      prior_mention_user_ids,
                                      mentioned_user_ids, mention_data),
            state_change_expected=True,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Verify do_update_embedded_data
        schema_checker = self.check_events_dict([
            ('type', equals('update_message')),
            ('flags', check_list(None)),
            ('content', check_string),
            ('message_id', check_int),
            ('message_ids', check_list(check_int)),
            ('rendered_content', check_string),
            ('sender', check_string),
        ])

        events = self.do_test(
            lambda: do_update_embedded_data(self.user_profile, message,
                                            "embed_content", "<p>embed_content</p>"),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_update_message_flags(self) -> None:
        # Test message flag update events
        schema_checker = self.check_events_dict([
            ('all', check_bool),
            ('type', equals('update_message_flags')),
            ('flag', check_string),
            ('messages', check_list(check_int)),
            ('operation', equals("add")),
        ])

        message = self.send_personal_message(
            self.example_user("cordelia"),
            self.example_user("hamlet"),
            "hello",
        )
        user_profile = self.example_user('hamlet')
        events = self.do_test(
            lambda: do_update_message_flags(user_profile, get_client("website"), 'add', 'starred', [message]),
            state_change_expected=True,
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
            lambda: do_update_message_flags(user_profile, get_client("website"), 'remove', 'starred', [message]),
            state_change_expected=True,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_update_read_flag_removes_unread_msg_ids(self) -> None:

        user_profile = self.example_user('hamlet')
        mention = '@**' + user_profile.full_name + '**'

        for content in ['hello', mention]:
            message = self.send_stream_message(
                self.example_user('cordelia'),
                "Verona",
                content
            )

            self.do_test(
                lambda: do_update_message_flags(user_profile, get_client("website"), 'add', 'read', [message]),
                state_change_expected=True,
            )

    def test_send_message_to_existing_recipient(self) -> None:
        sender = self.example_user('cordelia')
        self.send_stream_message(
            sender,
            "Verona",
            "hello 1"
        )
        self.do_test(
            lambda: self.send_stream_message(sender, "Verona", "hello 2"),
            state_change_expected=True,
        )

    def test_add_reaction_legacy(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('reaction')),
            ('op', equals('add')),
            ('message_id', check_int),
            ('emoji_name', check_string),
            ('emoji_code', check_string),
            ('reaction_type', check_string),
            ('user_id', check_int),
            ('user', check_dict_only([
                ('email', check_string),
                ('full_name', check_string),
                ('user_id', check_int)
            ])),
        ])

        message_id = self.send_stream_message(self.example_user("hamlet"), "Verona", "hello")
        message = Message.objects.get(id=message_id)
        events = self.do_test(
            lambda: do_add_reaction_legacy(
                self.user_profile, message, "tada"),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_remove_reaction_legacy(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('reaction')),
            ('op', equals('remove')),
            ('message_id', check_int),
            ('emoji_name', check_string),
            ('emoji_code', check_string),
            ('reaction_type', check_string),
            ('user_id', check_int),
            ('user', check_dict_only([
                ('email', check_string),
                ('full_name', check_string),
                ('user_id', check_int)
            ])),
        ])

        message_id = self.send_stream_message(self.example_user("hamlet"), "Verona", "hello")
        message = Message.objects.get(id=message_id)
        do_add_reaction_legacy(self.user_profile, message, "tada")
        events = self.do_test(
            lambda: do_remove_reaction_legacy(
                self.user_profile, message, "tada"),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_add_reaction(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('reaction')),
            ('op', equals('add')),
            ('message_id', check_int),
            ('emoji_name', check_string),
            ('emoji_code', check_string),
            ('reaction_type', check_string),
            ('user_id', check_int),
            ('user', check_dict_only([
                ('email', check_string),
                ('full_name', check_string),
                ('user_id', check_int)
            ])),
        ])

        message_id = self.send_stream_message(self.example_user("hamlet"), "Verona", "hello")
        message = Message.objects.get(id=message_id)
        events = self.do_test(
            lambda: do_add_reaction(
                self.user_profile, message, "tada", "1f389", "unicode_emoji"),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_add_submessage(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('submessage')),
            ('message_id', check_int),
            ('submessage_id', check_int),
            ('sender_id', check_int),
            ('msg_type', check_string),
            ('content', check_string),
        ])

        cordelia = self.example_user('cordelia')
        stream_name = 'Verona'
        message_id = self.send_stream_message(
            sender=cordelia,
            stream_name=stream_name,
        )
        events = self.do_test(
            lambda: do_add_submessage(
                realm=cordelia.realm,
                sender_id=cordelia.id,
                message_id=message_id,
                msg_type='whatever',
                content='"stuff"',
            ),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_remove_reaction(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('reaction')),
            ('op', equals('remove')),
            ('message_id', check_int),
            ('emoji_name', check_string),
            ('emoji_code', check_string),
            ('reaction_type', check_string),
            ('user_id', check_int),
            ('user', check_dict_only([
                ('email', check_string),
                ('full_name', check_string),
                ('user_id', check_int)
            ])),
        ])

        message_id = self.send_stream_message(self.example_user("hamlet"), "Verona", "hello")
        message = Message.objects.get(id=message_id)
        do_add_reaction(self.user_profile, message, "tada", "1f389", "unicode_emoji")
        events = self.do_test(
            lambda: do_remove_reaction(
                self.user_profile, message, "1f389", "unicode_emoji"),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_invite_user_event(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('invites_changed')),
        ])

        self.user_profile = self.example_user('iago')
        streams = []
        for stream_name in ["Denmark", "Scotland"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))
        events = self.do_test(
            lambda: do_invite_users(self.user_profile, ["foo@zulip.com"], streams, False),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_create_multiuse_invite_event(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('invites_changed')),
        ])

        self.user_profile = self.example_user('iago')
        streams = []
        for stream_name in ["Denmark", "Verona"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        events = self.do_test(
            lambda: do_create_multiuse_invite_link(self.user_profile, PreregistrationUser.INVITE_AS['MEMBER'], streams),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_revoke_user_invite_event(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('invites_changed')),
        ])

        self.user_profile = self.example_user('iago')
        streams = []
        for stream_name in ["Denmark", "Verona"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))
        do_invite_users(self.user_profile, ["foo@zulip.com"], streams, False)
        prereg_users = PreregistrationUser.objects.filter(referred_by__realm=self.user_profile.realm)
        events = self.do_test(
            lambda: do_revoke_user_invite(prereg_users[0]),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_revoke_multiuse_invite_event(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('invites_changed')),
        ])

        self.user_profile = self.example_user('iago')
        streams = []
        for stream_name in ["Denmark", "Verona"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))
        do_create_multiuse_invite_link(self.user_profile, PreregistrationUser.INVITE_AS['MEMBER'], streams)

        multiuse_object = MultiuseInvite.objects.get()
        events = self.do_test(
            lambda: do_revoke_multi_use_invite(multiuse_object),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_invitation_accept_invite_event(self) -> None:
        reset_emails_in_zulip_realm()

        schema_checker = self.check_events_dict([
            ('type', equals('invites_changed')),
        ])

        self.user_profile = self.example_user('iago')
        streams = []
        for stream_name in ["Denmark", "Scotland"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        do_invite_users(self.user_profile, ["foo@zulip.com"], streams, False)
        prereg_user = PreregistrationUser.objects.get(email="foo@zulip.com")

        events = self.do_test(
            lambda: do_create_user('foo@zulip.com', 'password', self.user_profile.realm,
                                   'full name', 'short name', prereg_user=prereg_user),
            state_change_expected=True,
            num_events=5,
        )

        error = schema_checker('events[4]', events[4])
        self.assert_on_error(error)

    def test_typing_events(self) -> None:
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
                self.user_profile, [self.example_user("cordelia").id], "start"),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_custom_profile_fields_events(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('custom_profile_fields')),
            ('op', equals('add')),
            ('fields', check_list(check_dict_only([
                ('id', check_int),
                ('type', check_int),
                ('name', check_string),
                ('hint', check_string),
                ('field_data', check_string),
                ('order', check_int),
            ]))),
        ])

        events = self.do_test(
            lambda: notify_realm_custom_profile_fields(
                self.user_profile.realm, 'add'),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        realm = self.user_profile.realm
        field = realm.customprofilefield_set.get(realm=realm, name='Biography')
        name = field.name
        hint = 'Biography of the user'
        try_update_realm_custom_profile_field(realm, field, name, hint=hint)

        events = self.do_test(
            lambda: notify_realm_custom_profile_fields(
                self.user_profile.realm, 'add'),
            state_change_expected=False,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_custom_profile_field_data_events(self) -> None:
        schema_checker_basic = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict_only([
                ('user_id', check_int),
                ('custom_profile_field', check_dict([
                    ('id', check_int),
                    ('value', check_none_or(check_string)),
                ])),
            ])),
        ])

        schema_checker_with_rendered_value = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict_only([
                ('user_id', check_int),
                ('custom_profile_field', check_dict([
                    ('id', check_int),
                    ('value', check_none_or(check_string)),
                    ('rendered_value', check_none_or(check_string)),
                ])),
            ])),
        ])

        field_id = self.user_profile.realm.customprofilefield_set.get(
            realm=self.user_profile.realm, name='Biography').id
        field = {
            "id": field_id,
            "value": "New value",
        }
        events = self.do_test(lambda: do_update_user_custom_profile_data_if_changed(self.user_profile, [field]))
        error = schema_checker_with_rendered_value('events[0]', events[0])
        self.assert_on_error(error)

        # Test we pass correct stringify value in custom-user-field data event
        field_id = self.user_profile.realm.customprofilefield_set.get(
            realm=self.user_profile.realm, name='Mentor').id
        field = {
            "id": field_id,
            "value": [self.example_user("ZOE").id],
        }
        events = self.do_test(lambda: do_update_user_custom_profile_data_if_changed(self.user_profile, [field]))
        error = schema_checker_basic('events[0]', events[0])
        self.assert_on_error(error)

    def test_presence_events(self) -> None:
        fields = [
            ('type', equals('presence')),
            ('user_id', check_int),
            ('server_timestamp', check_float),
            ('presence', check_dict_only([
                ('website', check_dict_only([
                    ('status', equals('active')),
                    ('timestamp', check_int),
                    ('client', check_string),
                    ('pushable', check_bool),
                ])),
            ])),
        ]

        email_field = ('email', check_string)

        events = self.do_test(lambda: do_update_user_presence(
            self.user_profile, get_client("website"),
            timezone_now(), UserPresence.ACTIVE),
            slim_presence=False)
        schema_checker = self.check_events_dict(fields + [email_field])
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_update_user_presence(
            self.example_user('cordelia'), get_client("website"),
            timezone_now(), UserPresence.ACTIVE),
            slim_presence=True)
        schema_checker = self.check_events_dict(fields)
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_presence_events_multiple_clients(self) -> None:
        schema_checker_android = self.check_events_dict([
            ('type', equals('presence')),
            ('email', check_string),
            ('user_id', check_int),
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

        self.api_post(self.user_profile, "/api/v1/users/me/presence", {'status': 'idle'},
                      HTTP_USER_AGENT="ZulipAndroid/1.0")
        self.do_test(lambda: do_update_user_presence(
            self.user_profile, get_client("website"), timezone_now(), UserPresence.ACTIVE))
        events = self.do_test(lambda: do_update_user_presence(
            self.user_profile, get_client("ZulipAndroid/1.0"), timezone_now(), UserPresence.IDLE))
        error = schema_checker_android('events[0]', events[0])
        self.assert_on_error(error)

    def test_pointer_events(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('pointer')),
            ('pointer', check_int)
        ])
        events = self.do_test(lambda: do_update_pointer(self.user_profile, get_client("website"), 1500))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_register_events(self) -> None:
        realm_user_add_checker = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('add')),
            ('person', check_dict_only([
                ('user_id', check_int),
                ('email', check_string),
                ('avatar_url', check_none_or(check_string)),
                ('avatar_version', check_int),
                ('full_name', check_string),
                ('is_admin', check_bool),
                ('is_bot', check_bool),
                ('is_guest', check_bool),
                ('is_active', check_bool),
                ('profile_data', check_dict_only([])),
                ('timezone', check_string),
                ('date_joined', check_string),
            ])),
        ])

        events = self.do_test(lambda: self.register("test1@zulip.com", "test1"))
        self.assert_length(events, 1)
        error = realm_user_add_checker('events[0]', events[0])
        self.assert_on_error(error)
        new_user_profile = get_user_by_delivery_email("test1@zulip.com", self.user_profile.realm)
        self.assertEqual(new_user_profile.delivery_email, "test1@zulip.com")

    def test_register_events_email_address_visibility(self) -> None:
        realm_user_add_checker = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('add')),
            ('person', check_dict_only([
                ('user_id', check_int),
                ('email', check_string),
                ('avatar_url', check_none_or(check_string)),
                ('avatar_version', check_int),
                ('full_name', check_string),
                ('is_active', check_bool),
                ('is_admin', check_bool),
                ('is_bot', check_bool),
                ('is_guest', check_bool),
                ('profile_data', check_dict_only([])),
                ('timezone', check_string),
                ('date_joined', check_string),
            ])),
        ])

        do_set_realm_property(self.user_profile.realm, "email_address_visibility",
                              Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS)

        events = self.do_test(lambda: self.register("test1@zulip.com", "test1"))
        self.assert_length(events, 1)
        error = realm_user_add_checker('events[0]', events[0])
        self.assert_on_error(error)
        new_user_profile = get_user_by_delivery_email("test1@zulip.com", self.user_profile.realm)
        self.assertEqual(new_user_profile.email, "user%s@zulip.testserver" % (new_user_profile.id,))

    def test_alert_words_events(self) -> None:
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

    def test_away_events(self) -> None:
        checker = self.check_events_dict([
            ('type', equals('user_status')),
            ('user_id', check_int),
            ('away', check_bool),
            ('status_text', check_string),
        ])

        client = get_client("website")
        events = self.do_test(lambda: do_update_user_status(user_profile=self.user_profile,
                                                            away=True,
                                                            status_text='out to lunch',
                                                            client_id=client.id))
        error = checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_update_user_status(user_profile=self.user_profile,
                                                            away=False,
                                                            status_text='',
                                                            client_id=client.id))
        error = checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_user_group_events(self) -> None:
        user_group_add_checker = self.check_events_dict([
            ('type', equals('user_group')),
            ('op', equals('add')),
            ('group', check_dict_only([
                ('id', check_int),
                ('name', check_string),
                ('members', check_list(check_int)),
                ('description', check_string),
            ])),
        ])
        othello = self.example_user('othello')
        events = self.do_test(lambda: check_add_user_group(self.user_profile.realm,
                                                           'backend', [othello],
                                                           'Backend team'))
        error = user_group_add_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Test name update
        user_group_update_checker = self.check_events_dict([
            ('type', equals('user_group')),
            ('op', equals('update')),
            ('group_id', check_int),
            ('data', check_dict_only([
                ('name', check_string),
            ])),
        ])
        backend = UserGroup.objects.get(name='backend')
        events = self.do_test(lambda: do_update_user_group_name(backend, 'backendteam'))
        error = user_group_update_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Test description update
        user_group_update_checker = self.check_events_dict([
            ('type', equals('user_group')),
            ('op', equals('update')),
            ('group_id', check_int),
            ('data', check_dict_only([
                ('description', check_string),
            ])),
        ])
        description = "Backend team to deal with backend code."
        events = self.do_test(lambda: do_update_user_group_description(backend, description))
        error = user_group_update_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Test add members
        user_group_add_member_checker = self.check_events_dict([
            ('type', equals('user_group')),
            ('op', equals('add_members')),
            ('group_id', check_int),
            ('user_ids', check_list(check_int)),
        ])
        hamlet = self.example_user('hamlet')
        events = self.do_test(lambda: bulk_add_members_to_user_group(backend, [hamlet]))
        error = user_group_add_member_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Test remove members
        user_group_remove_member_checker = self.check_events_dict([
            ('type', equals('user_group')),
            ('op', equals('remove_members')),
            ('group_id', check_int),
            ('user_ids', check_list(check_int)),
        ])
        hamlet = self.example_user('hamlet')
        events = self.do_test(lambda: remove_members_from_user_group(backend, [hamlet]))
        error = user_group_remove_member_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Test delete event
        user_group_remove_checker = self.check_events_dict([
            ('type', equals('user_group')),
            ('op', equals('remove')),
            ('group_id', check_int),
        ])
        events = self.do_test(lambda: check_delete_user_group(backend.id, othello))
        error = user_group_remove_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_default_stream_groups_events(self) -> None:
        default_stream_groups_checker = self.check_events_dict([
            ('type', equals('default_stream_groups')),
            ('default_stream_groups', check_list(check_dict_only([
                ('name', check_string),
                ('id', check_int),
                ('description', check_string),
                ('streams', check_list(check_dict_only([
                    ('description', check_string),
                    ('rendered_description', check_string),
                    ('invite_only', check_bool),
                    ('is_web_public', check_bool),
                    ('is_announcement_only', check_bool),
                    ('stream_post_policy', check_int_in(Stream.STREAM_POST_POLICY_TYPES)),
                    ('name', check_string),
                    ('stream_id', check_int),
                    ('first_message_id', check_none_or(check_int)),
                    ('history_public_to_subscribers', check_bool)]))),
            ]))),
        ])

        streams = []
        for stream_name in ["Scotland", "Verona", "Denmark"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        events = self.do_test(lambda: do_create_default_stream_group(
            self.user_profile.realm, "group1", "This is group1", streams))
        error = default_stream_groups_checker('events[0]', events[0])
        self.assert_on_error(error)

        group = lookup_default_stream_groups(["group1"], self.user_profile.realm)[0]
        venice_stream = get_stream("Venice", self.user_profile.realm)
        events = self.do_test(lambda: do_add_streams_to_default_stream_group(self.user_profile.realm,
                                                                             group, [venice_stream]))
        error = default_stream_groups_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_remove_streams_from_default_stream_group(self.user_profile.realm,
                                                                                  group, [venice_stream]))
        error = default_stream_groups_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_change_default_stream_group_description(self.user_profile.realm,
                                                                                 group, "New description"))
        error = default_stream_groups_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_change_default_stream_group_name(self.user_profile.realm,
                                                                          group, "New Group Name"))
        error = default_stream_groups_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_remove_default_stream_group(self.user_profile.realm, group))
        error = default_stream_groups_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_default_stream_group_events_guest(self) -> None:
        streams = []
        for stream_name in ["Scotland", "Verona", "Denmark"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        do_create_default_stream_group(self.user_profile.realm, "group1",
                                       "This is group1", streams)
        group = lookup_default_stream_groups(["group1"], self.user_profile.realm)[0]

        do_change_user_role(self.user_profile, UserProfile.ROLE_GUEST)
        venice_stream = get_stream("Venice", self.user_profile.realm)
        self.do_test(lambda: do_add_streams_to_default_stream_group(self.user_profile.realm,
                                                                    group, [venice_stream]),
                     state_change_expected = False, num_events=0)

    def test_default_streams_events(self) -> None:
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

    def test_default_streams_events_guest(self) -> None:
        do_change_user_role(self.user_profile, UserProfile.ROLE_GUEST)
        stream = get_stream("Scotland", self.user_profile.realm)
        self.do_test(lambda: do_add_default_stream(stream),
                     state_change_expected = False, num_events=0)
        self.do_test(lambda: do_remove_default_stream(stream),
                     state_change_expected = False, num_events=0)

    def test_muted_topics_events(self) -> None:
        muted_topics_checker = self.check_events_dict([
            ('type', equals('muted_topics')),
            ('muted_topics', check_list(check_list(sub_validator=None, length=3))),
        ])
        stream = get_stream('Denmark', self.user_profile.realm)
        recipient = stream.recipient
        events = self.do_test(lambda: do_mute_topic(
            self.user_profile, stream, recipient, "topic"))
        error = muted_topics_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_unmute_topic(
            self.user_profile, stream, "topic"))
        error = muted_topics_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_avatar_fields(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict_only([
                ('avatar_url', check_string),
                ('avatar_url_medium', check_string),
                ('avatar_version', check_int),
                ('avatar_source', check_string),
                ('user_id', check_int),
            ])),
        ])
        events = self.do_test(
            lambda: do_change_avatar_fields(self.user_profile, UserProfile.AVATAR_FROM_USER),
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        schema_checker = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict_only([
                ('avatar_source', check_string),
                ('avatar_url', check_none_or(check_string)),
                ('avatar_url_medium', check_none_or(check_string)),
                ('avatar_version', check_int),
                ('user_id', check_int),
            ])),
        ])
        events = self.do_test(
            lambda: do_change_avatar_fields(self.user_profile, UserProfile.AVATAR_FROM_GRAVATAR),
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_full_name(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict_only([
                ('full_name', check_string),
                ('user_id', check_int),
            ])),
        ])
        events = self.do_test(lambda: do_change_full_name(self.user_profile, 'Sir Hamlet', self.user_profile))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_user_delivery_email_email_address_visibilty_admins(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict_only([
                ('delivery_email', check_string),
                ('user_id', check_int),
            ])),
        ])
        avatar_schema_checker = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict_only([
                ('avatar_source', check_string),
                ('avatar_url', check_string),
                ('avatar_url_medium', check_string),
                ('avatar_version', check_int),
                ('user_id', check_int),
            ])),
        ])
        do_set_realm_property(self.user_profile.realm, "email_address_visibility",
                              Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS)
        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()
        action = lambda: do_change_user_delivery_email(self.user_profile, 'newhamlet@zulip.com')
        events = self.do_test(action, num_events=2, client_gravatar=False)
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)
        error = avatar_schema_checker('events[1]', events[1])
        self.assert_on_error(error)

    def do_set_realm_property_test(self, name: str) -> None:
        bool_tests: List[bool] = [True, False, True]
        test_values: Dict[str, Any] = dict(
            default_language=['es', 'de', 'en'],
            description=['Realm description', 'New description'],
            digest_weekday=[0, 1, 2],
            message_retention_days=[10, 20],
            name=['Zulip', 'New Name'],
            waiting_period_threshold=[10, 20],
            create_stream_policy=[3, 2, 1],
            invite_to_stream_policy=[3, 2, 1],
            private_message_policy=[2, 1],
            user_group_edit_policy=[1, 2],
            email_address_visibility=[Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS],
            bot_creation_policy=[Realm.BOT_CREATION_EVERYONE],
            video_chat_provider=[
                Realm.VIDEO_CHAT_PROVIDERS['jitsi_meet']['id'],
                Realm.VIDEO_CHAT_PROVIDERS['google_hangouts']['id']
            ],
            google_hangouts_domain=["zulip.com", "zulip.org"],
            zoom_api_secret=["abc", "xyz"],
            zoom_api_key=["abc", "xyz"],
            zoom_user_id=["example@example.com", "example@example.org"],
            default_code_block_language=['python', 'javascript'],
        )

        vals = test_values.get(name)
        property_type = Realm.property_types[name]
        if property_type is bool:
            validator = check_bool
            vals = bool_tests
        elif property_type is str:
            validator = check_string
        elif property_type == (str, type(None)):
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
            raise AssertionError('No test created for %s' % (name,))
        do_set_realm_property(self.user_profile.realm, name, vals[0])
        for val in vals[1:]:
            state_change_expected = True
            if name == "zoom_api_secret":
                state_change_expected = False
            events = self.do_test(
                lambda: do_set_realm_property(self.user_profile.realm, name, val),
                state_change_expected=state_change_expected)
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    @slow("Actually runs several full-stack fetching tests")
    def test_change_realm_property(self) -> None:
        for prop in Realm.property_types:
            with self.settings(SEND_DIGEST_EMAILS=True):
                self.do_set_realm_property_test(prop)

    @slow("Runs a large matrix of tests")
    def test_change_realm_authentication_methods(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update_dict')),
            ('property', equals('default')),
            ('data', check_dict_only([
                ('authentication_methods', check_dict([]))
            ])),
        ])

        def fake_backends() -> Any:
            backends = (
                'zproject.backends.DevAuthBackend',
                'zproject.backends.EmailAuthBackend',
                'zproject.backends.GitHubAuthBackend',
                'zproject.backends.GoogleAuthBackend',
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

    def test_change_pin_stream(self) -> None:
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

    def test_change_stream_notification_settings(self) -> None:
        for setting_name in ['email_notifications']:
            schema_checker = self.check_events_dict([
                ('type', equals('subscription')),
                ('op', equals('update')),
                ('property', equals(setting_name)),
                ('stream_id', check_int),
                ('value', check_bool),
                ('name', check_string),
                ('email', check_string),
            ])
        stream = get_stream("Denmark", self.user_profile.realm)
        sub = get_subscription(stream.name, self.user_profile)

        # First test with notification_settings_null enabled
        for value in (True, False):
            events = self.do_test(lambda: do_change_subscription_property(self.user_profile, sub, stream,
                                                                          setting_name, value),
                                  notification_settings_null=True)
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

        for value in (True, False):
            events = self.do_test(lambda: do_change_subscription_property(self.user_profile, sub, stream,
                                                                          setting_name, value))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    @slow("Runs a matrix of 6 queries to the /home view")
    def test_change_realm_message_edit_settings(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update_dict')),
            ('property', equals('default')),
            ('data', check_dict_only([
                ('allow_message_editing', check_bool),
                ('message_content_edit_limit_seconds', check_int),
                ('allow_community_topic_editing', check_bool),
            ])),
        ])
        # Test every transition among the four possibilities {T,F} x {0, non-0}
        for (allow_message_editing, message_content_edit_limit_seconds) in \
            ((True, 0), (False, 0), (False, 1234),
             (True, 600), (False, 0), (True, 1234)):
            events = self.do_test(
                lambda: do_set_realm_message_editing(self.user_profile.realm,
                                                     allow_message_editing,
                                                     message_content_edit_limit_seconds,
                                                     False))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_realm_notifications_stream(self) -> None:
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

    def test_change_realm_signup_notifications_stream(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update')),
            ('property', equals('signup_notifications_stream_id')),
            ('value', check_int),
        ])

        stream = get_stream("Rome", self.user_profile.realm)

        for signup_notifications_stream, signup_notifications_stream_id in ((stream, stream.id), (None, -1)):
            events = self.do_test(
                lambda: do_set_realm_signup_notifications_stream(self.user_profile.realm,
                                                                 signup_notifications_stream,
                                                                 signup_notifications_stream_id))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_is_admin(self) -> None:
        reset_emails_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        schema_checker = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict_only([
                ('is_admin', check_bool),
                ('user_id', check_int),
            ])),
        ])

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER)
        for role in [UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_MEMBER]:
            events = self.do_test(lambda: do_change_user_role(self.user_profile, role))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def do_set_user_display_settings_test(self, setting_name: str) -> None:
        """Test updating each setting in UserProfile.property_types dict."""

        test_changes: Dict[str, Any] = dict(
            emojiset = ['twitter'],
            default_language = ['es', 'de', 'en'],
            timezone = ['US/Mountain', 'US/Samoa', 'Pacific/Galapogos', ''],
            demote_inactive_streams = [2, 3, 1],
            buddy_list_mode = [2, 3, 1],
        )

        property_type = UserProfile.property_types[setting_name]
        if property_type is bool:
            validator = check_bool
        elif property_type is str:
            validator = check_string
        elif property_type is int:
            validator = check_int
        else:
            raise AssertionError("Unexpected property type %s" % (property_type,))

        num_events = 1
        if setting_name == "timezone":
            num_events = 2
        values = test_changes.get(setting_name)
        if property_type is bool:
            if getattr(self.user_profile, setting_name) is False:
                values = [True, False, True]
            else:
                values = [False, True, False]
        if values is None:
            raise AssertionError('No test created for %s' % (setting_name,))

        for value in values:
            events = self.do_test(lambda: do_set_user_display_setting(
                self.user_profile, setting_name, value), num_events=num_events)

            schema_checker = self.check_events_dict([
                ('type', equals('update_display_settings')),
                ('setting_name', equals(setting_name)),
                ('user', check_string),
                ('setting', validator),
            ])
            language_schema_checker = self.check_events_dict([
                ('type', equals('update_display_settings')),
                ('language_name', check_string),
                ('setting_name', equals(setting_name)),
                ('user', check_string),
                ('setting', validator),
            ])
            if setting_name == "default_language":
                error = language_schema_checker('events[0]', events[0])
            else:
                error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

            timezone_schema_checker = self.check_events_dict([
                ('type', equals('realm_user')),
                ('op', equals('update')),
                ('person', check_dict_only([
                    ('user_id', check_int),
                    ('timezone', check_string),
                ])),
            ])
            if setting_name == "timezone":
                error = timezone_schema_checker('events[1]', events[1])

    @slow("Actually runs several full-stack fetching tests")
    def test_set_user_display_settings(self) -> None:
        for prop in UserProfile.property_types:
            self.do_set_user_display_settings_test(prop)

    @slow("Actually runs several full-stack fetching tests")
    def test_change_notification_settings(self) -> None:
        for notification_setting, v in self.user_profile.notification_setting_types.items():
            if notification_setting in ["notification_sound", "desktop_icon_count_display"]:
                # These settings are tested in their own tests.
                continue

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

                # Also test with notification_settings_null=True
                events = self.do_test(
                    lambda: do_change_notification_settings(
                        self.user_profile, notification_setting, setting_value, log=False),
                    notification_settings_null=True,
                    state_change_expected=False)
                error = schema_checker('events[0]', events[0])
                self.assert_on_error(error)

    def test_change_notification_sound(self) -> None:
        notification_setting = "notification_sound"
        schema_checker = self.check_events_dict([
            ('type', equals('update_global_notifications')),
            ('notification_name', equals(notification_setting)),
            ('user', check_string),
            ('setting', equals("ding")),
        ])

        events = self.do_test(lambda: do_change_notification_settings(
            self.user_profile, notification_setting, 'ding', log=False))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_desktop_icon_count_display(self) -> None:
        notification_setting = "desktop_icon_count_display"
        schema_checker = self.check_events_dict([
            ('type', equals('update_global_notifications')),
            ('notification_name', equals(notification_setting)),
            ('user', check_string),
            ('setting', equals(2)),
        ])

        events = self.do_test(lambda: do_change_notification_settings(
            self.user_profile, notification_setting, 2, log=False))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        schema_checker = self.check_events_dict([
            ('type', equals('update_global_notifications')),
            ('notification_name', equals(notification_setting)),
            ('user', check_string),
            ('setting', equals(1)),
        ])

        events = self.do_test(lambda: do_change_notification_settings(
            self.user_profile, notification_setting, 1, log=False))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_realm_update_plan_type(self) -> None:
        realm = self.user_profile.realm

        state_data = fetch_initial_state_data(self.user_profile, None, "", False)
        self.assertEqual(state_data['realm_plan_type'], Realm.SELF_HOSTED)
        self.assertEqual(state_data['zulip_plan_is_not_limited'], True)

        schema_checker = self.check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update')),
            ('property', equals('plan_type')),
            ('value', equals(Realm.LIMITED)),
            ('extra_data', check_dict_only([
                ('upload_quota', check_int)
            ])),
        ])
        events = self.do_test(lambda: do_change_plan_type(realm, Realm.LIMITED))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        state_data = fetch_initial_state_data(self.user_profile, None, "", False)
        self.assertEqual(state_data['realm_plan_type'], Realm.LIMITED)
        self.assertEqual(state_data['zulip_plan_is_not_limited'], False)

    def test_realm_emoji_events(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('realm_emoji')),
            ('op', equals('update')),
            ('realm_emoji', check_dict([])),
        ])
        author = self.example_user('iago')
        with get_test_image_file('img.png') as img_file:
            events = self.do_test(lambda: check_add_realm_emoji(self.user_profile.realm,
                                                                "my_emoji",
                                                                author,
                                                                img_file))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_remove_realm_emoji(self.user_profile.realm, "my_emoji"))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_realm_filter_events(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('realm_filters')),
            ('realm_filters', check_list(None)),  # TODO: validate tuples in the list
        ])
        events = self.do_test(lambda: do_add_realm_filter(self.user_profile.realm, "#(?P<id>[123])",
                                                          "https://realm.com/my_realm_filter/%(id)s"))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_remove_realm_filter(self.user_profile.realm, "#(?P<id>[123])"))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_realm_domain_events(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('realm_domains')),
            ('op', equals('add')),
            ('realm_domain', check_dict_only([
                ('domain', check_string),
                ('allow_subdomains', check_bool),
            ])),
        ])
        events = self.do_test(lambda: do_add_realm_domain(
            self.user_profile.realm, 'zulip.org', False))
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
        test_domain = RealmDomain.objects.get(realm=self.user_profile.realm,
                                              domain='zulip.org')
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

    def test_create_bot(self) -> None:

        def get_bot_created_checker(bot_type: str) -> Validator:
            if bot_type == "GENERIC_BOT":
                check_services = check_list(sub_validator=None, length=0)
            elif bot_type == "OUTGOING_WEBHOOK_BOT":
                check_services = check_list(check_dict_only([
                    ('base_url', check_url),
                    ('interface', check_int),
                    ('token', check_string),
                ]), length=1)
            elif bot_type == "EMBEDDED_BOT":
                check_services = check_list(check_dict_only([
                    ('service_name', check_string),
                    ('config_data', check_dict(value_validator=check_string)),
                ]), length=1)
            return self.check_events_dict([
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
                    ('owner_id', check_int),
                    ('services', check_services),
                ])),
            ])
        action = lambda: self.create_bot('test')
        events = self.do_test(action, num_events=2)
        error = get_bot_created_checker(bot_type="GENERIC_BOT")('events[1]', events[1])
        self.assert_on_error(error)

        action = lambda: self.create_bot('test_outgoing_webhook',
                                         full_name='Outgoing Webhook Bot',
                                         payload_url=ujson.dumps('https://foo.bar.com'),
                                         interface_type=Service.GENERIC,
                                         bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)
        events = self.do_test(action, num_events=2)
        # The third event is the second call of notify_created_bot, which contains additional
        # data for services (in contrast to the first call).
        error = get_bot_created_checker(bot_type="OUTGOING_WEBHOOK_BOT")('events[1]', events[1])
        self.assert_on_error(error)

        action = lambda: self.create_bot('test_embedded',
                                         full_name='Embedded Bot',
                                         service_name='helloworld',
                                         config_data=ujson.dumps({'foo': 'bar'}),
                                         bot_type=UserProfile.EMBEDDED_BOT)
        events = self.do_test(action, num_events=2)
        error = get_bot_created_checker(bot_type="EMBEDDED_BOT")('events[1]', events[1])
        self.assert_on_error(error)

    def test_change_bot_full_name(self) -> None:
        bot = self.create_bot('test')
        action = lambda: do_change_full_name(bot, 'New Bot Name', self.user_profile)
        events = self.do_test(action, num_events=2)
        error = self.realm_bot_schema('full_name', check_string)('events[1]', events[1])
        self.assert_on_error(error)

    def test_regenerate_bot_api_key(self) -> None:
        bot = self.create_bot('test')
        action = lambda: do_regenerate_api_key(bot, self.user_profile)
        events = self.do_test(action)
        error = self.realm_bot_schema('api_key', check_string)('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_avatar_source(self) -> None:
        bot = self.create_bot('test')
        action = lambda: do_change_avatar_fields(bot, bot.AVATAR_FROM_USER)
        events = self.do_test(action, num_events=2)
        error = self.realm_bot_schema('avatar_url', check_string)('events[0]', events[0])
        self.assertEqual(events[1]['type'], 'realm_user')
        self.assert_on_error(error)

    def test_change_realm_icon_source(self) -> None:
        action = lambda: do_change_icon_source(self.user_profile.realm, Realm.ICON_UPLOADED)
        events = self.do_test(action, state_change_expected=True)
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

    def test_change_realm_day_mode_logo_source(self) -> None:
        action = lambda: do_change_logo_source(self.user_profile.realm, Realm.LOGO_UPLOADED, False)
        events = self.do_test(action, state_change_expected=True)
        schema_checker = self.check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update_dict')),
            ('property', equals('logo')),
            ('data', check_dict_only([
                ('logo_url', check_string),
                ('logo_source', check_string),
            ])),
        ])
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_realm_night_mode_logo_source(self) -> None:
        action = lambda: do_change_logo_source(self.user_profile.realm, Realm.LOGO_UPLOADED, True)
        events = self.do_test(action, state_change_expected=True)
        schema_checker = self.check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update_dict')),
            ('property', equals('night_logo')),
            ('data', check_dict_only([
                ('night_logo_url', check_string),
                ('night_logo_source', check_string),
            ])),
        ])
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_default_all_public_streams(self) -> None:
        bot = self.create_bot('test')
        action = lambda: do_change_default_all_public_streams(bot, True)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_all_public_streams', check_bool)('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_default_sending_stream(self) -> None:
        bot = self.create_bot('test')
        stream = get_stream("Rome", bot.realm)

        action = lambda: do_change_default_sending_stream(bot, stream)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_sending_stream', check_string)('events[0]', events[0])
        self.assert_on_error(error)

        action = lambda: do_change_default_sending_stream(bot, None)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_sending_stream', equals(None))('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_default_events_register_stream(self) -> None:
        bot = self.create_bot('test')
        stream = get_stream("Rome", bot.realm)

        action = lambda: do_change_default_events_register_stream(bot, stream)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_events_register_stream', check_string)('events[0]', events[0])
        self.assert_on_error(error)

        action = lambda: do_change_default_events_register_stream(bot, None)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_events_register_stream', equals(None))('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_owner(self) -> None:
        change_bot_owner_checker_user = self.check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict_only([
                ('user_id', check_int),
                ('bot_owner_id', check_int),
            ])),
        ])

        change_bot_owner_checker_bot = self.check_events_dict([
            ('type', equals('realm_bot')),
            ('op', equals('update')),
            ('bot', check_dict_only([
                ('user_id', check_int),
                ('owner_id', check_int),
            ])),
        ])
        self.user_profile = self.example_user('iago')
        owner = self.example_user('hamlet')
        bot = self.create_bot('test')
        action = lambda: do_change_bot_owner(bot, owner, self.user_profile)
        events = self.do_test(action, num_events=2)
        error = change_bot_owner_checker_bot('events[0]', events[0])
        self.assert_on_error(error)
        error = change_bot_owner_checker_user('events[1]', events[1])
        self.assert_on_error(error)

        change_bot_owner_checker_bot = self.check_events_dict([
            ('type', equals('realm_bot')),
            ('op', equals('delete')),
            ('bot', check_dict_only([
                ('user_id', check_int),
            ])),
        ])
        self.user_profile = self.example_user('aaron')
        owner = self.example_user('hamlet')
        bot = self.create_bot('test1', full_name='Test1 Testerson')
        action = lambda: do_change_bot_owner(bot, owner, self.user_profile)
        events = self.do_test(action, num_events=2)
        error = change_bot_owner_checker_bot('events[0]', events[0])
        self.assert_on_error(error)
        error = change_bot_owner_checker_user('events[1]', events[1])
        self.assert_on_error(error)

        check_services = check_list(sub_validator=None, length=0)
        change_bot_owner_checker_bot = self.check_events_dict([
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
                ('owner_id', check_int),
                ('services', check_services),
            ])),
        ])
        previous_owner = self.example_user('aaron')
        self.user_profile = self.example_user('hamlet')
        bot = self.create_test_bot('test2', previous_owner, full_name='Test2 Testerson')
        action = lambda: do_change_bot_owner(bot, self.user_profile, previous_owner)
        events = self.do_test(action, num_events=2)
        error = change_bot_owner_checker_bot('events[0]', events[0])
        self.assert_on_error(error)
        error = change_bot_owner_checker_user('events[1]', events[1])
        self.assert_on_error(error)

    def test_do_update_outgoing_webhook_service(self) -> None:
        update_outgoing_webhook_service_checker = self.check_events_dict([
            ('type', equals('realm_bot')),
            ('op', equals('update')),
            ('bot', check_dict_only([
                ('user_id', check_int),
                ('services', check_list(check_dict_only([
                    ('base_url', check_url),
                    ('interface', check_int),
                    ('token', check_string),
                ]))),
            ])),
        ])
        self.user_profile = self.example_user('iago')
        bot = self.create_test_bot('test', self.user_profile,
                                   full_name='Test Bot',
                                   bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                   payload_url=ujson.dumps('http://hostname.domain2.com'),
                                   interface_type=Service.GENERIC,
                                   )
        action = lambda: do_update_outgoing_webhook_service(bot, 2, 'http://hostname.domain2.com')
        events = self.do_test(action)
        error = update_outgoing_webhook_service_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_do_deactivate_user(self) -> None:
        bot_deactivate_checker = self.check_events_dict([
            ('type', equals('realm_bot')),
            ('op', equals('remove')),
            ('bot', check_dict_only([
                ('full_name', check_string),
                ('user_id', check_int),
            ])),
        ])
        bot = self.create_bot('test')
        action = lambda: do_deactivate_user(bot)
        events = self.do_test(action, num_events=2)
        error = bot_deactivate_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_do_reactivate_user(self) -> None:
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
                ('owner_id', check_none_or(check_int)),
                ('services', check_list(check_dict_only([
                    ('base_url', check_url),
                    ('interface', check_int),
                ]))),
            ])),
        ])
        bot = self.create_bot('test')
        do_deactivate_user(bot)
        action = lambda: do_reactivate_user(bot)
        events = self.do_test(action, num_events=2)
        error = bot_reactivate_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_do_mark_hotspot_as_read(self) -> None:
        self.user_profile.tutorial_status = UserProfile.TUTORIAL_WAITING
        self.user_profile.save(update_fields=['tutorial_status'])

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

    def test_rename_stream(self) -> None:
        stream = self.make_stream('old_name')
        new_name = 'stream with a brand new name'
        self.subscribe(self.user_profile, stream.name)
        notification = '<p><span class="user-mention silent" data-user-id="{user_id}">King Hamlet</span> renamed stream <strong>old_name</strong> to <strong>stream with a brand new name</strong>.</p>'
        notification = notification.format(user_id=self.user_profile.id)
        action = lambda: do_rename_stream(stream, new_name, self.user_profile)
        events = self.do_test(action, num_events=3)
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
        schema_checker = check_dict([
            ('flags', check_list(check_string)),
            ('type', equals('message')),
            ('message', check_dict([
                ('timestamp', check_int),
                ('content', equals(notification)),
                ('content_type', equals('text/html')),
                ('sender_email', equals('notification-bot@zulip.com')),
                ('sender_id', check_int),
                ('sender_short_name', equals('notification-bot')),
                ('display_recipient', equals(new_name)),
                ('id', check_int),
                ('stream_id', check_int),
                ('sender_realm_str', check_string),
                ('sender_full_name', equals('Notification Bot')),
                ('is_me_message', equals(False)),
                ('type', equals('stream')),
                ('submessages', check_list(check_string)),
                (TOPIC_LINKS, check_list(check_url)),
                ('avatar_url', check_none_or(check_url)),
                ('reactions', check_list(None)),
                ('client', equals('Internal')),
                (TOPIC_NAME, equals('stream events')),
                ('recipient_id', check_int)
            ])),
            ('id', check_int)
        ])
        error = schema_checker('events[2]', events[2])
        self.assert_on_error(error)

    def test_deactivate_stream_neversubscribed(self) -> None:
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

    def test_subscribe_other_user_never_subscribed(self) -> None:
        action = lambda: self.subscribe(self.example_user("othello"), "test_stream")
        events = self.do_test(action, num_events=2)
        peer_add_schema_checker = self.check_events_dict([
            ('type', equals('subscription')),
            ('op', equals('peer_add')),
            ('user_id', check_int),
            ('subscriptions', check_list(check_string)),
        ])
        error = peer_add_schema_checker('events[1]', events[1])
        self.assert_on_error(error)

    @slow("Actually several tests combined together")
    def test_subscribe_events(self) -> None:
        self.do_test_subscribe_events(include_subscribers=True)

    @slow("Actually several tests combined together")
    def test_subscribe_events_no_include_subscribers(self) -> None:
        self.do_test_subscribe_events(include_subscribers=False)

    def do_test_subscribe_events(self, include_subscribers: bool) -> None:
        subscription_fields = [
            ('color', check_string),
            ('description', check_string),
            ('rendered_description', check_string),
            ('email_address', check_string),
            ('invite_only', check_bool),
            ('is_web_public', check_bool),
            ('is_announcement_only', check_bool),
            ('stream_post_policy', check_int_in(Stream.STREAM_POST_POLICY_TYPES)),
            ('is_muted', check_bool),
            ('in_home_view', check_bool),
            ('name', check_string),
            ('audible_notifications', check_none_or(check_bool)),
            ('email_notifications', check_none_or(check_bool)),
            ('desktop_notifications', check_none_or(check_bool)),
            ('push_notifications', check_none_or(check_bool)),
            ('stream_id', check_int),
            ('first_message_id', check_none_or(check_int)),
            ('history_public_to_subscribers', check_bool),
            ('pin_to_top', check_bool),
            ('stream_weekly_traffic', check_none_or(check_int)),
            ('is_old_stream', check_bool),
            ('wildcard_mentions_notify', check_none_or(check_bool)),
        ]
        if include_subscribers:
            subscription_fields.append(('subscribers', check_list(check_int)))
        subscription_schema_checker = check_list(
            check_dict_only(subscription_fields),
        )
        stream_create_schema_checker = self.check_events_dict([
            ('type', equals('stream')),
            ('op', equals('create')),
            ('streams', check_list(check_dict_only([
                ('name', check_string),
                ('stream_id', check_int),
                ('invite_only', check_bool),
                ('description', check_string),
                ('rendered_description', check_string),
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
            ('rendered_description', check_string),
            ('stream_id', check_int),
            ('name', check_string),
        ])
        stream_update_invite_only_schema_checker = self.check_events_dict([
            ('type', equals('stream')),
            ('op', equals('update')),
            ('property', equals('invite_only')),
            ('stream_id', check_int),
            ('name', check_string),
            ('value', check_bool),
            ('history_public_to_subscribers', check_bool),
        ])
        stream_update_stream_post_policy_schema_checker = self.check_events_dict([
            ('type', equals('stream')),
            ('op', equals('update')),
            ('property', equals('stream_post_policy')),
            ('stream_id', check_int),
            ('name', check_string),
            ('value', check_int_in(Stream.STREAM_POST_POLICY_TYPES)),
        ])

        # Subscribe to a totally new stream, so it's just Hamlet on it
        action: Callable[[], object] = lambda: self.subscribe(self.example_user("hamlet"), "test_stream")
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
            [stream],
            get_client("website"))
        events = self.do_test(action,
                              include_subscribers=include_subscribers,
                              state_change_expected=include_subscribers,
                              )
        error = peer_remove_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Now remove the second user, to test the 'vacate' event flow
        action = lambda: bulk_remove_subscriptions(
            [self.example_user('hamlet')],
            [stream],
            get_client("website"))
        events = self.do_test(action,
                              include_subscribers=include_subscribers,
                              num_events=3)
        error = remove_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Now resubscribe a user, to make sure that works on a vacated stream
        action = lambda: self.subscribe(self.example_user("hamlet"), "test_stream")
        events = self.do_test(action,
                              include_subscribers=include_subscribers,
                              num_events=2)
        error = add_schema_checker('events[1]', events[1])
        self.assert_on_error(error)

        action = lambda: do_change_stream_description(stream, 'new description')
        events = self.do_test(action,
                              include_subscribers=include_subscribers)
        error = stream_update_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Update stream privacy
        action = lambda: do_change_stream_invite_only(stream, True, history_public_to_subscribers=True)
        events = self.do_test(action,
                              include_subscribers=include_subscribers)
        error = stream_update_invite_only_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Update stream stream_post_policy property
        action = lambda: do_change_stream_post_policy(stream, Stream.STREAM_POST_POLICY_ADMINS)
        events = self.do_test(action,
                              include_subscribers=include_subscribers, num_events=2)
        error = stream_update_stream_post_policy_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Subscribe to a totally new invite-only stream, so it's just Hamlet on it
        stream = self.make_stream("private", self.user_profile.realm, invite_only=True)
        user_profile = self.example_user('hamlet')
        action = lambda: bulk_add_subscriptions([stream], [user_profile])
        events = self.do_test(action, include_subscribers=include_subscribers,
                              num_events=2)
        error = stream_create_schema_checker('events[0]', events[0])
        error = add_schema_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_do_delete_message_stream(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('delete_message')),
            ('message_id', check_int),
            ('sender', check_string),
            ('sender_id', check_int),
            ('message_type', equals("stream")),
            ('stream_id', check_int),
            ('topic', check_string),
        ])
        hamlet = self.example_user('hamlet')
        msg_id = self.send_stream_message(hamlet, "Verona")
        message = Message.objects.get(id=msg_id)
        events = self.do_test(
            lambda: do_delete_messages(self.user_profile.realm, [message]),
            state_change_expected=True,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_do_delete_message_personal(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('delete_message')),
            ('message_id', check_int),
            ('sender', check_string),
            ('sender_id', check_int),
            ('message_type', equals("private")),
            ('recipient_id', check_int),
        ])
        msg_id = self.send_personal_message(
            self.example_user("cordelia"),
            self.user_profile,
            "hello",
        )
        message = Message.objects.get(id=msg_id)
        events = self.do_test(
            lambda: do_delete_messages(self.user_profile.realm, [message]),
            state_change_expected=True,
        )
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_do_delete_message_no_max_id(self) -> None:
        user_profile = self.example_user('aaron')
        # Delete all historical messages for this user
        user_profile = self.example_user('hamlet')
        UserMessage.objects.filter(user_profile=user_profile).delete()
        msg_id = self.send_stream_message(user_profile, "Verona")
        message = Message.objects.get(id=msg_id)
        self.do_test(
            lambda: do_delete_messages(self.user_profile.realm, [message]),
            state_change_expected=True,
        )
        result = fetch_initial_state_data(user_profile, None, "", client_gravatar=False)
        self.assertEqual(result['max_message_id'], -1)

    def test_add_attachment(self) -> None:
        schema_checker = self.check_events_dict([
            ('type', equals('attachment')),
            ('op', equals('add')),
            ('attachment', check_dict_only([
                ('id', check_int),
                ('name', check_string),
                ('size', check_int),
                ('path_id', check_string),
                ('create_time', check_float),
                ('messages', check_list(check_dict_only([
                    ('id', check_int),
                    ('name', check_float),
                ]))),
            ])),
            ('upload_space_used', equals(6)),
        ])

        self.login('hamlet')
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        data = {'uri': None}

        def do_upload() -> None:
            result = self.client_post("/json/user_uploads", {'file': fp})

            self.assert_json_success(result)
            self.assertIn("uri", result.json())
            uri = result.json()["uri"]
            base = '/user_uploads/'
            self.assertEqual(base, uri[:len(base)])
            data['uri'] = uri

        events = self.do_test(
            lambda: do_upload(),
            num_events=1, state_change_expected=False)
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Verify that the DB has the attachment marked as unclaimed
        entry = Attachment.objects.get(file_name='zulip.txt')
        self.assertEqual(entry.is_claimed(), False)

        # Now we send an actual message using this attachment.
        schema_checker = self.check_events_dict([
            ('type', equals('attachment')),
            ('op', equals('update')),
            ('attachment', check_dict_only([
                ('id', check_int),
                ('name', check_string),
                ('size', check_int),
                ('path_id', check_string),
                ('create_time', check_float),
                ('messages', check_list(check_dict_only([
                    ('id', check_int),
                    ('name', check_float),
                ]))),
            ])),
            ('upload_space_used', equals(6)),
        ])

        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "Denmark")
        body = "First message ...[zulip.txt](http://{}".format(hamlet.realm.host) + data['uri'] + ")"
        events = self.do_test(
            lambda: self.send_stream_message(self.example_user("hamlet"), "Denmark", body, "test"),
            num_events=2)
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # Now remove the attachment
        schema_checker = self.check_events_dict([
            ('type', equals('attachment')),
            ('op', equals('remove')),
            ('attachment', check_dict_only([
                ('id', check_int),
            ])),
            ('upload_space_used', equals(0)),
        ])

        events = self.do_test(
            lambda: self.client_delete("/json/attachments/%s" % (entry.id,)),
            num_events=1, state_change_expected=False)
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_notify_realm_export(self) -> None:
        pending_schema_checker = self.check_events_dict([
            ('type', equals('realm_export')),
            ('exports', check_list(check_dict_only([
                ('id', check_int),
                ('export_time', check_float),
                ('acting_user_id', check_int),
                ('export_url', equals(None)),
                ('deleted_timestamp', equals(None)),
                ('failed_timestamp', equals(None)),
                ('pending', check_bool),
            ]))),
        ])

        schema_checker = self.check_events_dict([
            ('type', equals('realm_export')),
            ('exports', check_list(check_dict_only([
                ('id', check_int),
                ('export_time', check_float),
                ('acting_user_id', check_int),
                ('export_url', check_string),
                ('deleted_timestamp', equals(None)),
                ('failed_timestamp', equals(None)),
                ('pending', check_bool),
            ]))),
        ])

        do_change_user_role(self.user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login_user(self.user_profile)

        with mock.patch('zerver.lib.export.do_export_realm',
                        return_value=create_dummy_file('test-export.tar.gz')):
            with stdout_suppressed():
                events = self.do_test(
                    lambda: self.client_post('/json/export/realm'),
                    state_change_expected=True, num_events=3)

        # We first notify when an export is initiated,
        error = pending_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        # The second event is then a message from notification-bot.
        error = schema_checker('events[2]', events[2])
        self.assert_on_error(error)

        # Now we check the deletion of the export.
        deletion_schema_checker = self.check_events_dict([
            ('type', equals('realm_export')),
            ('exports', check_list(check_dict_only([
                ('id', check_int),
                ('export_time', check_float),
                ('acting_user_id', check_int),
                ('export_url', equals(None)),
                ('deleted_timestamp', check_float),
                ('failed_timestamp', equals(None)),
                ('pending', check_bool),
            ]))),
        ])

        audit_log_entry = RealmAuditLog.objects.filter(
            event_type=RealmAuditLog.REALM_EXPORTED).first()
        events = self.do_test(
            lambda: self.client_delete('/json/export/realm/{id}'.format(id=audit_log_entry.id)),
            state_change_expected=False, num_events=1)
        error = deletion_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_notify_realm_export_on_failure(self) -> None:
        pending_schema_checker = self.check_events_dict([
            ('type', equals('realm_export')),
            ('exports', check_list(check_dict_only([
                ('id', check_int),
                ('export_time', check_float),
                ('acting_user_id', check_int),
                ('export_url', equals(None)),
                ('deleted_timestamp', equals(None)),
                ('failed_timestamp', equals(None)),
                ('pending', check_bool),
            ]))),
        ])

        failed_schema_checker = self.check_events_dict([
            ('type', equals('realm_export')),
            ('exports', check_list(check_dict_only([
                ('id', check_int),
                ('export_time', check_float),
                ('acting_user_id', check_int),
                ('export_url', equals(None)),
                ('deleted_timestamp', equals(None)),
                ('failed_timestamp', check_float),
                ('pending', check_bool),
            ]))),
        ])

        do_change_user_role(self.user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login_user(self.user_profile)

        with mock.patch('zerver.lib.export.do_export_realm',
                        side_effect=Exception("test")):
            with stdout_suppressed():
                events = self.do_test(
                    lambda: self.client_post('/json/export/realm'),
                    state_change_expected=False, num_events=2)

        error = pending_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        error = failed_schema_checker('events[1]', events[1])
        self.assert_on_error(error)

class FetchInitialStateDataTest(ZulipTestCase):
    # Non-admin users don't have access to all bots
    def test_realm_bots_non_admin(self) -> None:
        user_profile = self.example_user('cordelia')
        self.assertFalse(user_profile.is_realm_admin)
        result = fetch_initial_state_data(user_profile, None, "", client_gravatar=False)
        self.assert_length(result['realm_bots'], 0)

        # additionally the API key for a random bot is not present in the data
        api_key = get_api_key(self.notification_bot())
        self.assertNotIn(api_key, str(result))

    # Admin users have access to all bots in the realm_bots field
    def test_realm_bots_admin(self) -> None:
        user_profile = self.example_user('hamlet')
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.assertTrue(user_profile.is_realm_admin)
        result = fetch_initial_state_data(user_profile, None, "", client_gravatar=False)
        self.assertTrue(len(result['realm_bots']) > 2)

    def test_max_message_id_with_no_history(self) -> None:
        user_profile = self.example_user('aaron')
        # Delete all historical messages for this user
        UserMessage.objects.filter(user_profile=user_profile).delete()
        result = fetch_initial_state_data(user_profile, None, "", client_gravatar=False)
        self.assertEqual(result['max_message_id'], -1)

    def test_delivery_email_presence_for_non_admins(self) -> None:
        user_profile = self.example_user('aaron')
        self.assertFalse(user_profile.is_realm_admin)

        do_set_realm_property(user_profile.realm, "email_address_visibility",
                              Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE)
        result = fetch_initial_state_data(user_profile, None, "", client_gravatar=False)
        for key, value in result['raw_users'].items():
            self.assertNotIn('delivery_email', value)

        do_set_realm_property(user_profile.realm, "email_address_visibility",
                              Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS)
        result = fetch_initial_state_data(user_profile, None, "", client_gravatar=False)
        for key, value in result['raw_users'].items():
            self.assertNotIn('delivery_email', value)

    def test_delivery_email_presence_for_admins(self) -> None:
        user_profile = self.example_user('iago')
        self.assertTrue(user_profile.is_realm_admin)

        do_set_realm_property(user_profile.realm, "email_address_visibility",
                              Realm.EMAIL_ADDRESS_VISIBILITY_EVERYONE)
        result = fetch_initial_state_data(user_profile, None, "", client_gravatar=False)
        for key, value in result['raw_users'].items():
            self.assertNotIn('delivery_email', value)

        do_set_realm_property(user_profile.realm, "email_address_visibility",
                              Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS)
        result = fetch_initial_state_data(user_profile, None, "", client_gravatar=False)
        for key, value in result['raw_users'].items():
            self.assertIn('delivery_email', value)


class GetUnreadMsgsTest(ZulipTestCase):
    def mute_stream(self, user_profile: UserProfile, stream: Stream) -> None:
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        subscription = Subscription.objects.get(
            user_profile=user_profile,
            recipient=recipient
        )
        subscription.is_muted = True
        subscription.save()

    def mute_topic(self, user_profile: UserProfile, stream_name: str,
                   topic_name: str) -> None:
        realm = user_profile.realm
        stream = get_stream(stream_name, realm)
        recipient = stream.recipient

        add_topic_mute(
            user_profile=user_profile,
            stream_id=stream.id,
            recipient_id=recipient.id,
            topic_name=topic_name,
        )

    def test_raw_unread_stream(self) -> None:
        cordelia = self.example_user('cordelia')
        hamlet = self.example_user('hamlet')
        realm = hamlet.realm

        for stream_name in ['social', 'devel', 'test here']:
            self.subscribe(hamlet, stream_name)
            self.subscribe(cordelia, stream_name)

        all_message_ids: Set[int] = set()
        message_ids = dict()

        tups = [
            ('social', 'lunch'),
            ('test here', 'bla'),
            ('devel', 'python'),
            ('devel', 'ruby'),
        ]

        for stream_name, topic_name in tups:
            message_ids[topic_name] = [
                self.send_stream_message(
                    sender=cordelia,
                    stream_name=stream_name,
                    topic_name=topic_name,
                ) for i in range(3)
            ]
            all_message_ids |= set(message_ids[topic_name])

        self.assertEqual(len(all_message_ids), 12)  # sanity check on test setup

        self.mute_stream(
            user_profile=hamlet,
            stream=get_stream('test here', realm),
        )

        self.mute_topic(
            user_profile=hamlet,
            stream_name='devel',
            topic_name='ruby',
        )

        raw_unread_data = get_raw_unread_data(
            user_profile=hamlet,
        )

        stream_dict = raw_unread_data['stream_dict']

        self.assertEqual(
            set(stream_dict.keys()),
            all_message_ids,
        )

        self.assertEqual(
            raw_unread_data['unmuted_stream_msgs'],
            set(message_ids['python']) | set(message_ids['lunch']),
        )

        self.assertEqual(
            stream_dict[message_ids['lunch'][0]],
            dict(
                sender_id=cordelia.id,
                stream_id=get_stream('social', realm).id,
                topic='lunch',
            )
        )

    def test_raw_unread_huddle(self) -> None:
        cordelia = self.example_user('cordelia')
        othello = self.example_user('othello')
        hamlet = self.example_user('hamlet')
        prospero = self.example_user('prospero')

        huddle1_message_ids = [
            self.send_huddle_message(
                cordelia,
                [hamlet, othello]
            )
            for i in range(3)
        ]

        huddle2_message_ids = [
            self.send_huddle_message(
                cordelia,
                [hamlet, prospero]
            )
            for i in range(3)
        ]

        raw_unread_data = get_raw_unread_data(
            user_profile=hamlet,
        )

        huddle_dict = raw_unread_data['huddle_dict']

        self.assertEqual(
            set(huddle_dict.keys()),
            set(huddle1_message_ids) | set(huddle2_message_ids)
        )

        huddle_string = ','.join(
            str(uid)
            for uid in sorted([cordelia.id, hamlet.id, othello.id])
        )

        self.assertEqual(
            huddle_dict[huddle1_message_ids[0]],
            dict(user_ids_string=huddle_string),
        )

    def test_raw_unread_personal(self) -> None:
        cordelia = self.example_user('cordelia')
        othello = self.example_user('othello')
        hamlet = self.example_user('hamlet')

        cordelia_pm_message_ids = [
            self.send_personal_message(cordelia, hamlet)
            for i in range(3)
        ]

        othello_pm_message_ids = [
            self.send_personal_message(othello, hamlet)
            for i in range(3)
        ]

        raw_unread_data = get_raw_unread_data(
            user_profile=hamlet,
        )

        pm_dict = raw_unread_data['pm_dict']

        self.assertEqual(
            set(pm_dict.keys()),
            set(cordelia_pm_message_ids) | set(othello_pm_message_ids)
        )

        self.assertEqual(
            pm_dict[cordelia_pm_message_ids[0]],
            dict(sender_id=cordelia.id),
        )

    def test_raw_unread_personal_from_self(self) -> None:
        hamlet = self.example_user('hamlet')

        def send_unread_pm(other_user: UserProfile) -> Message:
            # It is rare to send a message from Hamlet to Othello
            # (or any other user) and have it be unread for
            # Hamlet himself, but that is actually normal
            # behavior for most API clients.
            message_id = self.send_personal_message(
                from_user=hamlet,
                to_user=other_user,
                sending_client_name='some_api_program',
            )

            # Check our test setup is correct--the message should
            # not have looked like it was sent by a human.
            message = Message.objects.get(id=message_id)
            self.assertFalse(message.sent_by_human())

            # And since it was not sent by a human, it should not
            # be read, not even by the sender (Hamlet).
            um = UserMessage.objects.get(
                user_profile_id=hamlet.id,
                message_id=message_id,
            )
            self.assertFalse(um.flags.read)

            return message

        othello = self.example_user('othello')
        othello_msg = send_unread_pm(other_user=othello)

        # And now check the unread data structure...
        raw_unread_data = get_raw_unread_data(
            user_profile=hamlet,
        )

        pm_dict = raw_unread_data['pm_dict']

        self.assertEqual(set(pm_dict.keys()), {othello_msg.id})

        # For legacy reason we call the field `sender_id` here,
        # but it really refers to the other user id in the conversation,
        # which is Othello.
        self.assertEqual(
            pm_dict[othello_msg.id],
            dict(sender_id=othello.id),
        )

        cordelia = self.example_user('cordelia')
        cordelia_msg = send_unread_pm(other_user=cordelia)

        apply_unread_message_event(
            user_profile=hamlet,
            state=raw_unread_data,
            message=MessageDict.wide_dict(cordelia_msg),
            flags=[],
        )
        self.assertEqual(
            set(pm_dict.keys()),
            {othello_msg.id, cordelia_msg.id}
        )

        # Again, `sender_id` is misnamed here.
        self.assertEqual(
            pm_dict[cordelia_msg.id],
            dict(sender_id=cordelia.id),
        )

        # Send a message to ourself.
        hamlet_msg = send_unread_pm(other_user=hamlet)
        apply_unread_message_event(
            user_profile=hamlet,
            state=raw_unread_data,
            message=MessageDict.wide_dict(hamlet_msg),
            flags=[],
        )
        self.assertEqual(
            set(pm_dict.keys()),
            {othello_msg.id, cordelia_msg.id, hamlet_msg.id}
        )

        # Again, `sender_id` is misnamed here.
        self.assertEqual(
            pm_dict[hamlet_msg.id],
            dict(sender_id=hamlet.id),
        )

        # Call get_raw_unread_data again.
        raw_unread_data = get_raw_unread_data(
            user_profile=hamlet,
        )
        pm_dict = raw_unread_data['pm_dict']

        self.assertEqual(
            set(pm_dict.keys()),
            {othello_msg.id, cordelia_msg.id, hamlet_msg.id}
        )

        # Again, `sender_id` is misnamed here.
        self.assertEqual(
            pm_dict[hamlet_msg.id],
            dict(sender_id=hamlet.id),
        )

    def test_unread_msgs(self) -> None:
        sender = self.example_user('cordelia')
        sender_id = sender.id
        user_profile = self.example_user('hamlet')
        othello = self.example_user('othello')

        pm1_message_id = self.send_personal_message(sender, user_profile, "hello1")
        pm2_message_id = self.send_personal_message(sender, user_profile, "hello2")

        muted_stream = self.subscribe(user_profile, 'Muted Stream')
        self.mute_stream(user_profile, muted_stream)
        self.mute_topic(user_profile, 'Denmark', 'muted-topic')

        stream_message_id = self.send_stream_message(sender, "Denmark", "hello")
        muted_stream_message_id = self.send_stream_message(sender, "Muted Stream", "hello")
        muted_topic_message_id = self.send_stream_message(
            sender,
            "Denmark",
            topic_name="muted-topic",
            content="hello",
        )

        huddle_message_id = self.send_huddle_message(
            sender,
            [user_profile, othello],
            'hello3',
        )

        def get_unread_data() -> UnreadMessagesResult:
            raw_unread_data = get_raw_unread_data(user_profile)
            aggregated_data = aggregate_unread_data(raw_unread_data)
            return aggregated_data

        result = get_unread_data()

        # The count here reflects the count of unread messages that we will
        # report to users in the bankruptcy dialog, and for now it excludes unread messages
        # from muted treams, but it doesn't exclude unread messages from muted topics yet.
        self.assertEqual(result['count'], 4)

        unread_pm = result['pms'][0]
        self.assertEqual(unread_pm['sender_id'], sender_id)
        self.assertEqual(unread_pm['unread_message_ids'], [pm1_message_id, pm2_message_id])
        self.assertTrue('sender_ids' not in unread_pm)

        unread_stream = result['streams'][0]
        self.assertEqual(unread_stream['stream_id'], get_stream('Denmark', user_profile.realm).id)
        self.assertEqual(unread_stream['topic'], 'muted-topic')
        self.assertEqual(unread_stream['unread_message_ids'], [muted_topic_message_id])
        self.assertEqual(unread_stream['sender_ids'], [sender_id])

        unread_stream = result['streams'][1]
        self.assertEqual(unread_stream['stream_id'], get_stream('Denmark', user_profile.realm).id)
        self.assertEqual(unread_stream['topic'], 'test')
        self.assertEqual(unread_stream['unread_message_ids'], [stream_message_id])
        self.assertEqual(unread_stream['sender_ids'], [sender_id])

        unread_stream = result['streams'][2]
        self.assertEqual(unread_stream['stream_id'], get_stream('Muted Stream', user_profile.realm).id)
        self.assertEqual(unread_stream['topic'], 'test')
        self.assertEqual(unread_stream['unread_message_ids'], [muted_stream_message_id])
        self.assertEqual(unread_stream['sender_ids'], [sender_id])

        huddle_string = ','.join(str(uid) for uid in sorted([sender_id, user_profile.id, othello.id]))

        unread_huddle = result['huddles'][0]
        self.assertEqual(unread_huddle['user_ids_string'], huddle_string)
        self.assertEqual(unread_huddle['unread_message_ids'], [huddle_message_id])
        self.assertTrue('sender_ids' not in unread_huddle)

        self.assertEqual(result['mentions'], [])

        um = UserMessage.objects.get(
            user_profile_id=user_profile.id,
            message_id=stream_message_id
        )
        um.flags |= UserMessage.flags.mentioned
        um.save()
        result = get_unread_data()
        self.assertEqual(result['mentions'], [stream_message_id])

        um.flags = UserMessage.flags.has_alert_word
        um.save()
        result = get_unread_data()
        # TODO: This should change when we make alert words work better.
        self.assertEqual(result['mentions'], [])

        um.flags = UserMessage.flags.wildcard_mentioned
        um.save()
        result = get_unread_data()
        self.assertEqual(result['mentions'], [stream_message_id])

        um.flags = 0
        um.save()
        result = get_unread_data()
        self.assertEqual(result['mentions'], [])

        # Test with a muted stream
        um = UserMessage.objects.get(
            user_profile_id=user_profile.id,
            message_id=muted_stream_message_id
        )
        um.flags = UserMessage.flags.mentioned
        um.save()
        result = get_unread_data()
        self.assertEqual(result['mentions'], [muted_stream_message_id])

        um.flags = UserMessage.flags.has_alert_word
        um.save()
        result = get_unread_data()
        self.assertEqual(result['mentions'], [])

        um.flags = UserMessage.flags.wildcard_mentioned
        um.save()
        result = get_unread_data()
        self.assertEqual(result['mentions'], [])

        um.flags = 0
        um.save()
        result = get_unread_data()
        self.assertEqual(result['mentions'], [])

        # Test with a muted topic
        um = UserMessage.objects.get(
            user_profile_id=user_profile.id,
            message_id=muted_topic_message_id
        )
        um.flags = UserMessage.flags.mentioned
        um.save()
        result = get_unread_data()
        self.assertEqual(result['mentions'], [muted_topic_message_id])

        um.flags = UserMessage.flags.has_alert_word
        um.save()
        result = get_unread_data()
        self.assertEqual(result['mentions'], [])

        um.flags = UserMessage.flags.wildcard_mentioned
        um.save()
        result = get_unread_data()
        self.assertEqual(result['mentions'], [])

        um.flags = 0
        um.save()
        result = get_unread_data()
        self.assertEqual(result['mentions'], [])

class ClientDescriptorsTest(ZulipTestCase):
    def test_get_client_info_for_all_public_streams(self) -> None:
        hamlet = self.example_user('hamlet')
        realm = hamlet.realm

        queue_data = dict(
            all_public_streams=True,
            apply_markdown=True,
            client_gravatar=True,
            client_type_name='website',
            event_types=['message'],
            last_connection_time=time.time(),
            queue_timeout=0,
            realm_id=realm.id,
            user_profile_id=hamlet.id,
        )

        client = allocate_client_descriptor(queue_data)

        message_event = dict(
            realm_id=realm.id,
            stream_name='whatever',
        )

        client_info = get_client_info_for_message_event(
            message_event,
            users=[],
        )

        self.assertEqual(len(client_info), 1)

        dct = client_info[client.event_queue.id]
        self.assertEqual(dct['client'].apply_markdown, True)
        self.assertEqual(dct['client'].client_gravatar, True)
        self.assertEqual(dct['client'].user_profile_id, hamlet.id)
        self.assertEqual(dct['flags'], [])
        self.assertEqual(dct['is_sender'], False)

        message_event = dict(
            realm_id=realm.id,
            stream_name='whatever',
            sender_queue_id=client.event_queue.id,
        )

        client_info = get_client_info_for_message_event(
            message_event,
            users=[],
        )
        dct = client_info[client.event_queue.id]
        self.assertEqual(dct['is_sender'], True)

    def test_get_client_info_for_normal_users(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        realm = hamlet.realm

        def test_get_info(apply_markdown: bool, client_gravatar: bool) -> None:
            clear_client_event_queues_for_testing()

            queue_data = dict(
                all_public_streams=False,
                apply_markdown=apply_markdown,
                client_gravatar=client_gravatar,
                client_type_name='website',
                event_types=['message'],
                last_connection_time=time.time(),
                queue_timeout=0,
                realm_id=realm.id,
                user_profile_id=hamlet.id,
            )

            client = allocate_client_descriptor(queue_data)
            message_event = dict(
                realm_id=realm.id,
                stream_name='whatever',
            )

            client_info = get_client_info_for_message_event(
                message_event,
                users=[
                    dict(id=cordelia.id),
                ],
            )

            self.assertEqual(len(client_info), 0)

            client_info = get_client_info_for_message_event(
                message_event,
                users=[
                    dict(id=cordelia.id),
                    dict(id=hamlet.id, flags=['mentioned']),
                ],
            )
            self.assertEqual(len(client_info), 1)

            dct = client_info[client.event_queue.id]
            self.assertEqual(dct['client'].apply_markdown, apply_markdown)
            self.assertEqual(dct['client'].client_gravatar, client_gravatar)
            self.assertEqual(dct['client'].user_profile_id, hamlet.id)
            self.assertEqual(dct['flags'], ['mentioned'])
            self.assertEqual(dct['is_sender'], False)

        test_get_info(apply_markdown=False, client_gravatar=False)
        test_get_info(apply_markdown=True, client_gravatar=False)

        test_get_info(apply_markdown=False, client_gravatar=True)
        test_get_info(apply_markdown=True, client_gravatar=True)

    def test_process_message_event_with_mocked_client_info(self) -> None:
        hamlet = self.example_user("hamlet")

        class MockClient:
            def __init__(self, user_profile_id: int,
                         apply_markdown: bool,
                         client_gravatar: bool) -> None:
                self.user_profile_id = user_profile_id
                self.apply_markdown = apply_markdown
                self.client_gravatar = client_gravatar
                self.client_type_name = 'whatever'
                self.events: List[Dict[str, Any]] = []

            def accepts_messages(self) -> bool:
                return True

            def accepts_event(self, event: Dict[str, Any]) -> bool:
                assert(event['type'] == 'message')
                return True

            def add_event(self, event: Dict[str, Any]) -> None:
                self.events.append(event)

        client1 = MockClient(
            user_profile_id=hamlet.id,
            apply_markdown=True,
            client_gravatar=False,
        )

        client2 = MockClient(
            user_profile_id=hamlet.id,
            apply_markdown=False,
            client_gravatar=False,
        )

        client3 = MockClient(
            user_profile_id=hamlet.id,
            apply_markdown=True,
            client_gravatar=True,
        )

        client4 = MockClient(
            user_profile_id=hamlet.id,
            apply_markdown=False,
            client_gravatar=True,
        )

        client_info = {
            'client:1': dict(
                client=client1,
                flags=['starred'],
            ),
            'client:2': dict(
                client=client2,
                flags=['has_alert_word'],
            ),
            'client:3': dict(
                client=client3,
                flags=[],
            ),
            'client:4': dict(
                client=client4,
                flags=[],
            ),
        }

        sender = hamlet

        message_event = dict(
            message_dict=dict(
                id=999,
                content='**hello**',
                rendered_content='<b>hello</b>',
                sender_id=sender.id,
                type='stream',
                client='website',

                # NOTE: Some of these fields are clutter, but some
                #       will be useful when we let clients specify
                #       that they can compute their own gravatar URLs.
                sender_email=sender.email,
                sender_delivery_email=sender.delivery_email,
                sender_realm_id=sender.realm_id,
                sender_avatar_source=UserProfile.AVATAR_FROM_GRAVATAR,
                sender_avatar_version=1,
                sender_is_mirror_dummy=None,
                recipient_type=None,
                recipient_type_id=None,
            ),
        )

        # Setting users to `[]` bypasses code we don't care about
        # for this test--we assume client_info is correct in our mocks,
        # and we are interested in how messages are put on event queue.
        users: List[Dict[str, Any]] = []

        with mock.patch('zerver.tornado.event_queue.get_client_info_for_message_event',
                        return_value=client_info):
            process_message_event(message_event, users)

        # We are not closely examining avatar_url at this point, so
        # just sanity check them and then delete the keys so that
        # upcoming comparisons work.
        for client in [client1, client2]:
            message = client.events[0]['message']
            self.assertIn('gravatar.com', message['avatar_url'])
            message.pop('avatar_url')

        self.assertEqual(client1.events, [
            dict(
                type='message',
                message=dict(
                    type='stream',
                    sender_id=sender.id,
                    sender_email=sender.email,
                    id=999,
                    content='<b>hello</b>',
                    content_type='text/html',
                    client='website',
                ),
                flags=['starred'],
            ),
        ])

        self.assertEqual(client2.events, [
            dict(
                type='message',
                message=dict(
                    type='stream',
                    sender_id=sender.id,
                    sender_email=sender.email,
                    id=999,
                    content='**hello**',
                    content_type='text/x-markdown',
                    client='website',
                ),
                flags=['has_alert_word'],
            ),
        ])

        self.assertEqual(client3.events, [
            dict(
                type='message',
                message=dict(
                    type='stream',
                    sender_id=sender.id,
                    sender_email=sender.email,
                    avatar_url=None,
                    id=999,
                    content='<b>hello</b>',
                    content_type='text/html',
                    client='website',
                ),
                flags=[],
            ),
        ])

        self.assertEqual(client4.events, [
            dict(
                type='message',
                message=dict(
                    type='stream',
                    sender_id=sender.id,
                    sender_email=sender.email,
                    avatar_url=None,
                    id=999,
                    content='**hello**',
                    content_type='text/x-markdown',
                    client='website',
                ),
                flags=[],
            ),
        ])

class FetchQueriesTest(ZulipTestCase):
    def test_queries(self) -> None:
        user = self.example_user("hamlet")

        self.login_user(user)

        flush_per_request_caches()
        with queries_captured() as queries:
            with mock.patch('zerver.lib.events.always_want') as want_mock:
                fetch_initial_state_data(
                    user_profile=user,
                    event_types=None,
                    queue_id='x',
                    client_gravatar=False,
                )

        self.assert_length(queries, 30)

        expected_counts = dict(
            alert_words=1,
            custom_profile_fields=1,
            default_streams=1,
            default_stream_groups=1,
            hotspots=0,
            message=1,
            muted_topics=1,
            pointer=0,
            presence=1,
            realm=0,
            realm_bot=1,
            realm_domains=1,
            realm_embedded_bots=0,
            realm_incoming_webhook_bots=0,
            realm_emoji=1,
            realm_filters=1,
            realm_user=3,
            realm_user_groups=2,
            recent_private_conversations=1,
            starred_messages=1,
            stream=2,
            stop_words=0,
            subscription=5,
            update_display_settings=0,
            update_global_notifications=0,
            update_message_flags=5,
            user_status=1,
        )

        wanted_event_types = {
            item[0][0] for item
            in want_mock.call_args_list
        }

        self.assertEqual(wanted_event_types, set(expected_counts))

        for event_type in sorted(wanted_event_types):
            count = expected_counts[event_type]
            flush_per_request_caches()
            with queries_captured() as queries:
                if event_type == 'update_message_flags':
                    event_types = ['update_message_flags', 'message']
                else:
                    event_types = [event_type]

                fetch_initial_state_data(
                    user_profile=user,
                    event_types=event_types,
                    queue_id='x',
                    client_gravatar=False,
                )
            self.assert_length(queries, count)


class TestEventsRegisterAllPublicStreamsDefaults(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email

    def test_use_passed_all_public_true_default_false(self) -> None:
        self.user_profile.default_all_public_streams = False
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, True)
        self.assertTrue(result)

    def test_use_passed_all_public_true_default(self) -> None:
        self.user_profile.default_all_public_streams = True
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, True)
        self.assertTrue(result)

    def test_use_passed_all_public_false_default_false(self) -> None:
        self.user_profile.default_all_public_streams = False
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, False)
        self.assertFalse(result)

    def test_use_passed_all_public_false_default_true(self) -> None:
        self.user_profile.default_all_public_streams = True
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, False)
        self.assertFalse(result)

    def test_use_true_default_for_none(self) -> None:
        self.user_profile.default_all_public_streams = True
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, None)
        self.assertTrue(result)

    def test_use_false_default_for_none(self) -> None:
        self.user_profile.default_all_public_streams = False
        self.user_profile.save()
        result = _default_all_public_streams(self.user_profile, None)
        self.assertFalse(result)

class TestEventsRegisterNarrowDefaults(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user('hamlet')
        self.email = self.user_profile.email
        self.stream = get_stream('Verona', self.user_profile.realm)

    def test_use_passed_narrow_no_default(self) -> None:
        self.user_profile.default_events_register_stream_id = None
        self.user_profile.save()
        result = _default_narrow(self.user_profile, [['stream', 'my_stream']])
        self.assertEqual(result, [['stream', 'my_stream']])

    def test_use_passed_narrow_with_default(self) -> None:
        self.user_profile.default_events_register_stream_id = self.stream.id
        self.user_profile.save()
        result = _default_narrow(self.user_profile, [['stream', 'my_stream']])
        self.assertEqual(result, [['stream', 'my_stream']])

    def test_use_default_if_narrow_is_empty(self) -> None:
        self.user_profile.default_events_register_stream_id = self.stream.id
        self.user_profile.save()
        result = _default_narrow(self.user_profile, [])
        self.assertEqual(result, [['stream', 'Verona']])

    def test_use_narrow_if_default_is_none(self) -> None:
        self.user_profile.default_events_register_stream_id = None
        self.user_profile.save()
        result = _default_narrow(self.user_profile, [])
        self.assertEqual(result, [])

class TestGetRawUserDataSystemBotRealm(ZulipTestCase):
    def test_get_raw_user_data_on_system_bot_realm(self) -> None:
        result = get_raw_user_data(get_realm("zulipinternal"), self.example_user('hamlet'), True)

        for bot_email in settings.CROSS_REALM_BOT_EMAILS:
            bot_profile = get_system_bot(bot_email)
            self.assertTrue(bot_profile.id in result)
            self.assertTrue(result[bot_profile.id]['is_cross_realm_bot'])
