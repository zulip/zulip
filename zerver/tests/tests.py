# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from typing import Any, Callable, Dict, Iterable, List, Mapping, Tuple, TypeVar
from mock import patch, MagicMock

from django.http import HttpResponse
from django.test import TestCase

from zerver.lib.test_helpers import (
    queries_captured, simulated_empty_cache,
    simulated_queue_client, tornado_redirected_to_list, AuthedTestCase,
    most_recent_usermessage, most_recent_message,
)
from zerver.lib.test_runner import slow

from zerver.models import UserProfile, Recipient, \
    Realm, Client, UserActivity, \
    get_user_profile_by_email, split_email_to_domain, get_realm, \
    get_client, get_stream, Message, get_unique_open_realm, \
    completely_open

from zerver.lib.avatar import get_avatar_url
from zerver.lib.initial_password import initial_password
from zerver.lib.email_mirror import create_missed_message_address
from zerver.lib.actions import \
    get_emails_from_user_ids, do_deactivate_user, do_reactivate_user, \
    do_change_is_admin, extract_recipients, \
    do_set_realm_name, do_deactivate_realm, \
    do_add_subscription, do_remove_subscription, do_make_stream_private
from zerver.lib.alert_words import alert_words_in_realm, user_alert_words, \
    add_user_alert_words, remove_user_alert_words
from zerver.lib.notifications import handle_missedmessage_emails
from zerver.lib.session_user import get_session_dict_user
from zerver.middleware import is_slow_query

from zerver.worker import queue_processors

from django.conf import settings
from django.core import mail
from six import text_type
from six.moves import range
import datetime
import os
import re
import sys
import time
import ujson
import random

def bail(msg):
    # type: (str) -> None
    print('\nERROR: %s\n' % (msg,))
    sys.exit(1)

try:
    settings.TEST_SUITE
except:
    bail('Test suite only runs correctly with --settings=zproject.test_settings')

# Even though we don't use pygments directly in this file, we need
# this import.
try:
    import pygments
except ImportError:
    bail('The Pygments library is required to run the backend test suite.')

K = TypeVar('K')
V = TypeVar('V')
def find_dict(lst, k, v):
    # type: (Iterable[Dict[K, V]], K, V) -> Dict[K, V]
    for dct in lst:
        if dct[k] == v:
            return dct
    raise Exception('Cannot find element in list where key %s == %s' % (k, v))

# same as in test_uploads.py
TEST_AVATAR_DIR = os.path.join(os.path.dirname(__file__), 'images')

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

class RealmTest(AuthedTestCase):
    def assert_user_profile_cache_gets_new_name(self, email, new_realm_name):
        # type: (text_type, text_type) -> None
        user_profile = get_user_profile_by_email(email)
        self.assertEqual(user_profile.realm.name, new_realm_name)

    def test_do_set_realm_name_caching(self):
        # type: () -> None
        """The main complicated thing about setting realm names is fighting the
        cache, and we start by populating the cache for Hamlet, and we end
        by checking the cache to ensure that the new value is there."""
        get_user_profile_by_email('hamlet@zulip.com')
        realm = get_realm('zulip.com')
        new_name = 'Zed You Elle Eye Pea'
        do_set_realm_name(realm, new_name)
        self.assertEqual(get_realm(realm.domain).name, new_name)
        self.assert_user_profile_cache_gets_new_name('hamlet@zulip.com', new_name)

    def test_do_set_realm_name_events(self):
        # type: () -> None
        realm = get_realm('zulip.com')
        new_name = 'Puliz'
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            do_set_realm_name(realm, new_name)
        event = events[0]['event']
        self.assertEqual(event, dict(
            type = 'realm',
            op = 'update',
            property = 'name',
            value = new_name,
        ))

    def test_realm_name_api(self):
        # type: () -> None
        new_name = 'Zulip: Worldwide Exporter of APIs'

        email = 'cordelia@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        do_change_is_admin(user_profile, True)

        req = dict(name=ujson.dumps(new_name))
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip.com')
        self.assertEqual(realm.name, new_name)

    def test_admin_restrictions_for_changing_realm_name(self):
        # type: () -> None
        new_name = 'Mice will play while the cat is away'

        email = 'othello@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        do_change_is_admin(user_profile, False)

        req = dict(name=ujson.dumps(new_name))
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_do_deactivate_realm(self):
        # type: () -> None
        """The main complicated thing about deactivating realm names is
        updating the cache, and we start by populating the cache for
        Hamlet, and we end by checking the cache to ensure that his
        realm appears to be deactivated.  You can make this test fail
        by disabling cache.flush_realm()."""
        get_user_profile_by_email('hamlet@zulip.com')
        realm = get_realm('zulip.com')
        do_deactivate_realm(realm)
        user = get_user_profile_by_email('hamlet@zulip.com')
        self.assertTrue(user.realm.deactivated)

    def test_do_set_realm_default_language(self):
        # type: () -> None
        new_lang = "de"
        realm = get_realm('zulip.com')
        self.assertNotEqual(realm.default_language, new_lang)
        # we need an admin user.
        email = 'iago@zulip.com'
        self.login(email)

        req = dict(default_language=ujson.dumps(new_lang))
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip.com')
        self.assertEqual(realm.default_language, new_lang)

        # Test setting zh_CN, we set zh_HANS instead of zh_CN in db
        chinese = "zh_CN"
        simplified_chinese = "zh_HANS"
        req = dict(default_language=ujson.dumps(chinese))
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip.com')
        self.assertEqual(realm.default_language, simplified_chinese)

        # Test to make sure that when invalid languages are passed
        # as the default realm language, correct validation error is
        # raised and the invalid language is not saved in db
        invalid_lang = "invalid_lang"
        req = dict(default_language=ujson.dumps(invalid_lang))
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, "Invalid language '%s'" % (invalid_lang,))
        realm = get_realm('zulip.com')
        self.assertNotEqual(realm.default_language, invalid_lang)


class PermissionTest(AuthedTestCase):
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

        # Make sure only admins can patch other user's info.
        self.login('othello@zulip.com')
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assert_json_error(result, 'Insufficient permission')

class AdminCreateUserTest(AuthedTestCase):
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

        result = self.client_put("/json/users", dict(
            user_profile=admin,
            )
        )
        self.assert_json_error(result, "Missing 'email' argument")

        result = self.client_put("/json/users", dict(
            email='romeo@not-zulip.com',
            )
        )
        self.assert_json_error(result, "Missing 'password' argument")

        result = self.client_put("/json/users", dict(
            email='romeo@not-zulip.com',
            password='xxxx',
            )
        )
        self.assert_json_error(result, "Missing 'full_name' argument")

        result = self.client_put("/json/users", dict(
            email='romeo@not-zulip.com',
            password='xxxx',
            full_name='Romeo Montague',
            )
        )
        self.assert_json_error(result, "Missing 'short_name' argument")

        result = self.client_put("/json/users", dict(
            email='broken',
            password='xxxx',
            full_name='Romeo Montague',
            short_name='Romeo',
            )
        )
        self.assert_json_error(result, "Bad name or username")

        result = self.client_put("/json/users", dict(
            email='romeo@not-zulip.com',
            password='xxxx',
            full_name='Romeo Montague',
            short_name='Romeo',
            )
        )
        self.assert_json_error(result,
            "Email 'romeo@not-zulip.com' does not belong to domain 'zulip.com'")

        # HAPPY PATH STARTS HERE
        valid_params = dict(
            email='romeo@zulip.com',
            password='xxxx',
            full_name='Romeo Montague',
            short_name='Romeo',
        )
        result = self.client_put("/json/users", valid_params)
        self.assert_json_success(result)

        new_user = get_user_profile_by_email('romeo@zulip.com')
        self.assertEqual(new_user.full_name, 'Romeo Montague')
        self.assertEqual(new_user.short_name, 'Romeo')

        # One more error condition to test--we can't create
        # the same user twice.
        result = self.client_put("/json/users", valid_params)
        self.assert_json_error(result,
            "Email 'romeo@zulip.com' already in use")

class WorkerTest(TestCase):
    class FakeClient(object):
        def __init__(self):
            # type: () -> None
            self.consumers = {} # type: Dict[str, Callable]
            self.queue = [] # type: List[Tuple[str, Dict[str, Any]]]

        def register_json_consumer(self, queue_name, callback):
            # type: (str, Callable) -> None
            self.consumers[queue_name] = callback

        def start_consuming(self):
            # type: () -> None
            for queue_name, data in self.queue:
                callback = self.consumers[queue_name]
                callback(data)


    def test_UserActivityWorker(self):
        # type: () -> None
        fake_client = self.FakeClient()

        user = get_user_profile_by_email('hamlet@zulip.com')
        UserActivity.objects.filter(
                user_profile = user.id,
                client = get_client('ios')
        ).delete()

        data = dict(
                user_profile_id = user.id,
                client = 'ios',
                time = time.time(),
                query = 'send_message'
        )
        fake_client.queue.append(('user_activity', data))

        with simulated_queue_client(lambda: fake_client):
            worker = queue_processors.UserActivityWorker()
            worker.setup()
            worker.start()
            activity_records = UserActivity.objects.filter(
                    user_profile = user.id,
                    client = get_client('ios')
            )
            self.assertTrue(len(activity_records), 1)
            self.assertTrue(activity_records[0].count, 1)

    def test_error_handling(self):
        # type: () -> None
        processed = []

        @queue_processors.assign_queue('unreliable_worker')
        class UnreliableWorker(queue_processors.QueueProcessingWorker):
            def consume(self, data):
                # type: (Mapping[str, Any]) -> None
                if data["type"] == 'unexpected behaviour':
                    raise Exception('Worker task not performing as expected!')
                processed.append(data["type"])

            def _log_problem(self):
                # type: () -> None

                # keep the tests quiet
                pass

        fake_client = self.FakeClient()
        for msg in ['good', 'fine', 'unexpected behaviour', 'back to normal']:
            fake_client.queue.append(('unreliable_worker', {'type': msg}))

        fn = os.path.join(settings.QUEUE_ERROR_DIR, 'unreliable_worker.errors')
        try:
            os.remove(fn)
        except OSError:
            pass

        with simulated_queue_client(lambda: fake_client):
            worker = UnreliableWorker()
            worker.setup()
            worker.start()

        self.assertEqual(processed, ['good', 'fine', 'back to normal'])
        line = open(fn).readline().strip()
        event = ujson.loads(line.split('\t')[1])
        self.assertEqual(event["type"], 'unexpected behaviour')

    def test_worker_noname(self):
        # type: () -> None
        class TestWorker(queue_processors.QueueProcessingWorker):
            def __init__(self):
                # type: () -> None
                super(TestWorker, self).__init__()
            def consume(self, data):
                # type: (Mapping[str, Any]) -> None
                pass
        with self.assertRaises(queue_processors.WorkerDeclarationException):
            TestWorker()

    def test_worker_noconsume(self):
        # type: () -> None
        @queue_processors.assign_queue('test_worker')
        class TestWorker(queue_processors.QueueProcessingWorker):
            def __init__(self):
                # type: () -> None
                super(TestWorker, self).__init__()

        with self.assertRaises(queue_processors.WorkerDeclarationException):
            worker = TestWorker()
            worker.consume({})

class ActivityTest(AuthedTestCase):
    def test_activity(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        client, _ = Client.objects.get_or_create(name='website')
        query = '/json/users/me/pointer'
        last_visit = datetime.datetime.now()
        count=150
        for user_profile in UserProfile.objects.all():
            UserActivity.objects.get_or_create(
                user_profile=user_profile,
                client=client,
                query=query,
                count=count,
                last_visit=last_visit
            )
        with queries_captured() as queries:
            self.client_get('/activity')

        self.assert_length(queries, 13)

class UserProfileTest(TestCase):
    def test_get_emails_from_user_ids(self):
        # type: () -> None
        hamlet = get_user_profile_by_email('hamlet@zulip.com')
        othello = get_user_profile_by_email('othello@zulip.com')
        dct = get_emails_from_user_ids([hamlet.id, othello.id])
        self.assertEqual(dct[hamlet.id], 'hamlet@zulip.com')
        self.assertEqual(dct[othello.id], 'othello@zulip.com')

class UserChangesTest(AuthedTestCase):
    def test_update_api_key(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        self.login(email)
        user = get_user_profile_by_email(email)
        old_api_key = user.api_key
        result = self.client_post('/json/users/me/api_key/regenerate')
        self.assert_json_success(result)
        new_api_key = ujson.loads(result.content)['api_key']
        self.assertNotEqual(old_api_key, new_api_key)
        user = get_user_profile_by_email(email)
        self.assertEqual(new_api_key, user.api_key)

class ActivateTest(AuthedTestCase):
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

class BotTest(AuthedTestCase):
    def assert_num_bots_equal(self, count):
        # type: (int) -> None
        result = self.client_get("/json/bots")
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(count, len(json['bots']))

    def create_bot(self, **extras):
        # type: (**Any) -> Dict[str, Any]
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        bot_info.update(extras)
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        return ujson.loads(result.content)

    def deactivate_bot(self):
        # type: () -> None
        result = self.client_delete("/json/bots/hambot-bot@zulip.com")
        self.assert_json_success(result)

    def test_add_bot_with_bad_username(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        bot_info = dict(
            full_name='',
            short_name='',
            )
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Bad name or username')
        self.assert_num_bots_equal(0)

    def test_add_bot(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.create_bot()
        self.assert_num_bots_equal(1)

        event = [e for e in events if e['event']['type'] == 'realm_bot'][0]
        self.assertEqual(
            dict(
                type='realm_bot',
                op='add',
                bot=dict(email='hambot-bot@zulip.com',
                     full_name='The Bot of Hamlet',
                     api_key=result['api_key'],
                     avatar_url=result['avatar_url'],
                     default_sending_stream=None,
                     default_events_register_stream=None,
                     default_all_public_streams=False,
                     owner='hamlet@zulip.com',
                )
            ),
            event['event']
        )

        users_result = self.client_get('/json/users')
        members = ujson.loads(users_result.content)['members']
        bots = [m for m in members if m['email'] == 'hambot-bot@zulip.com']
        self.assertEqual(len(bots), 1)
        bot = bots[0]
        self.assertEqual(bot['bot_owner'], 'hamlet@zulip.com')

    def test_add_bot_with_username_in_use(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot()
        self.assert_num_bots_equal(1)

        bot_info = dict(
            full_name='Duplicate',
            short_name='hambot',
            )
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Username already in use')

    def test_add_bot_with_user_avatar(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        with open(os.path.join(TEST_AVATAR_DIR, 'img.png'), 'rb') as fp:
            self.create_bot(file=fp)
        self.assert_num_bots_equal(1)

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.avatar_source, UserProfile.AVATAR_FROM_USER)
        # TODO: check img.png was uploaded properly

    def test_add_bot_with_too_many_files(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        with open(os.path.join(TEST_AVATAR_DIR, 'img.png'), 'rb') as fp1, \
             open(os.path.join(TEST_AVATAR_DIR, 'img.gif'), 'rb') as fp2:
            bot_info = dict(
                full_name='whatever',
                short_name='whatever',
                file1=fp1,
                file2=fp2,
                )
            result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'You may only upload one file at a time')
        self.assert_num_bots_equal(0)

    def test_add_bot_with_default_sending_stream(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_sending_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Denmark')

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.default_sending_stream.name, 'Denmark')

    def test_add_bot_with_default_sending_stream_not_subscribed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_sending_stream='Rome')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Rome')

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.default_sending_stream.name, 'Rome')

    def test_add_bot_with_default_sending_stream_private_allowed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_add_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        self.assert_num_bots_equal(0)
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.create_bot(default_sending_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Denmark')

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.default_sending_stream.name, 'Denmark')

        event = [e for e in events if e['event']['type'] == 'realm_bot'][0]
        self.assertEqual(
            dict(
                type='realm_bot',
                op='add',
                bot=dict(email='hambot-bot@zulip.com',
                     full_name='The Bot of Hamlet',
                     api_key=result['api_key'],
                     avatar_url=result['avatar_url'],
                     default_sending_stream='Denmark',
                     default_events_register_stream=None,
                     default_all_public_streams=False,
                     owner='hamlet@zulip.com',
                )
            ),
            event['event']
        )
        self.assertEqual(event['users'], (user_profile.id,))

    def test_add_bot_with_default_sending_stream_private_denied(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_remove_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        bot_info = {
             'full_name': 'The Bot of Hamlet',
             'short_name': 'hambot',
             'default_sending_stream': 'Denmark',
         }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Insufficient permission')

    def test_add_bot_with_default_events_register_stream(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_events_register_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_events_register_stream'], 'Denmark')

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.default_events_register_stream.name, 'Denmark')

    def test_add_bot_with_default_events_register_stream_private_allowed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_add_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        self.assert_num_bots_equal(0)
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.create_bot(default_events_register_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_events_register_stream'], 'Denmark')

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.default_events_register_stream.name, 'Denmark')

        event = [e for e in events if e['event']['type'] == 'realm_bot'][0]
        self.assertEqual(
            dict(
                type='realm_bot',
                op='add',
                bot=dict(email='hambot-bot@zulip.com',
                     full_name='The Bot of Hamlet',
                     api_key=result['api_key'],
                     avatar_url=result['avatar_url'],
                     default_sending_stream=None,
                     default_events_register_stream='Denmark',
                     default_all_public_streams=False,
                     owner='hamlet@zulip.com',
                )
            ),
            event['event']
        )
        self.assertEqual(event['users'], (user_profile.id,))

    def test_add_bot_with_default_events_register_stream_private_denied(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_remove_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        self.assert_num_bots_equal(0)
        bot_info = {
             'full_name': 'The Bot of Hamlet',
             'short_name': 'hambot',
             'default_events_register_stream': 'Denmark',
         }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, 'Insufficient permission')

    def test_add_bot_with_default_all_public_streams(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_all_public_streams=ujson.dumps(True))
        self.assert_num_bots_equal(1)
        self.assertTrue(result['default_all_public_streams'])

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.default_all_public_streams, True)

    def test_deactivate_bot(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)
        self.deactivate_bot()
        # You can deactivate the same bot twice.
        self.deactivate_bot()
        self.assert_num_bots_equal(0)

    def test_deactivate_bogus_bot(self):
        # type: () -> None
        """Deleting a bogus bot will succeed silently."""
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)
        result = self.client_delete("/json/bots/bogus-bot@zulip.com")
        self.assert_json_error(result, 'No such bot')
        self.assert_num_bots_equal(1)

    def test_bot_deactivation_attacks(self):
        # type: () -> None
        """You cannot deactivate somebody else's bot."""
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)

        # Have Othello try to deactivate both Hamlet and
        # Hamlet's bot.
        self.login("othello@zulip.com")

        # Can not deactivate a user as a bot
        result = self.client_delete("/json/bots/hamlet@zulip.com")
        self.assert_json_error(result, 'No such bot')

        result = self.client_delete("/json/bots/hambot-bot@zulip.com")
        self.assert_json_error(result, 'Insufficient permission')

        # But we don't actually deactivate the other person's bot.
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(1)

        # Can not deactivate a bot as a user
        result = self.client_delete("/json/users/hambot-bot@zulip.com")
        self.assert_json_error(result, 'No such user')
        self.assert_num_bots_equal(1)

    def test_bot_permissions(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)

        # Have Othello try to mess with Hamlet's bots.
        self.login("othello@zulip.com")

        result = self.client_post("/json/bots/hambot-bot@zulip.com/api_key/regenerate")
        self.assert_json_error(result, 'Insufficient permission')

        bot_info = {
            'full_name': 'Fred',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'Insufficient permission')

    def get_bot(self):
        # type: () -> Dict[str, Any]
        result = self.client_get("/json/bots")
        bots = ujson.loads(result.content)['bots']
        return bots[0]

    def test_update_api_key(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.create_bot()
        bot = self.get_bot()
        old_api_key = bot['api_key']
        result = self.client_post('/json/bots/hambot-bot@zulip.com/api_key/regenerate')
        self.assert_json_success(result)
        new_api_key = ujson.loads(result.content)['api_key']
        self.assertNotEqual(old_api_key, new_api_key)
        bot = self.get_bot()
        self.assertEqual(new_api_key, bot['api_key'])

    def test_update_api_key_for_invalid_user(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        result = self.client_post('/json/bots/nonexistentuser@zulip.com/api_key/regenerate')
        self.assert_json_error(result, 'No such user')

    def test_patch_bot_full_name(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'full_name': 'Fred',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        full_name = ujson.loads(result.content)['full_name']
        self.assertEqual('Fred', full_name)

        bot = self.get_bot()
        self.assertEqual('Fred', bot['full_name'])

    def test_patch_bot_avatar(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.avatar_source, UserProfile.AVATAR_FROM_GRAVATAR)

        # Try error case first (too many files):
        with open(os.path.join(TEST_AVATAR_DIR, 'img.png'), 'rb') as fp1, \
             open(os.path.join(TEST_AVATAR_DIR, 'img.gif'), 'rb') as fp2:
            result = self.client_patch_multipart(
                '/json/bots/hambot-bot@zulip.com',
                dict(file1=fp1, file2=fp2))
        self.assert_json_error(result, 'You may only upload one file at a time')

        # HAPPY PATH
        with open(os.path.join(TEST_AVATAR_DIR, 'img.png'), 'rb') as fp:
            result = self.client_patch_multipart(
                '/json/bots/hambot-bot@zulip.com',
                dict(file=fp))
        self.assert_json_success(result)

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.avatar_source, UserProfile.AVATAR_FROM_USER)
        # TODO: check img.png was uploaded properly

    def test_patch_bot_to_stream(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_sending_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        default_sending_stream = ujson.loads(result.content)['default_sending_stream']
        self.assertEqual('Denmark', default_sending_stream)

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_sending_stream'])

    def test_patch_bot_to_stream_not_subscribed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_sending_stream': 'Rome',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        default_sending_stream = ujson.loads(result.content)['default_sending_stream']
        self.assertEqual('Rome', default_sending_stream)

        bot = self.get_bot()
        self.assertEqual('Rome', bot['default_sending_stream'])

    def test_patch_bot_to_stream_none(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_sending_stream': '',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        default_sending_stream = ujson.loads(result.content)['default_sending_stream']
        self.assertEqual(None, default_sending_stream)

        bot = self.get_bot()
        self.assertEqual(None, bot['default_sending_stream'])

    def test_patch_bot_to_stream_private_allowed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_add_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        bot_info = {
            'default_sending_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        default_sending_stream = ujson.loads(result.content)['default_sending_stream']
        self.assertEqual('Denmark', default_sending_stream)

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_sending_stream'])

    def test_patch_bot_to_stream_private_denied(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_remove_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        bot_info = {
            'default_sending_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'Insufficient permission')

    def test_patch_bot_to_stream_not_found(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_sending_stream': 'missing',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'No such stream \'missing\'')

    def test_patch_bot_events_register_stream(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_events_register_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        default_events_register_stream = ujson.loads(result.content)['default_events_register_stream']
        self.assertEqual('Denmark', default_events_register_stream)

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_events_register_stream'])

    def test_patch_bot_events_register_stream_allowed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_add_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_events_register_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        default_events_register_stream = ujson.loads(result.content)['default_events_register_stream']
        self.assertEqual('Denmark', default_events_register_stream)

        bot = self.get_bot()
        self.assertEqual('Denmark', bot['default_events_register_stream'])

    def test_patch_bot_events_register_stream_denied(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_remove_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_events_register_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'Insufficient permission')

    def test_patch_bot_events_register_stream_none(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_events_register_stream': '',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        default_events_register_stream = ujson.loads(result.content)['default_events_register_stream']
        self.assertEqual(None, default_events_register_stream)

        bot = self.get_bot()
        self.assertEqual(None, bot['default_events_register_stream'])

    def test_patch_bot_events_register_stream_not_found(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_events_register_stream': 'missing',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'No such stream \'missing\'')

    def test_patch_bot_default_all_public_streams_true(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_all_public_streams': ujson.dumps(True),
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        default_events_register_stream = ujson.loads(result.content)['default_all_public_streams']
        self.assertEqual(default_events_register_stream, True)

        bot = self.get_bot()
        self.assertEqual(bot['default_all_public_streams'], True)

    def test_patch_bot_default_all_public_streams_false(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_all_public_streams': ujson.dumps(False),
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        default_events_register_stream = ujson.loads(result.content)['default_all_public_streams']
        self.assertEqual(default_events_register_stream, False)

        bot = self.get_bot()
        self.assertEqual(bot['default_all_public_streams'], False)

    def test_patch_bot_via_post(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'full_name': 'Fred',
            'method': 'PATCH'
        }
        result = self.client_post("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        full_name = ujson.loads(result.content)['full_name']
        self.assertEqual('Fred', full_name)

        bot = self.get_bot()
        self.assertEqual('Fred', bot['full_name'])

    def test_patch_bogus_bot(self):
        # type: () -> None
        """Deleting a bogus bot will succeed silently."""
        self.login("hamlet@zulip.com")
        self.create_bot()
        bot_info = {
            'full_name': 'Fred',
        }
        result = self.client_patch("/json/bots/nonexistent-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'No such user')
        self.assert_num_bots_equal(1)

class ChangeSettingsTest(AuthedTestCase):

    def check_well_formed_change_settings_response(self, result):
        # type: (Dict[str, Any]) -> None
        self.assertIn("full_name", result)

    def check_for_toggle_param(self, pattern, param):
        # type: (str, str) -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        json_result = self.client_post(pattern,
                                       {param: ujson.dumps(True)})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.assertEqual(getattr(user_profile, param), True)

        json_result = self.client_post(pattern,
                                       {param: ujson.dumps(False)})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.assertEqual(getattr(user_profile, param), False)

    def test_successful_change_settings(self):
        # type: () -> None
        """
        A call to /json/settings/change with valid parameters changes the user's
        settings correctly and returns correct values.
        """
        self.login("hamlet@zulip.com")
        json_result = self.client_post("/json/settings/change",
            dict(
                full_name='Foo Bar',
                old_password=initial_password('hamlet@zulip.com'),
                new_password='foobar1',
                confirm_password='foobar1',
            )
        )
        self.assert_json_success(json_result)
        result = ujson.loads(json_result.content)
        self.check_well_formed_change_settings_response(result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                full_name, "Foo Bar")
        self.client_post('/accounts/logout/')
        self.login("hamlet@zulip.com", "foobar1")
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    # This is basically a don't-explode test.
    def test_notify_settings(self):
        # type: () -> None
        self.check_for_toggle_param("/json/notify_settings/change", "enable_desktop_notifications")
        self.check_for_toggle_param("/json/notify_settings/change", "enable_stream_desktop_notifications")
        self.check_for_toggle_param("/json/notify_settings/change", "enable_stream_sounds")
        self.check_for_toggle_param("/json/notify_settings/change", "enable_sounds")
        self.check_for_toggle_param("/json/notify_settings/change", "enable_offline_email_notifications")
        self.check_for_toggle_param("/json/notify_settings/change", "enable_offline_push_notifications")
        self.check_for_toggle_param("/json/notify_settings/change", "enable_digest_emails")

    def test_ui_settings(self):
        # type: () -> None
        self.check_for_toggle_param("/json/ui_settings/change", "autoscroll_forever")
        self.check_for_toggle_param("/json/ui_settings/change", "default_desktop_notifications")

    def test_toggling_left_side_userlist(self):
        # type: () -> None
        self.check_for_toggle_param("/json/left_side_userlist", "left_side_userlist")

    def test_time_setting(self):
        # type: () -> None
        self.check_for_toggle_param("/json/time_setting", "twenty_four_hour_time")

    def test_enter_sends_setting(self):
        # type: () -> None
        self.check_for_toggle_param('/json/users/me/enter-sends', "enter_sends")

    def test_mismatching_passwords(self):
        # type: () -> None
        """
        new_password and confirm_password must match
        """
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/settings/change",
            dict(
                new_password="mismatched_password",
                confirm_password="not_the_same",
            )
        )
        self.assert_json_error(result,
                "New password must match confirmation password!")

    def test_wrong_old_password(self):
        # type: () -> None
        """
        new_password and confirm_password must match
        """
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/settings/change",
            dict(
                old_password='bad_password',
                new_password="ignored",
                confirm_password="ignored",
            )
        )
        self.assert_json_error(result, "Wrong password!")

    def test_changing_nothing_returns_error(self):
        # type: () -> None
        """
        We need to supply at least one non-empty parameter
        to this API, or it should fail.  (Eventually, we should
        probably use a patch interface for these changes.)
        """
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/settings/change",
            dict(
                old_password='ignored',
            )
        )
        self.assert_json_error(result, "No new data supplied")

    def test_change_default_language(self):
        # type: () -> None
        """
        Test changing the default language of the user.
        """
        email = "hamlet@zulip.com"
        self.login(email)
        german = "de"
        data = dict(default_language=ujson.dumps(german))
        result = self.client_post("/json/language_setting", data)
        self.assert_json_success(result)
        user_profile = get_user_profile_by_email(email)
        self.assertEqual(user_profile.default_language, german)

        # Test to make sure invalid languages are not accepted
        # and saved in the db.
        invalid_lang = "invalid_lang"
        data = dict(default_language=ujson.dumps(invalid_lang))
        result = self.client_post("/json/language_setting", data)
        self.assert_json_error(result, "Invalid language '%s'" % (invalid_lang,))
        user_profile = get_user_profile_by_email(email)
        self.assertNotEqual(user_profile.default_language, invalid_lang)

class GetProfileTest(AuthedTestCase):

    def common_update_pointer(self, email, pointer):
        # type: (text_type, int) -> None
        self.login(email)
        result = self.client_put("/json/users/me/pointer", {"pointer": pointer})
        self.assert_json_success(result)

    def common_get_profile(self, email):
        # type: (str) -> Dict[text_type, Any]
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

    def test_cache_behavior(self):
        # type: () -> None
        with queries_captured() as queries:
            with simulated_empty_cache() as cache_queries:
                user_profile = get_user_profile_by_email('hamlet@zulip.com')

        self.assert_length(queries, 1)
        self.assert_length(cache_queries, 1, exact=True)
        self.assertEqual(user_profile.email, 'hamlet@zulip.com')

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

        result = self.client_put("/json/users/me/pointer", {"pointer": 99999999})
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
                    get_avatar_url(user_profile.avatar_source, user_profile.email),
                )

class UserPresenceTests(AuthedTestCase):
    def test_get_empty(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/get_active_statuses")

        self.assert_json_success(result)
        json = ujson.loads(result.content)
        for email, presence in json['presences'].items():
            self.assertEqual(presence, {})

    def test_set_idle(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        self.login(email)
        client = 'website'

        def test_result(result):
            # type: (HttpResponse) -> datetime.datetime
            self.assert_json_success(result)
            json = ujson.loads(result.content)
            self.assertEqual(json['presences'][email][client]['status'], 'idle')
            self.assertIn('timestamp', json['presences'][email][client])
            self.assertIsInstance(json['presences'][email][client]['timestamp'], int)
            self.assertEqual(list(json['presences'].keys()), ['hamlet@zulip.com'])
            return json['presences'][email][client]['timestamp']

        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        test_result(result)

        result = self.client_post("/json/get_active_statuses", {})
        timestamp = test_result(result)

        email = "othello@zulip.com"
        self.login(email)
        self.client_post("/json/users/me/presence", {'status': 'idle'})
        result = self.client_post("/json/get_active_statuses", {})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')
        self.assertEqual(sorted(json['presences'].keys()), ['hamlet@zulip.com', 'othello@zulip.com'])
        newer_timestamp = json['presences'][email][client]['timestamp']
        self.assertGreaterEqual(newer_timestamp, timestamp)

    def test_set_active(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        client = 'website'

        self.client_post("/json/users/me/presence", {'status': 'idle'})
        result = self.client_post("/json/get_active_statuses", {})

        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences']["hamlet@zulip.com"][client]['status'], 'idle')

        email = "othello@zulip.com"
        self.login("othello@zulip.com")
        self.client_post("/json/users/me/presence", {'status': 'idle'})
        result = self.client_post("/json/get_active_statuses", {})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')

        self.client_post("/json/users/me/presence", {'status': 'active'})
        result = self.client_post("/json/get_active_statuses", {})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'active')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')

    def test_no_mit(self):
        # type: () -> None
        """Zephyr mirror realms such as MIT never get a list of users"""
        self.login("espuser@mit.edu")
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'], {})

    def test_same_realm(self):
        # type: () -> None
        self.login("espuser@mit.edu")
        self.client_post("/json/users/me/presence", {'status': 'idle'})
        result = self.client_post("/accounts/logout/")

        # Ensure we don't see hamlet@zulip.com information leakage
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/users/me/presence", {'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences']["hamlet@zulip.com"]["website"]['status'], 'idle')
        # We only want @zulip.com emails
        for email in json['presences'].keys():
            self.assertEqual(split_email_to_domain(email), 'zulip.com')

class AlertWordTests(AuthedTestCase):
    interesting_alert_word_list = ['alert', 'multi-word word', u'☃']

    def test_internal_endpoint(self):
        # type: () -> None
        email = "cordelia@zulip.com"
        self.login(email)

        params = {
            'alert_words': ujson.dumps(['milk', 'cookies'])
        }
        result = self.client_post('/json/users/me/alert_words', params)
        self.assert_json_success(result)
        user = get_user_profile_by_email(email)
        words = user_alert_words(user)
        self.assertEqual(words, ['milk', 'cookies'])


    def test_default_no_words(self):
        # type: () -> None
        """
        Users start out with no alert words.
        """
        email = "cordelia@zulip.com"
        user = get_user_profile_by_email(email)

        words = user_alert_words(user)

        self.assertEqual(words, [])

    def test_add_word(self):
        # type: () -> None
        """
        add_user_alert_words can add multiple alert words at once.
        """
        email = "cordelia@zulip.com"
        user = get_user_profile_by_email(email)

        # Add several words, including multi-word and non-ascii words.
        add_user_alert_words(user, self.interesting_alert_word_list)

        words = user_alert_words(user)
        self.assertEqual(words, self.interesting_alert_word_list)

    def test_remove_word(self):
        # type: () -> None
        """
        Removing alert words works via remove_user_alert_words, even
        for multi-word and non-ascii words.
        """
        email = "cordelia@zulip.com"
        user = get_user_profile_by_email(email)

        add_user_alert_words(user, self.interesting_alert_word_list)

        theoretical_remaining_alerts = self.interesting_alert_word_list[:]

        for alert_word in self.interesting_alert_word_list:
            remove_user_alert_words(user, alert_word)
            theoretical_remaining_alerts.remove(alert_word)
            actual_remaining_alerts = user_alert_words(user)
            self.assertEqual(actual_remaining_alerts,
                             theoretical_remaining_alerts)

    def test_realm_words(self):
        # type: () -> None
        """
        We can gather alert words for an entire realm via
        alert_words_in_realm. Alerts added for one user do not impact other
        users.
        """
        email = "cordelia@zulip.com"
        user1 = get_user_profile_by_email(email)

        add_user_alert_words(user1, self.interesting_alert_word_list)

        email = "othello@zulip.com"
        user2 = get_user_profile_by_email(email)
        add_user_alert_words(user2, ['another'])

        realm_words = alert_words_in_realm(user2.realm)
        self.assertEqual(len(realm_words), 2)
        self.assertEqual(list(realm_words.keys()), [user1.id, user2.id])
        self.assertEqual(realm_words[user1.id],
                         self.interesting_alert_word_list)
        self.assertEqual(realm_words[user2.id], ['another'])

    def test_json_list_default(self):
        # type: () -> None
        self.login("hamlet@zulip.com")

        result = self.client_get('/json/users/me/alert_words')
        self.assert_json_success(result)

        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], [])

    def test_json_list_add(self):
        # type: () -> None
        self.login("hamlet@zulip.com")

        result = self.client_put('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)


        result = self.client_get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['one', 'two', 'three'])

    def test_json_list_remove(self):
        # type: () -> None
        self.login("hamlet@zulip.com")

        result = self.client_put('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)

        result = self.client_delete('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one'])})
        self.assert_json_success(result)

        result = self.client_get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['two', 'three'])

    def test_json_list_set(self):
        # type: () -> None
        self.login("hamlet@zulip.com")

        result = self.client_put('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)

        result = self.client_post('/json/users/me/alert_words', {'alert_words': ujson.dumps(['a', 'b', 'c'])})
        self.assert_json_success(result)

        result = self.client_get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['a', 'b', 'c'])

    def message_does_alert(self, user_profile, message):
        # type: (UserProfile, text_type) -> bool
        """Send a bunch of messages as othello, so Hamlet is notified"""
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, message)
        user_message = most_recent_usermessage(user_profile)
        return 'has_alert_word' in user_message.flags_list()

    def test_alert_flags(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile_hamlet = get_user_profile_by_email("hamlet@zulip.com")

        result = self.client_put('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)

        result = self.client_get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['one', 'two', 'three'])

        # Alerts in the middle of messages work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "Normal alert one time"))
        # Alerts at the end of messages work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "Normal alert one"))
        # Alerts at the beginning of messages work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "two normal alerts"))
        # Alerts with surrounding punctuation work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "This one? should alert"))
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "Definitely time for three."))
        # Multiple alerts in a message work.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "One two three o'clock"))
        # Alerts are case-insensitive.
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "One o'clock"))
        self.assertTrue(self.message_does_alert(user_profile_hamlet, "Case of ONE, won't stop me"))

        # We don't cause alerts for matches in URLs.
        self.assertFalse(self.message_does_alert(user_profile_hamlet, "Don't alert on http://t.co/one/ urls"))
        self.assertFalse(self.message_does_alert(user_profile_hamlet, "Don't alert on http://t.co/one urls"))

class HomeTest(AuthedTestCase):
    @slow('big method')
    def test_home(self):
        # type: () -> None

        # Keep this list sorted!!!
        html_bits = [
            'Compose your message here...',
            'Exclude messages with topic',
            'Get started',
            'Keyboard shortcuts',
            'Loading...',
            'Manage Streams',
            'Narrow by topic',
            'Next message',
            'SHARE THE LOVE',
            'Search streams',
            'Welcome to Zulip',
            'pygments.css',
            'var page_params',
        ]

        # Keep this list sorted!!!
        expected_keys = [
            "alert_words",
            "autoscroll_forever",
            "avatar_url",
            "bot_list",
            "can_create_streams",
            "cross_realm_user_emails",
            "debug_mode",
            "default_desktop_notifications",
            "default_language",
            "desktop_notifications_enabled",
            "development_environment",
            "domain",
            "email",
            "email_dict",
            "enable_digest_emails",
            "enable_offline_email_notifications",
            "enable_offline_push_notifications",
            "enter_sends",
            "event_queue_id",
            "first_in_realm",
            "fullname",
            "furthest_read_time",
            "has_mobile_devices",
            "have_initial_messages",
            "initial_pointer",
            "initial_presences",
            "initial_servertime",
            "is_admin",
            "is_zephyr_mirror_realm",
            "language_list",
            "last_event_id",
            "left_side_userlist",
            "login_page",
            "mandatory_topics",
            "max_message_id",
            "maxfilesize",
            "muted_topics",
            "name_changes_disabled",
            "narrow",
            "narrow_stream",
            "needs_tutorial",
            "neversubbed_info",
            "notifications_stream",
            "password_auth_enabled",
            "people_list",
            "poll_timeout",
            "presence_disabled",
            "product_name",
            "prompt_for_invites",
            "realm_allow_message_editing",
            "realm_create_stream_by_admins_only",
            "realm_default_language",
            "realm_default_streams",
            "realm_emoji",
            "realm_filters",
            "realm_invite_by_admins_only",
            "realm_invite_required",
            "realm_message_content_edit_limit_seconds",
            "realm_name",
            "realm_restricted_to_domain",
            "referrals",
            "save_stacktraces",
            "server_generation",
            "share_the_love",
            "show_digest_email",
            "sounds_enabled",
            "stream_desktop_notifications_enabled",
            "stream_sounds_enabled",
            "subbed_info",
            "test_suite",
            "twenty_four_hour_time",
            "unread_count",
            "unsubbed_info",
        ]

        email = "hamlet@zulip.com"

        # Verify fails if logged-out
        result = self.client_get('/')
        self.assertEqual(result.status_code, 302)

        # Verify succeeds once logged-in
        self.login(email)
        with \
                patch('zerver.lib.actions.request_event_queue', return_value=42), \
                patch('zerver.lib.actions.get_user_events', return_value=[]):
            result = self.client_get('/', dict(stream='Denmark'))
        html = result.content.decode('utf-8')

        for html_bit in html_bits:
            if html_bit not in html:
                self.fail('%s not in result' % (html_bit,))

        lines = html.split('\n')
        page_params_line = [l for l in lines if l.startswith('var page_params')][0]
        page_params_json = page_params_line.split(' = ')[1].rstrip(';')
        page_params = ujson.loads(page_params_json)

        actual_keys = sorted([str(k) for k in page_params.keys()])
        self.assertEqual(actual_keys, expected_keys)

        # TODO: Inspect the page_params data further.
        # print(ujson.dumps(page_params, indent=2))

class MutedTopicsTests(AuthedTestCase):
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


class TestMissedMessages(AuthedTestCase):
    def normalize_string(self, s):
        # type: (text_type) -> text_type
        s = s.strip()
        return re.sub(r'\s+', ' ', s)

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_extra_context_in_missed_stream_messages(self, mock_random_token):
        # type: (MagicMock) -> None
        tokens = [str(random.getrandbits(32)) for _ in range(30)]
        mock_random_token.side_effect = tokens

        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '0')
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '1')
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '2')
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '3')
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '4')
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '5')
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '6')
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '7')
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '8')
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '9')
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '10')
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, '11', subject='test2')
        msg_id = self.send_message("othello@zulip.com", "denmark", Recipient.STREAM, '@**hamlet**')

        othello = get_user_profile_by_email('othello@zulip.com')
        hamlet = get_user_profile_by_email('hamlet@zulip.com')
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])

        msg = mail.outbox[0]
        reply_to_addresses = [settings.EMAIL_GATEWAY_PATTERN % (u'mm' + t)
                              for t in tokens]
        sender = 'Zulip <{}>'.format(settings.NOREPLY_EMAIL_ADDRESS)

        self.assertEquals(len(mail.outbox), 1)
        self.assertEqual(msg.from_email, "%s <%s>" % (othello.full_name, othello.email))
        self.assertIn(msg.extra_headers['Reply-To'], reply_to_addresses)
        self.assertEqual(msg.extra_headers['Sender'], sender)
        self.assertIn(
            'Denmark > test Othello, the Moor of Venice 1 2 3 4 5 6 7 8 9 10 @**hamlet**',
            self.normalize_string(mail.outbox[0].body),
        )

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_extra_context_in_personal_missed_stream_messages(self, mock_random_token):
        # type: (MagicMock) -> None
        tokens = [str(random.getrandbits(32)) for _ in range(30)]
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com", "hamlet@zulip.com",
                                   Recipient.PERSONAL,
                                   'Extremely personal message!')

        othello = get_user_profile_by_email('othello@zulip.com')
        hamlet = get_user_profile_by_email('hamlet@zulip.com')
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])

        msg = mail.outbox[0]
        reply_to_addresses = [settings.EMAIL_GATEWAY_PATTERN % (u'mm' + t)
                              for t in tokens]
        sender = 'Zulip <{}>'.format(settings.NOREPLY_EMAIL_ADDRESS)

        self.assertEquals(len(mail.outbox), 1)
        self.assertEqual(msg.from_email, "%s <%s>" % (othello.full_name, othello.email))
        self.assertIn(msg.extra_headers['Reply-To'], reply_to_addresses)
        self.assertEqual(msg.extra_headers['Sender'], sender)
        self.assertIn('You and Othello, the Moor of Venice Extremely personal message!',
                      self.normalize_string(msg.body))

    @patch('zerver.lib.email_mirror.generate_random_token')
    def test_extra_context_in_huddle_missed_stream_messages(self, mock_random_token):
        # type: (MagicMock) -> None
        tokens = [str(random.getrandbits(32)) for _ in range(30)]
        mock_random_token.side_effect = tokens

        msg_id = self.send_message("othello@zulip.com",
                                   ["hamlet@zulip.com", "iago@zulip.com"],
                                   Recipient.PERSONAL,
                                   'Group personal message!')

        othello = get_user_profile_by_email('othello@zulip.com')
        hamlet = get_user_profile_by_email('hamlet@zulip.com')
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])

        msg = mail.outbox[0]
        reply_to_addresses = [settings.EMAIL_GATEWAY_PATTERN % (u'mm' + t)
                              for t in tokens]
        sender = 'Zulip <{}>'.format(settings.NOREPLY_EMAIL_ADDRESS)

        self.assertEquals(len(mail.outbox), 1)
        self.assertEqual(msg.from_email, "%s <%s>" % (othello.full_name, othello.email))
        self.assertIn(msg.extra_headers['Reply-To'], reply_to_addresses)
        self.assertEqual(msg.extra_headers['Sender'], sender)
        body = ('You and Iago, Othello, the Moor of Venice Othello,'
                ' the Moor of Venice Group personal message')

        self.assertIn(body, self.normalize_string(msg.body))

class TestOpenRealms(AuthedTestCase):
    def test_open_realm_logic(self):
        # type: () -> None
        mit_realm = get_realm("mit.edu")
        self.assertEquals(get_unique_open_realm(), None)
        mit_realm.restricted_to_domain = False
        mit_realm.save()
        self.assertTrue(completely_open(mit_realm.domain))
        self.assertEquals(get_unique_open_realm(), None)
        settings.VOYAGER = True
        self.assertEquals(get_unique_open_realm(), mit_realm)
        # Restore state
        settings.VOYAGER = False
        mit_realm.restricted_to_domain = True
        mit_realm.save()
