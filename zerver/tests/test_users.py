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
    Realm, RealmAlias, UserActivity, \
    get_user_profile_by_email, get_realm, get_client, get_stream, \
    Message, get_context_for_message

from zerver.lib.avatar import avatar_url
from zerver.lib.email_mirror import create_missed_message_address
from zerver.lib.actions import \
    get_emails_from_user_ids, do_deactivate_user, do_reactivate_user, \
    do_change_is_admin, do_set_realm_name, do_deactivate_realm

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
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        do_change_is_admin(user_profile, False)
        admin_users = user_profile.realm.get_admin_users()
        self.assertFalse(user_profile in admin_users)
        do_change_is_admin(user_profile, True)
        admin_users = user_profile.realm.get_admin_users()
        self.assertTrue(user_profile in admin_users)

    def test_updating_non_existent_user(self):
        # type: () -> None
        self.login('hamlet@zulip.com')
        admin = get_user_profile_by_email('hamlet@zulip.com')
        do_change_is_admin(admin, True)

        result = self.client_patch('/json/users/nonexistentuser@zulip.com', {})
        self.assert_json_error(result, 'No such user')

    def test_admin_api(self):
        # type: () -> None
        self.login('hamlet@zulip.com')
        admin = get_user_profile_by_email('hamlet@zulip.com')
        user = get_user_profile_by_email('othello@zulip.com')
        realm = admin.realm
        do_change_is_admin(admin, True)

        # Make sure we see is_admin flag in /json/users
        result = self.client_get('/json/users')
        self.assert_json_success(result)
        members = ujson.loads(result.content)['members']
        hamlet = find_dict(members, 'email', 'hamlet@zulip.com')
        self.assertTrue(hamlet['is_admin'])
        othello = find_dict(members, 'email', 'othello@zulip.com')
        self.assertFalse(othello['is_admin'])

        # Giveth
        req = dict(is_admin=ujson.dumps(True))

        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/users/othello@zulip.com', req)
        self.assert_json_success(result)
        admin_users = realm.get_admin_users()
        self.assertTrue(user in admin_users)
        person = events[0]['event']['person']
        self.assertEqual(person['email'], 'othello@zulip.com')
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
        self.assertEqual(person['email'], 'othello@zulip.com')
        self.assertEqual(person['is_admin'], False)

        # Cannot take away from last admin
        self.login('iago@zulip.com')
        req = dict(is_admin=ujson.dumps(False))
        events = []
        with tornado_redirected_to_list(events):
            result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_success(result)
        admin_users = realm.get_admin_users()
        self.assertFalse(admin in admin_users)
        person = events[0]['event']['person']
        self.assertEqual(person['email'], 'hamlet@zulip.com')
        self.assertEqual(person['is_admin'], False)
        with tornado_redirected_to_list([]):
            result = self.client_patch('/json/users/iago@zulip.com', req)
        self.assert_json_error(result, 'Cannot remove the only organization administrator')

        # Make sure only admins can patch other user's info.
        self.login('othello@zulip.com')
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_error(result, 'Insufficient permission')

    def test_admin_user_can_change_full_name(self):
        # type: () -> None
        new_name = 'new name'
        self.login('iago@zulip.com')
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assertTrue(result.status_code == 200)
        hamlet = get_user_profile_by_email('hamlet@zulip.com')
        self.assertEqual(hamlet.full_name, new_name)

    def test_non_admin_cannot_change_full_name(self):
        # type: () -> None
        self.login('hamlet@zulip.com')
        req = dict(full_name=ujson.dumps('new name'))
        result = self.client_patch('/json/users/othello@zulip.com', req)
        self.assert_json_error(result, 'Insufficient permission')

    def test_admin_cannot_set_long_full_name(self):
        # type: () -> None
        new_name = 'a' * (UserProfile.MAX_NAME_LENGTH + 1)
        self.login('iago@zulip.com')
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_error(result, 'Name too long!')

    def test_admin_cannot_set_full_name_with_invalid_characters(self):
        # type: () -> None
        new_name = 'Opheli*'
        self.login('iago@zulip.com')
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

        admin_email = 'hamlet@zulip.com'
        self.login(admin_email)
        admin = get_user_profile_by_email(admin_email)
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

        RealmAlias.objects.create(realm=get_realm('zulip'), domain='zulip.net')

        # HAPPY PATH STARTS HERE
        valid_params = dict(
            email='romeo@zulip.net',
            password='xxxx',
            full_name='Romeo Montague',
            short_name='Romeo',
        )
        result = self.client_post("/json/users", valid_params)
        self.assert_json_success(result)

        new_user = get_user_profile_by_email('romeo@zulip.net')
        self.assertEqual(new_user.full_name, 'Romeo Montague')
        self.assertEqual(new_user.short_name, 'Romeo')

        # One more error condition to test--we can't create
        # the same user twice.
        result = self.client_post("/json/users", valid_params)
        self.assert_json_error(result,
                               "Email 'romeo@zulip.net' already in use")

class UserProfileTest(TestCase):
    def test_get_emails_from_user_ids(self):
        # type: () -> None
        hamlet = get_user_profile_by_email('hamlet@zulip.com')
        othello = get_user_profile_by_email('othello@zulip.com')
        dct = get_emails_from_user_ids([hamlet.id, othello.id])
        self.assertEqual(dct[hamlet.id], 'hamlet@zulip.com')
        self.assertEqual(dct[othello.id], 'othello@zulip.com')

class ActivateTest(ZulipTestCase):
    def test_basics(self):
        # type: () -> None
        user = get_user_profile_by_email('hamlet@zulip.com')
        do_deactivate_user(user)
        self.assertFalse(user.is_active)
        do_reactivate_user(user)
        self.assertTrue(user.is_active)

    def test_api(self):
        # type: () -> None
        admin = get_user_profile_by_email('othello@zulip.com')
        do_change_is_admin(admin, True)
        self.login('othello@zulip.com')

        user = get_user_profile_by_email('hamlet@zulip.com')
        self.assertTrue(user.is_active)

        result = self.client_delete('/json/users/hamlet@zulip.com')
        self.assert_json_success(result)
        user = get_user_profile_by_email('hamlet@zulip.com')
        self.assertFalse(user.is_active)

        result = self.client_post('/json/users/hamlet@zulip.com/reactivate')
        self.assert_json_success(result)
        user = get_user_profile_by_email('hamlet@zulip.com')
        self.assertTrue(user.is_active)

    def test_api_me_user(self):
        # type: () -> None
        """This test helps ensure that our URL patterns for /users/me URLs
        handle email addresses starting with "me" correctly."""
        self.register("me@zulip.com", "testpassword")
        self.login('iago@zulip.com')

        result = self.client_delete('/json/users/me@zulip.com')
        self.assert_json_success(result)
        user = get_user_profile_by_email('me@zulip.com')
        self.assertFalse(user.is_active)

        result = self.client_post('/json/users/me@zulip.com/reactivate')
        self.assert_json_success(result)
        user = get_user_profile_by_email('me@zulip.com')
        self.assertTrue(user.is_active)

    def test_api_with_nonexistent_user(self):
        # type: () -> None
        admin = get_user_profile_by_email('othello@zulip.com')
        do_change_is_admin(admin, True)
        self.login('othello@zulip.com')

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
        non_admin = get_user_profile_by_email('othello@zulip.com')
        do_change_is_admin(non_admin, False)
        self.login('othello@zulip.com')

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

    def common_get_profile(self, email):
        # type: (str) -> Dict[Text, Any]
        user_profile = get_user_profile_by_email(email)
        self.send_message(email, "Verona", Recipient.STREAM, "hello")

        result = self.client_get("/api/v1/users/me", **self.api_auth(email))

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
        email = "hamlet@zulip.com"
        self.login(email)
        result = self.client_get("/json/users/me/pointer")
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("pointer", json)

    def test_cache_behavior(self):
        # type: () -> None
        with queries_captured() as queries:
            with simulated_empty_cache() as cache_queries:
                user_profile = get_user_profile_by_email('hamlet@zulip.com')

        self.assert_max_length(queries, 1)
        self.assert_length(cache_queries, 1)
        self.assertEqual(user_profile.email, 'hamlet@zulip.com')

    def test_get_user_profile(self):
        # type: () -> None
        self.login('hamlet@zulip.com')
        result = ujson.loads(self.client_get('/json/users/me').content)
        self.assertEqual(result['short_name'], 'hamlet')
        self.assertEqual(result['email'], 'hamlet@zulip.com')
        self.assertEqual(result['full_name'], 'King Hamlet')
        self.assertIn("user_id", result)
        self.assertFalse(result['is_bot'])
        self.assertFalse(result['is_admin'])
        self.login('iago@zulip.com')
        result = ujson.loads(self.client_get('/json/users/me').content)
        self.assertEqual(result['short_name'], 'iago')
        self.assertEqual(result['email'], 'iago@zulip.com')
        self.assertEqual(result['full_name'], 'Iago')
        self.assertFalse(result['is_bot'])
        self.assertTrue(result['is_admin'])

    def test_api_get_empty_profile(self):
        # type: () -> None
        """
        Ensure GET /users/me returns a max message id and returns successfully
        """
        json = self.common_get_profile("othello@zulip.com")
        self.assertEqual(json["pointer"], -1)

    def test_profile_with_pointer(self):
        # type: () -> None
        """
        Ensure GET /users/me returns a proper pointer id after the pointer is updated
        """

        id1 = self.send_message("othello@zulip.com", "Verona", Recipient.STREAM)
        id2 = self.send_message("othello@zulip.com", "Verona", Recipient.STREAM)

        json = self.common_get_profile("hamlet@zulip.com")

        self.common_update_pointer("hamlet@zulip.com", id2)
        json = self.common_get_profile("hamlet@zulip.com")
        self.assertEqual(json["pointer"], id2)

        self.common_update_pointer("hamlet@zulip.com", id1)
        json = self.common_get_profile("hamlet@zulip.com")
        self.assertEqual(json["pointer"], id2) # pointer does not move backwards

        result = self.client_post("/json/users/me/pointer", {"pointer": 99999999})
        self.assert_json_error(result, "Invalid message ID")

    def test_get_all_profiles_avatar_urls(self):
        # type: () -> None
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        result = self.client_get("/api/v1/users", **self.api_auth('hamlet@zulip.com'))
        self.assert_json_success(result)
        json = ujson.loads(result.content)

        for user in json['members']:
            if user['email'] == 'hamlet@zulip.com':
                self.assertEqual(
                    user['avatar_url'],
                    avatar_url(user_profile),
                )
