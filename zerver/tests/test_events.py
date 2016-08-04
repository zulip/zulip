# -*- coding: utf-8 -*-
from __future__ import absolute_import
from typing import Any, Callable, Optional

from django.http import HttpRequest, HttpResponse
from django.test import TestCase

from zerver.models import (
    get_client, get_realm, get_stream, get_user_profile_by_email,
    Message, Recipient, UserProfile
)

from zerver.lib.actions import (
    apply_events,
    create_stream_if_needed,
    do_add_alert_words,
    check_add_realm_emoji,
    do_add_realm_filter,
    do_change_avatar_source,
    do_change_default_all_public_streams,
    do_change_default_events_register_stream,
    do_change_default_sending_stream,
    do_change_full_name,
    do_change_is_admin,
    do_change_stream_description,
    do_change_subscription_property,
    do_create_user,
    do_deactivate_stream,
    do_deactivate_user,
    do_regenerate_api_key,
    do_remove_alert_words,
    do_remove_realm_emoji,
    do_remove_realm_filter,
    do_remove_subscription,
    do_rename_stream,
    do_add_default_stream,
    do_set_muted_topics,
    do_set_realm_create_stream_by_admins_only,
    do_set_realm_name,
    do_set_realm_restricted_to_domain,
    do_set_realm_invite_required,
    do_set_realm_invite_by_admins_only,
    do_set_realm_message_editing,
    do_set_realm_default_language,
    do_update_message,
    do_update_pointer,
    do_change_twenty_four_hour_time,
    do_change_left_side_userlist,
    fetch_initial_state_data,
    get_subscription
)

from zerver.lib.event_queue import allocate_client_descriptor
from zerver.lib.test_helpers import AuthedTestCase, POSTRequestMock
from zerver.lib.validator import (
    check_bool, check_dict, check_int, check_list, check_string,
    equals, check_none_or, Validator
)

from zerver.views import _default_all_public_streams, _default_narrow

from zerver.tornadoviews import get_events_backend

from collections import OrderedDict
import time
import ujson
from six.moves import range


class GetEventsTest(AuthedTestCase):
    def tornado_call(self, view_func, user_profile, post_data):
        # type: (Callable[[HttpRequest, UserProfile], HttpResponse], UserProfile, Dict[str, Any]) -> HttpResponse
        request = POSTRequestMock(post_data, user_profile)
        return view_func(request, user_profile)

    def test_get_events(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        recipient_email = "othello@zulip.com"
        user_profile = get_user_profile_by_email(email)
        recipient_user_profile = get_user_profile_by_email(recipient_email)
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
        self.assert_length(events, 0, True)

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
        self.assert_length(events, 1, True)
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
        self.assert_length(events, 1, True)
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
        email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(email)
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
        self.assert_length(events, 0, True)

        self.send_message(email, "othello@zulip.com", Recipient.PERSONAL, "hello")
        self.send_message(email, "Denmark", Recipient.STREAM, "hello")

        result = self.tornado_call(get_events_backend, user_profile,
                                   {"queue_id": queue_id,
                                    "user_client": "website",
                                    "last_event_id": -1,
                                    "dont_block": ujson.dumps(True),
                                    })
        events = ujson.loads(result.content)["events"]
        self.assert_json_success(result)
        self.assert_length(events, 1, True)
        self.assertEqual(events[0]["type"], "message")
        self.assertEqual(events[0]["message"]["display_recipient"], "Denmark")

class EventsRegisterTest(AuthedTestCase):
    user_profile = get_user_profile_by_email("hamlet@zulip.com")
    bot = get_user_profile_by_email("welcome-bot@zulip.com")
    maxDiff = None # type: Optional[int]

    def create_bot(self, email):
        # type: (str) -> UserProfile
        return do_create_user(email, '123',
                              get_realm('zulip.com'), 'Test Bot', 'test',
                              bot_type=UserProfile.DEFAULT_BOT, bot_owner=self.user_profile)

    def realm_bot_schema(self, field_name, check):
        # type: (str, Validator) -> Validator
        return check_dict([
            ('type', equals('realm_bot')),
            ('op', equals('update')),
            ('bot', check_dict([
                ('email', check_string),
                (field_name, check),
            ])),
        ])

    def do_test(self, action, event_types=None):
        # type: (Callable[[], Any], Optional[List[str]]) -> List[Dict[str, Any]]
        client = allocate_client_descriptor(
            dict(user_profile_id = self.user_profile.id,
                 user_profile_email = self.user_profile.email,
                 realm_id = self.user_profile.realm.id,
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
        hybrid_state = fetch_initial_state_data(self.user_profile, event_types, "")
        action()
        events = client.event_queue.contents()
        self.assertTrue(len(events) > 0)
        apply_events(hybrid_state, events, self.user_profile)

        normal_state = fetch_initial_state_data(self.user_profile, event_types, "")
        self.match_states(hybrid_state, normal_state)
        return events

    def assert_on_error(self, error):
        # type: (str) -> None
        if error:
            raise AssertionError(error)

    def match_states(self, state1, state2):
        # type: (Dict[str, Any], Dict[str, Any]) -> None
        def normalize(state):
            # type: (Dict[str, Any]) -> None
            state['realm_users'] = {u['email']: u for u in state['realm_users']}
            for u in state['subscriptions']:
                u['subscribers'].sort()
            state['subscriptions'] = {u['name']: u for u in state['subscriptions']}
            state['unsubscribed'] = {u['name']: u for u in state['unsubscribed']}
            if 'realm_bots' in state:
                state['realm_bots'] = {u['email']: u for u in state['realm_bots']}
        normalize(state1)
        normalize(state2)
        self.assertEqual(state1, state2)

    def test_send_message_events(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('message')),
            ('flags', check_list(None)),
            ('message', check_dict([
                ('avatar_url', check_string),
                ('client', check_string),
                ('content', check_string),
                ('content_type', equals('text/html')),
                ('display_recipient', check_string),
                ('gravatar_hash', check_string),
                ('id', check_int),
                ('recipient_id', check_int),
                ('sender_domain', check_string),
                ('sender_email', check_string),
                ('sender_full_name', check_string),
                ('sender_id', check_int),
                ('sender_short_name', check_string),
                ('subject', check_string),
                ('subject_links', check_list(None)),
                ('timestamp', check_int),
                ('type', check_string),
            ])),
        ])
        events = self.do_test(lambda: self.send_message("hamlet@zulip.com", "Verona", Recipient.STREAM, "hello"))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        schema_checker = check_dict([
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
            ('propagate_mode', check_string),
            ('rendered_content', check_string),
            ('sender', check_string),
            ('stream_id', check_int),
            ('subject', check_string),
            ('subject_links', check_list(None)),
            # There is also a timestamp field in the event, but we ignore it, as
            # it's kind of an unwanted but harmless side effect of calling log_event.
        ])

        message = Message.objects.order_by('-id')[0]
        topic = 'new_topic'
        propagate_mode = 'change_all'
        content = 'new content'
        rendered_content = message.render_markdown(content)
        events = self.do_test(lambda: do_update_message(self.user_profile, message, topic, propagate_mode, content, rendered_content))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_pointer_events(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('pointer')),
            ('pointer', check_int)
        ])
        events = self.do_test(lambda: do_update_pointer(self.user_profile, 1500))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_register_events(self):
        # type: () -> None
        realm_user_add_checker = check_dict([
            ('type', equals('realm_user')),
            ('op', equals('add')),
            ('person', check_dict([
                ('email', check_string),
                ('full_name', check_string),
                ('is_admin', check_bool),
                ('is_bot', check_bool),
            ])),
        ])
        stream_create_checker = check_dict([
            ('type', equals('stream')),
            ('op', equals('create')),
            ('streams', check_list(check_dict([
                ('description', check_string),
                ('invite_only', check_bool),
                ('name', check_string),
                ('stream_id', check_int),
            ])))
        ])

        events = self.do_test(lambda: self.register("test1", "test1"))
        error = realm_user_add_checker('events[0]', events[0])
        self.assert_on_error(error)
        error = stream_create_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_alert_words_events(self):
        # type: () -> None
        alert_words_checker = check_dict([
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
        default_streams_checker = check_dict([
            ('type', equals('default_streams')),
            ('default_streams', check_list(check_dict([
                ('description', check_string),
                ('invite_only', check_bool),
                ('name', check_string),
                ('stream_id', check_int),
            ]))),
        ])

        events = self.do_test(lambda: do_add_default_stream(self.user_profile.realm, "Scotland"))
        error = default_streams_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_muted_topics_events(self):
        # type: () -> None
        muted_topics_checker = check_dict([
            ('type', equals('muted_topics')),
            ('muted_topics', check_list(check_list(check_string, 2))),
        ])
        events = self.do_test(lambda: do_set_muted_topics(self.user_profile, [[u"Denmark", u"topic"]]))
        error = muted_topics_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_full_name(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict([
                ('email', check_string),
                ('full_name', check_string),
            ])),
        ])
        events = self.do_test(lambda: do_change_full_name(self.user_profile, 'Sir Hamlet'))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_realm_name(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('realm')),
            ('op', equals('update')),
            ('property', equals('name')),
            ('value', check_string),
        ])
        events = self.do_test(lambda: do_set_realm_name(self.user_profile.realm, 'New Realm Name'))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_realm_restricted_to_domain(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('realm')),
            ('op', equals('update')),
            ('property', equals('restricted_to_domain')),
            ('value', check_bool),
        ])
        # The first True is probably a noop, then we get transitions in both directions.
        for restricted_to_domain in (True, False, True):
            events = self.do_test(lambda: do_set_realm_restricted_to_domain(self.user_profile.realm, restricted_to_domain))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_realm_invite_required(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('realm')),
            ('op', equals('update')),
            ('property', equals('invite_required')),
            ('value', check_bool),
        ])
        # The first False is probably a noop, then we get transitions in both directions.
        for invite_required in (False, True, False):
            events = self.do_test(lambda: do_set_realm_invite_required(self.user_profile.realm, invite_required))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_realm_invite_by_admins_only(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('realm')),
            ('op', equals('update')),
            ('property', equals('invite_by_admins_only')),
            ('value', check_bool),
        ])
        # The first False is probably a noop, then we get transitions in both directions.
        for invite_by_admins_only in (False, True, False):
            events = self.do_test(lambda: do_set_realm_invite_by_admins_only(self.user_profile.realm, invite_by_admins_only))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_realm_default_language(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('realm')),
            ('op', equals('update')),
            ('property', equals('default_language')),
            ('value', check_string),
            ])
        events = self.do_test(lambda: do_set_realm_default_language(self.user_profile.realm, 'de'))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_realm_create_stream_by_admins_only(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('realm')),
            ('op', equals('update')),
            ('property', equals('create_stream_by_admins_only')),
            ('value', check_bool),
        ])
        # The first False is probably a noop, then we get transitions in both directions.
        for create_stream_by_admins_only in (False, True, False):
            events = self.do_test(lambda: do_set_realm_create_stream_by_admins_only(self.user_profile.realm,
                                                                                create_stream_by_admins_only))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_pin_stream(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('subscription')),
            ('op', equals('update')),
            ('property', equals('pin_to_top')),
            ('value', check_bool),
        ])
        stream = "Denmark"
        sub = get_subscription(stream, self.user_profile)
        # The first False is probably a noop, then we get transitions in both directions.
        for pinned in (False, True, False):
            events = self.do_test(lambda: do_change_subscription_property(self.user_profile, sub, stream, "pin_to_top", pinned))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_realm_message_edit_settings(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('realm')),
            ('op', equals('update_dict')),
            ('property', equals('default')),
            ('data', check_dict([('allow_message_editing', check_bool),
                                 ('message_content_edit_limit_seconds', check_int)])),
        ])
        # Test every transition among the four possibilities {T,F} x {0, non-0}
        for (allow_message_editing, message_content_edit_limit_seconds) in \
            ((True, 0), (False, 0), (True, 0), (False, 1234), (True, 0), (True, 1234), (True, 0),
             (False, 0), (False, 1234), (False, 0), (True, 1234), (False, 0),
             (True, 1234), (True, 600), (False, 600), (False, 1234), (True, 600)):
            events = self.do_test(lambda: do_set_realm_message_editing(self.user_profile.realm,
                                      allow_message_editing, message_content_edit_limit_seconds))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_is_admin(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('realm_user')),
            ('op', equals('update')),
            ('person', check_dict([
                ('email', check_string),
                ('is_admin', check_bool),
            ])),
        ])
        # The first False is probably a noop, then we get transitions in both directions.
        for is_admin in [False, True, False]:
            events = self.do_test(lambda: do_change_is_admin(self.user_profile, is_admin))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_twenty_four_hour_time(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('update_display_settings')),
            ('setting_name', equals('twenty_four_hour_time')),
            ('user', check_string),
            ('setting', check_bool),
            ])
        # The first False is probably a noop, then we get transitions in both directions.
        for setting_value in [False, True, False]:
            events = self.do_test(lambda: do_change_twenty_four_hour_time(self.user_profile, setting_value))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_change_left_side_userlist(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('update_display_settings')),
            ('setting_name', equals('left_side_userlist')),
            ('user', check_string),
            ('setting', check_bool),
            ])
        # The first False is probably a noop, then we get transitions in both directions.
        for setting_value in [False, True, False]:
            events = self.do_test(lambda: do_change_left_side_userlist(self.user_profile, setting_value))
            error = schema_checker('events[0]', events[0])
            self.assert_on_error(error)

    def test_realm_emoji_events(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('realm_emoji')),
            ('op', equals('update')),
            ('realm_emoji', check_dict([])),
        ])
        events = self.do_test(lambda: check_add_realm_emoji(get_realm("zulip.com"), "my_emoji",
                                                         "https://realm.com/my_emoji"))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        events = self.do_test(lambda: do_remove_realm_emoji(get_realm("zulip.com"), "my_emoji"))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_realm_filter_events(self):
        # type: () -> None
        schema_checker = check_dict([
            ('type', equals('realm_filters')),
            ('realm_filters', check_list(None)), # TODO: validate tuples in the list
        ])
        events = self.do_test(lambda: do_add_realm_filter(get_realm("zulip.com"), "#[123]",
                                                          "https://realm.com/my_realm_filter/%(id)s"))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        self.do_test(lambda: do_remove_realm_filter(get_realm("zulip.com"), "#[123]"))
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)


    def test_create_bot(self):
        # type: () -> None
        bot_created_checker = check_dict([
            ('type', equals('realm_bot')),
            ('op', equals('add')),
            ('bot', check_dict([
                ('email', check_string),
                ('full_name', check_string),
                ('api_key', check_string),
                ('default_sending_stream', check_none_or(check_string)),
                ('default_events_register_stream', check_none_or(check_string)),
                ('default_all_public_streams', check_bool),
                ('avatar_url', check_string),
            ])),
        ])
        action = lambda: self.create_bot('test-bot@zulip.com')
        events = self.do_test(action)
        error = bot_created_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_change_bot_full_name(self):
        # type: () -> None
        action = lambda: do_change_full_name(self.bot, 'New Bot Name')
        events = self.do_test(action)
        error = self.realm_bot_schema('full_name', check_string)('events[1]', events[1])
        self.assert_on_error(error)

    def test_regenerate_bot_api_key(self):
        # type: () -> None
        action = lambda: do_regenerate_api_key(self.bot)
        events = self.do_test(action)
        error = self.realm_bot_schema('api_key', check_string)('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_avatar_source(self):
        # type: () -> None
        action = lambda: do_change_avatar_source(self.bot, self.bot.AVATAR_FROM_USER)
        events = self.do_test(action)
        error = self.realm_bot_schema('avatar_url', check_string)('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_default_all_public_streams(self):
        # type: () -> None
        action = lambda: do_change_default_all_public_streams(self.bot, True)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_all_public_streams', check_bool)('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_default_sending_stream(self):
        # type: () -> None
        stream = get_stream("Rome", self.bot.realm)
        action = lambda: do_change_default_sending_stream(self.bot, stream)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_sending_stream', check_string)('events[0]', events[0])
        self.assert_on_error(error)

    def test_change_bot_default_events_register_stream(self):
        # type: () -> None
        stream = get_stream("Rome", self.bot.realm)
        action = lambda: do_change_default_events_register_stream(self.bot, stream)
        events = self.do_test(action)
        error = self.realm_bot_schema('default_events_register_stream', check_string)('events[0]', events[0])
        self.assert_on_error(error)

    def test_do_deactivate_user(self):
        # type: () -> None
        bot_deactivate_checker = check_dict([
            ('type', equals('realm_bot')),
            ('op', equals('remove')),
            ('bot', check_dict([
                ('email', check_string),
                ('full_name', check_string),
            ])),
        ])
        bot = self.create_bot('foo-bot@zulip.com')
        action = lambda: do_deactivate_user(bot)
        events = self.do_test(action)
        error = bot_deactivate_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_rename_stream(self):
        # type: () -> None
        realm = get_realm('zulip.com')
        stream, _ = create_stream_if_needed(realm, 'old_name')
        new_name = u'stream with a brand new name'
        self.subscribe_to_stream(self.user_profile.email, stream.name)

        action = lambda: do_rename_stream(realm, stream.name, new_name)
        events = self.do_test(action)

        schema_checker = check_dict([
            ('type', equals('stream')),
            ('op', equals('update')),
            ('property', equals('email_address')),
            ('value', check_string),
            ('name', equals('old_name')),
        ])
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        schema_checker = check_dict([
            ('type', equals('stream')),
            ('op', equals('update')),
            ('property', equals('name')),
            ('value', equals(new_name)),
            ('name', equals('old_name')),
        ])
        error = schema_checker('events[1]', events[1])
        self.assert_on_error(error)

    def test_deactivate_stream_neversubscribed(self):
        # type: () -> None
        realm = get_realm('zulip.com')
        stream, _ = create_stream_if_needed(realm, 'old_name')

        action = lambda: do_deactivate_stream(stream)
        events = self.do_test(action)

        schema_checker = check_dict([
            ('type', equals('stream')),
            ('op', equals('delete')),
            ('streams', check_list(check_dict([]))),
        ])
        error = schema_checker('events[0]', events[0])
        self.assert_on_error(error)

    def test_subscribe_other_user_never_subscribed(self):
        # type: () -> None
        action = lambda: self.subscribe_to_stream("othello@zulip.com", u"test_stream")
        events = self.do_test(action)
        schema_checker = check_dict([
            ('type', equals('subscription')),
            ('op', equals('peer_add')),
            ('user_email', check_string),
            ('subscriptions', check_list(check_string)),
        ])
        error = schema_checker('events[2]', events[2])
        self.assert_on_error(error)

    def test_subscribe_events(self):
        # type: () -> None
        subscription_schema_checker = check_list(
            check_dict([
                ('color', check_string),
                ('description', check_string),
                ('email_address', check_string),
                ('invite_only', check_bool),
                ('in_home_view', check_bool),
                ('name', check_string),
                ('desktop_notifications', check_bool),
                ('audible_notifications', check_bool),
                ('stream_id', check_int),
                ('subscribers', check_list(check_int)),
            ])
        )
        add_schema_checker = check_dict([
            ('type', equals('subscription')),
            ('op', equals('add')),
            ('subscriptions', subscription_schema_checker),
        ])
        remove_schema_checker = check_dict([
            ('type', equals('subscription')),
            ('op', equals('remove')),
            ('subscriptions', check_list(
                check_dict([
                    ('name', equals('test_stream')),
                    ('stream_id', check_int),
                ]),
            )),
        ])
        peer_add_schema_checker = check_dict([
            ('type', equals('subscription')),
            ('op', equals('peer_add')),
            ('user_email', check_string),
            ('subscriptions', check_list(check_string)),
        ])
        peer_remove_schema_checker = check_dict([
            ('type', equals('subscription')),
            ('op', equals('peer_remove')),
            ('user_email', check_string),
            ('subscriptions', check_list(check_string)),
        ])
        stream_update_schema_checker = check_dict([
            ('type', equals('stream')),
            ('op', equals('update')),
            ('property', equals('description')),
            ('value', check_string),
            ('name', check_string),
        ])

        action = lambda: self.subscribe_to_stream("hamlet@zulip.com", "test_stream") # type: Callable
        events = self.do_test(action, event_types=["subscription", "realm_user"])
        error = add_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        action = lambda: self.subscribe_to_stream("othello@zulip.com", "test_stream")
        events = self.do_test(action)
        error = peer_add_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        stream = get_stream("test_stream", self.user_profile.realm)

        action = lambda: do_remove_subscription(get_user_profile_by_email("othello@zulip.com"), stream)
        events = self.do_test(action)
        error = peer_remove_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

        action = lambda: do_remove_subscription(get_user_profile_by_email("hamlet@zulip.com"), stream)
        events = self.do_test(action)
        error = remove_schema_checker('events[1]', events[1])
        self.assert_on_error(error)

        action = lambda: self.subscribe_to_stream("hamlet@zulip.com", "test_stream")
        events = self.do_test(action)
        error = add_schema_checker('events[1]', events[1])
        self.assert_on_error(error)

        action = lambda: do_change_stream_description(get_realm('zulip.com'), 'test_stream', u'new description')
        events = self.do_test(action)
        error = stream_update_schema_checker('events[0]', events[0])
        self.assert_on_error(error)

class FetchInitialStateDataTest(AuthedTestCase):
    # Non-admin users don't have access to all bots
    def test_realm_bots_non_admin(self):
        # type: () -> None
        email = 'cordelia@zulip.com'
        user_profile = get_user_profile_by_email(email)
        self.assertFalse(user_profile.is_realm_admin)
        result = fetch_initial_state_data(user_profile, None, "")
        self.assert_length(result['realm_bots'], 0)

        # additionally the API key for a random bot is not present in the data
        api_key = get_user_profile_by_email('notification-bot@zulip.com').api_key
        self.assertNotIn(api_key, str(result))

    # Admin users have access to all bots in the realm_bots field
    def test_realm_bots_admin(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        user_profile = get_user_profile_by_email(email)
        do_change_is_admin(user_profile, True)
        self.assertTrue(user_profile.is_realm_admin)
        result = fetch_initial_state_data(user_profile, None, "")
        self.assertTrue(len(result['realm_bots']) > 5)

from zerver.lib.event_queue import EventQueue
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
                           "id": 9,},
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
                           "id": 9,},
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

class TestEventsRegisterAllPublicStreamsDefaults(TestCase):
    def setUp(self):
        # type: () -> None
        self.email = 'hamlet@zulip.com'
        self.user_profile = get_user_profile_by_email(self.email)

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

class TestEventsRegisterNarrowDefaults(TestCase):
    def setUp(self):
        # type: () -> None
        self.email = 'hamlet@zulip.com'
        self.user_profile = get_user_profile_by_email(self.email)
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
