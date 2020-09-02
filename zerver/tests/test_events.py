# See https://zulip.readthedocs.io/en/latest/subsystems/events-system.html for
# high-level documentation on how this system works.
import copy
import sys
import time
from io import StringIO
from typing import Any, Callable, Dict, List, Optional, Set
from unittest import mock

import orjson
from django.utils.timezone import now as timezone_now

from zerver.lib.actions import (
    bulk_add_members_to_user_group,
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    check_add_realm_emoji,
    check_add_user_group,
    check_delete_user_group,
    check_send_typing_notification,
    do_add_alert_words,
    do_add_default_stream,
    do_add_reaction,
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
    do_change_notification_settings,
    do_change_plan_type,
    do_change_realm_domain,
    do_change_stream_description,
    do_change_stream_invite_only,
    do_change_stream_message_retention_days,
    do_change_stream_post_policy,
    do_change_subscription_property,
    do_change_user_delivery_email,
    do_change_user_role,
    do_create_default_stream_group,
    do_create_multiuse_invite_link,
    do_create_user,
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
    do_remove_realm_domain,
    do_remove_realm_emoji,
    do_remove_realm_filter,
    do_remove_streams_from_default_stream_group,
    do_rename_stream,
    do_revoke_multi_use_invite,
    do_revoke_user_invite,
    do_set_realm_authentication_methods,
    do_set_realm_message_editing,
    do_set_realm_notifications_stream,
    do_set_realm_property,
    do_set_realm_signup_notifications_stream,
    do_set_user_display_setting,
    do_set_zoom_token,
    do_unmute_topic,
    do_update_embedded_data,
    do_update_message,
    do_update_message_flags,
    do_update_outgoing_webhook_service,
    do_update_user_custom_profile_data_if_changed,
    do_update_user_group_description,
    do_update_user_group_name,
    do_update_user_presence,
    do_update_user_status,
    lookup_default_stream_groups,
    notify_realm_custom_profile_fields,
    remove_members_from_user_group,
    try_update_realm_custom_profile_field,
)
from zerver.lib.event_schema import (
    avatar_fields,
    check_alert_words,
    check_custom_profile_fields,
    check_default_stream_groups,
    check_default_streams,
    check_events_dict,
    check_invites_changed,
    check_message,
    check_reaction,
    check_realm_bot_add,
    check_realm_bot_delete,
    check_realm_bot_remove,
    check_realm_bot_update,
    check_realm_update,
    check_realm_user_update,
    check_stream_create,
    check_stream_delete,
    check_stream_update,
    check_submessage,
    check_subscription_add,
    check_subscription_peer_add,
    check_subscription_peer_remove,
    check_subscription_remove,
    check_typing_start,
    check_typing_stop,
    check_update_display_settings,
    check_update_global_notifications,
    check_update_message,
    check_update_message_embedded,
    check_update_message_flags,
    check_user_group_add,
    check_user_status,
)
from zerver.lib.events import apply_events, fetch_initial_state_data, post_process_state
from zerver.lib.markdown import MentionData
from zerver.lib.message import render_markdown
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    create_dummy_file,
    get_subscription,
    get_test_image_file,
    reset_emails_in_zulip_realm,
    stdout_suppressed,
)
from zerver.lib.topic import TOPIC_NAME
from zerver.lib.validator import (
    check_bool,
    check_dict_only,
    check_float,
    check_int,
    check_list,
    check_none_or,
    check_string,
    check_tuple,
    equals,
)
from zerver.models import (
    Attachment,
    Message,
    MultiuseInvite,
    PreregistrationUser,
    Realm,
    RealmAuditLog,
    RealmDomain,
    Service,
    Stream,
    UserGroup,
    UserMessage,
    UserPresence,
    UserProfile,
    get_client,
    get_stream,
    get_user_by_delivery_email,
)
from zerver.openapi.openapi import validate_against_openapi_schema
from zerver.tornado.event_queue import (
    allocate_client_descriptor,
    clear_client_event_queues_for_testing,
)


class BaseAction(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user('hamlet')

    def verify_action(self,
                      action: Callable[[], object],
                      event_types: Optional[List[str]]=None,
                      include_subscribers: bool=True,
                      state_change_expected: bool=True,
                      notification_settings_null: bool=False,
                      client_gravatar: bool=True,
                      user_avatar_url_field_optional: bool=False,
                      slim_presence: bool=False,
                      num_events: int=1,
                      bulk_message_deletion: bool=True) -> List[Dict[str, Any]]:
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
                 narrow = [],
                 bulk_message_deletion = bulk_message_deletion)
        )

        # hybrid_state = initial fetch state + re-applying events triggered by our action
        # normal_state = do action then fetch at the end (the "normal" code path)
        hybrid_state = fetch_initial_state_data(
            self.user_profile, event_types, "",
            client_gravatar=client_gravatar,
            user_avatar_url_field_optional=user_avatar_url_field_optional,
            slim_presence=slim_presence,
            include_subscribers=include_subscribers,
        )
        action()
        events = client.event_queue.contents()
        content = {
            'queue_id': '123.12',
            # The JSON wrapper helps in converting tuples to lists
            # as tuples aren't valid JSON structure.
            'events': orjson.loads(orjson.dumps(events)),
            'msg': '',
            'result': 'success'
        }
        validate_against_openapi_schema(content, '/events', 'get', '200')
        self.assertEqual(len(events), num_events)
        initial_state = copy.deepcopy(hybrid_state)
        post_process_state(self.user_profile, initial_state, notification_settings_null)
        before = orjson.dumps(initial_state)
        apply_events(hybrid_state, events, self.user_profile,
                     client_gravatar=client_gravatar,
                     slim_presence=slim_presence,
                     include_subscribers=include_subscribers)
        post_process_state(self.user_profile, hybrid_state, notification_settings_null)
        after = orjson.dumps(hybrid_state)

        if state_change_expected:
            if before == after:  # nocoverage
                print(orjson.dumps(initial_state, option=orjson.OPT_INDENT_2).decode())
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
            user_avatar_url_field_optional=user_avatar_url_field_optional,
            slim_presence=slim_presence,
            include_subscribers=include_subscribers,
        )
        post_process_state(self.user_profile, normal_state, notification_settings_null)
        self.match_states(hybrid_state, normal_state, events)
        return events

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

class NormalActionsTest(BaseAction):
    def create_bot(self, email: str, **extras: Any) -> UserProfile:
        return self.create_test_bot(email, self.user_profile, **extras)

    def test_mentioned_send_message_events(self) -> None:
        user = self.example_user('hamlet')

        for i in range(3):
            content = 'mentioning... @**' + user.full_name + '** hello ' + str(i)
            self.verify_action(
                lambda: self.send_stream_message(self.example_user('cordelia'),
                                                 "Verona",
                                                 content),

            )

    def test_wildcard_mentioned_send_message_events(self) -> None:
        for i in range(3):
            content = 'mentioning... @**all** hello ' + str(i)
            self.verify_action(
                lambda: self.send_stream_message(self.example_user('cordelia'),
                                                 "Verona",
                                                 content),

            )

    def test_pm_send_message_events(self) -> None:
        self.verify_action(
            lambda: self.send_personal_message(self.example_user('cordelia'),
                                               self.example_user('hamlet'),
                                               'hola'),

        )

    def test_huddle_send_message_events(self) -> None:
        huddle = [
            self.example_user('hamlet'),
            self.example_user('othello'),
        ]
        self.verify_action(
            lambda: self.send_huddle_message(self.example_user('cordelia'),
                                             huddle,
                                             'hola'),

        )

    def test_stream_send_message_events(self) -> None:
        events = self.verify_action(
            lambda: self.send_stream_message(self.example_user("hamlet"), "Verona", "hello"),
            client_gravatar=False,
        )
        check_message('events[0]', events[0])
        assert isinstance(events[0]['message']['avatar_url'], str)

        events = self.verify_action(
            lambda: self.send_stream_message(self.example_user("hamlet"), "Verona", "hello"),
            client_gravatar=True,
        )
        check_message('events[0]', events[0])
        assert events[0]['message']['avatar_url'] is None

        # Verify message editing
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

        events = self.verify_action(
            lambda: do_update_message(
                self.user_profile,
                message,
                None,
                topic,
                propagate_mode,
                False,
                False,
                content,
                rendered_content,
                prior_mention_user_ids,
                mentioned_user_ids,
                mention_data),
            state_change_expected=True,
        )
        check_update_message(
            'events[0]',
            events[0],
            has_content=True,
            has_topic=True,
            has_new_stream_id=False,
        )

        events = self.verify_action(
            lambda: do_update_embedded_data(self.user_profile, message,
                                            "embed_content", "<p>embed_content</p>"),
            state_change_expected=False,
        )
        check_update_message_embedded('events[0]', events[0])

        # Verify move topic to different stream.

        # Send 2 messages in "test" topic.
        self.send_stream_message(self.user_profile, "Verona")
        message_id = self.send_stream_message(self.user_profile, "Verona")
        message = Message.objects.get(id=message_id)
        topic = 'new_topic'
        stream = get_stream("Denmark", self.user_profile.realm)
        propagate_mode = 'change_all'
        prior_mention_user_ids = set()

        events = self.verify_action(
            lambda: do_update_message(
                self.user_profile,
                message,
                stream,
                topic,
                propagate_mode,
                True,
                True,
                None,
                None,
                set(),
                set(),
                None),
            state_change_expected=True,
            # There are 3 events generated for this action
            # * update_message: For updating existing messages
            # * 2 new message events: Breadcrumb messages in the new and old topics.
            num_events=3,
        )
        check_update_message(
            'events[0]',
            events[0],
            has_content=False,
            has_topic=True,
            has_new_stream_id=True,
        )

    def test_update_message_flags(self) -> None:
        # Test message flag update events
        message = self.send_personal_message(
            self.example_user("cordelia"),
            self.example_user("hamlet"),
            "hello",
        )
        user_profile = self.example_user('hamlet')
        events = self.verify_action(
            lambda: do_update_message_flags(user_profile, get_client("website"), 'add', 'starred', [message]),
            state_change_expected=True,
        )
        check_update_message_flags('events[0]', events[0], 'add')

        events = self.verify_action(
            lambda: do_update_message_flags(user_profile, get_client("website"), 'remove', 'starred', [message]),
            state_change_expected=True,
        )
        check_update_message_flags('events[0]', events[0], 'remove')

    def test_update_read_flag_removes_unread_msg_ids(self) -> None:

        user_profile = self.example_user('hamlet')
        mention = '@**' + user_profile.full_name + '**'

        for content in ['hello', mention]:
            message = self.send_stream_message(
                self.example_user('cordelia'),
                "Verona",
                content,
            )

            self.verify_action(
                lambda: do_update_message_flags(user_profile, get_client("website"), 'add', 'read', [message]),
                state_change_expected=True,
            )

    def test_send_message_to_existing_recipient(self) -> None:
        sender = self.example_user('cordelia')
        self.send_stream_message(
            sender,
            "Verona",
            "hello 1",
        )
        self.verify_action(
            lambda: self.send_stream_message(sender, "Verona", "hello 2"),
            state_change_expected=True,
        )

    def test_add_reaction(self) -> None:
        message_id = self.send_stream_message(self.example_user("hamlet"), "Verona", "hello")
        message = Message.objects.get(id=message_id)
        events = self.verify_action(
            lambda: do_add_reaction(
                self.user_profile, message, "tada", "1f389", "unicode_emoji"),
            state_change_expected=False,
        )
        check_reaction('events[0]', events[0], 'add')

    def test_add_submessage(self) -> None:
        cordelia = self.example_user('cordelia')
        stream_name = 'Verona'
        message_id = self.send_stream_message(
            sender=cordelia,
            stream_name=stream_name,
        )
        events = self.verify_action(
            lambda: do_add_submessage(
                realm=cordelia.realm,
                sender_id=cordelia.id,
                message_id=message_id,
                msg_type='whatever',
                content='"stuff"',
            ),
            state_change_expected=False,
        )
        check_submessage('events[0]', events[0])

    def test_remove_reaction(self) -> None:
        message_id = self.send_stream_message(self.example_user("hamlet"), "Verona", "hello")
        message = Message.objects.get(id=message_id)
        do_add_reaction(self.user_profile, message, "tada", "1f389", "unicode_emoji")
        events = self.verify_action(
            lambda: do_remove_reaction(
                self.user_profile, message, "1f389", "unicode_emoji"),
            state_change_expected=False,
        )
        check_reaction('events[0]', events[0], 'remove')

    def test_invite_user_event(self) -> None:
        self.user_profile = self.example_user('iago')
        streams = []
        for stream_name in ["Denmark", "Scotland"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))
        events = self.verify_action(
            lambda: do_invite_users(self.user_profile, ["foo@zulip.com"], streams, False),
            state_change_expected=False,
        )
        check_invites_changed('events[0]', events[0])

    def test_create_multiuse_invite_event(self) -> None:
        self.user_profile = self.example_user('iago')
        streams = []
        for stream_name in ["Denmark", "Verona"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        events = self.verify_action(
            lambda: do_create_multiuse_invite_link(self.user_profile, PreregistrationUser.INVITE_AS['MEMBER'], streams),
            state_change_expected=False,
        )
        check_invites_changed('events[0]', events[0])

    def test_revoke_user_invite_event(self) -> None:
        self.user_profile = self.example_user('iago')
        streams = []
        for stream_name in ["Denmark", "Verona"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))
        do_invite_users(self.user_profile, ["foo@zulip.com"], streams, False)
        prereg_users = PreregistrationUser.objects.filter(referred_by__realm=self.user_profile.realm)
        events = self.verify_action(
            lambda: do_revoke_user_invite(prereg_users[0]),
            state_change_expected=False,
        )
        check_invites_changed('events[0]', events[0])

    def test_revoke_multiuse_invite_event(self) -> None:
        self.user_profile = self.example_user('iago')
        streams = []
        for stream_name in ["Denmark", "Verona"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))
        do_create_multiuse_invite_link(self.user_profile, PreregistrationUser.INVITE_AS['MEMBER'], streams)

        multiuse_object = MultiuseInvite.objects.get()
        events = self.verify_action(
            lambda: do_revoke_multi_use_invite(multiuse_object),
            state_change_expected=False,
        )
        check_invites_changed('events[0]', events[0])

    def test_invitation_accept_invite_event(self) -> None:
        reset_emails_in_zulip_realm()

        self.user_profile = self.example_user('iago')
        streams = []
        for stream_name in ["Denmark", "Scotland"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        do_invite_users(self.user_profile, ["foo@zulip.com"], streams, False)
        prereg_user = PreregistrationUser.objects.get(email="foo@zulip.com")

        events = self.verify_action(
            lambda: do_create_user(
                'foo@zulip.com',
                'password',
                self.user_profile.realm,
                'full name',
                prereg_user=prereg_user,
            ),
            state_change_expected=True,
            num_events=5,
        )

        check_invites_changed('events[4]', events[4])

    def test_typing_events(self) -> None:
        events = self.verify_action(
            lambda: check_send_typing_notification(
                self.user_profile, [self.example_user("cordelia").id], "start"),
            state_change_expected=False,
        )
        check_typing_start('events[0]', events[0])
        events = self.verify_action(
            lambda: check_send_typing_notification(
                self.user_profile, [self.example_user("cordelia").id], "stop"),
            state_change_expected=False,
        )
        check_typing_stop('events[0]', events[0])

    def test_custom_profile_fields_events(self) -> None:
        events = self.verify_action(
            lambda: notify_realm_custom_profile_fields(
                self.user_profile.realm, 'add'),
            state_change_expected=False,
        )
        check_custom_profile_fields('events[0]', events[0])

        realm = self.user_profile.realm
        field = realm.customprofilefield_set.get(realm=realm, name='Biography')
        name = field.name
        hint = 'Biography of the user'
        try_update_realm_custom_profile_field(realm, field, name, hint=hint)

        events = self.verify_action(
            lambda: notify_realm_custom_profile_fields(
                self.user_profile.realm, 'add'),
            state_change_expected=False,
        )
        check_custom_profile_fields('events[0]', events[0])

    def test_custom_profile_field_data_events(self) -> None:
        field_id = self.user_profile.realm.customprofilefield_set.get(
            realm=self.user_profile.realm, name='Biography').id
        field = {
            "id": field_id,
            "value": "New value",
        }
        events = self.verify_action(
            lambda: do_update_user_custom_profile_data_if_changed(
                self.user_profile,
                [field]))
        check_realm_user_update('events[0]', events[0], {"custom_profile_field"})
        self.assertEqual(
            events[0]['person']['custom_profile_field'].keys(),
            {"id", "value", "rendered_value"}
        )

        # Test we pass correct stringify value in custom-user-field data event
        field_id = self.user_profile.realm.customprofilefield_set.get(
            realm=self.user_profile.realm, name='Mentor').id
        field = {
            "id": field_id,
            "value": [self.example_user("ZOE").id],
        }
        events = self.verify_action(
            lambda: do_update_user_custom_profile_data_if_changed(
                self.user_profile,
                [field]))
        check_realm_user_update('events[0]', events[0], {"custom_profile_field"})
        self.assertEqual(
            events[0]['person']['custom_profile_field'].keys(),
            {"id", "value"}
        )

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

        events = self.verify_action(
            lambda: do_update_user_presence(
                self.user_profile,
                get_client("website"),
                timezone_now(),
                UserPresence.ACTIVE),
            slim_presence=False)
        schema_checker = check_events_dict([*fields, email_field])
        schema_checker('events[0]', events[0])

        events = self.verify_action(
            lambda: do_update_user_presence(
                self.example_user('cordelia'),
                get_client("website"),
                timezone_now(),
                UserPresence.ACTIVE),
            slim_presence=True)
        schema_checker = check_events_dict(fields)
        schema_checker('events[0]', events[0])

    def test_presence_events_multiple_clients(self) -> None:
        schema_checker_android = check_events_dict([
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
        self.verify_action(
            lambda: do_update_user_presence(
                self.user_profile,
                get_client("website"),
                timezone_now(),
                UserPresence.ACTIVE))
        events = self.verify_action(
            lambda: do_update_user_presence(
                self.user_profile,
                get_client("ZulipAndroid/1.0"),
                timezone_now(),
                UserPresence.IDLE))
        schema_checker_android('events[0]', events[0])

    def test_register_events(self) -> None:
        realm_user_add_checker = check_events_dict([
            ('type', equals('realm_user')),
            ('op', equals('add')),
            ('person', check_dict_only([
                ('user_id', check_int),
                ('email', check_string),
                ('avatar_url', check_none_or(check_string)),
                ('avatar_version', check_int),
                ('full_name', check_string),
                ('is_admin', check_bool),
                ('is_owner', check_bool),
                ('is_bot', check_bool),
                ('is_guest', check_bool),
                ('is_active', check_bool),
                ('profile_data', check_dict_only([])),
                ('timezone', check_string),
                ('date_joined', check_string),
            ])),
        ])

        events = self.verify_action(
            lambda: self.register("test1@zulip.com", "test1"))
        self.assert_length(events, 1)
        realm_user_add_checker('events[0]', events[0])
        new_user_profile = get_user_by_delivery_email("test1@zulip.com", self.user_profile.realm)
        self.assertEqual(new_user_profile.delivery_email, "test1@zulip.com")

    def test_register_events_email_address_visibility(self) -> None:
        realm_user_add_checker = check_events_dict([
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
                ('is_owner', check_bool),
                ('is_bot', check_bool),
                ('is_guest', check_bool),
                ('profile_data', check_dict_only([])),
                ('timezone', check_string),
                ('date_joined', check_string),
            ])),
        ])

        do_set_realm_property(self.user_profile.realm, "email_address_visibility",
                              Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS)

        events = self.verify_action(
            lambda: self.register("test1@zulip.com", "test1"))
        self.assert_length(events, 1)
        realm_user_add_checker('events[0]', events[0])
        new_user_profile = get_user_by_delivery_email("test1@zulip.com", self.user_profile.realm)
        self.assertEqual(new_user_profile.email, f"user{new_user_profile.id}@zulip.testserver")

    def test_alert_words_events(self) -> None:
        events = self.verify_action(
            lambda: do_add_alert_words(self.user_profile, ["alert_word"]))
        check_alert_words('events[0]', events[0])

        events = self.verify_action(
            lambda: do_remove_alert_words(self.user_profile, ["alert_word"]))
        check_alert_words('events[0]', events[0])

    def test_away_events(self) -> None:
        client = get_client("website")
        events = self.verify_action(
            lambda: do_update_user_status(
                user_profile=self.user_profile,
                away=True,
                status_text='out to lunch',
                client_id=client.id))

        check_user_status('events[0]', events[0])

        events = self.verify_action(
            lambda: do_update_user_status(
                user_profile=self.user_profile,
                away=False,
                status_text='',
                client_id=client.id))

        check_user_status('events[0]', events[0])

    def test_user_group_events(self) -> None:
        othello = self.example_user('othello')
        events = self.verify_action(
            lambda: check_add_user_group(
                self.user_profile.realm,
                'backend',
                [othello],
                'Backend team'))
        check_user_group_add('events[0]', events[0])

        # Test name update
        user_group_update_checker = check_events_dict([
            ('type', equals('user_group')),
            ('op', equals('update')),
            ('group_id', check_int),
            ('data', check_dict_only([
                ('name', check_string),
            ])),
        ])
        backend = UserGroup.objects.get(name='backend')
        events = self.verify_action(
            lambda: do_update_user_group_name(backend, 'backendteam'))
        user_group_update_checker('events[0]', events[0])

        # Test description update
        user_group_update_checker = check_events_dict([
            ('type', equals('user_group')),
            ('op', equals('update')),
            ('group_id', check_int),
            ('data', check_dict_only([
                ('description', check_string),
            ])),
        ])
        description = "Backend team to deal with backend code."
        events = self.verify_action(
            lambda: do_update_user_group_description(backend, description))
        user_group_update_checker('events[0]', events[0])

        # Test add members
        user_group_add_member_checker = check_events_dict([
            ('type', equals('user_group')),
            ('op', equals('add_members')),
            ('group_id', check_int),
            ('user_ids', check_list(check_int)),
        ])
        hamlet = self.example_user('hamlet')
        events = self.verify_action(
            lambda: bulk_add_members_to_user_group(backend, [hamlet]))
        user_group_add_member_checker('events[0]', events[0])

        # Test remove members
        user_group_remove_member_checker = check_events_dict([
            ('type', equals('user_group')),
            ('op', equals('remove_members')),
            ('group_id', check_int),
            ('user_ids', check_list(check_int)),
        ])
        hamlet = self.example_user('hamlet')
        events = self.verify_action(
            lambda: remove_members_from_user_group(backend, [hamlet]))
        user_group_remove_member_checker('events[0]', events[0])

        # Test delete event
        user_group_remove_checker = check_events_dict([
            ('type', equals('user_group')),
            ('op', equals('remove')),
            ('group_id', check_int),
        ])
        events = self.verify_action(
            lambda: check_delete_user_group(backend.id, othello))
        user_group_remove_checker('events[0]', events[0])

    def test_default_stream_groups_events(self) -> None:
        streams = []
        for stream_name in ["Scotland", "Verona", "Denmark"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        events = self.verify_action(
            lambda: do_create_default_stream_group(
                self.user_profile.realm,
                "group1",
                "This is group1",
                streams))
        check_default_stream_groups('events[0]', events[0])

        group = lookup_default_stream_groups(["group1"], self.user_profile.realm)[0]
        venice_stream = get_stream("Venice", self.user_profile.realm)
        events = self.verify_action(
            lambda: do_add_streams_to_default_stream_group(
                self.user_profile.realm,
                group,
                [venice_stream]))
        check_default_stream_groups('events[0]', events[0])

        events = self.verify_action(
            lambda: do_remove_streams_from_default_stream_group(
                self.user_profile.realm,
                group,
                [venice_stream]))
        check_default_stream_groups('events[0]', events[0])

        events = self.verify_action(
            lambda: do_change_default_stream_group_description(
                self.user_profile.realm,
                group,
                "New description"))
        check_default_stream_groups('events[0]', events[0])

        events = self.verify_action(
            lambda: do_change_default_stream_group_name(
                self.user_profile.realm,
                group,
                "New Group Name"))
        check_default_stream_groups('events[0]', events[0])

        events = self.verify_action(
            lambda: do_remove_default_stream_group(self.user_profile.realm, group))
        check_default_stream_groups('events[0]', events[0])

    def test_default_stream_group_events_guest(self) -> None:
        streams = []
        for stream_name in ["Scotland", "Verona", "Denmark"]:
            streams.append(get_stream(stream_name, self.user_profile.realm))

        do_create_default_stream_group(self.user_profile.realm, "group1",
                                       "This is group1", streams)
        group = lookup_default_stream_groups(["group1"], self.user_profile.realm)[0]

        do_change_user_role(self.user_profile, UserProfile.ROLE_GUEST)
        venice_stream = get_stream("Venice", self.user_profile.realm)
        self.verify_action(
            lambda: do_add_streams_to_default_stream_group(
                self.user_profile.realm,
                group,
                [venice_stream]),
            state_change_expected = False,
            num_events=0)

    def test_default_streams_events(self) -> None:
        stream = get_stream("Scotland", self.user_profile.realm)
        events = self.verify_action(
            lambda: do_add_default_stream(stream))
        check_default_streams('events[0]', events[0])
        events = self.verify_action(
            lambda: do_remove_default_stream(stream))
        check_default_streams('events[0]', events[0])

    def test_default_streams_events_guest(self) -> None:
        do_change_user_role(self.user_profile, UserProfile.ROLE_GUEST)
        stream = get_stream("Scotland", self.user_profile.realm)
        self.verify_action(
            lambda: do_add_default_stream(stream),
            state_change_expected = False,
            num_events=0)
        self.verify_action(
            lambda: do_remove_default_stream(stream),
            state_change_expected = False,
            num_events=0)

    def test_muted_topics_events(self) -> None:
        muted_topics_checker = check_events_dict([
            ('type', equals('muted_topics')),
            ('muted_topics', check_list(check_tuple([
                check_string,  # stream name
                check_string,  # topic name
                check_int,  # timestamp
            ]))),
        ])
        stream = get_stream('Denmark', self.user_profile.realm)
        recipient = stream.recipient
        events = self.verify_action(
            lambda: do_mute_topic(
                self.user_profile,
                stream,
                recipient,
                "topic"))
        muted_topics_checker('events[0]', events[0])

        events = self.verify_action(
            lambda: do_unmute_topic(
                self.user_profile,
                stream,
                "topic"))
        muted_topics_checker('events[0]', events[0])

    def test_change_avatar_fields(self) -> None:
        events = self.verify_action(
            lambda: do_change_avatar_fields(self.user_profile, UserProfile.AVATAR_FROM_USER, acting_user=self.user_profile),
        )
        check_realm_user_update('events[0]', events[0], avatar_fields)
        assert isinstance(events[0]['person']['avatar_url'], str)
        assert isinstance(events[0]['person']['avatar_url_medium'], str)

        events = self.verify_action(
            lambda: do_change_avatar_fields(self.user_profile, UserProfile.AVATAR_FROM_GRAVATAR, acting_user=self.user_profile),
        )
        check_realm_user_update('events[0]', events[0], avatar_fields)
        self.assertEqual(events[0]['person']['avatar_url'], None)
        self.assertEqual(events[0]['person']['avatar_url_medium'], None)

    def test_change_full_name(self) -> None:
        events = self.verify_action(
            lambda: do_change_full_name(
                self.user_profile,
                'Sir Hamlet',
                self.user_profile))
        check_realm_user_update('events[0]', events[0], {'full_name'})

    def test_change_user_delivery_email_email_address_visibilty_admins(self) -> None:
        do_set_realm_property(self.user_profile.realm, "email_address_visibility",
                              Realm.EMAIL_ADDRESS_VISIBILITY_ADMINS)
        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()
        action = lambda: do_change_user_delivery_email(self.user_profile, 'newhamlet@zulip.com')
        events = self.verify_action(
            action,
            num_events=2,
            client_gravatar=False)

        check_realm_user_update('events[0]', events[0], {"delivery_email"})
        check_realm_user_update('events[1]', events[1], avatar_fields)
        assert isinstance(events[1]['person']['avatar_url'], str)
        assert isinstance(events[1]['person']['avatar_url_medium'], str)

    def test_change_realm_authentication_methods(self) -> None:
        schema_checker = check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update_dict')),
            ('property', equals('default')),
            ('data', check_dict_only([
                ('authentication_methods', check_dict_only([
                    ('Google', check_bool),
                    ('Dev', check_bool),
                    ('LDAP', check_bool),
                    ('GitHub', check_bool),
                    ('Email', check_bool),
                ])),
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
                events = self.verify_action(
                    lambda: do_set_realm_authentication_methods(
                        self.user_profile.realm,
                        auth_method_dict))

            schema_checker('events[0]', events[0])

    def test_change_pin_stream(self) -> None:
        schema_checker = check_events_dict([
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
            events = self.verify_action(
                lambda: do_change_subscription_property(
                    self.user_profile,
                    sub,
                    stream,
                    "pin_to_top",
                    pinned))
            schema_checker('events[0]', events[0])

    def test_change_stream_notification_settings(self) -> None:
        for setting_name in ['email_notifications']:
            schema_checker = check_events_dict([
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
                events = self.verify_action(
                    lambda: do_change_subscription_property(
                        self.user_profile,
                        sub,
                        stream,
                        setting_name, value),
                    notification_settings_null=True)
                schema_checker('events[0]', events[0])

            for value in (True, False):
                events = self.verify_action(
                    lambda: do_change_subscription_property(
                        self.user_profile,
                        sub,
                        stream,
                        setting_name,
                        value))
                schema_checker('events[0]', events[0])

    def test_change_realm_message_edit_settings(self) -> None:
        schema_checker = check_events_dict([
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
            events = self.verify_action(
                lambda: do_set_realm_message_editing(self.user_profile.realm,
                                                     allow_message_editing,
                                                     message_content_edit_limit_seconds,
                                                     False))
            schema_checker('events[0]', events[0])

    def test_change_realm_notifications_stream(self) -> None:

        stream = get_stream("Rome", self.user_profile.realm)

        for notifications_stream, notifications_stream_id in ((stream, stream.id), (None, -1)):
            events = self.verify_action(
                lambda: do_set_realm_notifications_stream(self.user_profile.realm,
                                                          notifications_stream,
                                                          notifications_stream_id))
            check_realm_update('events[0]', events[0], 'notifications_stream_id')

    def test_change_realm_signup_notifications_stream(self) -> None:
        stream = get_stream("Rome", self.user_profile.realm)

        for signup_notifications_stream, signup_notifications_stream_id in ((stream, stream.id), (None, -1)):
            events = self.verify_action(
                lambda: do_set_realm_signup_notifications_stream(self.user_profile.realm,
                                                                 signup_notifications_stream,
                                                                 signup_notifications_stream_id))
            check_realm_update('events[0]', events[0], 'signup_notifications_stream_id')

    def test_change_is_admin(self) -> None:
        reset_emails_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER)
        for role in [UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_MEMBER]:
            events = self.verify_action(
                lambda: do_change_user_role(self.user_profile, role))
            check_realm_user_update('events[0]', events[0], {'role'})
            self.assertEqual(events[0]['person']['role'], role)

    def test_change_is_owner(self) -> None:
        reset_emails_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER)
        for role in [UserProfile.ROLE_REALM_OWNER, UserProfile.ROLE_MEMBER]:
            events = self.verify_action(
                lambda: do_change_user_role(self.user_profile, role))
            check_realm_user_update('events[0]', events[0], {'role'})
            self.assertEqual(events[0]['person']['role'], role)

    def test_change_is_guest(self) -> None:
        reset_emails_in_zulip_realm()

        # Important: We need to refresh from the database here so that
        # we don't have a stale UserProfile object with an old value
        # for email being passed into this next function.
        self.user_profile.refresh_from_db()

        do_change_user_role(self.user_profile, UserProfile.ROLE_MEMBER)
        for role in [UserProfile.ROLE_GUEST, UserProfile.ROLE_MEMBER]:
            events = self.verify_action(
                lambda: do_change_user_role(self.user_profile, role))
            check_realm_user_update('events[0]', events[0], {'role'})
            self.assertEqual(events[0]['person']['role'], role)

    def test_change_notification_settings(self) -> None:
        for notification_setting, v in self.user_profile.notification_setting_types.items():
            if notification_setting in ["notification_sound", "desktop_icon_count_display"]:
                # These settings are tested in their own tests.
                continue

            do_change_notification_settings(self.user_profile, notification_setting, False,
                                            acting_user=self.user_profile)

            for setting_value in [True, False]:
                events = self.verify_action(
                    lambda: do_change_notification_settings(
                        self.user_profile,
                        notification_setting,
                        setting_value,
                        acting_user=self.user_profile))
                check_update_global_notifications('events[0]', events[0], setting_value)

                # Also test with notification_settings_null=True
                events = self.verify_action(
                    lambda: do_change_notification_settings(
                        self.user_profile, notification_setting, setting_value,
                        acting_user=self.user_profile),
                    notification_settings_null=True,
                    state_change_expected=False)
                check_update_global_notifications('events[0]', events[0], setting_value)

    def test_change_notification_sound(self) -> None:
        notification_setting = "notification_sound"

        events = self.verify_action(
            lambda: do_change_notification_settings(
                self.user_profile,
                notification_setting,
                'ding'))
        check_update_global_notifications('events[0]', events[0], 'ding')

    def test_change_desktop_icon_count_display(self) -> None:
        notification_setting = "desktop_icon_count_display"

        events = self.verify_action(
            lambda: do_change_notification_settings(
                self.user_profile,
                notification_setting,
                2,
                acting_user=self.user_profile))
        check_update_global_notifications('events[0]', events[0], 2)

        events = self.verify_action(
            lambda: do_change_notification_settings(
                self.user_profile,
                notification_setting,
                1,
                acting_user=self.user_profile))
        check_update_global_notifications('events[0]', events[0], 1)

    def test_realm_update_plan_type(self) -> None:
        realm = self.user_profile.realm

        state_data = fetch_initial_state_data(self.user_profile, None, "", False, False)
        self.assertEqual(state_data['realm_plan_type'], Realm.SELF_HOSTED)
        self.assertEqual(state_data['zulip_plan_is_not_limited'], True)

        events = self.verify_action(
            lambda: do_change_plan_type(realm, Realm.LIMITED))
        check_realm_update('events[0]', events[0], 'plan_type')

        state_data = fetch_initial_state_data(self.user_profile, None, "", False, False)
        self.assertEqual(state_data['realm_plan_type'], Realm.LIMITED)
        self.assertEqual(state_data['zulip_plan_is_not_limited'], False)

    def test_realm_emoji_events(self) -> None:
        check_realm_emoji_fields = check_dict_only([
            ('id', check_string),
            ('name', check_string),
            ('source_url', check_string),
            ('deactivated', check_bool),
            ('author_id', check_int),
        ])

        def realm_emoji_checker(var_name: str, val: object) -> None:
            '''
            The way we send realm emojis is kinda clumsy--we
            send a dict mapping the emoji id to a sub_dict with
            the fields (including the id).  Ideally we can streamline
            this and just send a list of dicts.  The clients can make
            a Map as needed.
            '''
            assert isinstance(val, dict)
            for k, v in val.items():
                assert isinstance(k, str)
                assert v['id'] == k
                check_realm_emoji_fields(f'{var_name}[{k}]', v)

        schema_checker = check_events_dict([
            ('type', equals('realm_emoji')),
            ('op', equals('update')),
            ('realm_emoji', realm_emoji_checker),
        ])
        author = self.example_user('iago')
        with get_test_image_file('img.png') as img_file:
            events = self.verify_action(
                lambda: check_add_realm_emoji(
                    self.user_profile.realm,
                    "my_emoji",
                    author,
                    img_file))

        schema_checker('events[0]', events[0])

        events = self.verify_action(
            lambda: do_remove_realm_emoji(self.user_profile.realm, "my_emoji"))
        schema_checker('events[0]', events[0])

    def test_realm_filter_events(self) -> None:
        regex = "#(?P<id>[123])"
        url = "https://realm.com/my_realm_filter/%(id)s"

        schema_checker = check_events_dict([
            ('type', equals('realm_filters')),
            ('realm_filters', check_list(check_tuple([
                check_string,
                check_string,
                check_int,
            ]))),
        ])
        events = self.verify_action(
            lambda: do_add_realm_filter(self.user_profile.realm, regex, url))
        schema_checker('events[0]', events[0])

        events = self.verify_action(
            lambda: do_remove_realm_filter(self.user_profile.realm, "#(?P<id>[123])"))
        schema_checker('events[0]', events[0])

    def test_realm_domain_events(self) -> None:
        schema_checker = check_events_dict([
            ('type', equals('realm_domains')),
            ('op', equals('add')),
            ('realm_domain', check_dict_only([
                ('domain', check_string),
                ('allow_subdomains', check_bool),
            ])),
        ])
        events = self.verify_action(
            lambda: do_add_realm_domain(self.user_profile.realm, 'zulip.org', False))
        schema_checker('events[0]', events[0])

        schema_checker = check_events_dict([
            ('type', equals('realm_domains')),
            ('op', equals('change')),
            ('realm_domain', check_dict_only([
                ('domain', equals('zulip.org')),
                ('allow_subdomains', equals(True)),
            ])),
        ])
        test_domain = RealmDomain.objects.get(realm=self.user_profile.realm,
                                              domain='zulip.org')
        events = self.verify_action(
            lambda: do_change_realm_domain(test_domain, True))
        schema_checker('events[0]', events[0])

        schema_checker = check_events_dict([
            ('type', equals('realm_domains')),
            ('op', equals('remove')),
            ('domain', equals('zulip.org')),
        ])
        events = self.verify_action(
            lambda: do_remove_realm_domain(test_domain))
        schema_checker('events[0]', events[0])

    def test_create_bot(self) -> None:
        action = lambda: self.create_bot('test')
        events = self.verify_action(action, num_events=2)
        check_realm_bot_add('events[1]', events[1])

        action = lambda: self.create_bot('test_outgoing_webhook',
                                         full_name='Outgoing Webhook Bot',
                                         payload_url=orjson.dumps('https://foo.bar.com').decode(),
                                         interface_type=Service.GENERIC,
                                         bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)
        events = self.verify_action(action, num_events=2)
        # The third event is the second call of notify_created_bot, which contains additional
        # data for services (in contrast to the first call).
        check_realm_bot_add('events[1]', events[1])

        action = lambda: self.create_bot('test_embedded',
                                         full_name='Embedded Bot',
                                         service_name='helloworld',
                                         config_data=orjson.dumps({'foo': 'bar'}).decode(),
                                         bot_type=UserProfile.EMBEDDED_BOT)
        events = self.verify_action(action, num_events=2)
        check_realm_bot_add('events[1]', events[1])

    def test_change_bot_full_name(self) -> None:
        bot = self.create_bot('test')
        action = lambda: do_change_full_name(bot, 'New Bot Name', self.user_profile)
        events = self.verify_action(action, num_events=2)
        check_realm_bot_update('events[1]', events[1], 'full_name')

    def test_regenerate_bot_api_key(self) -> None:
        bot = self.create_bot('test')
        action = lambda: do_regenerate_api_key(bot, self.user_profile)
        events = self.verify_action(action)
        check_realm_bot_update('events[0]', events[0], 'api_key')

    def test_change_bot_avatar_source(self) -> None:
        bot = self.create_bot('test')
        action = lambda: do_change_avatar_fields(bot, bot.AVATAR_FROM_USER, acting_user=self.user_profile)
        events = self.verify_action(action, num_events=2)
        check_realm_bot_update('events[0]', events[0], 'avatar_url')
        self.assertEqual(events[1]['type'], 'realm_user')

    def test_change_realm_icon_source(self) -> None:
        action = lambda: do_change_icon_source(self.user_profile.realm, Realm.ICON_UPLOADED)
        events = self.verify_action(action, state_change_expected=True)
        schema_checker = check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update_dict')),
            ('property', equals('icon')),
            ('data', check_dict_only([
                ('icon_url', check_string),
                ('icon_source', check_string),
            ])),
        ])
        schema_checker('events[0]', events[0])

    def test_change_realm_day_mode_logo_source(self) -> None:
        action = lambda: do_change_logo_source(self.user_profile.realm, Realm.LOGO_UPLOADED, False, acting_user=self.user_profile)
        events = self.verify_action(action, state_change_expected=True)
        schema_checker = check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update_dict')),
            ('property', equals('logo')),
            ('data', check_dict_only([
                ('logo_url', check_string),
                ('logo_source', check_string),
            ])),
        ])
        schema_checker('events[0]', events[0])

    def test_change_realm_night_mode_logo_source(self) -> None:
        action = lambda: do_change_logo_source(self.user_profile.realm, Realm.LOGO_UPLOADED, True, acting_user=self.user_profile)
        events = self.verify_action(action, state_change_expected=True)
        schema_checker = check_events_dict([
            ('type', equals('realm')),
            ('op', equals('update_dict')),
            ('property', equals('night_logo')),
            ('data', check_dict_only([
                ('night_logo_url', check_string),
                ('night_logo_source', check_string),
            ])),
        ])
        schema_checker('events[0]', events[0])

    def test_change_bot_default_all_public_streams(self) -> None:
        bot = self.create_bot('test')
        action = lambda: do_change_default_all_public_streams(bot, True)
        events = self.verify_action(action)
        check_realm_bot_update('events[0]', events[0], 'default_all_public_streams')

    def test_change_bot_default_sending_stream(self) -> None:
        bot = self.create_bot('test')
        stream = get_stream("Rome", bot.realm)

        action = lambda: do_change_default_sending_stream(bot, stream)
        events = self.verify_action(action)
        check_realm_bot_update('events[0]', events[0], 'default_sending_stream')

        action = lambda: do_change_default_sending_stream(bot, None)
        events = self.verify_action(action)
        check_realm_bot_update('events[0]', events[0], 'default_sending_stream')

    def test_change_bot_default_events_register_stream(self) -> None:
        bot = self.create_bot('test')
        stream = get_stream("Rome", bot.realm)

        action = lambda: do_change_default_events_register_stream(bot, stream)
        events = self.verify_action(action)
        check_realm_bot_update('events[0]', events[0], 'default_events_register_stream')

        action = lambda: do_change_default_events_register_stream(bot, None)
        events = self.verify_action(action)
        check_realm_bot_update('events[0]', events[0], 'default_events_register_stream')

    def test_change_bot_owner(self) -> None:
        self.user_profile = self.example_user('iago')
        owner = self.example_user('hamlet')
        bot = self.create_bot('test')
        action = lambda: do_change_bot_owner(bot, owner, self.user_profile)
        events = self.verify_action(action, num_events=2)
        check_realm_bot_update('events[0]', events[0], 'owner_id')
        check_realm_user_update('events[1]', events[1], {"bot_owner_id"})

        self.user_profile = self.example_user('aaron')
        owner = self.example_user('hamlet')
        bot = self.create_bot('test1', full_name='Test1 Testerson')
        action = lambda: do_change_bot_owner(bot, owner, self.user_profile)
        events = self.verify_action(action, num_events=2)
        check_realm_bot_delete('events[0]', events[0])
        check_realm_user_update('events[1]', events[1], {"bot_owner_id"})

        previous_owner = self.example_user('aaron')
        self.user_profile = self.example_user('hamlet')
        bot = self.create_test_bot('test2', previous_owner, full_name='Test2 Testerson')
        action = lambda: do_change_bot_owner(bot, self.user_profile, previous_owner)
        events = self.verify_action(action, num_events=2)
        check_realm_bot_add('events[0]', events[0])
        check_realm_user_update('events[1]', events[1], {"bot_owner_id"})

    def test_do_update_outgoing_webhook_service(self) -> None:
        self.user_profile = self.example_user('iago')
        bot = self.create_test_bot('test', self.user_profile,
                                   full_name='Test Bot',
                                   bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                   payload_url=orjson.dumps('http://hostname.domain2.com').decode(),
                                   interface_type=Service.GENERIC,
                                   )
        action = lambda: do_update_outgoing_webhook_service(bot, 2, 'http://hostname.domain2.com')
        events = self.verify_action(action)
        check_realm_bot_update('events[0]', events[0], 'services')

    def test_do_deactivate_user(self) -> None:
        bot = self.create_bot('test')
        action = lambda: do_deactivate_user(bot)
        events = self.verify_action(action, num_events=2)
        check_realm_bot_remove('events[1]', events[1])

    def test_do_reactivate_user(self) -> None:
        bot = self.create_bot('test')
        do_deactivate_user(bot)
        action = lambda: do_reactivate_user(bot)
        events = self.verify_action(action, num_events=2)
        check_realm_bot_add('events[1]', events[1])

    def test_do_mark_hotspot_as_read(self) -> None:
        self.user_profile.tutorial_status = UserProfile.TUTORIAL_WAITING
        self.user_profile.save(update_fields=['tutorial_status'])

        schema_checker = check_events_dict([
            ('type', equals('hotspots')),
            ('hotspots', check_list(check_dict_only([
                ('name', check_string),
                ('title', check_string),
                ('description', check_string),
                ('delay', check_float),
            ]))),
        ])
        events = self.verify_action(
            lambda: do_mark_hotspot_as_read(self.user_profile, 'intro_reply'))
        schema_checker('events[0]', events[0])

    def test_rename_stream(self) -> None:
        stream = self.make_stream('old_name')
        new_name = 'stream with a brand new name'
        self.subscribe(self.user_profile, stream.name)
        notification = '<p><span class="user-mention silent" data-user-id="{user_id}">King Hamlet</span> renamed stream <strong>old_name</strong> to <strong>stream with a brand new name</strong>.</p>'
        notification = notification.format(user_id=self.user_profile.id)
        action = lambda: do_rename_stream(stream, new_name, self.user_profile)
        events = self.verify_action(action, num_events=3)

        check_stream_update('events[0]', events[0])
        self.assertEqual(events[0]['name'], 'old_name')

        check_stream_update('events[1]', events[1])
        self.assertEqual(events[1]['name'], 'old_name')

        check_message('events[2]', events[2])

        fields = dict(
            sender_email='notification-bot@zulip.com',
            display_recipient=new_name,
            sender_full_name='Notification Bot',
            is_me_message=False,
            type='stream',
            client='Internal',
        )

        fields[TOPIC_NAME] = 'stream events'

        msg = events[2]['message']
        for k, v in fields.items():
            self.assertEqual(msg[k], v)

    def test_deactivate_stream_neversubscribed(self) -> None:
        stream = self.make_stream('old_name')

        action = lambda: do_deactivate_stream(stream)
        events = self.verify_action(action)

        check_stream_delete('events[0]', events[0])

    def test_subscribe_other_user_never_subscribed(self) -> None:
        action = lambda: self.subscribe(self.example_user("othello"), "test_stream")
        events = self.verify_action(action, num_events=2)
        check_subscription_peer_add('events[1]', events[1])

    def test_do_delete_message_stream(self) -> None:
        schema_checker = check_events_dict([
            ('type', equals('delete_message')),
            ('message_ids', check_list(check_int, 2)),
            ('message_type', equals("stream")),
            ('stream_id', check_int),
            ('topic', check_string),
        ])
        hamlet = self.example_user('hamlet')
        msg_id = self.send_stream_message(hamlet, "Verona")
        msg_id_2 = self.send_stream_message(hamlet, "Verona")
        messages = [
            Message.objects.get(id=msg_id),
            Message.objects.get(id=msg_id_2)
        ]
        events = self.verify_action(
            lambda: do_delete_messages(self.user_profile.realm, messages),
            state_change_expected=True,
        )
        schema_checker('events[0]', events[0])

    def test_do_delete_message_stream_legacy(self) -> None:
        """
        Test for legacy method of deleting messages which
        sends an event per message to delete to the client.
        """
        schema_checker = check_events_dict([
            ('type', equals('delete_message')),
            ('message_id', check_int),
            ('message_type', equals("stream")),
            ('stream_id', check_int),
            ('topic', check_string),
        ])
        hamlet = self.example_user('hamlet')
        msg_id = self.send_stream_message(hamlet, "Verona")
        msg_id_2 = self.send_stream_message(hamlet, "Verona")
        messages = [
            Message.objects.get(id=msg_id),
            Message.objects.get(id=msg_id_2)
        ]
        events = self.verify_action(
            lambda: do_delete_messages(self.user_profile.realm, messages),
            state_change_expected=True, bulk_message_deletion=False,
            num_events=2
        )
        schema_checker('events[0]', events[0])

    def test_do_delete_message_personal(self) -> None:
        schema_checker = check_events_dict([
            ('type', equals('delete_message')),
            ('message_ids', check_list(check_int, 1)),
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
        events = self.verify_action(
            lambda: do_delete_messages(self.user_profile.realm, [message]),
            state_change_expected=True,
        )
        schema_checker('events[0]', events[0])

    def test_do_delete_message_personal_legacy(self) -> None:
        schema_checker = check_events_dict([
            ('type', equals('delete_message')),
            ('message_id', check_int),
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
        events = self.verify_action(
            lambda: do_delete_messages(self.user_profile.realm, [message]),
            state_change_expected=True, bulk_message_deletion=False
        )
        schema_checker('events[0]', events[0])

    def test_do_delete_message_no_max_id(self) -> None:
        user_profile = self.example_user('aaron')
        # Delete all historical messages for this user
        user_profile = self.example_user('hamlet')
        UserMessage.objects.filter(user_profile=user_profile).delete()
        msg_id = self.send_stream_message(user_profile, "Verona")
        message = Message.objects.get(id=msg_id)
        self.verify_action(
            lambda: do_delete_messages(self.user_profile.realm, [message]),
            state_change_expected=True,
        )
        result = fetch_initial_state_data(user_profile, None, "", client_gravatar=False, user_avatar_url_field_optional=False)
        self.assertEqual(result['max_message_id'], -1)

    def test_add_attachment(self) -> None:
        schema_checker = check_events_dict([
            ('type', equals('attachment')),
            ('op', equals('add')),
            ('attachment', check_dict_only([
                ('id', check_int),
                ('name', check_string),
                ('size', check_int),
                ('path_id', check_string),
                ('create_time', check_int),
                ('messages', check_list(check_dict_only([
                    ('id', check_int),
                    ('date_sent', check_int),
                ]))),
            ])),
            ('upload_space_used', equals(6)),
        ])

        self.login('hamlet')
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"
        uri = None

        def do_upload() -> None:
            nonlocal uri
            result = self.client_post("/json/user_uploads", {'file': fp})

            self.assert_json_success(result)
            self.assertIn("uri", result.json())
            uri = result.json()["uri"]
            base = '/user_uploads/'
            self.assertEqual(base, uri[:len(base)])

        events = self.verify_action(
            lambda: do_upload(),
            num_events=1, state_change_expected=False)
        schema_checker('events[0]', events[0])

        # Verify that the DB has the attachment marked as unclaimed
        entry = Attachment.objects.get(file_name='zulip.txt')
        self.assertEqual(entry.is_claimed(), False)

        # Now we send an actual message using this attachment.
        schema_checker = check_events_dict([
            ('type', equals('attachment')),
            ('op', equals('update')),
            ('attachment', check_dict_only([
                ('id', check_int),
                ('name', check_string),
                ('size', check_int),
                ('path_id', check_string),
                ('create_time', check_int),
                ('messages', check_list(check_dict_only([
                    ('id', check_int),
                    ('date_sent', check_int),
                ]))),
            ])),
            ('upload_space_used', equals(6)),
        ])

        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "Denmark")
        assert uri is not None
        body = f"First message ...[zulip.txt](http://{hamlet.realm.host}" + uri + ")"
        events = self.verify_action(
            lambda: self.send_stream_message(self.example_user("hamlet"), "Denmark", body, "test"),
            num_events=2)
        schema_checker('events[0]', events[0])

        # Now remove the attachment
        schema_checker = check_events_dict([
            ('type', equals('attachment')),
            ('op', equals('remove')),
            ('attachment', check_dict_only([
                ('id', check_int),
            ])),
            ('upload_space_used', equals(0)),
        ])

        events = self.verify_action(
            lambda: self.client_delete(f"/json/attachments/{entry.id}"),
            num_events=1, state_change_expected=False)
        schema_checker('events[0]', events[0])

    def test_notify_realm_export(self) -> None:
        pending_schema_checker = check_events_dict([
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

        schema_checker = check_events_dict([
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
            with stdout_suppressed(), self.assertLogs(level='INFO') as info_logs:
                events = self.verify_action(
                    lambda: self.client_post('/json/export/realm'),
                    state_change_expected=True, num_events=3)
            self.assertTrue(
                'INFO:root:Completed data export for zulip in' in info_logs.output[0]
            )

        # We first notify when an export is initiated,
        pending_schema_checker('events[0]', events[0])

        # The second event is then a message from notification-bot.
        schema_checker('events[2]', events[2])

        # Now we check the deletion of the export.
        deletion_schema_checker = check_events_dict([
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
        events = self.verify_action(
            lambda: self.client_delete(f'/json/export/realm/{audit_log_entry.id}'),
            state_change_expected=False, num_events=1)
        deletion_schema_checker('events[0]', events[0])

    def test_notify_realm_export_on_failure(self) -> None:
        pending_schema_checker = check_events_dict([
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

        failed_schema_checker = check_events_dict([
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
                        side_effect=Exception("test")), \
                self.assertLogs(level="ERROR") as error_log:
            with stdout_suppressed():
                events = self.verify_action(
                    lambda: self.client_post('/json/export/realm'),
                    state_change_expected=False, num_events=2)

            # Log is of following format: "ERROR:root:Data export for zulip failed after 0.004499673843383789"
            # Where last floating number is time and will vary in each test hence the following assertion is
            # independent of time bit by not matching exact log but only part of it.
            self.assertTrue("ERROR:root:Data export for zulip failed after" in error_log.output[0])

        pending_schema_checker('events[0]', events[0])

        failed_schema_checker('events[1]', events[1])

    def test_has_zoom_token(self) -> None:
        schema_checker = check_events_dict([
            ('type', equals('has_zoom_token')),
            ('value', equals(True)),
        ])
        events = self.verify_action(
            lambda: do_set_zoom_token(self.user_profile, {'access_token': 'token'}),
        )
        schema_checker('events[0]', events[0])

        schema_checker = check_events_dict([
            ('type', equals('has_zoom_token')),
            ('value', equals(False)),
        ])
        events = self.verify_action(
            lambda: do_set_zoom_token(self.user_profile, None))
        schema_checker('events[0]', events[0])

class RealmPropertyActionTest(BaseAction):
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
            ],
            default_code_block_language=['python', 'javascript'],
            message_content_delete_limit_seconds=[1000, 1100, 1200]
        )

        vals = test_values.get(name)
        property_type = Realm.property_types[name]
        if property_type is bool:
            vals = bool_tests

        if vals is None:
            raise AssertionError(f'No test created for {name}')
        now = timezone_now()
        do_set_realm_property(self.user_profile.realm, name, vals[0], acting_user=self.user_profile)
        self.assertEqual(RealmAuditLog.objects.filter(realm=self.user_profile.realm, event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                                                      event_time__gte=now, acting_user=self.user_profile).count(), 1)
        for count, val in enumerate(vals[1:]):
            now = timezone_now()
            state_change_expected = True
            events = self.verify_action(
                lambda: do_set_realm_property(self.user_profile.realm, name, val, acting_user=self.user_profile),
                state_change_expected=state_change_expected)

            old_value = vals[count]
            self.assertEqual(RealmAuditLog.objects.filter(
                realm=self.user_profile.realm, event_type=RealmAuditLog.REALM_PROPERTY_CHANGED,
                event_time__gte=now, acting_user=self.user_profile,
                extra_data=orjson.dumps({
                    RealmAuditLog.OLD_VALUE: old_value,
                    RealmAuditLog.NEW_VALUE: val,
                    'property': name,
                }).decode()).count(), 1)
            check_realm_update('events[0]', events[0], name)

    def test_change_realm_property(self) -> None:
        for prop in Realm.property_types:
            with self.settings(SEND_DIGEST_EMAILS=True):
                self.do_set_realm_property_test(prop)

class UserDisplayActionTest(BaseAction):
    def do_set_user_display_settings_test(self, setting_name: str) -> None:
        """Test updating each setting in UserProfile.property_types dict."""

        test_changes: Dict[str, Any] = dict(
            emojiset = ['twitter'],
            default_language = ['es', 'de', 'en'],
            timezone = ['US/Mountain', 'US/Samoa', 'Pacific/Galapogos', ''],
            demote_inactive_streams = [2, 3, 1],
            color_scheme = [2, 3, 1]
        )

        num_events = 1
        if setting_name == "timezone":
            num_events = 2
        values = test_changes.get(setting_name)

        property_type = UserProfile.property_types[setting_name]
        if property_type is bool:
            if getattr(self.user_profile, setting_name) is False:
                values = [True, False, True]
            else:
                values = [False, True, False]

        if values is None:
            raise AssertionError(f'No test created for {setting_name}')

        for value in values:
            events = self.verify_action(
                lambda: do_set_user_display_setting(
                    self.user_profile,
                    setting_name,
                    value),
                num_events=num_events)

            check_update_display_settings('events[0]', events[0])

            if setting_name == "timezone":
                check_realm_user_update('events[1]', events[1], {"email", "timezone"})

    def test_set_user_display_settings(self) -> None:
        for prop in UserProfile.property_types:
            self.do_set_user_display_settings_test(prop)

class SubscribeActionTest(BaseAction):
    def test_subscribe_events(self) -> None:
        self.do_test_subscribe_events(include_subscribers=True)

    def test_subscribe_events_no_include_subscribers(self) -> None:
        self.do_test_subscribe_events(include_subscribers=False)

    def do_test_subscribe_events(self, include_subscribers: bool) -> None:
        # Subscribe to a totally new stream, so it's just Hamlet on it
        action: Callable[[], object] = lambda: self.subscribe(self.example_user("hamlet"), "test_stream")
        events = self.verify_action(
            action,
            event_types=["subscription", "realm_user"],
            include_subscribers=include_subscribers)
        check_subscription_add('events[0]', events[0], include_subscribers)

        # Add another user to that totally new stream
        action = lambda: self.subscribe(self.example_user("othello"), "test_stream")
        events = self.verify_action(
            action,
            include_subscribers=include_subscribers,
            state_change_expected=include_subscribers)
        check_subscription_peer_add('events[0]', events[0])

        stream = get_stream("test_stream", self.user_profile.realm)

        # Now remove the first user, to test the normal unsubscribe flow
        action = lambda: bulk_remove_subscriptions(
            [self.example_user('othello')],
            [stream],
            get_client("website"))
        events = self.verify_action(
            action,
            include_subscribers=include_subscribers,
            state_change_expected=include_subscribers)
        check_subscription_peer_remove('events[0]', events[0])

        # Now remove the second user, to test the 'vacate' event flow
        action = lambda: bulk_remove_subscriptions(
            [self.example_user('hamlet')],
            [stream],
            get_client("website"))
        events = self.verify_action(
            action,
            include_subscribers=include_subscribers,
            num_events=3)
        check_subscription_remove('events[0]', events[0])
        self.assertEqual(len(events[0]['subscriptions']), 1)
        self.assertEqual(
            events[0]['subscriptions'][0]['name'],
            'test_stream',
        )

        # Now resubscribe a user, to make sure that works on a vacated stream
        action = lambda: self.subscribe(self.example_user("hamlet"), "test_stream")
        events = self.verify_action(
            action,
            include_subscribers=include_subscribers,
            num_events=2)
        check_subscription_add('events[1]', events[1], include_subscribers)

        action = lambda: do_change_stream_description(stream, 'new description')
        events = self.verify_action(
            action,
            include_subscribers=include_subscribers)
        check_stream_update('events[0]', events[0])

        # Update stream privacy
        action = lambda: do_change_stream_invite_only(stream, True, history_public_to_subscribers=True)
        events = self.verify_action(
            action,
            include_subscribers=include_subscribers)
        check_stream_update('events[0]', events[0])

        # Update stream stream_post_policy property
        action = lambda: do_change_stream_post_policy(stream, Stream.STREAM_POST_POLICY_ADMINS)
        events = self.verify_action(
            action,
            include_subscribers=include_subscribers, num_events=2)
        check_stream_update('events[0]', events[0])

        action = lambda: do_change_stream_message_retention_days(stream, -1)
        events = self.verify_action(
            action,
            include_subscribers=include_subscribers, num_events=1)
        check_stream_update('events[0]', events[0])

        # Subscribe to a totally new invite-only stream, so it's just Hamlet on it
        stream = self.make_stream("private", self.user_profile.realm, invite_only=True)
        user_profile = self.example_user('hamlet')
        action = lambda: bulk_add_subscriptions([stream], [user_profile])
        events = self.verify_action(
            action,
            include_subscribers=include_subscribers,
            num_events=2)
        check_stream_create('events[0]', events[0])
        check_subscription_add('events[1]', events[1], include_subscribers)
