# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from typing import (Any, Dict, Iterable, List,
                    Optional, TypeVar, Text, Union)

from django.http import HttpResponse
from django.test import TestCase

from zerver.lib.test_helpers import (
    queries_captured, simulated_empty_cache,
    tornado_redirected_to_list,
    most_recent_message, make_client, avatar_disk_path,
    get_test_image_file
)
from zerver.lib.test_classes import (
    ZulipTestCase,
)
from zerver.lib.test_runner import slow

from zerver.models import UserProfile, Recipient, \
    Realm, RealmDomain, UserActivity, \
    get_user, get_realm, get_client, get_stream, \
    Message, get_context_for_message

from zerver.lib.avatar import avatar_url
from zerver.lib.email_mirror import create_missed_message_address
from zerver.lib.actions import (
    get_emails_from_user_ids,
    do_deactivate_user,
    do_reactivate_user,
    do_change_is_admin,
)

from django.conf import settings
import os
import sys
import time
import ujson

K = TypeVar('K')
V = TypeVar('V')
def find_dict(lst, k, v):
    # type: (Iterable[Dict[K, V]], K, V) -> Dict[K, V]
    for dct in lst:
        if dct[k] == v:
            return dct
    raise AssertionError('Cannot find element in list where key %s == %s' % (k, v))

class PermissionTest(ZulipTestCase):
    def test_get_admin_users(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        do_change_is_admin(user_profile, False)
        admin_users = user_profile.realm.get_admin_users()
        self.assertFalse(user_profile in admin_users)
        do_change_is_admin(user_profile, True)
        admin_users = user_profile.realm.get_admin_users()
        self.assertTrue(user_profile in admin_users)

    def test_updating_non_existent_user(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        admin = self.example_user('hamlet')
        do_change_is_admin(admin, True)

        result = self.client_patch('/json/users/nonexistentuser@zulip.com', {})
        self.assert_json_error(result, 'No such user')

    def test_admin_api(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        admin = self.example_user('hamlet')
        user = self.example_user('othello')
        realm = admin.realm
        do_change_is_admin(admin, True)

        # Make sure we see is_admin flag in /json/users
        result = self.client_get('/json/users')
        self.assert_json_success(result)
        members = ujson.loads(result.content)['members']
        hamlet = find_dict(members, 'email', self.example_email("hamlet"))
        self.assertTrue(hamlet['is_admin'])
        othello = find_dict(members, 'email', self.example_email("othello"))
        self.assertFalse(othello['is_admin'])

        # Giveth
        req = dict(is_admin=ujson.dumps(True))

        events = []  # type: List[Dict[str, Any]]
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

    def test_admin_user_can_change_full_name(self):
        # type: () -> None
        new_name = 'new name'
        self.login(self.example_email("iago"))
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assertTrue(result.status_code == 200)
        hamlet = self.example_user('hamlet')
        self.assertEqual(hamlet.full_name, new_name)

    def test_non_admin_cannot_change_full_name(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        req = dict(full_name=ujson.dumps('new name'))
        result = self.client_patch('/json/users/othello@zulip.com', req)
        self.assert_json_error(result, 'Insufficient permission')

    def test_admin_cannot_set_long_full_name(self):
        # type: () -> None
        new_name = 'a' * (UserProfile.MAX_NAME_LENGTH + 1)
        self.login(self.example_email("iago"))
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_error(result, 'Name too long!')

    def test_admin_cannot_set_short_full_name(self):
        # type: () -> None
        new_name = 'a'
        self.login(self.example_email("iago"))
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_error(result, 'Name too short!')

    def test_admin_cannot_set_full_name_with_invalid_characters(self):
        # type: () -> None
        new_name = 'Opheli*'
        self.login(self.example_email("iago"))
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_error(result, 'Invalid characters in name!')

class AdminCreateUserTest(ZulipTestCase):
    def test_create_user_backend(self):
        # type: () -> None

        # This test should give us complete coverage on
        # create_user_backend.  It mostly exercises error
        # conditions, and it also does a basic test of the success
        # path.

        admin = self.example_user('hamlet')
        admin_email = admin.email
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
                               "Email 'romeo@not-zulip.com' not allowed for realm 'zulip'")

        RealmDomain.objects.create(realm=get_realm('zulip'), domain='zulip.net')

        # HAPPY PATH STARTS HERE
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

        # One more error condition to test--we can't create
        # the same user twice.
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result,
                               "Email 'romeo@zulip.net' already in use")

class UserProfileTest(ZulipTestCase):
    def test_get_emails_from_user_ids(self):
        # type: () -> None
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        dct = get_emails_from_user_ids([hamlet.id, othello.id])
        self.assertEqual(dct[hamlet.id], self.example_email("hamlet"))
        self.assertEqual(dct[othello.id], self.example_email("othello"))

class ActivateTest(ZulipTestCase):
    def test_basics(self):
        # type: () -> None
        user = self.example_user('hamlet')
        do_deactivate_user(user)
        self.assertFalse(user.is_active)
        do_reactivate_user(user)
        self.assertTrue(user.is_active)

    def test_api(self):
        # type: () -> None
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

    def test_api_me_user(self):
        # type: () -> None
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

    def test_api_with_nonexistent_user(self):
        # type: () -> None
        admin = self.example_user('othello')
        do_change_is_admin(admin, True)
        self.login(self.example_email("othello"))

        # Can not deactivate a user with the bot api
        result = self.client_delete('/json/bots/hamlet@zulip.com')
        self.assert_json_error(result, 'No such bot')

        # Can not deactivate a nonexistent user.
        result = self.client_delete('/json/users/nonexistent@zulip.com')
        self.assert_json_error(result, 'No such user')

        result = self.client_delete('/json/users/iago@zulip.com')
        self.assert_json_success(result)

        result = self.client_delete('/json/users/othello@zulip.com')
        self.assert_json_error(result, 'Cannot deactivate the only organization administrator')

        # Can not reactivate a nonexistent user.
        result = self.client_post('/json/users/nonexistent@zulip.com/reactivate')
        self.assert_json_error(result, 'No such user')

    def test_api_with_insufficient_permissions(self):
        # type: () -> None
        non_admin = self.example_user('othello')
        do_change_is_admin(non_admin, False)
        self.login(self.example_email("othello"))

        # Can not deactivate a user with the users api
        result = self.client_delete('/json/users/hamlet@zulip.com')
        self.assert_json_error(result, 'Insufficient permission')

        # Can not reactivate a user
        result = self.client_post('/json/users/hamlet@zulip.com/reactivate')
        self.assert_json_error(result, 'Insufficient permission')

class GetProfileTest(ZulipTestCase):

    def common_update_pointer(self, email, pointer):
        # type: (Text, int) -> None
        self.login(email)
        result = self.client_post("/json/users/me/pointer", {"pointer": pointer})
        self.assert_json_success(result)

    def common_get_profile(self, user_id):
        # type: (str) -> Dict[Text, Any]
        # Assumes all users are example users in realm 'zulip'
        user_profile = self.example_user(user_id)
        self.send_message(user_profile.email, "Verona", Recipient.STREAM, "hello")

        result = self.client_get("/api/v1/users/me", **self.api_auth(user_profile.email))

        max_id = most_recent_message(user_profile).id

        self.assert_json_success(result)
        json = ujson.loads(result.content)

        self.assertIn("client_id", json)
        self.assertIn("max_message_id", json)
        self.assertIn("pointer", json)

        self.assertEqual(json["max_message_id"], max_id)
        return json

    def test_get_pointer(self):
        # type: () -> None
        email = self.example_email("hamlet")
        self.login(email)
        result = self.client_get("/json/users/me/pointer")
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("pointer", json)

    def test_cache_behavior(self):
        # type: () -> None
        with queries_captured() as queries:
            with simulated_empty_cache() as cache_queries:
                user_profile = self.example_user('hamlet')

        self.assert_length(queries, 1)
        self.assert_length(cache_queries, 1)
        self.assertEqual(user_profile.email, self.example_email("hamlet"))

    def test_get_user_profile(self):
        # type: () -> None
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

    def test_api_get_empty_profile(self):
        # type: () -> None
        """
        Ensure GET /users/me returns a max message id and returns successfully
        """
        json = self.common_get_profile("othello")
        self.assertEqual(json["pointer"], -1)

    def test_profile_with_pointer(self):
        # type: () -> None
        """
        Ensure GET /users/me returns a proper pointer id after the pointer is updated
        """

        id1 = self.send_message(self.example_email("othello"), "Verona", Recipient.STREAM)
        id2 = self.send_message(self.example_email("othello"), "Verona", Recipient.STREAM)

        json = self.common_get_profile("hamlet")

        self.common_update_pointer(self.example_email("hamlet"), id2)
        json = self.common_get_profile("hamlet")
        self.assertEqual(json["pointer"], id2)

        self.common_update_pointer(self.example_email("hamlet"), id1)
        json = self.common_get_profile("hamlet")
        self.assertEqual(json["pointer"], id2)  # pointer does not move backwards

        result = self.client_post("/json/users/me/pointer", {"pointer": 99999999})
        self.assert_json_error(result, "Invalid message ID")

    def test_get_all_profiles_avatar_urls(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        result = self.client_get("/api/v1/users", **self.api_auth(self.example_email("hamlet")))
        self.assert_json_success(result)
        json = ujson.loads(result.content)

        for user in json['members']:
            if user['email'] == self.example_email("hamlet"):
                self.assertEqual(
                    user['avatar_url'],
                    avatar_url(user_profile),
                )
