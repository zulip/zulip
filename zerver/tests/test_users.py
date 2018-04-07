# -*- coding: utf-8 -*-

from typing import (Any, Dict, Iterable, List, Mapping,
                    Optional, TypeVar, Text, Union)

from django.http import HttpResponse
from django.test import TestCase

from zerver.lib.test_helpers import (
    queries_captured, simulated_empty_cache,
    tornado_redirected_to_list, get_subscription,
    most_recent_message, make_client, avatar_disk_path,
    get_test_image_file
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.test_runner import slow

from zerver.models import UserProfile, Recipient, \
    Realm, RealmDomain, UserActivity, \
    get_user, get_realm, get_client, get_stream, get_stream_recipient, \
    Message, get_context_for_message, ScheduledEmail

from zerver.lib.avatar import avatar_url
from zerver.lib.email_mirror import create_missed_message_address
from zerver.lib.exceptions import JsonableError
from zerver.lib.send_email import send_future_email
from zerver.lib.actions import (
    get_emails_from_user_ids,
    get_recipient_info,
    do_deactivate_user,
    do_reactivate_user,
    do_change_is_admin,
    do_create_user,
)
from zerver.lib.topic_mutes import add_topic_mute
from zerver.lib.stream_topic import StreamTopicTarget
from zerver.lib.users import user_ids_to_users

from django.conf import settings

import datetime
import mock
import os
import sys
import time
import ujson

K = TypeVar('K')
V = TypeVar('V')
def find_dict(lst: Iterable[Dict[K, V]], k: K, v: V) -> Dict[K, V]:
    for dct in lst:
        if dct[k] == v:
            return dct
    raise AssertionError('Cannot find element in list where key %s == %s' % (k, v))

class PermissionTest(ZulipTestCase):
    def test_get_admin_users(self) -> None:
        user_profile = self.example_user('hamlet')
        do_change_is_admin(user_profile, False)
        admin_users = user_profile.realm.get_admin_users()
        self.assertFalse(user_profile in admin_users)
        do_change_is_admin(user_profile, True)
        admin_users = user_profile.realm.get_admin_users()
        self.assertTrue(user_profile in admin_users)

    def test_updating_non_existent_user(self) -> None:
        self.login(self.example_email("hamlet"))
        admin = self.example_user('hamlet')
        do_change_is_admin(admin, True)

        result = self.client_patch('/json/users/nonexistentuser@zulip.com', {})
        self.assert_json_error(result, 'No such user')

    def test_admin_api(self) -> None:
        self.login(self.example_email("hamlet"))
        admin = self.example_user('hamlet')
        user = self.example_user('othello')
        realm = admin.realm
        do_change_is_admin(admin, True)

        # Make sure we see is_admin flag in /json/users
        result = self.client_get('/json/users')
        self.assert_json_success(result)
        members = result.json()['members']
        hamlet = find_dict(members, 'email', self.example_email("hamlet"))
        self.assertTrue(hamlet['is_admin'])
        othello = find_dict(members, 'email', self.example_email("othello"))
        self.assertFalse(othello['is_admin'])

        # Giveth
        req = dict(is_admin=ujson.dumps(True))

        events = []  # type: List[Mapping[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/users/othello@zulip.com', req)
        self.assert_json_success(result)
        admin_users = realm.get_admin_users()
        self.assertTrue(user in admin_users)
        person = events[0]['event']['person']
        self.assertEqual(person['email'], self.example_email("othello"))
        self.assertEqual(person['is_admin'], True)

        # Taketh away
        req = dict(is_admin=ujson.dumps(False))
        events = []
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/users/othello@zulip.com', req)
        self.assert_json_success(result)
        admin_users = realm.get_admin_users()
        self.assertFalse(user in admin_users)
        person = events[0]['event']['person']
        self.assertEqual(person['email'], self.example_email("othello"))
        self.assertEqual(person['is_admin'], False)

        # Cannot take away from last admin
        self.login(self.example_email("iago"))
        req = dict(is_admin=ujson.dumps(False))
        events = []
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_success(result)
        admin_users = realm.get_admin_users()
        self.assertFalse(admin in admin_users)
        person = events[0]['event']['person']
        self.assertEqual(person['email'], self.example_email("hamlet"))
        self.assertEqual(person['is_admin'], False)
        with tornado_redirected_to_list([]):
            result = self.client_patch('/json/users/iago@zulip.com', req)
        self.assert_json_error(result, 'Cannot remove the only organization administrator')

        # Make sure only admins can patch other user's info.
        self.login(self.example_email("othello"))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_error(result, 'Insufficient permission')

    def test_user_cannot_promote_to_admin(self) -> None:
        self.login(self.example_email("hamlet"))
        req = dict(is_admin=ujson.dumps(True))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_error(result, 'Insufficient permission')

    def test_admin_user_can_change_full_name(self) -> None:
        new_name = 'new name'
        self.login(self.example_email("iago"))
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assertTrue(result.status_code == 200)
        hamlet = self.example_user('hamlet')
        self.assertEqual(hamlet.full_name, new_name)

    def test_non_admin_cannot_change_full_name(self) -> None:
        self.login(self.example_email("hamlet"))
        req = dict(full_name=ujson.dumps('new name'))
        result = self.client_patch('/json/users/othello@zulip.com', req)
        self.assert_json_error(result, 'Insufficient permission')

    def test_admin_cannot_set_long_full_name(self) -> None:
        new_name = 'a' * (UserProfile.MAX_NAME_LENGTH + 1)
        self.login(self.example_email("iago"))
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_error(result, 'Name too long!')

    def test_admin_cannot_set_short_full_name(self) -> None:
        new_name = 'a'
        self.login(self.example_email("iago"))
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_error(result, 'Name too short!')

    def test_admin_cannot_set_full_name_with_invalid_characters(self) -> None:
        new_name = 'Opheli*'
        self.login(self.example_email("iago"))
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_error(result, 'Invalid characters in name!')

class AdminCreateUserTest(ZulipTestCase):
    def test_create_user_backend(self) -> None:

        # This test should give us complete coverage on
        # create_user_backend.  It mostly exercises error
        # conditions, and it also does a basic test of the success
        # path.

        admin = self.example_user('hamlet')
        admin_email = admin.email
        realm = admin.realm
        self.login(admin_email)
        do_change_is_admin(admin, True)

        result = self.client_post("/json/users", dict())
        self.assert_json_error(result, "Missing 'email' argument")

        result = self.client_post("/json/users", dict(
            email='romeo@not-zulip.com',
        ))
        self.assert_json_error(result, "Missing 'password' argument")

        result = self.client_post("/json/users", dict(
            email='romeo@not-zulip.com',
            password='xxxx',
        ))
        self.assert_json_error(result, "Missing 'full_name' argument")

        result = self.client_post("/json/users", dict(
            email='romeo@not-zulip.com',
            password='xxxx',
            full_name='Romeo Montague',
        ))
        self.assert_json_error(result, "Missing 'short_name' argument")

        result = self.client_post("/json/users", dict(
            email='broken',
            password='xxxx',
            full_name='Romeo Montague',
            short_name='Romeo',
        ))
        self.assert_json_error(result, "Bad name or username")

        result = self.client_post("/json/users", dict(
            email='romeo@not-zulip.com',
            password='xxxx',
            full_name='Romeo Montague',
            short_name='Romeo',
        ))
        self.assert_json_error(result,
                               "Email 'romeo@not-zulip.com' not allowed in this organization")

        RealmDomain.objects.create(realm=get_realm('zulip'), domain='zulip.net')
        valid_params = dict(
            email='romeo@zulip.net',
            password='xxxx',
            full_name='Romeo Montague',
            short_name='Romeo',
        )
        result = self.client_post("/json/users", valid_params)
        self.assert_json_success(result)

        # Romeo is a newly registered user
        new_user = get_user('romeo@zulip.net', get_realm('zulip'))
        self.assertEqual(new_user.full_name, 'Romeo Montague')
        self.assertEqual(new_user.short_name, 'Romeo')

        # we can't create the same user twice.
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result,
                               "Email 'romeo@zulip.net' already in use")

        # Don't allow user to sign up with disposable email.
        realm.restricted_to_domain = False
        realm.disallow_disposable_email_addresses = True
        realm.save()

        valid_params["email"] = "abc@mailnator.com"
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result, "Disposable email addresses are not allowed in this organization")

class UserProfileTest(ZulipTestCase):
    def test_get_emails_from_user_ids(self) -> None:
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        dct = get_emails_from_user_ids([hamlet.id, othello.id])
        self.assertEqual(dct[hamlet.id], self.example_email("hamlet"))
        self.assertEqual(dct[othello.id], self.example_email("othello"))

    def test_cache_invalidation(self) -> None:
        hamlet = self.example_user('hamlet')
        with mock.patch('zerver.lib.cache.delete_display_recipient_cache') as m:
            hamlet.full_name = 'Hamlet Junior'
            hamlet.save(update_fields=["full_name"])

        self.assertTrue(m.called)

        with mock.patch('zerver.lib.cache.delete_display_recipient_cache') as m:
            hamlet.long_term_idle = True
            hamlet.save(update_fields=["long_term_idle"])

        self.assertFalse(m.called)

    def test_user_ids_to_users(self) -> None:
        real_user_ids = [
            self.example_user('hamlet').id,
            self.example_user('cordelia').id,
        ]

        self.assertEqual(user_ids_to_users([], get_realm("zulip")), [])
        self.assertEqual(set([user_profile.id for user_profile in user_ids_to_users(real_user_ids, get_realm("zulip"))]),
                         set(real_user_ids))
        with self.assertRaises(JsonableError):
            user_ids_to_users([1234], get_realm("zephyr"))
        with self.assertRaises(JsonableError):
            user_ids_to_users(real_user_ids, get_realm("zephyr"))

    def test_bulk_get_users(self) -> None:
        from zerver.lib.users import bulk_get_users
        hamlet = self.example_email("hamlet")
        cordelia = self.example_email("cordelia")
        webhook_bot = self.example_email("webhook_bot")
        result = bulk_get_users([hamlet, cordelia], get_realm("zulip"))
        self.assertEqual(result[hamlet].email, hamlet)
        self.assertEqual(result[cordelia].email, cordelia)

        result = bulk_get_users([hamlet, cordelia, webhook_bot], None,
                                base_query=UserProfile.objects.all())
        self.assertEqual(result[hamlet].email, hamlet)
        self.assertEqual(result[cordelia].email, cordelia)
        self.assertEqual(result[webhook_bot].email, webhook_bot)

class ActivateTest(ZulipTestCase):
    def test_basics(self) -> None:
        user = self.example_user('hamlet')
        do_deactivate_user(user)
        self.assertFalse(user.is_active)
        do_reactivate_user(user)
        self.assertTrue(user.is_active)

    def test_api(self) -> None:
        admin = self.example_user('othello')
        do_change_is_admin(admin, True)
        self.login(self.example_email("othello"))

        user = self.example_user('hamlet')
        self.assertTrue(user.is_active)

        result = self.client_delete('/json/users/hamlet@zulip.com')
        self.assert_json_success(result)
        user = self.example_user('hamlet')
        self.assertFalse(user.is_active)

        result = self.client_post('/json/users/hamlet@zulip.com/reactivate')
        self.assert_json_success(result)
        user = self.example_user('hamlet')
        self.assertTrue(user.is_active)

    def test_api_me_user(self) -> None:
        """This test helps ensure that our URL patterns for /users/me URLs
        handle email addresses starting with "me" correctly."""
        self.register(self.nonreg_email('me'), "testpassword")
        self.login(self.example_email("iago"))

        result = self.client_delete('/json/users/me@zulip.com')
        self.assert_json_success(result)
        user = self.nonreg_user('me')
        self.assertFalse(user.is_active)

        result = self.client_post('/json/users/{email}/reactivate'.format(email=self.nonreg_email('me')))
        self.assert_json_success(result)
        user = self.nonreg_user('me')
        self.assertTrue(user.is_active)

    def test_api_with_nonexistent_user(self) -> None:
        admin = self.example_user('othello')
        do_change_is_admin(admin, True)
        self.login(self.example_email("othello"))

        # Cannot deactivate a user with the bot api
        result = self.client_delete('/json/bots/hamlet@zulip.com')
        self.assert_json_error(result, 'No such bot')

        # Cannot deactivate a nonexistent user.
        result = self.client_delete('/json/users/nonexistent@zulip.com')
        self.assert_json_error(result, 'No such user')

        result = self.client_delete('/json/users/iago@zulip.com')
        self.assert_json_success(result)

        result = self.client_delete('/json/users/othello@zulip.com')
        self.assert_json_error(result, 'Cannot deactivate the only organization administrator')

        # Cannot reactivate a nonexistent user.
        result = self.client_post('/json/users/nonexistent@zulip.com/reactivate')
        self.assert_json_error(result, 'No such user')

    def test_api_with_insufficient_permissions(self) -> None:
        non_admin = self.example_user('othello')
        do_change_is_admin(non_admin, False)
        self.login(self.example_email("othello"))

        # Cannot deactivate a user with the users api
        result = self.client_delete('/json/users/hamlet@zulip.com')
        self.assert_json_error(result, 'Insufficient permission')

        # Cannot reactivate a user
        result = self.client_post('/json/users/hamlet@zulip.com/reactivate')
        self.assert_json_error(result, 'Insufficient permission')

    def test_clear_scheduled_jobs(self) -> None:
        user = self.example_user('hamlet')
        send_future_email('zerver/emails/followup_day1', user.realm,
                          to_user_id=user.id, delay=datetime.timedelta(hours=1))
        self.assertEqual(ScheduledEmail.objects.count(), 1)
        do_deactivate_user(user)
        self.assertEqual(ScheduledEmail.objects.count(), 0)

class RecipientInfoTest(ZulipTestCase):
    def test_stream_recipient_info(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        othello = self.example_user('othello')

        realm = hamlet.realm

        stream_name = 'Test Stream'
        topic_name = 'test topic'

        for user in [hamlet, cordelia, othello]:
            self.subscribe(user, stream_name)

        stream = get_stream(stream_name, realm)
        recipient = get_stream_recipient(stream.id)

        stream_topic = StreamTopicTarget(
            stream_id=stream.id,
            topic_name=topic_name,
        )

        sub = get_subscription(stream_name, hamlet)
        sub.push_notifications = True
        sub.save()

        info = get_recipient_info(
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
        )

        all_user_ids = {hamlet.id, cordelia.id, othello.id}

        expected_info = dict(
            active_user_ids=all_user_ids,
            push_notify_user_ids=set(),
            stream_push_user_ids={hamlet.id},
            um_eligible_user_ids=all_user_ids,
            long_term_idle_user_ids=set(),
            default_bot_user_ids=set(),
            service_bot_tuples=[],
        )

        self.assertEqual(info, expected_info)

        # Now mute Hamlet to omit him from stream_push_user_ids.
        add_topic_mute(
            user_profile=hamlet,
            stream_id=stream.id,
            recipient_id=recipient.id,
            topic_name=topic_name,
        )

        info = get_recipient_info(
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
        )

        self.assertEqual(info['stream_push_user_ids'], set())

        # Add a service bot.
        service_bot = do_create_user(
            email='service-bot@zulip.com',
            password='',
            realm=realm,
            full_name='',
            short_name='',
            bot_type=UserProfile.EMBEDDED_BOT,
        )

        info = get_recipient_info(
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possibly_mentioned_user_ids={service_bot.id}
        )
        self.assertEqual(info['service_bot_tuples'], [
            (service_bot.id, UserProfile.EMBEDDED_BOT),
        ])

        # Add a normal bot.
        normal_bot = do_create_user(
            email='normal-bot@zulip.com',
            password='',
            realm=realm,
            full_name='',
            short_name='',
            bot_type=UserProfile.DEFAULT_BOT,
        )

        info = get_recipient_info(
            recipient=recipient,
            sender_id=hamlet.id,
            stream_topic=stream_topic,
            possibly_mentioned_user_ids={service_bot.id, normal_bot.id}
        )
        self.assertEqual(info['default_bot_user_ids'], {normal_bot.id})

class BulkUsersTest(ZulipTestCase):
    def test_client_gravatar_option(self) -> None:
        self.login(self.example_email('cordelia'))

        hamlet = self.example_user('hamlet')

        def get_hamlet_avatar(client_gravatar: bool) -> Optional[Text]:
            data = dict(client_gravatar=ujson.dumps(client_gravatar))
            result = self.client_get('/json/users', data)
            self.assert_json_success(result)
            rows = result.json()['members']
            hamlet_data = [
                row for row in rows
                if row['user_id'] == hamlet.id
            ][0]
            return hamlet_data['avatar_url']

        self.assertEqual(
            get_hamlet_avatar(client_gravatar=True),
            None
        )

        '''
        The main purpose of this test is to make sure we
        return None for avatar_url when client_gravatar is
        set to True.  And we do a sanity check for when it's
        False, but we leave it to other tests to validate
        the specific URL.
        '''
        self.assertIn(
            'gravatar.com',
            get_hamlet_avatar(client_gravatar=False),
        )

class GetProfileTest(ZulipTestCase):

    def common_update_pointer(self, email: Text, pointer: int) -> None:
        self.login(email)
        result = self.client_post("/json/users/me/pointer", {"pointer": pointer})
        self.assert_json_success(result)

    def common_get_profile(self, user_id: str) -> Dict[Text, Any]:
        # Assumes all users are example users in realm 'zulip'
        user_profile = self.example_user(user_id)
        self.send_stream_message(user_profile.email, "Verona", "hello")

        result = self.api_get(user_profile.email, "/api/v1/users/me")

        max_id = most_recent_message(user_profile).id

        self.assert_json_success(result)
        json = result.json()

        self.assertIn("client_id", json)
        self.assertIn("max_message_id", json)
        self.assertIn("pointer", json)

        self.assertEqual(json["max_message_id"], max_id)
        return json

    def test_get_pointer(self) -> None:
        email = self.example_email("hamlet")
        self.login(email)
        result = self.client_get("/json/users/me/pointer")
        self.assert_json_success(result)
        self.assertIn("pointer", result.json())

    def test_cache_behavior(self) -> None:
        """Tests whether fetching a user object the normal way, with
        `get_user`, makes 1 cache query and 1 database query.
        """
        realm = get_realm("zulip")
        email = self.example_email("hamlet")
        with queries_captured() as queries:
            with simulated_empty_cache() as cache_queries:
                user_profile = get_user(email, realm)

        self.assert_length(queries, 1)
        self.assert_length(cache_queries, 1)
        self.assertEqual(user_profile.email, email)

    def test_get_user_profile(self) -> None:
        self.login(self.example_email("hamlet"))
        result = ujson.loads(self.client_get('/json/users/me').content)
        self.assertEqual(result['short_name'], 'hamlet')
        self.assertEqual(result['email'], self.example_email("hamlet"))
        self.assertEqual(result['full_name'], 'King Hamlet')
        self.assertIn("user_id", result)
        self.assertFalse(result['is_bot'])
        self.assertFalse(result['is_admin'])
        self.login(self.example_email("iago"))
        result = ujson.loads(self.client_get('/json/users/me').content)
        self.assertEqual(result['short_name'], 'iago')
        self.assertEqual(result['email'], self.example_email("iago"))
        self.assertEqual(result['full_name'], 'Iago')
        self.assertFalse(result['is_bot'])
        self.assertTrue(result['is_admin'])

    def test_api_get_empty_profile(self) -> None:
        """
        Ensure GET /users/me returns a max message id and returns successfully
        """
        json = self.common_get_profile("othello")
        self.assertEqual(json["pointer"], -1)

    def test_profile_with_pointer(self) -> None:
        """
        Ensure GET /users/me returns a proper pointer id after the pointer is updated
        """

        id1 = self.send_stream_message(self.example_email("othello"), "Verona")
        id2 = self.send_stream_message(self.example_email("othello"), "Verona")

        json = self.common_get_profile("hamlet")

        self.common_update_pointer(self.example_email("hamlet"), id2)
        json = self.common_get_profile("hamlet")
        self.assertEqual(json["pointer"], id2)

        self.common_update_pointer(self.example_email("hamlet"), id1)
        json = self.common_get_profile("hamlet")
        self.assertEqual(json["pointer"], id2)  # pointer does not move backwards

        result = self.client_post("/json/users/me/pointer", {"pointer": 99999999})
        self.assert_json_error(result, "Invalid message ID")

    def test_get_all_profiles_avatar_urls(self) -> None:
        user_profile = self.example_user('hamlet')
        result = self.api_get(self.example_email("hamlet"), "/api/v1/users")
        self.assert_json_success(result)

        for user in result.json()['members']:
            if user['email'] == self.example_email("hamlet"):
                self.assertEqual(
                    user['avatar_url'],
                    avatar_url(user_profile),
                )
