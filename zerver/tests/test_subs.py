import random
from datetime import timedelta
from typing import Any, Dict, List, Mapping, Optional, Set, Union
from unittest import mock

import ujson
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now

from zerver.decorator import JsonableError
from zerver.lib import cache
from zerver.lib.actions import (
    bulk_add_subscriptions,
    bulk_get_subscriber_user_ids,
    bulk_remove_subscriptions,
    can_access_stream_user_ids,
    create_stream_if_needed,
    do_add_default_stream,
    do_add_streams_to_default_stream_group,
    do_change_default_stream_group_description,
    do_change_default_stream_group_name,
    do_change_stream_post_policy,
    do_change_user_role,
    do_create_default_stream_group,
    do_create_realm,
    do_deactivate_stream,
    do_deactivate_user,
    do_get_streams,
    do_remove_default_stream,
    do_remove_default_stream_group,
    do_remove_streams_from_default_stream_group,
    do_set_realm_property,
    ensure_stream,
    gather_subscriptions,
    gather_subscriptions_helper,
    get_average_weekly_stream_traffic,
    get_default_streams_for_realm,
    get_stream,
    lookup_default_stream_groups,
    round_to_2_significant_digits,
    validate_user_access_to_subscribers_helper,
)
from zerver.lib.message import aggregate_unread_data, get_raw_unread_data
from zerver.lib.response import json_error, json_success
from zerver.lib.stream_recipient import StreamRecipientMap
from zerver.lib.stream_subscription import (
    get_active_subscriptions_for_stream_id,
    num_subscribers_for_stream_id,
)
from zerver.lib.streams import (
    access_stream_by_id,
    access_stream_by_name,
    create_streams_if_needed,
    filter_stream_authorization,
    list_to_streams,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    get_subscription,
    queries_captured,
    reset_emails_in_zulip_realm,
    tornado_redirected_to_list,
)
from zerver.lib.test_runner import slow
from zerver.models import (
    DefaultStream,
    DefaultStreamGroup,
    Message,
    Realm,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
    active_non_guest_user_ids,
    flush_per_request_caches,
    get_client,
    get_default_stream_groups,
    get_realm,
    get_user,
    get_user_profile_by_id_in_realm,
)
from zerver.views.streams import compose_views


class TestMiscStuff(ZulipTestCase):
    def test_empty_results(self) -> None:
        # These are essentially just tests to ensure line
        # coverage for codepaths that won't ever really be
        # called in practice.

        user_profile = self.example_user('cordelia')

        result = bulk_get_subscriber_user_ids(
            stream_dicts=[],
            user_profile=user_profile,
            sub_dict={},
            stream_recipient=StreamRecipientMap(),
        )
        self.assertEqual(result, {})

        streams = do_get_streams(
            user_profile=user_profile,
            include_public=False,
            include_subscribed=False,
            include_all_active=False,
            include_default=False,
        )
        self.assertEqual(streams, [])

class TestCreateStreams(ZulipTestCase):
    def test_creating_streams(self) -> None:
        stream_names = ['new1', 'new2', 'new3']
        stream_descriptions = ['des1', 'des2', 'des3']
        realm = get_realm('zulip')

        # Test stream creation events.
        events: List[Mapping[str, Any]] = []
        with tornado_redirected_to_list(events):
            ensure_stream(realm, "Public stream", invite_only=False)
        self.assert_length(events, 1)

        self.assertEqual(events[0]['event']['type'], 'stream')
        self.assertEqual(events[0]['event']['op'], 'create')
        # Send public stream creation event to all active users.
        self.assertEqual(events[0]['users'], active_non_guest_user_ids(realm.id))
        self.assertEqual(events[0]['event']['streams'][0]['name'], "Public stream")

        events = []
        with tornado_redirected_to_list(events):
            ensure_stream(realm, "Private stream", invite_only=True)
        self.assert_length(events, 1)

        self.assertEqual(events[0]['event']['type'], 'stream')
        self.assertEqual(events[0]['event']['op'], 'create')
        # Send private stream creation event to only realm admins.
        self.assertEqual(len(events[0]['users']), 2)
        self.assertTrue(self.example_user("iago").id in events[0]['users'])
        self.assertTrue(self.example_user("desdemona").id in events[0]['users'])
        self.assertEqual(events[0]['event']['streams'][0]['name'], "Private stream")

        new_streams, existing_streams = create_streams_if_needed(
            realm,
            [{"name": stream_name,
              "description": stream_description,
              "invite_only": True,
              "stream_post_policy": Stream.STREAM_POST_POLICY_ADMINS}
             for (stream_name, stream_description) in zip(stream_names, stream_descriptions)])

        self.assertEqual(len(new_streams), 3)
        self.assertEqual(len(existing_streams), 0)

        actual_stream_names = {stream.name for stream in new_streams}
        self.assertEqual(actual_stream_names, set(stream_names))
        actual_stream_descriptions = {stream.description for stream in new_streams}
        self.assertEqual(actual_stream_descriptions, set(stream_descriptions))
        for stream in new_streams:
            self.assertTrue(stream.invite_only)
            self.assertTrue(stream.stream_post_policy == Stream.STREAM_POST_POLICY_ADMINS)

        new_streams, existing_streams = create_streams_if_needed(
            realm,
            [{"name": stream_name,
              "description": stream_description,
              "invite_only": True}
             for (stream_name, stream_description) in zip(stream_names, stream_descriptions)])

        self.assertEqual(len(new_streams), 0)
        self.assertEqual(len(existing_streams), 3)

        actual_stream_names = {stream.name for stream in existing_streams}
        self.assertEqual(actual_stream_names, set(stream_names))
        actual_stream_descriptions = {stream.description for stream in existing_streams}
        self.assertEqual(actual_stream_descriptions, set(stream_descriptions))
        for stream in existing_streams:
            self.assertTrue(stream.invite_only)

    def test_create_api_multiline_description(self) -> None:
        user = self.example_user("hamlet")
        realm = user.realm
        self.login_user(user)
        post_data = {'subscriptions': ujson.dumps([{"name": 'new_stream',
                                                    "description": "multi\nline\ndescription"}]),
                     'invite_only': ujson.dumps(False)}
        result = self.api_post(user, "/api/v1/users/me/subscriptions", post_data,
                               subdomain="zulip")
        self.assert_json_success(result)
        stream = get_stream("new_stream", realm)
        self.assertEqual(stream.description, 'multi line description')

    def test_history_public_to_subscribers_on_stream_creation(self) -> None:
        realm = get_realm('zulip')
        stream_dicts: List[Mapping[str, Any]] = [
            {
                "name": "publicstream",
                "description": "Public stream with public history",
            },
            {
                "name": "privatestream",
                "description": "Private stream with non-public history",
                "invite_only": True,
            },
            {
                "name": "privatewithhistory",
                "description": "Private stream with public history",
                "invite_only": True,
                "history_public_to_subscribers": True,
            },
            {
                "name": "publictrywithouthistory",
                "description": "Public stream without public history (disallowed)",
                "invite_only": False,
                "history_public_to_subscribers": False,
            },
        ]

        created, existing = create_streams_if_needed(realm, stream_dicts)

        self.assertEqual(len(created), 4)
        self.assertEqual(len(existing), 0)
        for stream in created:
            if stream.name == 'publicstream':
                self.assertTrue(stream.history_public_to_subscribers)
            if stream.name == 'privatestream':
                self.assertFalse(stream.history_public_to_subscribers)
            if stream.name == 'privatewithhistory':
                self.assertTrue(stream.history_public_to_subscribers)
            if stream.name == 'publictrywithouthistory':
                self.assertTrue(stream.history_public_to_subscribers)

    def test_history_public_to_subscribers_zephyr_realm(self) -> None:
        realm = get_realm('zephyr')

        stream, created = create_stream_if_needed(realm, "private_stream", invite_only=True)
        self.assertTrue(created)
        self.assertTrue(stream.invite_only)
        self.assertFalse(stream.history_public_to_subscribers)

        stream, created = create_stream_if_needed(realm, "public_stream", invite_only=False)
        self.assertTrue(created)
        self.assertFalse(stream.invite_only)
        self.assertFalse(stream.history_public_to_subscribers)

    def test_auto_mark_stream_created_message_as_read_for_stream_creator(self) -> None:
        # This test relies on email == delivery_email for
        # convenience.
        reset_emails_in_zulip_realm()

        realm = Realm.objects.get(name='Zulip Dev')
        iago = self.example_user('iago')
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        aaron = self.example_user('aaron')

        # Establish a stream for notifications.
        announce_stream = ensure_stream(realm, "announce", False, "announcements here.")
        realm.notifications_stream_id = announce_stream.id
        realm.save(update_fields=['notifications_stream_id'])

        self.subscribe(iago, announce_stream.name)
        self.subscribe(hamlet, announce_stream.name)

        notification_bot = UserProfile.objects.get(full_name="Notification Bot")
        self.login_user(iago)

        initial_message_count = Message.objects.count()
        initial_usermessage_count = UserMessage.objects.count()

        data = {
            "subscriptions": '[{"name":"brand new stream","description":""}]',
            "history_public_to_subscribers": 'true',
            "invite_only": 'false',
            "announce": 'true',
            "principals": ujson.dumps([iago.id, aaron.id, cordelia.id, hamlet.id]),
            "stream_post_policy": '1',
        }

        response = self.client_post("/json/users/me/subscriptions", data)

        final_message_count = Message.objects.count()
        final_usermessage_count = UserMessage.objects.count()

        expected_response = {
            "result": "success",
            "msg": "",
            "subscribed": {
                "AARON@zulip.com": ["brand new stream"],
                "cordelia@zulip.com": ["brand new stream"],
                "hamlet@zulip.com": ["brand new stream"],
                "iago@zulip.com": ["brand new stream"],
            },
            "already_subscribed": {},
        }
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ujson.loads(response.content.decode()), expected_response)

        # 2 messages should be created, one in announce and one in the new stream itself.
        self.assertEqual(final_message_count - initial_message_count, 2)
        # 4 UserMessages per subscriber: One for each of the subscribers, plus 1 for
        # each user in the notifications stream.
        announce_stream_subs = Subscription.objects.filter(recipient=announce_stream.recipient)
        self.assertEqual(final_usermessage_count - initial_usermessage_count,
                         4 + announce_stream_subs.count())

        def get_unread_stream_data(user: UserProfile) -> List[Dict[str, Any]]:
            raw_unread_data = get_raw_unread_data(user)
            aggregated_data = aggregate_unread_data(raw_unread_data)
            return aggregated_data['streams']

        stream_id = Stream.objects.get(name='brand new stream').id
        iago_unread_messages = get_unread_stream_data(iago)
        hamlet_unread_messages = get_unread_stream_data(hamlet)

        # The stream creation messages should be unread for Hamlet
        self.assertEqual(len(hamlet_unread_messages), 2)

        # According to the code in zerver/views/streams/add_subscriptions_backend
        # the notification stream message is sent first, then the new stream's message.
        self.assertEqual(hamlet_unread_messages[0]['sender_ids'][0], notification_bot.id)
        self.assertEqual(hamlet_unread_messages[1]['stream_id'], stream_id)

        # But it should be marked as read for Iago, the stream creator.
        self.assertEqual(len(iago_unread_messages), 0)

class RecipientTest(ZulipTestCase):
    def test_recipient(self) -> None:
        realm = get_realm('zulip')
        stream = get_stream('Verona', realm)
        recipient = Recipient.objects.get(
            type_id=stream.id,
            type=Recipient.STREAM,
        )
        self.assertEqual(str(recipient), '<Recipient: Verona (%d, %d)>' % (
            stream.id, Recipient.STREAM))

class StreamAdminTest(ZulipTestCase):
    def test_make_stream_public(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        self.make_stream('private_stream', invite_only=True)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)
        params = {
            'stream_name': ujson.dumps('private_stream'),
            'is_private': ujson.dumps(False),
        }
        stream_id = get_stream('private_stream', user_profile.realm).id
        result = self.client_patch("/json/streams/%d" % (stream_id,), params)
        self.assert_json_error(result, 'Invalid stream id')

        stream = self.subscribe(user_profile, 'private_stream')
        self.assertFalse(stream.is_in_zephyr_realm)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)
        params = {
            'stream_name': ujson.dumps('private_stream'),
            'is_private': ujson.dumps(False),
        }
        result = self.client_patch("/json/streams/%d" % (stream_id,), params)
        self.assert_json_success(result)

        realm = user_profile.realm
        stream = get_stream('private_stream', realm)
        self.assertFalse(stream.invite_only)
        self.assertTrue(stream.history_public_to_subscribers)

    def test_make_stream_private(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        realm = user_profile.realm
        self.make_stream('public_stream', realm=realm)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)
        params = {
            'stream_name': ujson.dumps('public_stream'),
            'is_private': ujson.dumps(True),
        }
        stream_id = get_stream('public_stream', realm).id
        result = self.client_patch("/json/streams/%d" % (stream_id,), params)
        self.assert_json_success(result)
        stream = get_stream('public_stream', realm)
        self.assertTrue(stream.invite_only)
        self.assertFalse(stream.history_public_to_subscribers)

    def test_make_stream_public_zephyr_mirror(self) -> None:
        user_profile = self.mit_user('starnine')
        self.login_user(user_profile)
        realm = user_profile.realm
        self.make_stream('target_stream', realm=realm, invite_only=True)
        self.subscribe(user_profile, 'target_stream')

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)
        params = {
            'stream_name': ujson.dumps('target_stream'),
            'is_private': ujson.dumps(False),
        }
        stream_id = get_stream('target_stream', realm).id
        result = self.client_patch("/json/streams/%d" % (stream_id,), params,
                                   subdomain="zephyr")
        self.assert_json_success(result)
        stream = get_stream('target_stream', realm)
        self.assertFalse(stream.invite_only)
        self.assertFalse(stream.history_public_to_subscribers)

    def test_make_stream_private_with_public_history(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        realm = user_profile.realm
        self.make_stream('public_history_stream', realm=realm)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)
        params = {
            'stream_name': ujson.dumps('public_history_stream'),
            'is_private': ujson.dumps(True),
            'history_public_to_subscribers': ujson.dumps(True),
        }
        stream_id = get_stream('public_history_stream', realm).id
        result = self.client_patch("/json/streams/%d" % (stream_id,), params)
        self.assert_json_success(result)
        stream = get_stream('public_history_stream', realm)
        self.assertTrue(stream.invite_only)
        self.assertTrue(stream.history_public_to_subscribers)

    def test_try_make_stream_public_with_private_history(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        realm = user_profile.realm
        self.make_stream('public_stream', realm=realm)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)
        params = {
            'stream_name': ujson.dumps('public_stream'),
            'is_private': ujson.dumps(False),
            'history_public_to_subscribers': ujson.dumps(False),
        }
        stream_id = get_stream('public_stream', realm).id
        result = self.client_patch("/json/streams/%d" % (stream_id,), params)
        self.assert_json_success(result)
        stream = get_stream('public_stream', realm)
        self.assertFalse(stream.invite_only)
        self.assertTrue(stream.history_public_to_subscribers)

    def test_deactivate_stream_backend(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        stream = self.make_stream('new_stream')
        self.subscribe(user_profile, stream.name)
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)

        result = self.client_delete('/json/streams/%d' % (stream.id,))
        self.assert_json_success(result)
        subscription_exists = get_active_subscriptions_for_stream_id(stream.id).filter(
            user_profile=user_profile,
        ).exists()
        self.assertFalse(subscription_exists)

    def test_deactivate_stream_removes_default_stream(self) -> None:
        stream = self.make_stream('new_stream')
        do_add_default_stream(stream)
        self.assertEqual(1, DefaultStream.objects.filter(stream_id=stream.id).count())
        do_deactivate_stream(stream)
        self.assertEqual(0, DefaultStream.objects.filter(stream_id=stream.id).count())

    def test_deactivate_stream_removes_stream_from_default_stream_groups(self) -> None:
        realm = get_realm('zulip')
        streams_to_keep = []
        for stream_name in ["stream1", "stream2"]:
            stream = ensure_stream(realm, stream_name)
            streams_to_keep.append(stream)

        streams_to_remove = []
        stream = ensure_stream(realm, "stream3")
        streams_to_remove.append(stream)

        all_streams = streams_to_keep + streams_to_remove

        def get_streams(group: DefaultStreamGroup) -> List[Stream]:
            return list(group.streams.all().order_by('name'))

        group_name = "group1"
        description = "This is group1"
        do_create_default_stream_group(realm, group_name, description, all_streams)
        default_stream_groups = get_default_stream_groups(realm)
        self.assertEqual(get_streams(default_stream_groups[0]), all_streams)

        do_deactivate_stream(streams_to_remove[0])
        self.assertEqual(get_streams(default_stream_groups[0]), streams_to_keep)

    def test_vacate_private_stream_removes_default_stream(self) -> None:
        stream = self.make_stream('new_stream', invite_only=True)
        self.subscribe(self.example_user("hamlet"), stream.name)
        do_add_default_stream(stream)
        self.assertEqual(1, DefaultStream.objects.filter(stream_id=stream.id).count())
        self.unsubscribe(self.example_user("hamlet"), stream.name)
        self.assertEqual(0, DefaultStream.objects.filter(stream_id=stream.id).count())
        # Fetch stream again from database.
        stream = Stream.objects.get(id=stream.id)
        self.assertTrue(stream.deactivated)

    def test_deactivate_stream_backend_requires_existing_stream(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        self.make_stream('new_stream')
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)

        result = self.client_delete('/json/streams/999999999')
        self.assert_json_error(result, 'Invalid stream id')

    def test_deactivate_stream_backend_requires_realm_admin(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        self.subscribe(user_profile, 'new_stream')

        stream_id = get_stream('new_stream', user_profile.realm).id
        result = self.client_delete('/json/streams/%d' % (stream_id,))
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_private_stream_live_updates(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)

        self.make_stream('private_stream', invite_only=True)
        self.subscribe(user_profile, 'private_stream')
        self.subscribe(self.example_user("cordelia"), 'private_stream')

        events: List[Mapping[str, Any]] = []
        with tornado_redirected_to_list(events):
            stream_id = get_stream('private_stream', user_profile.realm).id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'description': ujson.dumps('Test description')})
        self.assert_json_success(result)
        # Should be just a description change event
        self.assert_length(events, 1)

        cordelia = self.example_user('cordelia')
        prospero = self.example_user('prospero')

        notified_user_ids = set(events[-1]['users'])
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertIn(cordelia.id, notified_user_ids)
        self.assertNotIn(prospero.id, notified_user_ids)

        events = []
        with tornado_redirected_to_list(events):
            stream_id = get_stream('private_stream', user_profile.realm).id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps('whatever')})
        self.assert_json_success(result)
        # Should be a name event, an email address event and a notification event
        self.assert_length(events, 3)

        notified_user_ids = set(events[0]['users'])
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertIn(cordelia.id, notified_user_ids)
        self.assertNotIn(prospero.id, notified_user_ids)

        notified_with_bot_users = events[-1]['users']
        notified_with_bot_user_ids = []
        notified_with_bot_user_ids.append(notified_with_bot_users[0]['id'])
        notified_with_bot_user_ids.append(notified_with_bot_users[1]['id'])
        self.assertIn(user_profile.id, notified_with_bot_user_ids)
        self.assertIn(cordelia.id, notified_with_bot_user_ids)
        self.assertNotIn(prospero.id, notified_with_bot_user_ids)

    def test_rename_stream(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        realm = user_profile.realm
        stream = self.subscribe(user_profile, 'stream_name1')
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)

        result = self.client_patch('/json/streams/%d' % (stream.id,),
                                   {'new_name': ujson.dumps('stream_name1')})
        self.assert_json_error(result, "Stream already has that name!")
        result = self.client_patch('/json/streams/%d' % (stream.id,),
                                   {'new_name': ujson.dumps('Denmark')})
        self.assert_json_error(result, "Stream name 'Denmark' is already taken.")
        result = self.client_patch('/json/streams/%d' % (stream.id,),
                                   {'new_name': ujson.dumps('denmark ')})
        self.assert_json_error(result, "Stream name 'denmark' is already taken.")

        # Do a rename that is case-only--this should succeed.
        result = self.client_patch('/json/streams/%d' % (stream.id,),
                                   {'new_name': ujson.dumps('sTREAm_name1')})
        self.assert_json_success(result)

        events: List[Mapping[str, Any]] = []
        with tornado_redirected_to_list(events):
            stream_id = get_stream('stream_name1', user_profile.realm).id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps('stream_name2')})
        self.assert_json_success(result)
        event = events[1]['event']
        self.assertEqual(event, dict(
            op='update',
            type='stream',
            property='name',
            value='stream_name2',
            stream_id=stream_id,
            name='sTREAm_name1',
        ))
        notified_user_ids = set(events[1]['users'])

        self.assertRaises(Stream.DoesNotExist, get_stream, 'stream_name1', realm)

        stream_name2_exists = get_stream('stream_name2', realm)
        self.assertTrue(stream_name2_exists)

        self.assertEqual(notified_user_ids, set(active_non_guest_user_ids(realm.id)))
        self.assertIn(user_profile.id,
                      notified_user_ids)
        self.assertIn(self.example_user('prospero').id,
                      notified_user_ids)
        self.assertNotIn(self.example_user('polonius').id,
                         notified_user_ids)

        # Test case to handle unicode stream name change
        # *NOTE: Here Encoding is needed when Unicode string is passed as an argument*
        with tornado_redirected_to_list(events):
            stream_id = stream_name2_exists.id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps('नया नाम'.encode())})
        self.assert_json_success(result)
        # While querying, system can handle unicode strings.
        stream_name_uni_exists = get_stream('नया नाम', realm)
        self.assertTrue(stream_name_uni_exists)

        # Test case to handle changing of unicode stream name to newer name
        # NOTE: Unicode string being part of URL is handled cleanly
        # by client_patch call, encoding of URL is not needed.
        with tornado_redirected_to_list(events):
            stream_id = stream_name_uni_exists.id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps('नाम में क्या रक्खा हे'.encode())})
        self.assert_json_success(result)
        # While querying, system can handle unicode strings.
        self.assertRaises(Stream.DoesNotExist, get_stream, 'नया नाम', realm)

        stream_name_new_uni_exists = get_stream('नाम में क्या रक्खा हे', realm)
        self.assertTrue(stream_name_new_uni_exists)

        # Test case to change name from one language to other.
        with tornado_redirected_to_list(events):
            stream_id = stream_name_new_uni_exists.id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps('français'.encode())})
        self.assert_json_success(result)
        stream_name_fr_exists = get_stream('français', realm)
        self.assertTrue(stream_name_fr_exists)

        # Test case to change name to mixed language name.
        with tornado_redirected_to_list(events):
            stream_id = stream_name_fr_exists.id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps('français name'.encode())})
        self.assert_json_success(result)
        stream_name_mixed_exists = get_stream('français name', realm)
        self.assertTrue(stream_name_mixed_exists)

        # Test case for notified users in private streams.
        stream_private = self.make_stream('stream_private_name1', realm=user_profile.realm, invite_only=True)
        self.subscribe(self.example_user('cordelia'), 'stream_private_name1')
        del events[:]
        with tornado_redirected_to_list(events):
            stream_id = get_stream('stream_private_name1', realm).id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'new_name': ujson.dumps('stream_private_name2')})
        self.assert_json_success(result)
        notified_user_ids = set(events[1]['users'])
        self.assertEqual(notified_user_ids, can_access_stream_user_ids(stream_private))
        self.assertIn(self.example_user('cordelia').id, notified_user_ids)
        # An important corner case is that all organization admins are notified.
        self.assertIn(self.example_user('iago').id, notified_user_ids)
        # The current user, Hamlet was made an admin and thus should be notified too.
        self.assertIn(user_profile.id, notified_user_ids)
        self.assertNotIn(self.example_user('prospero').id,
                         notified_user_ids)

    def test_rename_stream_requires_realm_admin(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        self.make_stream('stream_name1')

        stream_id = get_stream('stream_name1', user_profile.realm).id
        result = self.client_patch('/json/streams/%d' % (stream_id,),
                                   {'new_name': ujson.dumps('stream_name2')})
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_notify_on_stream_rename(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        self.make_stream('stream_name1')

        stream = self.subscribe(user_profile, 'stream_name1')
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)
        result = self.client_patch('/json/streams/%d' % (stream.id,),
                                   {'new_name': ujson.dumps('stream_name2')})
        self.assert_json_success(result)

        # Inspect the notification message sent
        message = self.get_last_message()
        actual_stream = Stream.objects.get(id=message.recipient.type_id)
        message_content = f'@_**King Hamlet|{user_profile.id}** renamed stream **stream_name1** to **stream_name2**.'
        self.assertEqual(actual_stream.name, 'stream_name2')
        self.assertEqual(actual_stream.realm_id, user_profile.realm_id)
        self.assertEqual(message.recipient.type, Recipient.STREAM)
        self.assertEqual(message.content, message_content)
        self.assertEqual(message.sender.email, 'notification-bot@zulip.com')
        self.assertEqual(message.sender.realm, get_realm(settings.SYSTEM_BOT_REALM))

    def test_realm_admin_can_update_unsub_private_stream(self) -> None:
        iago = self.example_user('iago')
        hamlet = self.example_user('hamlet')

        self.login_user(iago)
        result = self.common_subscribe_to_streams(iago, ["private_stream"],
                                                  dict(principals=ujson.dumps([hamlet.id])),
                                                  invite_only=True)
        self.assert_json_success(result)

        stream_id = get_stream('private_stream', iago.realm).id
        result = self.client_patch('/json/streams/%d' % (stream_id,),
                                   {'new_name': ujson.dumps('new_private_stream')})
        self.assert_json_success(result)

        result = self.client_patch('/json/streams/%d' % (stream_id,),
                                   {'new_description': ujson.dumps('new description')})
        self.assert_json_success(result)

        # But cannot change stream type.
        result = self.client_patch('/json/streams/%d' % (stream_id,),
                                   {'stream_name': ujson.dumps('private_stream'),
                                    'is_private': ujson.dumps(True)})
        self.assert_json_error(result, "Invalid stream id")

    def test_change_stream_description(self) -> None:
        user_profile = self.example_user('iago')
        self.login_user(user_profile)
        realm = user_profile.realm
        self.subscribe(user_profile, 'stream_name1')

        events: List[Mapping[str, Any]] = []
        with tornado_redirected_to_list(events):
            stream_id = get_stream('stream_name1', realm).id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'description': ujson.dumps('Test description')})
        self.assert_json_success(result)

        event = events[0]['event']
        self.assertEqual(event, dict(
            op='update',
            type='stream',
            property='description',
            value='Test description',
            rendered_description='<p>Test description</p>',
            stream_id=stream_id,
            name='stream_name1',
        ))
        notified_user_ids = set(events[0]['users'])

        stream = get_stream('stream_name1', realm)
        self.assertEqual(notified_user_ids, set(active_non_guest_user_ids(realm.id)))
        self.assertIn(user_profile.id,
                      notified_user_ids)
        self.assertIn(self.example_user('prospero').id,
                      notified_user_ids)
        self.assertNotIn(self.example_user('polonius').id,
                         notified_user_ids)

        self.assertEqual('Test description', stream.description)

        result = self.client_patch('/json/streams/%d' % (stream_id,),
                                   {'description': ujson.dumps('a' * 1025)})
        self.assert_json_error(result, "description is too long (limit: %s characters)"
                               % (Stream.MAX_DESCRIPTION_LENGTH,))

        result = self.client_patch('/json/streams/%d' % (stream_id,),
                                   {'description': ujson.dumps('a\nmulti\nline\ndescription')})
        self.assert_json_success(result)
        stream = get_stream('stream_name1', realm)
        self.assertEqual(stream.description, 'a multi line description')

        # Verify that we don't render inline URL previews in this code path.
        with self.settings(INLINE_URL_EMBED_PREVIEW=True):
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'description': ujson.dumps('See https://zulip.com/team')})
        self.assert_json_success(result)
        stream = get_stream('stream_name1', realm)
        self.assertEqual(
            stream.rendered_description,
            '<p>See <a href="https://zulip.com/team">https://zulip.com/team</a></p>',
        )

    def test_change_stream_description_requires_realm_admin(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)

        self.subscribe(user_profile, 'stream_name1')
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER)

        stream_id = get_stream('stream_name1', user_profile.realm).id
        result = self.client_patch('/json/streams/%d' % (stream_id,),
                                   {'description': ujson.dumps('Test description')})
        self.assert_json_error(result, 'Must be an organization administrator')

    def test_change_to_stream_post_policy_admins(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)

        self.subscribe(user_profile, 'stream_name1')
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)

        stream_id = get_stream('stream_name1', user_profile.realm).id
        result = self.client_patch('/json/streams/%d' % (stream_id,),
                                   {'is_announcement_only': ujson.dumps(True)})
        self.assert_json_success(result)
        stream = get_stream('stream_name1', user_profile.realm)
        self.assertTrue(stream.stream_post_policy == Stream.STREAM_POST_POLICY_ADMINS)

    def test_change_stream_post_policy_requires_realm_admin(self) -> None:
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)

        self.subscribe(user_profile, 'stream_name1')
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER)

        do_set_realm_property(user_profile.realm, 'waiting_period_threshold', 10)

        def test_non_admin(how_old: int, is_new: bool, policy: int) -> None:
            user_profile.date_joined = timezone_now() - timedelta(days=how_old)
            user_profile.save()
            self.assertEqual(user_profile.is_new_member, is_new)
            stream_id = get_stream('stream_name1', user_profile.realm).id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'stream_post_policy': ujson.dumps(policy)})
            self.assert_json_error(result, 'Must be an organization administrator')

        policies = [Stream.STREAM_POST_POLICY_ADMINS, Stream.STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS]

        for policy in policies:
            test_non_admin(how_old=15, is_new=False, policy=policy)
            test_non_admin(how_old=5, is_new=True, policy=policy)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)

        for policy in policies:
            stream_id = get_stream('stream_name1', user_profile.realm).id
            result = self.client_patch('/json/streams/%d' % (stream_id,),
                                       {'stream_post_policy': ujson.dumps(policy)})
            self.assert_json_success(result)
            stream = get_stream('stream_name1', user_profile.realm)
            self.assertEqual(stream.stream_post_policy, policy)

    def set_up_stream_for_deletion(self, stream_name: str, invite_only: bool=False,
                                   subscribed: bool=True) -> Stream:
        """
        Create a stream for deletion by an administrator.
        """
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)
        stream = self.make_stream(stream_name, invite_only=invite_only)

        # For testing deleting streams you aren't on.
        if subscribed:
            self.subscribe(user_profile, stream_name)

        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)

        return stream

    def delete_stream(self, stream: Stream) -> None:
        """
        Delete the stream and assess the result.
        """
        active_name = stream.name
        realm = stream.realm
        stream_id = stream.id

        # Simulate that a stream by the same name has already been
        # deactivated, just to exercise our renaming logic:
        ensure_stream(realm, "!DEACTIVATED:" + active_name)

        events: List[Mapping[str, Any]] = []
        with tornado_redirected_to_list(events):
            result = self.client_delete('/json/streams/' + str(stream_id))
        self.assert_json_success(result)

        # We no longer send subscription events for stream deactivations.
        sub_events = [e for e in events if e['event']['type'] == 'subscription']
        self.assertEqual(sub_events, [])

        stream_events = [e for e in events if e['event']['type'] == 'stream']
        self.assertEqual(len(stream_events), 1)
        event = stream_events[0]['event']
        self.assertEqual(event['op'], 'delete')
        self.assertEqual(event['streams'][0]['stream_id'], stream.id)

        with self.assertRaises(Stream.DoesNotExist):
            Stream.objects.get(realm=get_realm("zulip"), name=active_name)

        # A deleted stream's name is changed, is deactivated, is invite-only,
        # and has no subscribers.
        deactivated_stream_name = "!!DEACTIVATED:" + active_name
        deactivated_stream = get_stream(deactivated_stream_name, realm)
        self.assertTrue(deactivated_stream.deactivated)
        self.assertTrue(deactivated_stream.invite_only)
        self.assertEqual(deactivated_stream.name, deactivated_stream_name)
        subscribers = self.users_subscribed_to_stream(
            deactivated_stream_name, realm)
        self.assertEqual(subscribers, [])

        # It doesn't show up in the list of public streams anymore.
        result = self.client_get("/json/streams?include_subscribed=false")
        public_streams = [s["name"] for s in result.json()["streams"]]
        self.assertNotIn(active_name, public_streams)
        self.assertNotIn(deactivated_stream_name, public_streams)

        # Even if you could guess the new name, you can't subscribe to it.
        result = self.client_post(
            "/json/users/me/subscriptions",
            {"subscriptions": ujson.dumps([{"name": deactivated_stream_name}])})
        self.assert_json_error(
            result, f"Unable to access stream ({deactivated_stream_name}).")

    def test_you_must_be_realm_admin(self) -> None:
        """
        You must be on the realm to create a stream.
        """
        user_profile = self.example_user('hamlet')
        self.login_user(user_profile)

        other_realm = Realm.objects.create(string_id='other')
        stream = self.make_stream('other_realm_stream', realm=other_realm)

        result = self.client_delete('/json/streams/' + str(stream.id))
        self.assert_json_error(result, 'Must be an organization administrator')

        # Even becoming a realm admin doesn't help us for an out-of-realm
        # stream.
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)
        result = self.client_delete('/json/streams/' + str(stream.id))
        self.assert_json_error(result, 'Invalid stream id')

    def test_delete_public_stream(self) -> None:
        """
        When an administrator deletes a public stream, that stream is not
        visible to users at all anymore.
        """
        stream = self.set_up_stream_for_deletion("newstream")
        self.delete_stream(stream)

    def test_delete_private_stream(self) -> None:
        """
        Administrators can delete private streams they are on.
        """
        stream = self.set_up_stream_for_deletion("newstream", invite_only=True)
        self.delete_stream(stream)

    def test_delete_streams_youre_not_on(self) -> None:
        """
        Administrators can delete public streams they aren't on, including
        private streams in their realm.
        """
        pub_stream = self.set_up_stream_for_deletion(
            "pubstream", subscribed=False)
        self.delete_stream(pub_stream)

        priv_stream = self.set_up_stream_for_deletion(
            "privstream", subscribed=False, invite_only=True)
        self.delete_stream(priv_stream)

    def attempt_unsubscribe_of_principal(self, query_count: int, target_users: List[UserProfile],
                                         is_admin: bool=False, is_subbed: bool=True, invite_only: bool=False,
                                         target_users_subbed: bool=True, using_legacy_emails: bool=False,
                                         other_sub_users: Optional[List[UserProfile]]=None) -> HttpResponse:

        # Set up the main user, who is in most cases an admin.
        if is_admin:
            user_profile = self.example_user('iago')
        else:
            user_profile = self.example_user('hamlet')

        self.login_user(user_profile)

        # Set up the stream.
        stream_name = "hümbüǵ"
        self.make_stream(stream_name, invite_only=invite_only)

        # Set up the principal to be unsubscribed.
        principals = []
        for user in target_users:
            if using_legacy_emails:
                principals.append(user.email)
            else:
                principals.append(user.id)

        # Subscribe the admin and/or principal as specified in the flags.
        if is_subbed:
            self.subscribe(user_profile, stream_name)
        if target_users_subbed:
            for user in target_users:
                self.subscribe(user, stream_name)
        if other_sub_users:
            for user in other_sub_users:
                self.subscribe(user, stream_name)

        with queries_captured() as queries:
            result = self.client_delete(
                "/json/users/me/subscriptions",
                {"subscriptions": ujson.dumps([stream_name]),
                 "principals": ujson.dumps(principals)})
        self.assert_length(queries, query_count)

        # If the removal succeeded, then assert that Cordelia is no longer subscribed.
        if result.status_code not in [400]:
            subbed_users = self.users_subscribed_to_stream(stream_name, user_profile.realm)
            for user in target_users:
                self.assertNotIn(user, subbed_users)

        return result

    def test_cant_remove_others_from_stream(self) -> None:
        """
        If you're not an admin, you can't remove other people from streams.
        """
        result = self.attempt_unsubscribe_of_principal(
            query_count=3, target_users=[self.example_user('cordelia')], is_admin=False, is_subbed=True,
            invite_only=False, target_users_subbed=True)
        self.assert_json_error(
            result, "This action requires administrative rights")

    def test_admin_remove_others_from_public_stream(self) -> None:
        """
        If you're an admin, you can remove people from public streams, even
        those you aren't on.
        """
        result = self.attempt_unsubscribe_of_principal(
            query_count=21, target_users=[self.example_user('cordelia')], is_admin=True, is_subbed=True,
            invite_only=False, target_users_subbed=True)
        json = self.assert_json_success(result)
        self.assertEqual(len(json["removed"]), 1)
        self.assertEqual(len(json["not_removed"]), 0)

    def test_admin_remove_multiple_users_from_stream(self) -> None:
        """
        If you're an admin, you can remove multiple users from a stream,
        """
        result = self.attempt_unsubscribe_of_principal(
            query_count=30, target_users=[self.example_user('cordelia'), self.example_user('prospero')],
            is_admin=True, is_subbed=True, invite_only=False, target_users_subbed=True)
        json = self.assert_json_success(result)
        self.assertEqual(len(json["removed"]), 2)
        self.assertEqual(len(json["not_removed"]), 0)

    def test_admin_remove_others_from_subbed_private_stream(self) -> None:
        """
        If you're an admin, you can remove other people from private streams you
        are on.
        """
        result = self.attempt_unsubscribe_of_principal(
            query_count=21, target_users=[self.example_user('cordelia')], is_admin=True, is_subbed=True,
            invite_only=True, target_users_subbed=True)
        json = self.assert_json_success(result)
        self.assertEqual(len(json["removed"]), 1)
        self.assertEqual(len(json["not_removed"]), 0)

    def test_admin_remove_others_from_unsubbed_private_stream(self) -> None:
        """
        If you're an admin, you can remove people from private
        streams you aren't on.
        """
        result = self.attempt_unsubscribe_of_principal(
            query_count=21, target_users=[self.example_user('cordelia')], is_admin=True, is_subbed=False,
            invite_only=True, target_users_subbed=True, other_sub_users=[self.example_user("othello")])
        json = self.assert_json_success(result)
        self.assertEqual(len(json["removed"]), 1)
        self.assertEqual(len(json["not_removed"]), 0)

    def test_cant_remove_others_from_stream_legacy_emails(self) -> None:
        result = self.attempt_unsubscribe_of_principal(
            query_count=3, is_admin=False, is_subbed=True, invite_only=False,
            target_users=[self.example_user('cordelia')], target_users_subbed=True,
            using_legacy_emails=True)
        self.assert_json_error(
            result, "This action requires administrative rights")

    def test_admin_remove_others_from_stream_legacy_emails(self) -> None:
        result = self.attempt_unsubscribe_of_principal(
            query_count=21, target_users=[self.example_user('cordelia')], is_admin=True, is_subbed=True,
            invite_only=False, target_users_subbed=True, using_legacy_emails=True)
        json = self.assert_json_success(result)
        self.assertEqual(len(json["removed"]), 1)
        self.assertEqual(len(json["not_removed"]), 0)

    def test_admin_remove_multiple_users_from_stream_legacy_emails(self) -> None:
        result = self.attempt_unsubscribe_of_principal(
            query_count=30, target_users=[self.example_user('cordelia'), self.example_user('prospero')],
            is_admin=True, is_subbed=True, invite_only=False, target_users_subbed=True, using_legacy_emails=True)
        json = self.assert_json_success(result)
        self.assertEqual(len(json["removed"]), 2)
        self.assertEqual(len(json["not_removed"]), 0)

    def test_create_stream_policy_setting(self) -> None:
        """
        When realm.create_stream_policy setting is Realm.POLICY_MEMBERS_ONLY then
        test that any user can create a stream.

        When realm.create_stream_policy setting is Realm.POLICY_ADMINS_ONLY then
        test that only admins can create a stream.

        When realm.create_stream_policy setting is Realm.POLICY_FULL_MEMBERS_ONLY then
        test that admins and users with accounts older than the waiting period can create a stream.
        """
        user_profile = self.example_user('hamlet')
        user_profile.date_joined = timezone_now()
        user_profile.save()
        self.login_user(user_profile)
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER)

        # Allow all members to create streams.
        do_set_realm_property(user_profile.realm, 'create_stream_policy',
                              Realm.POLICY_MEMBERS_ONLY)
        # Set waiting period to 10 days.
        do_set_realm_property(user_profile.realm, 'waiting_period_threshold', 10)

        # Can successfully create stream despite being less than waiting period and not an admin,
        # due to create stream policy.
        stream_name = ['all_members']
        result = self.common_subscribe_to_streams(user_profile, stream_name)
        self.assert_json_success(result)

        # Allow only administrators to create streams.
        do_set_realm_property(user_profile.realm, 'create_stream_policy',
                              Realm.POLICY_ADMINS_ONLY)

        # Cannot create stream because not an admin.
        stream_name = ['admins_only']
        result = self.common_subscribe_to_streams(user_profile, stream_name)
        self.assert_json_error(result, 'User cannot create streams.')

        # Make current user an admin.
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)

        # Can successfully create stream as user is now an admin.
        stream_name = ['admins_only']
        result = self.common_subscribe_to_streams(user_profile, stream_name)
        self.assert_json_success(result)

        # Allow users older than the waiting period to create streams.
        do_set_realm_property(user_profile.realm, 'create_stream_policy',
                              Realm.POLICY_FULL_MEMBERS_ONLY)

        # Can successfully create stream despite being under waiting period because user is admin.
        stream_name = ['waiting_period_as_admin']
        result = self.common_subscribe_to_streams(user_profile, stream_name)
        self.assert_json_success(result)

        # Make current user no longer an admin.
        do_change_user_role(user_profile, UserProfile.ROLE_MEMBER)

        # Cannot create stream because user is not an admin and is not older than the waiting
        # period.
        stream_name = ['waiting_period']
        result = self.common_subscribe_to_streams(user_profile, stream_name)
        self.assert_json_error(result, 'User cannot create streams.')

        # Make user account 11 days old..
        user_profile.date_joined = timezone_now() - timedelta(days=11)
        user_profile.save()

        # Can successfully create stream now that account is old enough.
        stream_name = ['waiting_period']
        result = self.common_subscribe_to_streams(user_profile, stream_name)
        self.assert_json_success(result)

    def test_invite_to_stream_by_invite_period_threshold(self) -> None:
        """
        Non admin users with account age greater or equal to the invite
        to stream threshold should be able to invite others to a stream.
        """
        hamlet_user = self.example_user('hamlet')
        hamlet_user.date_joined = timezone_now()
        hamlet_user.save()

        cordelia_user = self.example_user('cordelia')
        cordelia_user.date_joined = timezone_now()
        cordelia_user.save()

        do_set_realm_property(hamlet_user.realm, 'invite_to_stream_policy',
                              Realm.POLICY_FULL_MEMBERS_ONLY)
        cordelia_user_id = cordelia_user.id

        self.login_user(hamlet_user)
        do_change_user_role(hamlet_user, UserProfile.ROLE_REALM_ADMINISTRATOR)

        # Hamlet creates a stream as an admin..
        stream_name = ['waitingperiodtest']
        result = self.common_subscribe_to_streams(hamlet_user, stream_name)
        self.assert_json_success(result)

        # Can only invite users to stream if their account is ten days old..
        do_change_user_role(hamlet_user, UserProfile.ROLE_MEMBER)
        do_set_realm_property(hamlet_user.realm, 'waiting_period_threshold', 10)

        # Attempt and fail to invite Cordelia to the stream..
        result = self.common_subscribe_to_streams(hamlet_user, stream_name, {"principals": ujson.dumps([cordelia_user_id])})
        self.assert_json_error(result,
                               "Your account is too new to modify other users' subscriptions.")

        # Anyone can invite users..
        do_set_realm_property(hamlet_user.realm, 'waiting_period_threshold', 0)

        # Attempt and succeed to invite Cordelia to the stream..
        result = self.common_subscribe_to_streams(hamlet_user, stream_name, {"principals": ujson.dumps([cordelia_user_id])})
        self.assert_json_success(result)

        # Set threshold to 20 days..
        do_set_realm_property(hamlet_user.realm, 'waiting_period_threshold', 20)
        # Make Hamlet's account 21 days old..
        hamlet_user.date_joined = timezone_now() - timedelta(days=21)
        hamlet_user.save()
        # Unsubscribe Cordelia..
        self.unsubscribe(cordelia_user, stream_name[0])

        # Attempt and succeed to invite Aaron to the stream..
        result = self.common_subscribe_to_streams(hamlet_user, stream_name, {"principals": ujson.dumps([cordelia_user_id])})
        self.assert_json_success(result)

    def test_remove_already_not_subbed(self) -> None:
        """
        Trying to unsubscribe someone who already isn't subscribed to a stream
        fails gracefully.
        """
        result = self.attempt_unsubscribe_of_principal(
            query_count=11, target_users=[self.example_user('cordelia')], is_admin=True, is_subbed=False,
            invite_only=False, target_users_subbed=False)
        json = self.assert_json_success(result)
        self.assertEqual(len(json["removed"]), 0)
        self.assertEqual(len(json["not_removed"]), 1)

    def test_remove_invalid_user(self) -> None:
        """
        Trying to unsubscribe an invalid user from a stream fails gracefully.
        """
        admin = self.example_user('iago')
        self.login_user(admin)
        self.assertTrue(admin.is_realm_admin)

        stream_name = "hümbüǵ"
        self.make_stream(stream_name)

        result = self.client_delete("/json/users/me/subscriptions",
                                    {"subscriptions": ujson.dumps([stream_name]),
                                     "principals": ujson.dumps([99])})
        self.assert_json_error(
            result,
            "User not authorized to execute queries on behalf of '99'",
            status_code=403)

class DefaultStreamTest(ZulipTestCase):
    def get_default_stream_names(self, realm: Realm) -> Set[str]:
        streams = get_default_streams_for_realm(realm.id)
        stream_names = [s.name for s in streams]
        return set(stream_names)

    def test_add_and_remove_default_stream(self) -> None:
        realm = get_realm("zulip")
        stream = ensure_stream(realm, "Added Stream")
        orig_stream_names = self.get_default_stream_names(realm)
        do_add_default_stream(stream)
        new_stream_names = self.get_default_stream_names(realm)
        added_stream_names = new_stream_names - orig_stream_names
        self.assertEqual(added_stream_names, {'Added Stream'})
        # idempotentcy--2nd call to add_default_stream should be a noop
        do_add_default_stream(stream)
        self.assertEqual(self.get_default_stream_names(realm), new_stream_names)

        # start removing
        do_remove_default_stream(stream)
        self.assertEqual(self.get_default_stream_names(realm), orig_stream_names)
        # idempotentcy--2nd call to remove_default_stream should be a noop
        do_remove_default_stream(stream)
        self.assertEqual(self.get_default_stream_names(realm), orig_stream_names)

    def test_api_calls(self) -> None:
        user_profile = self.example_user('hamlet')
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.login_user(user_profile)

        stream_name = 'stream ADDED via api'
        stream = ensure_stream(user_profile.realm, stream_name)
        result = self.client_post('/json/default_streams', dict(stream_id=stream.id))
        self.assert_json_success(result)
        self.assertTrue(stream_name in self.get_default_stream_names(user_profile.realm))

        # look for it
        self.subscribe(user_profile, stream_name)
        payload = dict(
            include_public='true',
            include_default='true',
        )
        result = self.client_get('/json/streams', payload)
        self.assert_json_success(result)
        streams = result.json()['streams']
        default_streams = {
            stream['name']
            for stream in streams
            if stream['is_default']
        }
        self.assertEqual(default_streams, {stream_name})

        other_streams = {
            stream['name']
            for stream in streams
            if not stream['is_default']
        }
        self.assertTrue(len(other_streams) > 0)

        # and remove it
        result = self.client_delete('/json/default_streams', dict(stream_id=stream.id))
        self.assert_json_success(result)
        self.assertFalse(stream_name in self.get_default_stream_names(user_profile.realm))

        # Test admin can't add unsubscribed private stream
        stream_name = "private_stream"
        stream = self.make_stream(stream_name, invite_only=True)
        self.subscribe(self.example_user('iago'), stream_name)
        result = self.client_post('/json/default_streams', dict(stream_id=stream.id))
        self.assert_json_error(result, "Invalid stream id")

        self.subscribe(user_profile, stream_name)
        result = self.client_post('/json/default_streams', dict(stream_id=stream.id))
        self.assert_json_success(result)
        self.assertTrue(stream_name in self.get_default_stream_names(user_profile.realm))

        # Test admin can remove unsubscribed private stream
        self.unsubscribe(user_profile, stream_name)
        result = self.client_delete('/json/default_streams', dict(stream_id=stream.id))
        self.assert_json_success(result)
        self.assertFalse(stream_name in self.get_default_stream_names(user_profile.realm))

class DefaultStreamGroupTest(ZulipTestCase):
    def test_create_update_and_remove_default_stream_group(self) -> None:
        realm = get_realm("zulip")

        # Test creating new default stream group
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 0)

        streams = []
        for stream_name in ["stream1", "stream2", "stream3"]:
            stream = ensure_stream(realm, stream_name)
            streams.append(stream)

        def get_streams(group: DefaultStreamGroup) -> List[Stream]:
            return list(group.streams.all().order_by('name'))

        group_name = "group1"
        description = "This is group1"
        do_create_default_stream_group(realm, group_name, description, streams)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(default_stream_groups[0].description, description)
        self.assertEqual(get_streams(default_stream_groups[0]), streams)

        # Test adding streams to existing default stream group
        group = lookup_default_stream_groups(["group1"], realm)[0]
        new_stream_names = ["stream4", "stream5"]
        new_streams = []
        for new_stream_name in new_stream_names:
            new_stream = ensure_stream(realm, new_stream_name)
            new_streams.append(new_stream)
            streams.append(new_stream)

        do_add_streams_to_default_stream_group(realm, group, new_streams)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(get_streams(default_stream_groups[0]), streams)

        # Test removing streams from existing default stream group
        do_remove_streams_from_default_stream_group(realm, group, new_streams)
        remaining_streams = streams[0:3]
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(get_streams(default_stream_groups[0]), remaining_streams)

        # Test changing default stream group description
        new_description = "group1 new description"
        do_change_default_stream_group_description(realm, group, new_description)
        default_stream_groups = get_default_stream_groups(realm)
        self.assertEqual(default_stream_groups[0].description, new_description)
        self.assert_length(default_stream_groups, 1)

        # Test changing default stream group name
        new_group_name = "new group1"
        do_change_default_stream_group_name(realm, group, new_group_name)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, new_group_name)
        self.assertEqual(get_streams(default_stream_groups[0]), remaining_streams)

        # Test removing default stream group
        do_remove_default_stream_group(realm, group)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 0)

        # Test creating a default stream group which contains a default stream
        do_add_default_stream(remaining_streams[0])
        with self.assertRaisesRegex(
                JsonableError, "'stream1' is a default stream and cannot be added to 'new group1'"):
            do_create_default_stream_group(realm, new_group_name, "This is group1", remaining_streams)

    def test_api_calls(self) -> None:
        self.login('hamlet')
        user_profile = self.example_user('hamlet')
        realm = user_profile.realm
        do_change_user_role(user_profile, UserProfile.ROLE_REALM_ADMINISTRATOR)

        # Test creating new default stream group
        stream_names = ["stream1", "stream2", "stream3"]
        group_name = "group1"
        description = "This is group1"
        streams = []
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 0)

        for stream_name in stream_names:
            stream = ensure_stream(realm, stream_name)
            streams.append(stream)

        result = self.client_post('/json/default_stream_groups/create',
                                  {"group_name": group_name, "description": description,
                                   "stream_names": ujson.dumps(stream_names)})
        self.assert_json_success(result)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(default_stream_groups[0].description, description)
        self.assertEqual(list(default_stream_groups[0].streams.all().order_by("id")), streams)

        # Try adding the same streams to the group.
        result = self.client_post('/json/default_stream_groups/create',
                                  {"group_name": group_name, "description": description,
                                   "stream_names": ujson.dumps(stream_names)})
        self.assert_json_error(result, "Default stream group 'group1' already exists")

        # Test adding streams to existing default stream group
        group_id = default_stream_groups[0].id
        new_stream_names = ["stream4", "stream5"]
        new_streams = []
        for new_stream_name in new_stream_names:
            new_stream = ensure_stream(realm, new_stream_name)
            new_streams.append(new_stream)
            streams.append(new_stream)

        result = self.client_patch(f"/json/default_stream_groups/{group_id}/streams",
                                   {"stream_names": ujson.dumps(new_stream_names)})
        self.assert_json_error(result, "Missing 'op' argument")

        result = self.client_patch(f"/json/default_stream_groups/{group_id}/streams",
                                   {"op": "invalid", "stream_names": ujson.dumps(new_stream_names)})
        self.assert_json_error(result, 'Invalid value for "op". Specify one of "add" or "remove".')

        result = self.client_patch("/json/default_stream_groups/12345/streams",
                                   {"op": "add", "stream_names": ujson.dumps(new_stream_names)})
        self.assert_json_error(result, "Default stream group with id '12345' does not exist.")

        result = self.client_patch(f"/json/default_stream_groups/{group_id}/streams", {"op": "add"})
        self.assert_json_error(result, "Missing 'stream_names' argument")

        do_add_default_stream(new_streams[0])
        result = self.client_patch(f"/json/default_stream_groups/{group_id}/streams",
                                   {"op": "add", "stream_names": ujson.dumps(new_stream_names)})
        self.assert_json_error(result, "'stream4' is a default stream and cannot be added to 'group1'")

        do_remove_default_stream(new_streams[0])
        result = self.client_patch(f"/json/default_stream_groups/{group_id}/streams",
                                   {"op": "add", "stream_names": ujson.dumps(new_stream_names)})
        self.assert_json_success(result)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(list(default_stream_groups[0].streams.all().order_by('name')), streams)

        result = self.client_patch(f"/json/default_stream_groups/{group_id}/streams",
                                   {"op": "add", "stream_names": ujson.dumps(new_stream_names)})
        self.assert_json_error(result,
                               "Stream 'stream4' is already present in default stream group 'group1'")

        # Test removing streams from default stream group
        result = self.client_patch("/json/default_stream_groups/12345/streams",
                                   {"op": "remove", "stream_names": ujson.dumps(new_stream_names)})
        self.assert_json_error(result, "Default stream group with id '12345' does not exist.")

        result = self.client_patch(f"/json/default_stream_groups/{group_id}/streams",
                                   {"op": "remove", "stream_names": ujson.dumps(["random stream name"])})
        self.assert_json_error(result, "Invalid stream name 'random stream name'")

        streams.remove(new_streams[0])
        result = self.client_patch(f"/json/default_stream_groups/{group_id}/streams",
                                   {"op": "remove", "stream_names": ujson.dumps([new_stream_names[0]])})
        self.assert_json_success(result)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(list(default_stream_groups[0].streams.all().order_by('name')), streams)

        result = self.client_patch(f"/json/default_stream_groups/{group_id}/streams",
                                   {"op": "remove", "stream_names": ujson.dumps(new_stream_names)})
        self.assert_json_error(result, "Stream 'stream4' is not present in default stream group 'group1'")

        # Test changing description of default stream group
        new_description = "new group1 description"

        result = self.client_patch(f"/json/default_stream_groups/{group_id}",
                                   {"group_name": group_name, "op": "change"})
        self.assert_json_error(result, 'You must pass "new_description" or "new_group_name".')

        result = self.client_patch("/json/default_stream_groups/12345",
                                   {"op": "change", "new_description": ujson.dumps(new_description)})
        self.assert_json_error(result, "Default stream group with id '12345' does not exist.")

        result = self.client_patch(f"/json/default_stream_groups/{group_id}",
                                   {"group_name": group_name,
                                    "op": "change",
                                    "new_description": ujson.dumps(new_description)})
        self.assert_json_success(result)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, group_name)
        self.assertEqual(default_stream_groups[0].description, new_description)

        # Test changing name of default stream group
        new_group_name = "new group1"
        do_create_default_stream_group(realm, "group2", "", [])
        result = self.client_patch(f"/json/default_stream_groups/{group_id}",
                                   {"op": "change", "new_group_name": ujson.dumps("group2")})
        self.assert_json_error(result, "Default stream group 'group2' already exists")
        new_group = lookup_default_stream_groups(["group2"], realm)[0]
        do_remove_default_stream_group(realm, new_group)

        result = self.client_patch(f"/json/default_stream_groups/{group_id}",
                                   {"op": "change", "new_group_name": ujson.dumps(group_name)})
        self.assert_json_error(result, "This default stream group is already named 'group1'")

        result = self.client_patch(f"/json/default_stream_groups/{group_id}",
                                   {"op": "change", "new_group_name": ujson.dumps(new_group_name)})
        self.assert_json_success(result)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 1)
        self.assertEqual(default_stream_groups[0].name, new_group_name)
        self.assertEqual(default_stream_groups[0].description, new_description)

        # Test deleting a default stream group
        result = self.client_delete(f'/json/default_stream_groups/{group_id}')
        self.assert_json_success(result)
        default_stream_groups = get_default_stream_groups(realm)
        self.assert_length(default_stream_groups, 0)

        result = self.client_delete(f'/json/default_stream_groups/{group_id}')
        self.assert_json_error(result, f"Default stream group with id '{group_id}' does not exist.")

    def test_invalid_default_stream_group_name(self) -> None:
        self.login('iago')
        user_profile = self.example_user('iago')
        realm = user_profile.realm

        stream_names = ["stream1", "stream2", "stream3"]
        description = "This is group1"
        streams = []

        for stream_name in stream_names:
            stream = ensure_stream(realm, stream_name)
            streams.append(stream)

        result = self.client_post('/json/default_stream_groups/create',
                                  {"group_name": "", "description": description,
                                   "stream_names": ujson.dumps(stream_names)})
        self.assert_json_error(result, "Invalid default stream group name ''")

        result = self.client_post('/json/default_stream_groups/create',
                                  {"group_name": 'x'*100, "description": description,
                                   "stream_names": ujson.dumps(stream_names)})
        self.assert_json_error(result, "Default stream group name too long (limit: {} characters)"
                               .format(DefaultStreamGroup.MAX_NAME_LENGTH))

        result = self.client_post('/json/default_stream_groups/create',
                                  {"group_name": "abc\000", "description": description,
                                   "stream_names": ujson.dumps(stream_names)})
        self.assert_json_error(result, "Default stream group name 'abc\000' contains NULL (0x00) characters.")

        # Also test that lookup_default_stream_groups raises an
        # error if we pass it a bad name.  This function is used
        # during registration, but it's a bit heavy to do a full
        # test of that.
        with self.assertRaisesRegex(JsonableError, 'Invalid default stream group invalid-name'):
            lookup_default_stream_groups(['invalid-name'], realm)

class SubscriptionPropertiesTest(ZulipTestCase):
    def test_set_stream_color(self) -> None:
        """
        A POST request to /api/v1/users/me/subscriptions/properties with stream_id and
        color data sets the stream color, and for that stream only. Also, make sure that
        any invalid hex color codes are bounced.
        """
        test_user = self.example_user('hamlet')
        self.login_user(test_user)

        old_subs, _ = gather_subscriptions(test_user)
        sub = old_subs[0]
        stream_id = sub['stream_id']
        new_color = "#ffffff"  # TODO: ensure that this is different from old_color
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": "color",
                                                                   "stream_id": stream_id,
                                                                   "value": "#ffffff"}])})
        self.assert_json_success(result)

        new_subs = gather_subscriptions(test_user)[0]
        found_sub = None
        for sub in new_subs:
            if sub['stream_id'] == stream_id:
                found_sub = sub
                break

        assert(found_sub is not None)
        self.assertEqual(found_sub['color'], new_color)

        new_subs.remove(found_sub)
        for sub in old_subs:
            if sub['stream_id'] == stream_id:
                found_sub = sub
                break
        old_subs.remove(found_sub)
        self.assertEqual(old_subs, new_subs)

        invalid_color = "3ffrff"
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": "color",
                                                                   "stream_id": stream_id,
                                                                   "value": invalid_color}])})
        self.assert_json_error(result, "color is not a valid hex color code")

    def test_set_color_missing_stream_id(self) -> None:
        """
        Updating the color property requires a `stream_id` key.
        """
        test_user = self.example_user('hamlet')
        self.login_user(test_user)
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": "color",
                                                                   "value": "#ffffff"}])})
        self.assert_json_error(
            result, "stream_id key is missing from subscription_data[0]")

    def test_set_color_unsubscribed_stream_id(self) -> None:
        """
        Updating the color property requires a subscribed stream.
        """
        test_user = self.example_user("hamlet")
        self.login_user(test_user)

        subscribed, unsubscribed, never_subscribed = gather_subscriptions_helper(test_user)
        not_subbed = unsubscribed + never_subscribed
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": "color",
                                                                   "stream_id": not_subbed[0]["stream_id"],
                                                                   "value": "#ffffff"}])})
        self.assert_json_error(
            result, "Not subscribed to stream id %d" % (not_subbed[0]["stream_id"],))

    def test_set_color_missing_color(self) -> None:
        """
        Updating the color property requires a color.
        """
        test_user = self.example_user('hamlet')
        self.login_user(test_user)
        subs = gather_subscriptions(test_user)[0]
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": "color",
                                                                   "stream_id": subs[0]["stream_id"]}])})
        self.assert_json_error(
            result, "value key is missing from subscription_data[0]")

    def test_set_stream_wildcard_mentions_notify(self) -> None:
        """
        A POST request to /api/v1/users/me/subscriptions/properties with wildcard_mentions_notify
        sets the property.
        """
        test_user = self.example_user('hamlet')
        self.login_user(test_user)

        subs = gather_subscriptions(test_user)[0]
        sub = subs[0]
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": "wildcard_mentions_notify",
                                                                   "stream_id": sub["stream_id"],
                                                                   "value": True}])})

        self.assert_json_success(result)

        updated_sub = get_subscription(sub['name'], test_user)
        self.assertIsNotNone(updated_sub)
        self.assertEqual(updated_sub.wildcard_mentions_notify, True)

    def test_set_pin_to_top(self) -> None:
        """
        A POST request to /api/v1/users/me/subscriptions/properties with stream_id and
        pin_to_top data pins the stream.
        """
        user = self.example_user('hamlet')
        self.login_user(user)

        old_subs, _ = gather_subscriptions(user)
        sub = old_subs[0]
        stream_id = sub['stream_id']
        new_pin_to_top = not sub['pin_to_top']
        result = self.api_post(user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": "pin_to_top",
                                                                   "stream_id": stream_id,
                                                                   "value": new_pin_to_top}])})
        self.assert_json_success(result)

        updated_sub = get_subscription(sub['name'], user)

        self.assertIsNotNone(updated_sub)
        self.assertEqual(updated_sub.pin_to_top, new_pin_to_top)

    def test_change_is_muted(self) -> None:
        test_user = self.example_user('hamlet')
        self.login_user(test_user)
        subs = gather_subscriptions(test_user)[0]

        sub = Subscription.objects.get(recipient__type=Recipient.STREAM,
                                       recipient__type_id=subs[0]["stream_id"],
                                       user_profile=test_user)
        self.assertEqual(sub.is_muted, False)

        events: List[Mapping[str, Any]] = []
        property_name = "is_muted"
        with tornado_redirected_to_list(events):
            result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                                   {"subscription_data": ujson.dumps([{"property": property_name,
                                                                       "value": True,
                                                                       "stream_id": subs[0]["stream_id"]}])})
        self.assert_json_success(result)
        self.assert_length(events, 1)
        self.assertEqual(events[0]['event']['property'], 'in_home_view')
        self.assertEqual(events[0]['event']['value'], False)
        sub = Subscription.objects.get(recipient__type=Recipient.STREAM,
                                       recipient__type_id=subs[0]["stream_id"],
                                       user_profile=test_user)
        self.assertEqual(sub.is_muted, True)

        events = []
        legacy_property_name = 'in_home_view'
        with tornado_redirected_to_list(events):
            result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                                   {"subscription_data": ujson.dumps([{"property": legacy_property_name,
                                                                       "value": True,
                                                                       "stream_id": subs[0]["stream_id"]}])})
        self.assert_json_success(result)
        self.assert_length(events, 1)
        self.assertEqual(events[0]['event']['property'], 'in_home_view')
        self.assertEqual(events[0]['event']['value'], True)
        self.assert_json_success(result)
        sub = Subscription.objects.get(recipient__type=Recipient.STREAM,
                                       recipient__type_id=subs[0]["stream_id"],
                                       user_profile=test_user)
        self.assertEqual(sub.is_muted, False)

        events = []
        with tornado_redirected_to_list(events):
            result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                                   {"subscription_data": ujson.dumps([{"property": legacy_property_name,
                                                                       "value": False,
                                                                       "stream_id": subs[0]["stream_id"]}])})
        self.assert_json_success(result)
        self.assert_length(events, 1)
        self.assertEqual(events[0]['event']['property'], 'in_home_view')
        self.assertEqual(events[0]['event']['value'], False)

        sub = Subscription.objects.get(recipient__type=Recipient.STREAM,
                                       recipient__type_id=subs[0]["stream_id"],
                                       user_profile=test_user)
        self.assertEqual(sub.is_muted, True)

    def test_set_subscription_property_incorrect(self) -> None:
        """
        Trying to set a property incorrectly returns a JSON error.
        """
        test_user = self.example_user('hamlet')
        self.login_user(test_user)
        subs = gather_subscriptions(test_user)[0]

        property_name = "is_muted"
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": property_name,
                                                                   "value": "bad",
                                                                   "stream_id": subs[0]["stream_id"]}])})
        self.assert_json_error(result,
                               f'{property_name} is not a boolean')

        property_name = "in_home_view"
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": property_name,
                                                                   "value": "bad",
                                                                   "stream_id": subs[0]["stream_id"]}])})
        self.assert_json_error(result,
                               f'{property_name} is not a boolean')

        property_name = "desktop_notifications"
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": property_name,
                                                                   "value": "bad",
                                                                   "stream_id": subs[0]["stream_id"]}])})
        self.assert_json_error(result,
                               f'{property_name} is not a boolean')

        property_name = "audible_notifications"
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": property_name,
                                                                   "value": "bad",
                                                                   "stream_id": subs[0]["stream_id"]}])})
        self.assert_json_error(result,
                               f'{property_name} is not a boolean')

        property_name = "push_notifications"
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": property_name,
                                                                   "value": "bad",
                                                                   "stream_id": subs[0]["stream_id"]}])})
        self.assert_json_error(result,
                               f'{property_name} is not a boolean')

        property_name = "email_notifications"
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": property_name,
                                                                   "value": "bad",
                                                                   "stream_id": subs[0]["stream_id"]}])})
        self.assert_json_error(result,
                               f'{property_name} is not a boolean')

        property_name = "wildcard_mentions_notify"
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": property_name,
                                                                   "value": "bad",
                                                                   "stream_id": subs[0]["stream_id"]}])})

        self.assert_json_error(result,
                               f"{property_name} is not a boolean")

        property_name = "color"
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": property_name,
                                                                   "value": False,
                                                                   "stream_id": subs[0]["stream_id"]}])})
        self.assert_json_error(result,
                               f'{property_name} is not a string')

    def test_json_subscription_property_invalid_stream(self) -> None:
        test_user = self.example_user("hamlet")
        self.login_user(test_user)

        stream_id = 1000
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": "is_muted",
                                                                   "stream_id": stream_id,
                                                                   "value": False}])})
        self.assert_json_error(result, "Invalid stream id")

    def test_set_invalid_property(self) -> None:
        """
        Trying to set an invalid property returns a JSON error.
        """
        test_user = self.example_user('hamlet')
        self.login_user(test_user)
        subs = gather_subscriptions(test_user)[0]
        result = self.api_post(test_user, "/api/v1/users/me/subscriptions/properties",
                               {"subscription_data": ujson.dumps([{"property": "bad",
                                                                   "value": "bad",
                                                                   "stream_id": subs[0]["stream_id"]}])})
        self.assert_json_error(result,
                               "Unknown subscription property: bad")

class SubscriptionRestApiTest(ZulipTestCase):
    def test_basic_add_delete(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        # add
        request = {
            'add': ujson.dumps([{'name': 'my_test_stream_1'}]),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_success(result)
        streams = self.get_streams(user)
        self.assertTrue('my_test_stream_1' in streams)

        # now delete the same stream
        request = {
            'delete': ujson.dumps(['my_test_stream_1']),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_success(result)
        streams = self.get_streams(user)
        self.assertTrue('my_test_stream_1' not in streams)

    def test_add_with_color(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        # add with color proposition
        request = {
            'add': ujson.dumps([{'name': 'my_test_stream_2', 'color': '#afafaf'}]),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_success(result)

        # incorrect color format
        request = {
            'subscriptions': ujson.dumps([{'name': 'my_test_stream_3', 'color': '#0g0g0g'}]),
        }
        result = self.api_post(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_error(result, 'subscriptions[0]["color"] is not a valid hex color code')

    def test_api_valid_property(self) -> None:
        """
        Trying to set valid json returns success message.
        """
        user = self.example_user('hamlet')

        self.login_user(user)
        subs = gather_subscriptions(user)[0]
        result = self.api_patch(user, "/api/v1/users/me/subscriptions/%d" % (subs[0]["stream_id"],),
                                {'property': 'color', 'value': '#c2c2c2'})
        self.assert_json_success(result)

    def test_api_invalid_property(self) -> None:
        """
        Trying to set an invalid property returns a JSON error.
        """

        user = self.example_user('hamlet')

        self.login_user(user)
        subs = gather_subscriptions(user)[0]

        result = self.api_patch(user, "/api/v1/users/me/subscriptions/%d" % (subs[0]["stream_id"],),
                                {'property': 'invalid', 'value': 'somevalue'})
        self.assert_json_error(result,
                               "Unknown subscription property: invalid")

    def test_api_invalid_stream_id(self) -> None:
        """
        Trying to set an invalid stream id returns a JSON error.
        """
        user = self.example_user("hamlet")
        self.login_user(user)
        result = self.api_patch(user, "/api/v1/users/me/subscriptions/121",
                                {'property': 'is_muted', 'value': 'somevalue'})
        self.assert_json_error(result,
                               "Invalid stream id")

    def test_bad_add_parameters(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        def check_for_error(val: Any, expected_message: str) -> None:
            request = {
                'add': ujson.dumps(val),
            }
            result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
            self.assert_json_error(result, expected_message)

        check_for_error(['foo'], 'add[0] is not a dict')
        check_for_error([{'bogus': 'foo'}], 'name key is missing from add[0]')
        check_for_error([{'name': {}}], 'add[0]["name"] is not a string')

    def test_bad_principals(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        request = {
            'add': ujson.dumps([{'name': 'my_new_stream'}]),
            'principals': ujson.dumps([{}]),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_error(result, 'principals is not an allowed_type')

    def test_bad_delete_parameters(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        request = {
            'delete': ujson.dumps([{'name': 'my_test_stream_1'}]),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_error(result, "delete[0] is not a string")

    def test_add_or_delete_not_specified(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        result = self.api_patch(user, "/api/v1/users/me/subscriptions", {})
        self.assert_json_error(result,
                               'Nothing to do. Specify at least one of "add" or "delete".')

    def test_patch_enforces_valid_stream_name_check(self) -> None:
        """
        Only way to force an error is with a empty string.
        """
        user = self.example_user('hamlet')
        self.login_user(user)

        invalid_stream_name = ""
        request = {
            'delete': ujson.dumps([invalid_stream_name]),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_error(result,
                               f"Invalid stream name '{invalid_stream_name}'")

    def test_stream_name_too_long(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        long_stream_name = "a" * 61
        request = {
            'delete': ujson.dumps([long_stream_name]),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_error(result,
                               "Stream name too long (limit: 60 characters).")

    def test_stream_name_contains_null(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        stream_name = "abc\000"
        request = {
            'delete': ujson.dumps([stream_name]),
        }
        result = self.api_patch(user, "/api/v1/users/me/subscriptions", request)
        self.assert_json_error(result,
                               f"Stream name '{stream_name}' contains NULL (0x00) characters.")

    def test_compose_views_rollback(self) -> None:
        '''
        The compose_views function() is used under the hood by
        update_subscriptions_backend.  It's a pretty simple method in terms of
        control flow, but it uses a Django rollback, which may make it brittle
        code when we upgrade Django.  We test the functions's rollback logic
        here with a simple scenario to avoid false positives related to
        subscription complications.
        '''
        user_profile = self.example_user('hamlet')
        user_profile.full_name = 'Hamlet'
        user_profile.save()

        def method1(req: HttpRequest, user_profile: UserProfile) -> HttpResponse:
            user_profile.full_name = 'Should not be committed'
            user_profile.save()
            return json_success()

        def method2(req: HttpRequest, user_profile: UserProfile) -> HttpResponse:
            return json_error('random failure')

        with self.assertRaises(JsonableError):
            compose_views(None, user_profile, [(method1, {}), (method2, {})])

        user_profile = self.example_user('hamlet')
        self.assertEqual(user_profile.full_name, 'Hamlet')

class SubscriptionAPITest(ZulipTestCase):

    def setUp(self) -> None:
        """
        All tests will be logged in as hamlet. Also save various useful values
        as attributes that tests can access.
        """
        super().setUp()
        self.user_profile = self.example_user('hamlet')
        self.test_email = self.user_profile.email
        self.test_user = self.user_profile
        self.login_user(self.user_profile)
        self.test_realm = self.user_profile.realm
        self.streams = self.get_streams(self.user_profile)

    def make_random_stream_names(self, existing_stream_names: List[str]) -> List[str]:
        """
        Helper function to make up random stream names. It takes
        existing_stream_names and randomly appends a digit to the end of each,
        but avoids names that appear in the list names_to_avoid.
        """
        random_streams = []
        all_stream_names = [stream.name for stream in Stream.objects.filter(realm=self.test_realm)]
        for stream in existing_stream_names:
            random_stream = stream + str(random.randint(0, 9))
            if random_stream not in all_stream_names:
                random_streams.append(random_stream)
        return random_streams

    def test_successful_subscriptions_list(self) -> None:
        """
        Calling /api/v1/users/me/subscriptions should successfully return your subscriptions.
        """
        result = self.api_get(self.test_user, "/api/v1/users/me/subscriptions")
        self.assert_json_success(result)
        json = result.json()
        self.assertIn("subscriptions", json)
        for stream in json['subscriptions']:
            self.assertIsInstance(stream['name'], str)
            self.assertIsInstance(stream['color'], str)
            self.assertIsInstance(stream['invite_only'], bool)
            # check that the stream name corresponds to an actual
            # stream; will throw Stream.DoesNotExist if it doesn't
            get_stream(stream['name'], self.test_realm)
        list_streams = [stream['name'] for stream in json["subscriptions"]]
        # also check that this matches the list of your subscriptions
        self.assertEqual(sorted(list_streams), sorted(self.streams))

    def helper_check_subs_before_and_after_add(self, subscriptions: List[str],
                                               other_params: Dict[str, Any],
                                               subscribed: List[str],
                                               already_subscribed: List[str],
                                               email: str, new_subs: List[str],
                                               realm: Realm,
                                               invite_only: bool=False) -> None:
        """
        Check result of adding subscriptions.

        You can add subscriptions for yourself or possibly many
        principals, which is why e-mails map to subscriptions in the
        result.

        The result json is of the form

        {"msg": "",
         "result": "success",
         "already_subscribed": {self.example_email("iago"): ["Venice", "Verona"]},
         "subscribed": {self.example_email("iago"): ["Venice8"]}}
        """
        result = self.common_subscribe_to_streams(self.test_user, subscriptions,
                                                  other_params, invite_only=invite_only)
        self.assert_json_success(result)
        json = result.json()
        self.assertEqual(sorted(subscribed), sorted(json["subscribed"][email]))
        self.assertEqual(sorted(already_subscribed), sorted(json["already_subscribed"][email]))
        user = get_user(email, realm)
        new_streams = self.get_streams(user)
        self.assertEqual(sorted(new_streams), sorted(new_subs))

    def test_successful_subscriptions_add(self) -> None:
        """
        Calling POST /json/users/me/subscriptions should successfully add
        streams, and should determine which are new subscriptions vs
        which were already subscribed. We add 2 new streams to the
        list of subscriptions and confirm the right number of events
        are generated.
        """
        self.assertNotEqual(len(self.streams), 0)  # necessary for full test coverage
        add_streams = ["Verona2", "Denmark5"]
        self.assertNotEqual(len(add_streams), 0)  # necessary for full test coverage
        events: List[Mapping[str, Any]] = []
        with tornado_redirected_to_list(events):
            self.helper_check_subs_before_and_after_add(self.streams + add_streams, {},
                                                        add_streams, self.streams, self.test_email,
                                                        self.streams + add_streams, self.test_realm)
        self.assert_length(events, 8)

    def test_successful_subscriptions_add_with_announce(self) -> None:
        """
        Calling POST /json/users/me/subscriptions should successfully add
        streams, and should determine which are new subscriptions vs
        which were already subscribed. We add 2 new streams to the
        list of subscriptions and confirm the right number of events
        are generated.
        """
        self.assertNotEqual(len(self.streams), 0)
        add_streams = ["Verona2", "Denmark5"]
        self.assertNotEqual(len(add_streams), 0)
        events: List[Mapping[str, Any]] = []
        other_params = {
            'announce': 'true',
        }
        notifications_stream = get_stream(self.streams[0], self.test_realm)
        self.test_realm.notifications_stream_id = notifications_stream.id
        self.test_realm.save()

        # Delete the UserProfile from the cache so the realm change will be
        # picked up
        cache.cache_delete(cache.user_profile_by_email_cache_key(self.test_email))
        with tornado_redirected_to_list(events):
            self.helper_check_subs_before_and_after_add(self.streams + add_streams, other_params,
                                                        add_streams, self.streams, self.test_email,
                                                        self.streams + add_streams, self.test_realm)
        self.assertEqual(len(events), 9)

    def test_successful_subscriptions_notifies_pm(self) -> None:
        """
        Calling POST /json/users/me/subscriptions should notify when a new stream is created.
        """
        invitee = self.example_user("iago")

        current_stream = self.get_streams(invitee)[0]
        invite_streams = self.make_random_stream_names([current_stream])[:1]
        result = self.common_subscribe_to_streams(
            invitee,
            invite_streams,
            extra_post_data={
                'announce': 'true',
                'principals': ujson.dumps([self.user_profile.id]),
            },
        )
        self.assert_json_success(result)

    def test_successful_subscriptions_notifies_stream(self) -> None:
        """
        Calling POST /json/users/me/subscriptions should notify when a new stream is created.
        """
        invitee = self.example_user("iago")
        invitee_full_name = 'Iago'

        current_stream = self.get_streams(invitee)[0]
        invite_streams = self.make_random_stream_names([current_stream])[:1]

        notifications_stream = get_stream(current_stream, self.test_realm)
        self.test_realm.notifications_stream_id = notifications_stream.id
        self.test_realm.save()

        # Delete the UserProfile from the cache so the realm change will be
        # picked up
        cache.cache_delete(cache.user_profile_by_email_cache_key(invitee.email))

        result = self.common_subscribe_to_streams(
            invitee,
            invite_streams,
            extra_post_data=dict(
                announce='true',
                principals= ujson.dumps([self.user_profile.id]),
            ),
        )
        self.assert_json_success(result)

        msg = self.get_second_to_last_message()
        self.assertEqual(msg.recipient.type, Recipient.STREAM)
        self.assertEqual(msg.sender_id, self.notification_bot().id)
        expected_msg = "@_**%s|%d** created a new stream #**%s**." % (invitee_full_name, invitee.id, invite_streams[0])
        self.assertEqual(msg.content, expected_msg)

    def test_successful_cross_realm_notification(self) -> None:
        """
        Calling POST /json/users/me/subscriptions in a new realm
        should notify with a proper new stream link
        """
        realm = do_create_realm("testrealm", "Test Realm")

        notifications_stream = Stream.objects.get(name='general', realm=realm)
        realm.notifications_stream = notifications_stream
        realm.save()

        invite_streams = ["cross_stream"]

        user = self.example_user('AARON')
        user.realm = realm
        user.save()

        # Delete the UserProfile from the cache so the realm change will be
        # picked up
        cache.cache_delete(cache.user_profile_by_email_cache_key(user.email))

        result = self.common_subscribe_to_streams(
            user,
            invite_streams,
            extra_post_data=dict(
                announce='true',
            ),
            subdomain="testrealm",
        )
        self.assert_json_success(result)

        msg = self.get_second_to_last_message()
        self.assertEqual(msg.recipient.type, Recipient.STREAM)
        self.assertEqual(msg.sender_id, self.notification_bot().id)
        stream_id = Stream.objects.latest('id').id
        expected_rendered_msg = '<p><span class="user-mention silent" data-user-id="%d">%s</span> created a new stream <a class="stream" data-stream-id="%d" href="/#narrow/stream/%s-%s">#%s</a>.</p>' % (
            user.id, user.full_name, stream_id, stream_id, invite_streams[0], invite_streams[0])
        self.assertEqual(msg.rendered_content, expected_rendered_msg)

    def test_successful_subscriptions_notifies_with_escaping(self) -> None:
        """
        Calling POST /json/users/me/subscriptions should notify when a new stream is created.
        """
        invitee_full_name = 'Iago'
        invitee = self.example_user('iago')

        current_stream = self.get_streams(invitee)[0]
        notifications_stream = get_stream(current_stream, self.test_realm)
        self.test_realm.notifications_stream_id = notifications_stream.id
        self.test_realm.save()

        invite_streams = ['strange ) \\ test']
        result = self.common_subscribe_to_streams(
            invitee,
            invite_streams,
            extra_post_data={
                'announce': 'true',
                'principals': ujson.dumps([self.user_profile.id]),
            },
        )
        self.assert_json_success(result)

        msg = self.get_second_to_last_message()
        self.assertEqual(msg.sender_id, self.notification_bot().id)
        expected_msg = "@_**%s|%d** created a new stream #**%s**." % (invitee_full_name, invitee.id, invite_streams[0])
        self.assertEqual(msg.content, expected_msg)

    def test_non_ascii_stream_subscription(self) -> None:
        """
        Subscribing to a stream name with non-ASCII characters succeeds.
        """
        self.helper_check_subs_before_and_after_add(self.streams + ["hümbüǵ"], {},
                                                    ["hümbüǵ"], self.streams, self.test_email,
                                                    self.streams + ["hümbüǵ"], self.test_realm)

    def test_subscriptions_add_too_long(self) -> None:
        """
        Calling POST /json/users/me/subscriptions on a stream whose name is >60
        characters should return a JSON error.
        """
        # character limit is 60 characters
        long_stream_name = "a" * 61
        result = self.common_subscribe_to_streams(self.test_user, [long_stream_name])
        self.assert_json_error(result,
                               "Stream name too long (limit: 60 characters).")

    def test_subscriptions_add_stream_with_null(self) -> None:
        """
        Calling POST /json/users/me/subscriptions on a stream whose name contains
        null characters should return a JSON error.
        """
        stream_name = "abc\000"
        result = self.common_subscribe_to_streams(self.test_user, [stream_name])
        self.assert_json_error(result,
                               f"Stream name '{stream_name}' contains NULL (0x00) characters.")

    def test_user_settings_for_adding_streams(self) -> None:
        with mock.patch('zerver.models.UserProfile.can_create_streams', return_value=False):
            result = self.common_subscribe_to_streams(self.test_user, ['stream1'])
            self.assert_json_error(result, 'User cannot create streams.')

        with mock.patch('zerver.models.UserProfile.can_create_streams', return_value=True):
            result = self.common_subscribe_to_streams(self.test_user, ['stream2'])
            self.assert_json_success(result)

        # User should still be able to subscribe to an existing stream
        with mock.patch('zerver.models.UserProfile.can_create_streams', return_value=False):
            result = self.common_subscribe_to_streams(self.test_user, ['stream2'])
            self.assert_json_success(result)

    def test_can_create_streams(self) -> None:
        othello = self.example_user('othello')
        othello.role = UserProfile.ROLE_REALM_ADMINISTRATOR
        self.assertTrue(othello.can_create_streams())

        othello.role = UserProfile.ROLE_MEMBER
        othello.realm.create_stream_policy = Realm.POLICY_ADMINS_ONLY
        self.assertFalse(othello.can_create_streams())

        othello.realm.create_stream_policy = Realm.POLICY_MEMBERS_ONLY
        othello.role = UserProfile.ROLE_GUEST
        self.assertFalse(othello.can_create_streams())

        othello.role = UserProfile.ROLE_MEMBER
        othello.realm.waiting_period_threshold = 1000
        othello.realm.create_stream_policy = Realm.POLICY_FULL_MEMBERS_ONLY
        othello.date_joined = timezone_now() - timedelta(days=(othello.realm.waiting_period_threshold - 1))
        self.assertFalse(othello.can_create_streams())

        othello.date_joined = timezone_now() - timedelta(days=(othello.realm.waiting_period_threshold + 1))
        self.assertTrue(othello.can_create_streams())

    def test_user_settings_for_subscribing_other_users(self) -> None:
        """
        You can't subscribe other people to streams if you are a guest or your account is not old
        enough.
        """
        user_profile = self.example_user("cordelia")
        invitee_user_id = user_profile.id
        realm = user_profile.realm

        do_set_realm_property(realm, "create_stream_policy", Realm.POLICY_MEMBERS_ONLY)
        do_set_realm_property(realm, "invite_to_stream_policy",
                              Realm.POLICY_ADMINS_ONLY)
        result = self.common_subscribe_to_streams(
            self.test_user, ['stream1'], {"principals": ujson.dumps([invitee_user_id])})
        self.assert_json_error(
            result, "Only administrators can modify other users' subscriptions.")

        do_set_realm_property(realm, "invite_to_stream_policy",
                              Realm.POLICY_MEMBERS_ONLY)
        result = self.common_subscribe_to_streams(
            self.test_user, ['stream2'],  {"principals": ujson.dumps([
                self.test_user.id, invitee_user_id])})
        self.assert_json_success(result)
        self.unsubscribe(user_profile, "stream2")

        do_set_realm_property(realm, "invite_to_stream_policy",
                              Realm.POLICY_FULL_MEMBERS_ONLY)
        do_set_realm_property(realm, "waiting_period_threshold", 100000)
        result = self.common_subscribe_to_streams(
            self.test_user, ['stream2'], {"principals": ujson.dumps([invitee_user_id])})
        self.assert_json_error(
            result, "Your account is too new to modify other users' subscriptions.")

        do_set_realm_property(realm, "waiting_period_threshold", 0)
        result = self.common_subscribe_to_streams(
            self.test_user, ['stream2'], {"principals": ujson.dumps([invitee_user_id])})
        self.assert_json_success(result)

    def test_can_subscribe_other_users(self) -> None:
        """
        You can't subscribe other people to streams if you are a guest or your account is not old
        enough.
        """
        othello = self.example_user('othello')
        do_change_user_role(othello, UserProfile.ROLE_REALM_ADMINISTRATOR)
        self.assertTrue(othello.can_subscribe_other_users())

        do_change_user_role(othello, UserProfile.ROLE_MEMBER)
        do_change_user_role(othello, UserProfile.ROLE_GUEST)
        self.assertFalse(othello.can_subscribe_other_users())

        do_change_user_role(othello, UserProfile.ROLE_MEMBER)
        do_set_realm_property(othello.realm, "waiting_period_threshold", 1000)
        do_set_realm_property(othello.realm, "invite_to_stream_policy",
                              Realm.POLICY_FULL_MEMBERS_ONLY)
        othello.date_joined = timezone_now() - timedelta(days=(othello.realm.waiting_period_threshold - 1))
        self.assertFalse(othello.can_subscribe_other_users())

        othello.date_joined = timezone_now() - timedelta(days=(othello.realm.waiting_period_threshold + 1))
        self.assertTrue(othello.can_subscribe_other_users())

    def test_subscriptions_add_invalid_stream(self) -> None:
        """
        Calling POST /json/users/me/subscriptions on a stream whose name is invalid (as
        defined by valid_stream_name in zerver/views.py) should return a JSON
        error.
        """
        # currently, the only invalid name is the empty string
        invalid_stream_name = ""
        result = self.common_subscribe_to_streams(self.test_user, [invalid_stream_name])
        self.assert_json_error(result,
                               f"Invalid stream name '{invalid_stream_name}'")

    def assert_adding_subscriptions_for_principal(self, invitee_data: Union[str, int], invitee_realm: Realm,
                                                  streams: List[str], invite_only: bool=False) -> None:
        """
        Calling POST /json/users/me/subscriptions on behalf of another principal (for
        whom you have permission to add subscriptions) should successfully add
        those subscriptions and send a message to the subscribee notifying
        them.
        """
        if isinstance(invitee_data, str):
            other_profile = get_user(invitee_data, invitee_realm)
        else:
            other_profile = get_user_profile_by_id_in_realm(invitee_data, invitee_realm)
        current_streams = self.get_streams(other_profile)
        self.assertIsInstance(other_profile, UserProfile)
        self.assertNotEqual(len(current_streams), 0)  # necessary for full test coverage
        self.assertNotEqual(len(streams), 0)  # necessary for full test coverage
        streams_to_sub = streams[:1]  # just add one, to make the message easier to check
        streams_to_sub.extend(current_streams)
        self.helper_check_subs_before_and_after_add(streams_to_sub,
                                                    {"principals": ujson.dumps([invitee_data])}, streams[:1],
                                                    current_streams, other_profile.email, streams_to_sub,
                                                    invitee_realm, invite_only=invite_only)

        # verify that a welcome message was sent to the stream
        msg = self.get_last_message()
        self.assertEqual(msg.recipient.type, msg.recipient.STREAM)
        self.assertEqual(msg.topic_name(), 'stream events')
        self.assertEqual(msg.sender.email, settings.NOTIFICATION_BOT)
        self.assertIn('Stream created by @_**', msg.content)

    def test_multi_user_subscription(self) -> None:
        user1 = self.example_user("cordelia")
        user2 = self.example_user("iago")
        realm = get_realm("zulip")
        streams_to_sub = ['multi_user_stream']
        events: List[Mapping[str, Any]] = []
        flush_per_request_caches()
        with tornado_redirected_to_list(events):
            with queries_captured() as queries:
                self.common_subscribe_to_streams(
                    self.test_user,
                    streams_to_sub,
                    dict(principals=ujson.dumps([user1.id, user2.id])),
                )
        self.assert_length(queries, 39)

        self.assert_length(events, 7)
        for ev in [x for x in events if x['event']['type'] not in ('message', 'stream')]:
            if ev['event']['op'] == 'add':
                self.assertEqual(
                    set(ev['event']['subscriptions'][0]['subscribers']),
                    {user1.id, user2.id},
                )
            else:
                # Check "peer_add" events for streams users were
                # never subscribed to, in order for the neversubscribed
                # structure to stay up-to-date.
                self.assertEqual(ev['event']['op'], 'peer_add')

        stream = get_stream('multi_user_stream', realm)
        self.assertEqual(num_subscribers_for_stream_id(stream.id), 2)

        # Now add ourselves
        events = []
        with tornado_redirected_to_list(events):
            with queries_captured() as queries:
                self.common_subscribe_to_streams(
                    self.test_user,
                    streams_to_sub,
                    dict(principals=ujson.dumps([self.test_user.id])),
                )
        self.assert_length(queries, 14)

        self.assert_length(events, 2)
        add_event, add_peer_event = events
        self.assertEqual(add_event['event']['type'], 'subscription')
        self.assertEqual(add_event['event']['op'], 'add')
        self.assertEqual(add_event['users'], [get_user(self.test_email, self.test_realm).id])
        self.assertEqual(
            set(add_event['event']['subscriptions'][0]['subscribers']),
            {user1.id, user2.id, self.test_user.id},
        )

        self.assertNotIn(self.example_user('polonius').id, add_peer_event['users'])
        self.assertEqual(len(add_peer_event['users']), 11)
        self.assertEqual(add_peer_event['event']['type'], 'subscription')
        self.assertEqual(add_peer_event['event']['op'], 'peer_add')
        self.assertEqual(add_peer_event['event']['user_id'], self.user_profile.id)

        stream = get_stream('multi_user_stream', realm)
        self.assertEqual(num_subscribers_for_stream_id(stream.id), 3)

        # Finally, add othello.
        events = []
        user_profile = self.example_user('othello')
        email3 = user_profile.email
        user3 = user_profile
        realm3 = user_profile.realm
        stream = get_stream('multi_user_stream', realm)
        with tornado_redirected_to_list(events):
            bulk_add_subscriptions([stream], [user_profile])

        self.assert_length(events, 2)
        add_event, add_peer_event = events

        self.assertEqual(add_event['event']['type'], 'subscription')
        self.assertEqual(add_event['event']['op'], 'add')
        self.assertEqual(add_event['users'], [get_user(email3, realm3).id])
        self.assertEqual(
            set(add_event['event']['subscriptions'][0]['subscribers']),
            {user1.id, user2.id, user3.id, self.test_user.id},
        )

        # We don't send a peer_add event to othello
        self.assertNotIn(user_profile.id, add_peer_event['users'])
        self.assertNotIn(self.example_user('polonius').id, add_peer_event['users'])
        self.assertEqual(len(add_peer_event['users']), 11)
        self.assertEqual(add_peer_event['event']['type'], 'subscription')
        self.assertEqual(add_peer_event['event']['op'], 'peer_add')
        self.assertEqual(add_peer_event['event']['user_id'], user_profile.id)

    def test_private_stream_subscription(self) -> None:
        realm = get_realm("zulip")

        # Create a private stream with Hamlet subscribed
        stream_name = "private"
        stream = ensure_stream(realm, stream_name, invite_only=True)

        existing_user_profile = self.example_user('hamlet')
        bulk_add_subscriptions([stream], [existing_user_profile])

        # Now subscribe Cordelia to the stream, capturing events
        user_profile = self.example_user('cordelia')

        events: List[Mapping[str, Any]] = []
        with tornado_redirected_to_list(events):
            bulk_add_subscriptions([stream], [user_profile])

        self.assert_length(events, 3)
        create_event, add_event, add_peer_event = events

        self.assertEqual(create_event['event']['type'], 'stream')
        self.assertEqual(create_event['event']['op'], 'create')
        self.assertEqual(create_event['users'], [user_profile.id])
        self.assertEqual(create_event['event']['streams'][0]['name'], stream_name)

        self.assertEqual(add_event['event']['type'], 'subscription')
        self.assertEqual(add_event['event']['op'], 'add')
        self.assertEqual(add_event['users'], [user_profile.id])
        self.assertEqual(
            set(add_event['event']['subscriptions'][0]['subscribers']),
            {user_profile.id, existing_user_profile.id},
        )

        # We don't send a peer_add event to othello, but we do send peer_add event to
        # all realm admins.
        self.assertNotIn(user_profile.id, add_peer_event['users'])
        self.assertEqual(len(add_peer_event['users']), 3)
        self.assertEqual(add_peer_event['event']['type'], 'subscription')
        self.assertEqual(add_peer_event['event']['op'], 'peer_add')
        self.assertEqual(add_peer_event['event']['user_id'], user_profile.id)

        # Do not send stream creation event to realm admin users
        # even if realm admin is subscribed to stream cause realm admin already get
        # private stream creation event on stream creation.
        new_stream = ensure_stream(realm, "private stream", invite_only=True)
        events = []
        with tornado_redirected_to_list(events):
            bulk_add_subscriptions([new_stream], [self.example_user("iago")])

        self.assert_length(events, 3)
        create_event, add_event, add_peer_event = events
        self.assertEqual(create_event['event']['type'], 'stream')
        self.assertEqual(create_event['event']['op'], 'create')
        self.assertEqual(create_event['users'], [])

        self.assertEqual(add_event['event']['type'], 'subscription')
        self.assertEqual(add_event['event']['op'], 'add')
        self.assertEqual(add_event['users'], [self.example_user("iago").id])

        self.assertEqual(len(add_peer_event['users']), 1)
        self.assertEqual(add_peer_event['event']['type'], 'subscription')
        self.assertEqual(add_peer_event['event']['op'], 'peer_add')
        self.assertEqual(add_peer_event['event']['user_id'], self.example_user("iago").id)

    def test_subscribe_to_stream_post_policy_admins_stream(self) -> None:
        """
        Members can subscribe to streams where only admins can post
        """
        member = self.example_user("AARON")
        stream = self.make_stream('stream1')
        do_change_stream_post_policy(stream, Stream.STREAM_POST_POLICY_ADMINS)
        result = self.common_subscribe_to_streams(member, ["stream1"])
        self.assert_json_success(result)

        json = result.json()
        self.assertEqual(json["subscribed"], {member.email: ["stream1"]})
        self.assertEqual(json["already_subscribed"], {})

    def test_subscribe_to_stream_post_policy_restrict_new_members_stream(self) -> None:
        """
        New members can subscribe to streams where they can not post
        """
        new_member_email = self.nonreg_email('test')
        self.register(new_member_email, "test")
        new_member = self.nonreg_user('test')

        do_set_realm_property(new_member.realm, 'waiting_period_threshold', 10)
        self.assertTrue(new_member.is_new_member)

        stream = self.make_stream('stream1')
        do_change_stream_post_policy(stream, Stream.STREAM_POST_POLICY_RESTRICT_NEW_MEMBERS)
        result = self.common_subscribe_to_streams(new_member, ["stream1"])
        self.assert_json_success(result)

        json = result.json()
        self.assertEqual(json["subscribed"], {new_member.email: ["stream1"]})
        self.assertEqual(json["already_subscribed"], {})

    def test_guest_user_subscribe(self) -> None:
        """Guest users cannot subscribe themselves to anything"""
        guest_user = self.example_user("polonius")
        result = self.common_subscribe_to_streams(guest_user, ["Denmark"])
        self.assert_json_error(result, "Not allowed for guest users")

        # Verify the internal checks also block guest users.
        stream = get_stream("Denmark", guest_user.realm)
        self.assertEqual(filter_stream_authorization(guest_user, [stream]),
                         ([], [stream]))

        # Test UserProfile.can_create_streams for guest users.
        streams_raw = [{
            'invite_only': False,
            'history_public_to_subscribers': None,
            'name': 'new_stream',
            'stream_post_policy': Stream.STREAM_POST_POLICY_EVERYONE,
        }]

        with self.assertRaisesRegex(JsonableError, "User cannot create streams."):
            list_to_streams(streams_raw, guest_user)

        stream = self.make_stream('private_stream', invite_only=True)
        result = self.common_subscribe_to_streams(guest_user, ["private_stream"])
        self.assert_json_error(result, "Not allowed for guest users")
        self.assertEqual(filter_stream_authorization(guest_user, [stream]),
                         ([], [stream]))

    def test_users_getting_add_peer_event(self) -> None:
        """
        Check users getting add_peer_event is correct
        """
        streams_to_sub = ['multi_user_stream']
        othello = self.example_user('othello')
        cordelia = self.example_user('cordelia')
        iago = self.example_user('iago')
        orig_user_ids_to_subscribe = [self.test_user.id, othello.id]
        self.common_subscribe_to_streams(
            self.test_user,
            streams_to_sub,
            dict(principals=ujson.dumps(orig_user_ids_to_subscribe)))

        new_user_ids_to_subscribe = [iago.id, cordelia.id]
        events: List[Mapping[str, Any]] = []
        with tornado_redirected_to_list(events):
            self.common_subscribe_to_streams(
                self.test_user,
                streams_to_sub,
                dict(principals=ujson.dumps(new_user_ids_to_subscribe)),
            )

        add_peer_events = [events[2], events[3]]
        for add_peer_event in add_peer_events:
            self.assertEqual(add_peer_event['event']['type'], 'subscription')
            self.assertEqual(add_peer_event['event']['op'], 'peer_add')
            event_sent_to_ids = add_peer_event['users']
            for user_id in new_user_ids_to_subscribe:
                # Make sure new users subscribed to stream is not in
                # peer_add event recipient list
                self.assertNotIn(user_id, event_sent_to_ids)
            for old_user in orig_user_ids_to_subscribe:
                # Check non new users are in peer_add event recipient list.
                self.assertIn(old_user, event_sent_to_ids)

    def test_users_getting_remove_peer_event(self) -> None:
        """
        Check users getting add_peer_event is correct
        """
        user1 = self.example_user("othello")
        user2 = self.example_user("cordelia")
        user3 = self.example_user("hamlet")
        user4 = self.example_user("iago")
        user5 = self.example_user("AARON")

        stream1 = self.make_stream('stream1')
        stream2 = self.make_stream('stream2')
        private = self.make_stream('private_stream', invite_only=True)

        self.subscribe(user1, 'stream1')
        self.subscribe(user2, 'stream1')
        self.subscribe(user3, 'stream1')

        self.subscribe(user2, 'stream2')

        self.subscribe(user1, 'private_stream')
        self.subscribe(user2, 'private_stream')
        self.subscribe(user3, 'private_stream')

        events: List[Mapping[str, Any]] = []
        with tornado_redirected_to_list(events):
            bulk_remove_subscriptions(
                [user1, user2],
                [stream1, stream2, private],
                get_client("website"),
            )

        peer_events = [e for e in events
                       if e['event'].get('op') == 'peer_remove']

        notifications = set()
        for event in peer_events:
            for user_id in event['users']:
                for stream_name in event['event']['subscriptions']:
                    removed_user_id = event['event']['user_id']
                    notifications.add((user_id, removed_user_id, stream_name))

        # POSITIVE CASES FIRST
        self.assertIn((user3.id, user1.id, 'stream1'), notifications)
        self.assertIn((user4.id, user1.id, 'stream1'), notifications)

        self.assertIn((user3.id, user2.id, 'stream1'), notifications)
        self.assertIn((user4.id, user2.id, 'stream1'), notifications)

        self.assertIn((user1.id, user2.id, 'stream2'), notifications)
        self.assertIn((user3.id, user2.id, 'stream2'), notifications)
        self.assertIn((user4.id, user2.id, 'stream2'), notifications)

        self.assertIn((user3.id, user1.id, 'private_stream'), notifications)
        self.assertIn((user3.id, user2.id, 'private_stream'), notifications)

        self.assertIn((user4.id, user1.id, 'private_stream'), notifications)
        self.assertIn((user4.id, user2.id, 'private_stream'), notifications)

        # NEGATIVE

        # don't be notified if you are being removed yourself
        self.assertNotIn((user1.id, user1.id, 'stream1'), notifications)

        # don't send false notifications for folks that weren't actually
        # subscribed int he first place
        self.assertNotIn((user3.id, user1.id, 'stream2'), notifications)

        # don't send notifications for random people
        self.assertNotIn((user3.id, user4.id, 'stream2'), notifications)

        # don't send notifications to unsubscribed non realm admin users for private streams
        self.assertNotIn((user5.id, user1.id, 'private_stream'), notifications)

    def test_bulk_subscribe_MIT(self) -> None:
        mit_user = self.mit_user('starnine')

        realm = get_realm("zephyr")
        stream_names = [f"stream_{i}" for i in range(40)]
        streams = [
            self.make_stream(stream_name, realm=realm)
            for stream_name in stream_names]

        for stream in streams:
            stream.is_in_zephyr_realm = True
            stream.save()

        events: List[Mapping[str, Any]] = []
        with tornado_redirected_to_list(events):
            with queries_captured() as queries:
                self.common_subscribe_to_streams(
                    mit_user,
                    stream_names,
                    dict(principals=ujson.dumps([mit_user.id])),
                    subdomain="zephyr",
                )
        # Make sure Zephyr mirroring realms such as MIT do not get
        # any tornado subscription events
        self.assert_length(events, 0)
        self.assert_length(queries, 5)

        events = []
        with tornado_redirected_to_list(events):
            bulk_remove_subscriptions(
                users=[mit_user],
                streams=streams,
                acting_client=get_client('website'),
            )

        self.assert_length(events, 0)

    def test_bulk_subscribe_many(self) -> None:

        # Create a whole bunch of streams
        streams = [f"stream_{i}" for i in range(20)]
        for stream_name in streams:
            self.make_stream(stream_name)

        with queries_captured() as queries:
            self.common_subscribe_to_streams(
                self.test_user,
                streams,
                dict(principals=ujson.dumps([self.test_user.id])),
            )
        # Make sure we don't make O(streams) queries
        self.assert_length(queries, 16)

    def test_subscriptions_add_for_principal(self) -> None:
        """
        You can subscribe other people to streams.
        """
        invitee = self.example_user("iago")
        current_streams = self.get_streams(invitee)
        invite_streams = self.make_random_stream_names(current_streams)
        self.assert_adding_subscriptions_for_principal(invitee.id, invitee.realm, invite_streams)

    def test_subscriptions_add_for_principal_legacy_emails(self) -> None:
        invitee = self.example_user("iago")
        current_streams = self.get_streams(invitee)
        invite_streams = self.make_random_stream_names(current_streams)
        self.assert_adding_subscriptions_for_principal(invitee.email, invitee.realm, invite_streams)

    def test_subscriptions_add_for_principal_deactivated(self) -> None:
        """
        You can't subscribe deactivated people to streams.
        """
        target_profile = self.example_user("cordelia")
        post_data = dict(
            principals=ujson.dumps([target_profile.id]),
        )
        result = self.common_subscribe_to_streams(self.test_user, "Verona", post_data)
        self.assert_json_success(result)

        do_deactivate_user(target_profile)
        result = self.common_subscribe_to_streams(self.test_user, "Denmark", post_data)
        self.assert_json_error(
            result,
            f"User not authorized to execute queries on behalf of '{target_profile.id}'",
            status_code=403)

    def test_subscriptions_add_for_principal_invite_only(self) -> None:
        """
        You can subscribe other people to invite only streams.
        """
        invitee = self.example_user("iago")
        current_streams = self.get_streams(invitee)
        invite_streams = self.make_random_stream_names(current_streams)
        self.assert_adding_subscriptions_for_principal(invitee.id, invitee.realm, invite_streams,
                                                       invite_only=True)

    def test_non_ascii_subscription_for_principal(self) -> None:
        """
        You can subscribe other people to streams even if they containing
        non-ASCII characters.
        """
        iago = self.example_user('iago')
        self.assert_adding_subscriptions_for_principal(iago.id, get_realm('zulip'), ["hümbüǵ"])

    def test_subscription_add_invalid_principal_legacy_emails(self) -> None:
        """
        Calling subscribe on behalf of a principal that does not exist
        should return a JSON error.
        """
        invalid_principal = "rosencrantz-and-guildenstern@zulip.com"
        invalid_principal_realm = get_realm("zulip")
        # verify that invalid_principal actually doesn't exist
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user(invalid_principal, invalid_principal_realm)
        result = self.common_subscribe_to_streams(self.test_user, self.streams,
                                                  {"principals": ujson.dumps([invalid_principal])})
        self.assert_json_error(result, "User not authorized to execute queries on behalf of '%s'"
                               % (invalid_principal,), status_code=403)

    def test_subscription_add_invalid_principal(self) -> None:
        invalid_principal = 999
        invalid_principal_realm = get_realm("zulip")
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user_profile_by_id_in_realm(invalid_principal, invalid_principal_realm)
        result = self.common_subscribe_to_streams(self.test_user, self.streams,
                                                  {"principals": ujson.dumps([invalid_principal])})
        self.assert_json_error(result, "User not authorized to execute queries on behalf of '%s'"
                               % (invalid_principal,), status_code=403)

    def test_subscription_add_principal_other_realm(self) -> None:
        """
        Calling subscribe on behalf of a principal in another realm
        should return a JSON error.
        """
        profile = self.mit_user('starnine')
        principal = profile.id
        # verify that principal exists (thus, the reason for the error is the cross-realming)
        self.assertIsInstance(profile, UserProfile)
        result = self.common_subscribe_to_streams(self.test_user, self.streams,
                                                  {"principals": ujson.dumps([principal])})
        self.assert_json_error(result, "User not authorized to execute queries on behalf of '%s'"
                               % (principal,), status_code=403)

    def helper_check_subs_before_and_after_remove(self, subscriptions: List[str],
                                                  json_dict: Dict[str, Any],
                                                  email: str, new_subs: List[str],
                                                  realm: Realm) -> None:
        """
        Check result of removing subscriptions.

        Unlike adding subscriptions, you can only remove subscriptions
        for yourself, so the result format is different.

        {"msg": "",
         "removed": ["Denmark", "Scotland", "Verona"],
         "not_removed": ["Rome"], "result": "success"}
        """
        result = self.client_delete("/json/users/me/subscriptions",
                                    {"subscriptions": ujson.dumps(subscriptions)})
        self.assert_json_success(result)
        json = result.json()
        for key, val in json_dict.items():
            self.assertEqual(sorted(val), sorted(json[key]))  # we don't care about the order of the items
        user = get_user(email, realm)
        new_streams = self.get_streams(user)
        self.assertEqual(sorted(new_streams), sorted(new_subs))

    def test_successful_subscriptions_remove(self) -> None:
        """
        Calling DELETE /json/users/me/subscriptions should successfully remove streams,
        and should determine which were removed vs which weren't subscribed to.
        We cannot randomly generate stream names because the remove code
        verifies whether streams exist.
        """
        self.assertGreaterEqual(len(self.streams), 2)
        streams_to_remove = self.streams[1:]
        not_subbed = []
        for stream in Stream.objects.all():
            if stream.name not in self.streams:
                not_subbed.append(stream.name)
        random.shuffle(not_subbed)
        self.assertNotEqual(len(not_subbed), 0)  # necessary for full test coverage
        try_to_remove = not_subbed[:3]  # attempt to remove up to 3 streams not already subbed to
        streams_to_remove.extend(try_to_remove)
        self.helper_check_subs_before_and_after_remove(streams_to_remove,
                                                       {"removed": self.streams[1:], "not_removed": try_to_remove},
                                                       self.test_email, [self.streams[0]], self.test_realm)

    def test_subscriptions_remove_fake_stream(self) -> None:
        """
        Calling DELETE /json/users/me/subscriptions on a stream that doesn't exist
        should return a JSON error.
        """
        random_streams = self.make_random_stream_names(self.streams)
        self.assertNotEqual(len(random_streams), 0)  # necessary for full test coverage
        streams_to_remove = random_streams[:1]  # pick only one fake stream, to make checking the error message easy
        result = self.client_delete("/json/users/me/subscriptions",
                                    {"subscriptions": ujson.dumps(streams_to_remove)})
        self.assert_json_error(result, f"Stream(s) ({random_streams[0]}) do not exist")

    def helper_subscriptions_exists(self, stream: str, expect_success: bool, subscribed: bool) -> None:
        """
        Call /json/subscriptions/exists on a stream and expect a certain result.
        """
        result = self.client_post("/json/subscriptions/exists",
                                  {"stream": stream})
        json = result.json()
        if expect_success:
            self.assert_json_success(result)
        else:
            self.assertEqual(result.status_code, 404)
        if subscribed:
            self.assertIn("subscribed", json)
            self.assertEqual(json["subscribed"], subscribed)

    def test_successful_subscriptions_exists_subbed(self) -> None:
        """
        Calling /json/subscriptions/exist on a stream to which you are subbed
        should return that it exists and that you are subbed.
        """
        self.assertNotEqual(len(self.streams), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(self.streams[0], True, True)

    def test_successful_subscriptions_exists_not_subbed(self) -> None:
        """
        Calling /json/subscriptions/exist on a stream to which you are not
        subbed should return that it exists and that you are not subbed.
        """
        all_stream_names = [stream.name for stream in Stream.objects.filter(realm=self.test_realm)]
        streams_not_subbed = list(set(all_stream_names) - set(self.streams))
        self.assertNotEqual(len(streams_not_subbed), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(streams_not_subbed[0], True, False)

    def test_subscriptions_does_not_exist(self) -> None:
        """
        Calling /json/subscriptions/exist on a stream that doesn't exist should
        return that it doesn't exist.
        """
        random_streams = self.make_random_stream_names(self.streams)
        self.assertNotEqual(len(random_streams), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(random_streams[0], False, False)

    def test_subscriptions_exist_invalid_name(self) -> None:
        """
        Calling /json/subscriptions/exist on a stream whose name is invalid (as
        defined by valid_stream_name in zerver/views.py) should return a JSON
        error.
        """
        # currently, the only invalid stream name is the empty string
        invalid_stream_name = ""
        result = self.client_post("/json/subscriptions/exists",
                                  {"stream": invalid_stream_name})
        self.assert_json_error(result, "Invalid stream name ''")

    def test_existing_subscriptions_autosubscription(self) -> None:
        """
        Call /json/subscriptions/exist on an existing stream and autosubscribe to it.
        """
        stream_name = "new_public_stream"
        cordelia = self.example_user('cordelia')
        result = self.common_subscribe_to_streams(cordelia, [stream_name],
                                                  invite_only=False)
        result = self.client_post("/json/subscriptions/exists",
                                  {"stream": stream_name, "autosubscribe": "false"})
        self.assert_json_success(result)
        self.assertIn("subscribed", result.json())
        self.assertFalse(result.json()["subscribed"])

        result = self.client_post("/json/subscriptions/exists",
                                  {"stream": stream_name, "autosubscribe": "true"})
        self.assert_json_success(result)
        self.assertIn("subscribed", result.json())
        self.assertTrue(result.json()["subscribed"])

    def test_existing_subscriptions_autosubscription_private_stream(self) -> None:
        """Call /json/subscriptions/exist on an existing private stream with
        autosubscribe should fail.
        """
        stream_name = "Saxony"
        cordelia = self.example_user('cordelia')
        result = self.common_subscribe_to_streams(cordelia, [stream_name],
                                                  invite_only=True)
        stream = get_stream(stream_name, self.test_realm)

        result = self.client_post("/json/subscriptions/exists",
                                  {"stream": stream_name, "autosubscribe": "true"})
        # We can't see invite-only streams here
        self.assert_json_error(result, "Invalid stream name 'Saxony'", status_code=404)
        # Importantly, we are not now subscribed
        self.assertEqual(num_subscribers_for_stream_id(stream.id), 1)

        # A user who is subscribed still sees the stream exists
        self.login('cordelia')
        result = self.client_post("/json/subscriptions/exists",
                                  {"stream": stream_name, "autosubscribe": "false"})
        self.assert_json_success(result)
        self.assertIn("subscribed", result.json())
        self.assertTrue(result.json()["subscribed"])

    def get_subscription(self, user_profile: UserProfile, stream_name: str) -> Subscription:
        stream = get_stream(stream_name, self.test_realm)
        return Subscription.objects.get(
            user_profile=user_profile,
            recipient__type=Recipient.STREAM,
            recipient__type_id=stream.id,
        )

    def test_subscriptions_add_notification_default_none(self) -> None:
        """
        When creating a subscription, the desktop, push, and audible notification
        settings for that stream are none. A value of None means to use the values
        inherited from the global notification settings.
        """
        user_profile = self.example_user('iago')
        invitee_user_id = user_profile.id
        invitee_realm = user_profile.realm
        user_profile.enable_stream_desktop_notifications = True
        user_profile.enable_stream_push_notifications = True
        user_profile.enable_stream_audible_notifications = True
        user_profile.enable_stream_email_notifications = True
        user_profile.save()
        current_stream = self.get_streams(user_profile)[0]
        invite_streams = self.make_random_stream_names([current_stream])
        self.assert_adding_subscriptions_for_principal(invitee_user_id, invitee_realm, invite_streams)
        subscription = self.get_subscription(user_profile, invite_streams[0])

        with mock.patch('zerver.models.Recipient.__str__', return_value='recip'):
            self.assertEqual(str(subscription),
                             '<Subscription: '
                             '<UserProfile: %s %s> -> recip>' % (user_profile.email, user_profile.realm))

        self.assertIsNone(subscription.desktop_notifications)
        self.assertIsNone(subscription.push_notifications)
        self.assertIsNone(subscription.audible_notifications)
        self.assertIsNone(subscription.email_notifications)

    def test_mark_messages_as_unread_on_unsubscribe(self) -> None:
        realm = get_realm("zulip")
        user = self.example_user("iago")
        random_user = self.example_user("hamlet")
        stream1 = ensure_stream(realm, "stream1", invite_only=False)
        stream2 = ensure_stream(realm, "stream2", invite_only=False)
        private = ensure_stream(realm, "private_stream", invite_only=True)

        self.subscribe(user, "stream1")
        self.subscribe(user, "stream2")
        self.subscribe(user, "private_stream")
        self.subscribe(random_user, "stream1")
        self.subscribe(random_user, "stream2")
        self.subscribe(random_user, "private_stream")

        self.send_stream_message(random_user, "stream1", "test", "test")
        self.send_stream_message(random_user, "stream2", "test", "test")
        self.send_stream_message(random_user, "private_stream", "test", "test")

        def get_unread_stream_data() -> List[Dict[str, Any]]:
            raw_unread_data = get_raw_unread_data(user)
            aggregated_data = aggregate_unread_data(raw_unread_data)
            return aggregated_data['streams']

        result = get_unread_stream_data()
        self.assert_length(result, 3)
        self.assertEqual(result[0]['stream_id'], stream1.id)
        self.assertEqual(result[1]['stream_id'], stream2.id)
        self.assertEqual(result[2]['stream_id'], private.id)

        # Unsubscribing should mark all the messages in stream2 as read
        self.unsubscribe(user, "stream2")
        self.unsubscribe(user, "private_stream")

        self.subscribe(user, "stream2")
        self.subscribe(user, "private_stream")
        result = get_unread_stream_data()
        self.assert_length(result, 1)
        self.assertEqual(result[0]['stream_id'], stream1.id)

    def test_gather_subscriptions_excludes_deactivated_streams(self) -> None:
        """
        Check that gather_subscriptions_helper does not include deactivated streams in its
        results.
        """
        realm = get_realm("zulip")
        admin_user = self.example_user("iago")
        non_admin_user = self.example_user("cordelia")

        self.login_user(admin_user)

        for stream_name in ["stream1", "stream2", "stream3"]:
            self.make_stream(stream_name, realm=realm, invite_only=False)
            self.subscribe(admin_user, stream_name)
            self.subscribe(non_admin_user, stream_name)
            self.subscribe(self.example_user("othello"), stream_name)

        def delete_stream(stream_name: str) -> None:
            stream_id = get_stream(stream_name, realm).id
            result = self.client_delete('/json/streams/%d' % (stream_id,))
            self.assert_json_success(result)

        # Deleted/deactivated stream should not be returned in the helper results
        admin_before_delete = gather_subscriptions_helper(admin_user)
        non_admin_before_delete = gather_subscriptions_helper(non_admin_user)

        # Delete our stream
        delete_stream("stream1")

        # Get subs after delete
        admin_after_delete = gather_subscriptions_helper(admin_user)
        non_admin_after_delete = gather_subscriptions_helper(non_admin_user)

        # Compare results - should be 1 stream less
        self.assertTrue(
            len(admin_before_delete[0]) == len(admin_after_delete[0]) + 1,
            'Expected exactly 1 less stream from gather_subscriptions_helper')
        self.assertTrue(
            len(non_admin_before_delete[0]) == len(non_admin_after_delete[0]) + 1,
            'Expected exactly 1 less stream from gather_subscriptions_helper')

    def test_validate_user_access_to_subscribers_helper(self) -> None:
        """
        Ensure the validate_user_access_to_subscribers_helper is properly raising
        ValidationError on missing user, user not-in-realm.
        """
        user_profile = self.example_user('othello')
        realm_name = 'no_othello_allowed'
        realm = do_create_realm(realm_name, 'Everyone but Othello is allowed')
        stream_dict = {
            'name': 'publicstream',
            'description': 'Public stream with public history',
            'realm_id': realm.id,
        }

        # For this test to work, othello can't be in the no_othello_here realm
        self.assertNotEqual(user_profile.realm.id, realm.id, 'Expected othello user to not be in this realm.')

        # This should result in missing user
        with self.assertRaises(ValidationError):
            validate_user_access_to_subscribers_helper(None, stream_dict, lambda: True)

        # This should result in user not in realm
        with self.assertRaises(ValidationError):
            validate_user_access_to_subscribers_helper(user_profile, stream_dict, lambda: True)

    def test_subscriptions_query_count(self) -> None:
        """
        Test database query count when creating stream with api/v1/users/me/subscriptions.
        """
        user1 = self.example_user("cordelia")
        user2 = self.example_user("iago")
        new_streams = [
            'query_count_stream_1',
            'query_count_stream_2',
            'query_count_stream_3',
        ]

        # Test creating a public stream when realm does not have a notification stream.
        with queries_captured() as queries:
            self.common_subscribe_to_streams(
                self.test_user,
                [new_streams[0]],
                dict(principals=ujson.dumps([user1.id, user2.id])),
            )
        self.assert_length(queries, 39)

        # Test creating private stream.
        with queries_captured() as queries:
            self.common_subscribe_to_streams(
                self.test_user,
                [new_streams[1]],
                dict(principals=ujson.dumps([user1.id, user2.id])),
                invite_only=True,
            )
        self.assert_length(queries, 39)

        # Test creating a public stream with announce when realm has a notification stream.
        notifications_stream = get_stream(self.streams[0], self.test_realm)
        self.test_realm.notifications_stream_id = notifications_stream.id
        self.test_realm.save()
        with queries_captured() as queries:
            self.common_subscribe_to_streams(
                self.test_user,
                [new_streams[2]],
                dict(
                    announce='true',
                    principals=ujson.dumps([user1.id, user2.id]),
                ),
            )
        self.assert_length(queries, 50)

class GetStreamsTest(ZulipTestCase):
    def test_streams_api_for_bot_owners(self) -> None:
        hamlet = self.example_user('hamlet')
        test_bot = self.create_test_bot('foo', hamlet, bot_owner=hamlet)
        assert test_bot is not None
        realm = get_realm('zulip')
        self.login_user(hamlet)

        # Check it correctly lists the bot owner's subs with
        # include_owner_subscribed=true
        result = self.api_get(
            test_bot,
            "/api/v1/streams?include_owner_subscribed=true&include_public=false&include_subscribed=false")
        owner_subs = self.api_get(hamlet, "/api/v1/users/me/subscriptions")

        self.assert_json_success(result)
        json = result.json()
        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

        self.assert_json_success(owner_subs)
        owner_subs_json = ujson.loads(owner_subs.content)

        self.assertEqual(sorted([s["name"] for s in json["streams"]]),
                         sorted([s["name"] for s in owner_subs_json["subscriptions"]]))

        # Check it correctly lists the bot owner's subs and the
        # bot's subs
        self.subscribe(test_bot, 'Scotland')
        result = self.api_get(
            test_bot,
            "/api/v1/streams?include_owner_subscribed=true&include_public=false&include_subscribed=true",
        )

        self.assert_json_success(result)
        json = result.json()
        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

        actual = sorted([s["name"] for s in json["streams"]])
        expected = [s["name"] for s in owner_subs_json["subscriptions"]]
        expected.append('Scotland')
        expected.sort()

        self.assertEqual(actual, expected)

        # Check it correctly lists the bot owner's subs + all public streams
        self.make_stream('private_stream', realm=realm, invite_only=True)
        self.subscribe(test_bot, 'private_stream')
        result = self.api_get(
            test_bot,
            "/api/v1/streams?include_owner_subscribed=true&include_public=true&include_subscribed=false",
        )

        self.assert_json_success(result)
        json = result.json()
        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

        actual = sorted([s["name"] for s in json["streams"]])
        expected = [s["name"] for s in owner_subs_json["subscriptions"]]
        expected.extend(['Rome', 'Venice', 'Scotland'])
        expected.sort()

        self.assertEqual(actual, expected)

        # Check it correctly lists the bot owner's subs + all public streams +
        # the bot's subs
        result = self.api_get(
            test_bot,
            "/api/v1/streams?include_owner_subscribed=true&include_public=true&include_subscribed=true",
        )

        self.assert_json_success(result)
        json = result.json()
        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

        actual = sorted([s["name"] for s in json["streams"]])
        expected = [s["name"] for s in owner_subs_json["subscriptions"]]
        expected.extend(['Rome', 'Venice', 'Scotland', 'private_stream'])
        expected.sort()

        self.assertEqual(actual, expected)

    def test_all_active_streams_api(self) -> None:
        url = '/api/v1/streams?include_all_active=true'

        # Check non-superuser can't use include_all_active
        normal_user = self.example_user('cordelia')
        result = self.api_get(normal_user, url)
        self.assertEqual(result.status_code, 400)

        # Even realm admin users can't see all
        # active streams (without additional privileges).
        admin_user = self.example_user('iago')
        self.assertTrue(admin_user.is_realm_admin)
        result = self.api_get(admin_user, url)
        self.assertEqual(result.status_code, 400)

        '''
        HAPPY PATH:

            We can get all active streams ONLY if we are
            an API "super user".  We typically create
            api-super-user accounts for things like
            Zephyr/Jabber mirror API users, but here
            we just "knight" Hamlet for testing expediency.
        '''
        super_user = self.example_user('hamlet')
        super_user.is_api_super_user = True
        super_user.save()

        result = self.api_get(super_user, url)
        self.assert_json_success(result)
        json = result.json()

        self.assertIn('streams', json)
        self.assertIsInstance(json['streams'], list)

        stream_names = {s['name'] for s in json['streams']}

        self.assertEqual(
            stream_names,
            {'Venice', 'Denmark', 'Scotland', 'Verona', 'Rome'},
        )

    def test_public_streams_api(self) -> None:
        """
        Ensure that the query we use to get public streams successfully returns
        a list of streams
        """
        user = self.example_user('hamlet')
        realm = get_realm('zulip')
        self.login_user(user)

        # Check it correctly lists the user's subs with include_public=false
        result = self.api_get(user, "/api/v1/streams?include_public=false")
        result2 = self.api_get(user, "/api/v1/users/me/subscriptions")

        self.assert_json_success(result)
        json = result.json()

        self.assertIn("streams", json)

        self.assertIsInstance(json["streams"], list)

        self.assert_json_success(result2)
        json2 = ujson.loads(result2.content)

        self.assertEqual(sorted([s["name"] for s in json["streams"]]),
                         sorted([s["name"] for s in json2["subscriptions"]]))

        # Check it correctly lists all public streams with include_subscribed=false
        result = self.api_get(user, "/api/v1/streams?include_public=true&include_subscribed=false")
        self.assert_json_success(result)

        json = result.json()
        all_streams = [stream.name for stream in
                       Stream.objects.filter(realm=realm)]
        self.assertEqual(sorted(s["name"] for s in json["streams"]),
                         sorted(all_streams))

class StreamIdTest(ZulipTestCase):
    def test_get_stream_id(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)
        stream = gather_subscriptions(user)[0][0]
        result = self.client_get("/json/get_stream_id?stream={}".format(stream['name']))
        self.assert_json_success(result)
        self.assertEqual(result.json()['stream_id'], stream['stream_id'])

    def test_get_stream_id_wrong_name(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)
        result = self.client_get("/json/get_stream_id?stream=wrongname")
        self.assert_json_error(result, "Invalid stream name 'wrongname'")

class InviteOnlyStreamTest(ZulipTestCase):
    def test_must_be_subbed_to_send(self) -> None:
        """
        If you try to send a message to an invite-only stream to which
        you aren't subscribed, you'll get a 400.
        """
        user = self.example_user('hamlet')
        self.login_user(user)
        # Create Saxony as an invite-only stream.
        self.assert_json_success(
            self.common_subscribe_to_streams(user, ["Saxony"],
                                             invite_only=True))

        cordelia = self.example_user("cordelia")
        with self.assertRaises(JsonableError):
            self.send_stream_message(cordelia, "Saxony")

    def test_list_respects_invite_only_bit(self) -> None:
        """
        Make sure that /api/v1/users/me/subscriptions properly returns
        the invite-only bit for streams that are invite-only
        """

        user = self.example_user('hamlet')
        self.login_user(user)

        result1 = self.common_subscribe_to_streams(user, ["Saxony"], invite_only=True)
        self.assert_json_success(result1)
        result2 = self.common_subscribe_to_streams(user, ["Normandy"], invite_only=False)
        self.assert_json_success(result2)
        result = self.api_get(user, "/api/v1/users/me/subscriptions")
        self.assert_json_success(result)
        self.assertIn("subscriptions", result.json())
        for sub in result.json()["subscriptions"]:
            if sub['name'] == "Normandy":
                self.assertEqual(sub['invite_only'], False, "Normandy was mistakenly marked private")
            if sub['name'] == "Saxony":
                self.assertEqual(sub['invite_only'], True, "Saxony was not properly marked private")

    @slow("lots of queries")
    def test_inviteonly(self) -> None:
        # Creating an invite-only stream is allowed
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')

        stream_name = "Saxony"

        result = self.common_subscribe_to_streams(hamlet, [stream_name], invite_only=True)
        self.assert_json_success(result)

        json = result.json()
        self.assertEqual(json["subscribed"], {hamlet.email: [stream_name]})
        self.assertEqual(json["already_subscribed"], {})

        # Subscribing oneself to an invite-only stream is not allowed
        self.login_user(othello)
        result = self.common_subscribe_to_streams(othello, [stream_name])
        self.assert_json_error(result, 'Unable to access stream (Saxony).')

        # authorization_errors_fatal=False works
        self.login_user(othello)
        result = self.common_subscribe_to_streams(othello, [stream_name],
                                                  extra_post_data={'authorization_errors_fatal': ujson.dumps(False)})
        self.assert_json_success(result)
        json = result.json()
        self.assertEqual(json["unauthorized"], [stream_name])
        self.assertEqual(json["subscribed"], {})
        self.assertEqual(json["already_subscribed"], {})

        # Inviting another user to an invite-only stream is allowed
        self.login_user(hamlet)
        result = self.common_subscribe_to_streams(
            hamlet, [stream_name],
            extra_post_data={'principals': ujson.dumps([othello.id])})
        self.assert_json_success(result)
        json = result.json()
        self.assertEqual(json["subscribed"], {othello.email: [stream_name]})
        self.assertEqual(json["already_subscribed"], {})

        # Make sure both users are subscribed to this stream
        stream_id = get_stream(stream_name, hamlet.realm).id
        result = self.api_get(hamlet, "/api/v1/streams/%d/members" % (stream_id,))
        self.assert_json_success(result)
        json = result.json()

        self.assertTrue(othello.email in json['subscribers'])
        self.assertTrue(hamlet.email in json['subscribers'])

class GetSubscribersTest(ZulipTestCase):

    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user('hamlet')
        self.login_user(self.user_profile)

    def assert_user_got_subscription_notification(self, expected_msg: str) -> None:
        # verify that the user was sent a message informing them about the subscription
        msg = self.get_last_message()
        self.assertEqual(msg.recipient.type, msg.recipient.PERSONAL)
        self.assertEqual(msg.sender_id, self.notification_bot().id)

        def non_ws(s: str) -> str:
            return s.replace('\n', '').replace(' ', '')

        self.assertEqual(non_ws(msg.content), non_ws(expected_msg))

    def check_well_formed_result(self, result: Dict[str, Any], stream_name: str, realm: Realm) -> None:
        """
        A successful call to get_subscribers returns the list of subscribers in
        the form:

        {"msg": "",
         "result": "success",
         "subscribers": [self.example_email("hamlet"), self.example_email("prospero")]}
        """
        self.assertIn("subscribers", result)
        self.assertIsInstance(result["subscribers"], list)
        true_subscribers = [user_profile.email for user_profile in self.users_subscribed_to_stream(
            stream_name, realm)]
        self.assertEqual(sorted(result["subscribers"]), sorted(true_subscribers))

    def make_subscriber_request(self, stream_id: int, user: Optional[UserProfile]=None) -> HttpResponse:
        if user is None:
            user = self.user_profile
        return self.api_get(user, "/api/v1/streams/%d/members" % (stream_id,))

    def make_successful_subscriber_request(self, stream_name: str) -> None:
        stream_id = get_stream(stream_name, self.user_profile.realm).id
        result = self.make_subscriber_request(stream_id)
        self.assert_json_success(result)
        self.check_well_formed_result(result.json(),
                                      stream_name, self.user_profile.realm)

    def test_subscriber(self) -> None:
        """
        get_subscribers returns the list of subscribers.
        """
        stream_name = gather_subscriptions(self.user_profile)[0][0]['name']
        self.make_successful_subscriber_request(stream_name)

    @slow("common_subscribe_to_streams is slow")
    def test_gather_subscriptions(self) -> None:
        """
        gather_subscriptions returns correct results with only 3 queries

        (We also use this test to verify subscription notifications to
        folks who get subscribed to streams.)
        """
        streams = [f"stream_{i}" for i in range(10)]
        for stream_name in streams:
            self.make_stream(stream_name)

        users_to_subscribe = [
            self.user_profile.id,
            self.example_user("othello").id,
            self.example_user("cordelia").id,
        ]
        ret = self.common_subscribe_to_streams(
            self.user_profile,
            streams,
            dict(principals=ujson.dumps(users_to_subscribe)))

        self.assert_json_success(ret)

        msg = '''
            @**King Hamlet** subscribed you to the following streams:

            * #**stream_0**
            * #**stream_1**
            * #**stream_2**
            * #**stream_3**
            * #**stream_4**
            * #**stream_5**
            * #**stream_6**
            * #**stream_7**
            * #**stream_8**
            * #**stream_9**
            '''

        self.assert_user_got_subscription_notification(msg)

        # Subscribe ourself first.
        ret = self.common_subscribe_to_streams(
            self.user_profile,
            ["stream_invite_only_1"],
            dict(principals=ujson.dumps([self.user_profile.id])),
            invite_only=True)
        self.assert_json_success(ret)

        # Now add in other users, and this should trigger messages
        # to notify the user.
        ret = self.common_subscribe_to_streams(
            self.user_profile,
            ["stream_invite_only_1"],
            dict(principals=ujson.dumps(users_to_subscribe)),
            invite_only=True)
        self.assert_json_success(ret)

        msg = '''
            @**King Hamlet** subscribed you to the stream #**stream_invite_only_1**.
            '''
        self.assert_user_got_subscription_notification(msg)

        with queries_captured() as queries:
            subscribed_streams, _ = gather_subscriptions(
                self.user_profile, include_subscribers=True)
        self.assertTrue(len(subscribed_streams) >= 11)
        for sub in subscribed_streams:
            if not sub["name"].startswith("stream_"):
                continue
            self.assertTrue(len(sub["subscribers"]) == len(users_to_subscribe))
        self.assert_length(queries, 6)

    @slow("common_subscribe_to_streams is slow")
    def test_never_subscribed_streams(self) -> None:
        """
        Check never_subscribed streams are fetched correctly and not include invite_only streams.
        """
        realm = get_realm("zulip")
        users_to_subscribe = [
            self.example_user("othello").id,
            self.example_user("cordelia").id,
        ]

        public_streams = [
            'test_stream_public_1',
            'test_stream_public_2',
            'test_stream_public_3',
            'test_stream_public_4',
            'test_stream_public_5',
        ]

        private_streams = [
            'test_stream_invite_only_1',
            'test_stream_invite_only_2',
        ]

        def create_public_streams() -> None:
            for stream_name in public_streams:
                self.make_stream(stream_name, realm=realm)

            ret = self.common_subscribe_to_streams(
                self.user_profile,
                public_streams,
                dict(principals=ujson.dumps(users_to_subscribe)),
            )
            self.assert_json_success(ret)

        create_public_streams()

        def create_private_streams() -> None:
            ret = self.common_subscribe_to_streams(
                self.user_profile,
                private_streams,
                dict(principals=ujson.dumps(users_to_subscribe)),
                invite_only=True,
            )
            self.assert_json_success(ret)

        create_private_streams()

        def get_never_subscribed() -> List[Dict[str, Any]]:
            with queries_captured() as queries:
                sub_data = gather_subscriptions_helper(self.user_profile)
            never_subscribed = sub_data[2]
            self.assert_length(queries, 5)

            # Ignore old streams.
            never_subscribed = [
                dct for dct in never_subscribed
                if dct['name'].startswith('test_')
            ]
            return never_subscribed

        never_subscribed = get_never_subscribed()

        # Invite only stream should not be there in never_subscribed streams
        self.assertEqual(len(never_subscribed), len(public_streams))
        for stream_dict in never_subscribed:
            name = stream_dict['name']
            self.assertFalse('invite_only' in name)
            self.assertTrue(len(stream_dict["subscribers"]) == len(users_to_subscribe))

        # Send private stream subscribers to all realm admins.
        def test_admin_case() -> None:
            self.user_profile.role = UserProfile.ROLE_REALM_ADMINISTRATOR
            # Test realm admins can get never subscribed private stream's subscribers.
            never_subscribed = get_never_subscribed()

            self.assertEqual(
                len(never_subscribed),
                len(public_streams) + len(private_streams),
            )
            for stream_dict in never_subscribed:
                self.assertTrue(len(stream_dict["subscribers"]) == len(users_to_subscribe))

        test_admin_case()

    def test_gather_subscribed_streams_for_guest_user(self) -> None:
        guest_user = self.example_user("polonius")

        stream_name_sub = "public_stream_1"
        self.make_stream(stream_name_sub, realm=get_realm("zulip"))
        self.subscribe(guest_user, stream_name_sub)

        stream_name_unsub = "public_stream_2"
        self.make_stream(stream_name_unsub, realm=get_realm("zulip"))
        self.subscribe(guest_user, stream_name_unsub)
        self.unsubscribe(guest_user, stream_name_unsub)

        stream_name_never_sub = "public_stream_3"
        self.make_stream(stream_name_never_sub, realm=get_realm("zulip"))

        normal_user = self.example_user("aaron")
        self.subscribe(normal_user, stream_name_sub)
        self.subscribe(normal_user, stream_name_unsub)
        self.subscribe(normal_user, stream_name_unsub)

        subs, unsubs, neversubs = gather_subscriptions_helper(guest_user)

        # Guest users get info about subscribed public stream's subscribers
        expected_stream_exists = False
        for sub in subs:
            if sub["name"] == stream_name_sub:
                expected_stream_exists = True
                self.assertEqual(len(sub["subscribers"]), 2)
        self.assertTrue(expected_stream_exists)

        # Guest users don't get info about unsubscribed public stream's subscribers
        expected_stream_exists = False
        for unsub in unsubs:
            if unsub["name"] == stream_name_unsub:
                expected_stream_exists = True
                self.assertNotIn("subscribers", unsub)
        self.assertTrue(expected_stream_exists)

        # Guest user don't get data about never subscribed public stream's data
        self.assertEqual(len(neversubs), 0)

    def test_previously_subscribed_private_streams(self) -> None:
        admin_user = self.example_user("iago")
        non_admin_user = self.example_user("cordelia")
        stream_name = "private_stream"

        self.make_stream(stream_name, realm=get_realm("zulip"), invite_only=True)
        self.subscribe(admin_user, stream_name)
        self.subscribe(non_admin_user, stream_name)
        self.subscribe(self.example_user("othello"), stream_name)

        self.unsubscribe(admin_user, stream_name)
        self.unsubscribe(non_admin_user, stream_name)

        # Test admin user gets previously subscribed private stream's subscribers.
        sub_data = gather_subscriptions_helper(admin_user)
        unsubscribed_streams = sub_data[1]
        self.assertEqual(len(unsubscribed_streams), 1)
        self.assertEqual(len(unsubscribed_streams[0]["subscribers"]), 1)

        # Test non admin users cannot get previously subscribed private stream's subscribers.
        sub_data = gather_subscriptions_helper(non_admin_user)
        unsubscribed_streams = sub_data[1]
        self.assertEqual(len(unsubscribed_streams), 1)
        self.assertFalse('subscribers' in unsubscribed_streams[0])

    def test_gather_subscriptions_mit(self) -> None:
        """
        gather_subscriptions returns correct results with only 3 queries
        """
        # Subscribe only ourself because invites are disabled on mit.edu
        mit_user_profile = self.mit_user('starnine')
        user_id = mit_user_profile.id
        users_to_subscribe = [user_id, self.mit_user("espuser").id]
        for email in users_to_subscribe:
            stream = self.subscribe(mit_user_profile, "mit_stream")
            self.assertTrue(stream.is_in_zephyr_realm)

        ret = self.common_subscribe_to_streams(
            mit_user_profile,
            ["mit_invite_only"],
            dict(principals=ujson.dumps(users_to_subscribe)),
            invite_only=True,
            subdomain="zephyr")
        self.assert_json_success(ret)

        with queries_captured() as queries:
            subscribed_streams, _ = gather_subscriptions(
                mit_user_profile, include_subscribers=True)

        self.assertTrue(len(subscribed_streams) >= 2)
        for sub in subscribed_streams:
            if not sub["name"].startswith("mit_"):
                raise AssertionError("Unexpected stream!")
            if sub["name"] == "mit_invite_only":
                self.assertTrue(len(sub["subscribers"]) == len(users_to_subscribe))
            else:
                self.assertTrue(len(sub["subscribers"]) == 0)
        self.assert_length(queries, 6)

    def test_nonsubscriber(self) -> None:
        """
        Even a non-subscriber to a public stream can query a stream's membership
        with get_subscribers.
        """
        # Create a stream for which Hamlet is the only subscriber.
        stream_name = "Saxony"
        self.common_subscribe_to_streams(self.user_profile, [stream_name])
        other_user = self.example_user("othello")

        # Fetch the subscriber list as a non-member.
        self.login_user(other_user)
        self.make_successful_subscriber_request(stream_name)

    def test_subscriber_private_stream(self) -> None:
        """
        A subscriber to a private stream can query that stream's membership.
        """
        stream_name = "Saxony"
        self.common_subscribe_to_streams(self.user_profile, [stream_name],
                                         invite_only=True)
        self.make_successful_subscriber_request(stream_name)

        stream_id = get_stream(stream_name, self.user_profile.realm).id
        # Verify another user can't get the data.
        self.login('cordelia')
        result = self.client_get("/json/streams/%d/members" % (stream_id,))
        self.assert_json_error(result, 'Invalid stream id')

        # But an organization administrator can
        self.login('iago')
        result = self.client_get("/json/streams/%d/members" % (stream_id,))
        self.assert_json_success(result)

    def test_json_get_subscribers_stream_not_exist(self) -> None:
        """
        json_get_subscribers also returns the list of subscribers for a stream.
        """
        stream_id = 99999999
        result = self.client_get("/json/streams/%d/members" % (stream_id,))
        self.assert_json_error(result, 'Invalid stream id')

    def test_json_get_subscribers(self) -> None:
        """
        json_get_subscribers in zerver/views/streams.py
        also returns the list of subscribers for a stream, when requested.
        """
        stream_name = gather_subscriptions(self.user_profile)[0][0]['name']
        stream_id = get_stream(stream_name, self.user_profile.realm).id
        expected_subscribers = gather_subscriptions(
            self.user_profile, include_subscribers=True)[0][0]['subscribers']
        result = self.client_get("/json/streams/%d/members" % (stream_id,))
        self.assert_json_success(result)
        result_dict = result.json()
        self.assertIn('subscribers', result_dict)
        self.assertIsInstance(result_dict['subscribers'], list)
        subscribers: List[str] = []
        for subscriber in result_dict['subscribers']:
            self.assertIsInstance(subscriber, str)
            subscribers.append(subscriber)
        self.assertEqual(set(subscribers), set(expected_subscribers))

    def test_nonsubscriber_private_stream(self) -> None:
        """
        A non-subscriber non realm admin user to a private stream can't query that stream's membership.
        But unsubscribed realm admin users can query private stream's membership.
        """
        # Create a private stream for which Hamlet is the only subscriber.
        stream_name = "NewStream"
        self.common_subscribe_to_streams(self.user_profile, [stream_name],
                                         invite_only=True)
        user_profile = self.example_user('othello')

        # Try to fetch the subscriber list as a non-member & non-realm-admin-user.
        stream_id = get_stream(stream_name, user_profile.realm).id
        result = self.make_subscriber_request(stream_id, user=user_profile)
        self.assert_json_error(result, "Invalid stream id")

        # Try to fetch the subscriber list as a non-member & realm-admin-user.
        self.login('iago')
        self.make_successful_subscriber_request(stream_name)

class AccessStreamTest(ZulipTestCase):
    def test_access_stream(self) -> None:
        """
        A comprehensive security test for the access_stream_by_* API functions.
        """
        # Create a private stream for which Hamlet is the only subscriber.
        hamlet = self.example_user('hamlet')

        stream_name = "new_private_stream"
        self.login_user(hamlet)
        self.common_subscribe_to_streams(hamlet, [stream_name],
                                         invite_only=True)
        stream = get_stream(stream_name, hamlet.realm)

        othello = self.example_user('othello')

        # Nobody can access a stream that doesn't exist
        with self.assertRaisesRegex(JsonableError, "Invalid stream id"):
            access_stream_by_id(hamlet, 501232)
        with self.assertRaisesRegex(JsonableError, "Invalid stream name 'invalid stream'"):
            access_stream_by_name(hamlet, "invalid stream")

        # Hamlet can access the private stream
        (stream_ret, rec_ret, sub_ret) = access_stream_by_id(hamlet, stream.id)
        self.assertEqual(stream.id, stream_ret.id)
        assert sub_ret is not None
        self.assertEqual(sub_ret.recipient, rec_ret)
        self.assertEqual(sub_ret.recipient.type_id, stream.id)
        (stream_ret2, rec_ret2, sub_ret2) = access_stream_by_name(hamlet, stream.name)
        self.assertEqual(stream_ret.id, stream_ret2.id)
        self.assertEqual(sub_ret, sub_ret2)
        self.assertEqual(rec_ret, rec_ret2)

        # Othello cannot access the private stream
        with self.assertRaisesRegex(JsonableError, "Invalid stream id"):
            access_stream_by_id(othello, stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid stream name 'new_private_stream'"):
            access_stream_by_name(othello, stream.name)

        # Both Othello and Hamlet can access a public stream that only
        # Hamlet is subscribed to in this realm
        public_stream_name = "public_stream"
        self.common_subscribe_to_streams(hamlet, [public_stream_name],
                                         invite_only=False)
        public_stream = get_stream(public_stream_name, hamlet.realm)
        access_stream_by_id(othello, public_stream.id)
        access_stream_by_name(othello, public_stream.name)
        access_stream_by_id(hamlet, public_stream.id)
        access_stream_by_name(hamlet, public_stream.name)

        # Nobody can access a public stream in another realm
        mit_realm = get_realm("zephyr")
        mit_stream = ensure_stream(mit_realm, "mit_stream", invite_only=False)
        sipbtest = self.mit_user("sipbtest")
        with self.assertRaisesRegex(JsonableError, "Invalid stream id"):
            access_stream_by_id(hamlet, mit_stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid stream name 'mit_stream'"):
            access_stream_by_name(hamlet, mit_stream.name)
        with self.assertRaisesRegex(JsonableError, "Invalid stream id"):
            access_stream_by_id(sipbtest, stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid stream name 'new_private_stream'"):
            access_stream_by_name(sipbtest, stream.name)

        # MIT realm users cannot access even public streams in their realm
        with self.assertRaisesRegex(JsonableError, "Invalid stream id"):
            access_stream_by_id(sipbtest, mit_stream.id)
        with self.assertRaisesRegex(JsonableError, "Invalid stream name 'mit_stream'"):
            access_stream_by_name(sipbtest, mit_stream.name)

        # But they can access streams they are subscribed to
        self.common_subscribe_to_streams(sipbtest, [mit_stream.name], subdomain="zephyr")
        access_stream_by_id(sipbtest, mit_stream.id)
        access_stream_by_name(sipbtest, mit_stream.name)

    def test_stream_access_by_guest(self) -> None:
        guest_user_profile = self.example_user('polonius')
        self.login_user(guest_user_profile)
        stream_name = "public_stream_1"
        stream = self.make_stream(stream_name, guest_user_profile.realm, invite_only=False)

        # Guest user don't have access to unsubscribed public streams
        with self.assertRaisesRegex(JsonableError, "Invalid stream id"):
            access_stream_by_id(guest_user_profile, stream.id)

        # Guest user have access to subscribed public streams
        self.subscribe(guest_user_profile, stream_name)
        (stream_ret, rec_ret, sub_ret) = access_stream_by_id(guest_user_profile, stream.id)
        assert sub_ret is not None
        self.assertEqual(stream.id, stream_ret.id)
        self.assertEqual(sub_ret.recipient, rec_ret)
        self.assertEqual(sub_ret.recipient.type_id, stream.id)

        stream_name = "private_stream_1"
        stream = self.make_stream(stream_name, guest_user_profile.realm, invite_only=True)
        # Obviously, a guest user doesn't have access to unsubscribed private streams either
        with self.assertRaisesRegex(JsonableError, "Invalid stream id"):
            access_stream_by_id(guest_user_profile, stream.id)

        # Guest user have access to subscribed private streams
        self.subscribe(guest_user_profile, stream_name)
        (stream_ret, rec_ret, sub_ret) = access_stream_by_id(guest_user_profile, stream.id)
        assert sub_ret is not None
        self.assertEqual(stream.id, stream_ret.id)
        self.assertEqual(sub_ret.recipient, rec_ret)
        self.assertEqual(sub_ret.recipient.type_id, stream.id)

class StreamTrafficTest(ZulipTestCase):
    def test_average_weekly_stream_traffic_calculation(self) -> None:
        # No traffic data for the stream
        self.assertEqual(
            get_average_weekly_stream_traffic(42, timezone_now() - timedelta(days=300), {1: 4003}), 0)

        # using high numbers here to make it more likely to catch small errors in the denominators
        # of the calculations. That being said we don't want to go over 100, since then the 2
        # significant digits calculation gets applied
        # old stream
        self.assertEqual(
            get_average_weekly_stream_traffic(42, timezone_now() - timedelta(days=300), {42: 98*4+3}), 98)
        # stream between 7 and 27 days old
        self.assertEqual(
            get_average_weekly_stream_traffic(42, timezone_now() - timedelta(days=10), {42: (98*10+9) // 7}), 98)
        # stream less than 7 days old
        self.assertEqual(
            get_average_weekly_stream_traffic(42, timezone_now() - timedelta(days=5), {42: 100}), None)

        # average traffic between 0 and 1
        self.assertEqual(
            get_average_weekly_stream_traffic(42, timezone_now() - timedelta(days=300), {42: 1}), 1)

    def test_round_to_2_significant_digits(self) -> None:
        self.assertEqual(120, round_to_2_significant_digits(116))
