# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from typing import (Any, Dict, Iterable, List,
                    Optional, TypeVar, Text, Union)
from mock import patch, MagicMock

from django.http import HttpResponse
from django.test import TestCase, override_settings

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
from zerver.forms import WRONG_SUBDOMAIN_ERROR

from zerver.models import UserProfile, Recipient, \
    Realm, RealmAlias, UserActivity, \
    get_user_profile_by_email, get_realm, get_client, get_stream, \
    Message, get_unique_open_realm, completely_open, get_context_for_message

from zerver.lib.avatar import avatar_url
from zerver.lib.email_mirror import create_missed_message_address
from zerver.lib.actions import \
    get_emails_from_user_ids, do_deactivate_user, do_reactivate_user, \
    do_change_is_admin, extract_recipients, \
    do_set_realm_name, do_deactivate_realm
from zerver.lib.notifications import handle_missedmessage_emails, \
    send_missedmessage_email
from zerver.middleware import is_slow_query
from zerver.lib.utils import split_by

from django.conf import settings
from django.core import mail
from six.moves import range
import os
import re
import sys
import time
import ujson
import random
import subprocess

K = TypeVar('K')
V = TypeVar('V')
def find_dict(lst, k, v):
    # type: (Iterable[Dict[K, V]], K, V) -> Dict[K, V]
    for dct in lst:
        if dct[k] == v:
            return dct
    raise AssertionError('Cannot find element in list where key %s == %s' % (k, v))

class SlowQueryTest(TestCase):
    def test_is_slow_query(self):
        # type: () -> None
        self.assertFalse(is_slow_query(1.1, '/some/random/url'))
        self.assertTrue(is_slow_query(2, '/some/random/url'))
        self.assertTrue(is_slow_query(5.1, '/activity'))
        self.assertFalse(is_slow_query(2, '/activity'))
        self.assertFalse(is_slow_query(2, '/json/report_error'))
        self.assertFalse(is_slow_query(2, '/api/v1/deployments/report_error'))
        self.assertFalse(is_slow_query(2, '/realm_activity/whatever'))
        self.assertFalse(is_slow_query(2, '/user_activity/whatever'))
        self.assertFalse(is_slow_query(9, '/accounts/webathena_kerberos_login/'))
        self.assertTrue(is_slow_query(11, '/accounts/webathena_kerberos_login/'))

class ModelTest(TestCase):
    def test_miscellaneous_things(self):
        # type: () -> None
        '''
        This is a kitchen sink test that is designed simply to get
        test coverage up to 100% for models.py.
        '''
        client = make_client('some_client')
        self.assertEqual(str(client), u'<Client: some_client>')

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
                               "Email 'romeo@not-zulip.com' does not belong to domain 'zulip.com'")

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

class DocPageTest(ZulipTestCase):
        def _test(self, url, expected_content):
            # type: (str, str) -> None
            result = self.client_get(url)
            self.assertEqual(result.status_code, 200)
            self.assertIn(expected_content, str(result.content))

        def test_doc_endpoints(self):
            # type: () -> None
            self._test('/api/', 'We hear you like APIs')
            self._test('/api/endpoints/', 'pre-built API bindings for')
            self._test('/about/', 'Cambridge, Massachusetts')
            # Test the i18n version of one of these pages.
            self._test('/en/about/', 'Cambridge, Massachusetts')
            self._test('/apps/', 'Appsolutely')
            self._test('/features/', 'Talk about multiple topics at once')
            self._test('/hello/', 'workplace chat that actually improves your productivity')
            self._test('/integrations/', 'require creating a Zulip bot')
            self._test('/login/', '(Normal users)')
            self._test('/register/', 'get started')

            result = self.client_get('/new-user/')
            self.assertEqual(result.status_code, 301)
            self.assertIn('hello', result['Location'])

            result = self.client_get('/robots.txt')
            self.assertEqual(result.status_code, 301)
            self.assertIn('static/robots.txt', result['Location'])

            result = self.client_get('/static/robots.txt')
            self.assertEqual(result.status_code, 200)
            self.assertIn(
                'Disallow: /',
                ''.join(str(x) for x in list(result.streaming_content))
            )

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

class AuthorsPageTest(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        """ Manual installation which did not execute `tools/provision`
        would not have the `static/generated/github-contributors.json` fixture
        file.
        """
        # This block has unreliable test coverage due to the implicit
        # caching here, so we exclude it from coverage.
        if not os.path.exists(settings.CONTRIBUTORS_DATA):
            # Copy the fixture file in `zerver/fixtures` to `static/generated`
            update_script = os.path.join(os.path.dirname(__file__),
                                         '../../tools/update-authors-json')  # nocoverage
            subprocess.check_call([update_script, '--use-fixture'])  # nocoverage

    def test_endpoint(self):
        # type: () -> None
        result = self.client_get('/authors/')
        self.assert_in_success_response(
            ['Contributors', 'Statistic last Updated:', 'commits',
             '@timabbott'],
            result
        )

class MutedTopicsTests(ZulipTestCase):
    def test_json_set(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)

        url = '/json/set_muted_topics'
        data = {'muted_topics': '[["stream", "topic"]]'}
        result = self.client_post(url, data)
        self.assert_json_success(result)

        user = get_user_profile_by_email(email)
        self.assertEqual(ujson.loads(user.muted_topics), [["stream", "topic"]])

        url = '/json/set_muted_topics'
        data = {'muted_topics': '[["stream2", "topic2"]]'}
        result = self.client_post(url, data)
        self.assert_json_success(result)

        user = get_user_profile_by_email(email)
        self.assertEqual(ujson.loads(user.muted_topics), [["stream2", "topic2"]])

class ExtractedRecipientsTest(TestCase):
    def test_extract_recipients(self):
        # type: () -> None

        # JSON list w/dups, empties, and trailing whitespace
        s = ujson.dumps([' alice@zulip.com ', ' bob@zulip.com ', '   ', 'bob@zulip.com'])
        self.assertEqual(sorted(extract_recipients(s)), ['alice@zulip.com', 'bob@zulip.com'])

        # simple string with one name
        s = 'alice@zulip.com    '
        self.assertEqual(extract_recipients(s), ['alice@zulip.com'])

        # JSON-encoded string
        s = '"alice@zulip.com"'
        self.assertEqual(extract_recipients(s), ['alice@zulip.com'])

        # bare comma-delimited string
        s = 'bob@zulip.com, alice@zulip.com'
        self.assertEqual(sorted(extract_recipients(s)), ['alice@zulip.com', 'bob@zulip.com'])

        # JSON-encoded, comma-delimited string
        s = '"bob@zulip.com,alice@zulip.com"'
        self.assertEqual(sorted(extract_recipients(s)), ['alice@zulip.com', 'bob@zulip.com'])


class TestMissedMessages(ZulipTestCase):
    def normalize_string(self, s):
        # type: (Text) -> Text
        s = s.strip()
        return re.sub(r'\s+', ' ', s)

    def _get_tokens(self):
        # type: () -> List[str]
        return [str(random.getrandbits(32)) for _ in range(30)]

    def _test_cases(self, tokens, msg_id, body, send_as_user):
        # type: (List[str], int, str, bool) -> None
        othello = get_user_profile_by_email('othello@zulip.com')
        hamlet = get_user_profile_by_email('hamlet@zulip.com')
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])
        reply_to_addresses = [settings.EMAIL_GATEWAY_PATTERN % (u'mm' + t) for t in tokens]
        msg = mail.outbox[0]
        sender = 'Zulip <{}>'.format(settings.NOREPLY_EMAIL_ADDRESS)
        from_email = sender
        self.assertEqual(len(mail.outbox), 1)
        if send_as_user:
            from_email = '"%s" <%s>' % (othello.full_name, othello.email)
            self.assertEqual(msg.extra_headers['Sender'], sender)
        else:
            self.assertNotIn("Sender", msg.extra_headers)
        self.assertEqual(msg.from_email, from_email)
        self.assertIn(msg.extra_headers['Reply-To'], reply_to_addresses)
        self.assertIn(body, self.normalize_string(msg.body))

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_missed_stream_messages(self, send_as_user, mock_random_token):
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        for i in range(0, 11):
            self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, str(i))
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '11', subject='test2')
        msg_id = self.send_message("othello@zulip.com", "denmark", Recipient.STREAM, '@**hamlet**')
        body = 'Denmark > test Othello, the Moor of Venice 1 2 3 4 5 6 7 8 9 10 @**hamlet**'
        self._test_cases(tokens, msg_id, body, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_personal_missed_stream_messages(self, send_as_user, mock_random_token):
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com", "hamlet@zulip.com",
                                   Recipient.PERSONAL,
                                   'Extremely personal message!')
        body = 'You and Othello, the Moor of Venice Extremely personal message!'
        self._test_cases(tokens, msg_id, body, send_as_user)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def _extra_context_in_huddle_missed_stream_messages(self, send_as_user, mock_random_token):
        # type: (bool, MagicMock) -> None
        tokens = self._get_tokens()
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com",
                                   ["hamlet@zulip.com", "iago@zulip.com"],
                                   Recipient.PERSONAL,
                                   'Group personal message!')

        body = ('You and Iago, Othello, the Moor of Venice Othello,'
                ' the Moor of Venice Group personal message')
        self._test_cases(tokens, msg_id, body, send_as_user)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_missed_stream_messages_as_user(self):
        # type: () -> None
        self._extra_context_in_missed_stream_messages(True)

    def test_extra_context_in_missed_stream_messages(self):
        # type: () -> None
        self._extra_context_in_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_personal_missed_stream_messages_as_user(self):
        # type: () -> None
        self._extra_context_in_personal_missed_stream_messages(True)

    def test_extra_context_in_personal_missed_stream_messages(self):
        # type: () -> None
        self._extra_context_in_personal_missed_stream_messages(False)

    @override_settings(SEND_MISSED_MESSAGE_EMAILS_AS_USER=True)
    def test_extra_context_in_huddle_missed_stream_messages_as_user(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages(True)

    def test_extra_context_in_huddle_missed_stream_messages(self):
        # type: () -> None
        self._extra_context_in_huddle_missed_stream_messages(False)


class TestOpenRealms(ZulipTestCase):
    def test_open_realm_logic(self):
        # type: () -> None
        realm = get_realm('simple')
        do_deactivate_realm(realm)

        mit_realm = get_realm("zephyr")
        self.assertEqual(get_unique_open_realm(), None)
        mit_realm.restricted_to_domain = False
        mit_realm.save()
        self.assertTrue(completely_open(mit_realm))
        self.assertEqual(get_unique_open_realm(), None)
        with self.settings(SYSTEM_ONLY_REALMS={"zulip"}):
            self.assertEqual(get_unique_open_realm(), mit_realm)
        mit_realm.restricted_to_domain = True
        mit_realm.save()

class TestLoginPage(ZulipTestCase):
    def test_login_page_wrong_subdomain_error(self):
        # type: () -> None
        result = self.client_get("/login/?subdomain=1")
        self.assertIn(WRONG_SUBDOMAIN_ERROR, result.content.decode('utf8'))

    @patch('django.http.HttpRequest.get_host')
    def test_login_page_redirects_for_root_alias(self, mock_get_host):
        # type: (MagicMock) -> None
        mock_get_host.return_value = 'www.testserver'
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           ROOT_SUBDOMAIN_ALIASES=['www']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/find_my_team/')

    @patch('django.http.HttpRequest.get_host')
    def test_login_page_redirects_for_root_domain(self, mock_get_host):
        # type: (MagicMock) -> None
        mock_get_host.return_value = 'testserver'
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           ROOT_SUBDOMAIN_ALIASES=['www']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/find_my_team/')

        mock_get_host.return_value = 'www.testserver.com'
        with self.settings(REALMS_HAVE_SUBDOMAINS=True,
                           EXTERNAL_HOST='www.testserver.com',
                           ROOT_SUBDOMAIN_ALIASES=['test']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 302)
            self.assertEqual(result.url, '/find_my_team/')

    @patch('django.http.HttpRequest.get_host')
    def test_login_page_works_without_subdomains(self, mock_get_host):
        # type: (MagicMock) -> None
        mock_get_host.return_value = 'www.testserver'
        with self.settings(ROOT_SUBDOMAIN_ALIASES=['www']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 200)

        mock_get_host.return_value = 'testserver'
        with self.settings(ROOT_SUBDOMAIN_ALIASES=['www']):
            result = self.client_get("/en/login/")
            self.assertEqual(result.status_code, 200)

class TestFindMyTeam(ZulipTestCase):
    def test_template(self):
        # type: () -> None
        result = self.client_get('/find_my_team/')
        self.assertIn("Find your team", result.content.decode('utf8'))

    def test_result(self):
        # type: () -> None
        url = '/find_my_team/?emails=iago@zulip.com,cordelia@zulip.com'
        result = self.client_get(url)
        content = result.content.decode('utf8')
        self.assertIn("Emails sent! You will only receive emails", content)
        self.assertIn("iago@zulip.com", content)
        self.assertIn("cordelia@zulip.com", content)

    def test_find_team_zero_emails(self):
        # type: () -> None
        data = {'emails': ''}
        result = self.client_post('/find_my_team/', data)
        self.assertIn('This field is required', result.content.decode('utf8'))
        self.assertEqual(result.status_code, 200)

    def test_find_team_one_email(self):
        # type: () -> None
        data = {'emails': 'hamlet@zulip.com'}
        result = self.client_post('/find_my_team/', data)
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/find_my_team/?emails=hamlet%40zulip.com')

    def test_find_team_multiple_emails(self):
        # type: () -> None
        data = {'emails': 'hamlet@zulip.com,iago@zulip.com'}
        result = self.client_post('/find_my_team/', data)
        self.assertEqual(result.status_code, 302)
        expected = '/find_my_team/?emails=hamlet%40zulip.com%2Ciago%40zulip.com'
        self.assertEqual(result.url, expected)

    def test_find_team_more_than_ten_emails(self):
        # type: () -> None
        data = {'emails': ','.join(['hamlet-{}@zulip.com'.format(i) for i in range(11)])}
        result = self.client_post('/find_my_team/', data)
        self.assertEqual(result.status_code, 200)
        self.assertIn("Please enter at most 10", result.content.decode('utf8'))

class UtilsUnitTest(TestCase):
    def test_split_by(self):
        # type: () -> None
        flat_list = [1, 2, 3, 4, 5, 6, 7]
        expected_result = [[1, 2], [3, 4], [5, 6], [7, None]]
        self.assertEqual(split_by(flat_list, 2, None), expected_result)
