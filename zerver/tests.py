# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.test import TestCase

from zerver.lib.test_helpers import (
    queries_captured, simulated_empty_cache,
    simulated_queue_client, tornado_redirected_to_list, AuthedTestCase,
    most_recent_usermessage, most_recent_message,
)

from zerver.models import UserProfile, Recipient, \
    Realm, Client, UserActivity, \
    get_user_profile_by_email, split_email_to_domain, get_realm, \
    get_client, get_stream, Message

from zerver.lib.avatar import get_avatar_url
from zerver.lib.initial_password import initial_password
from zerver.lib.actions import \
    get_emails_from_user_ids, do_deactivate_user, do_reactivate_user, \
    do_change_is_admin, extract_recipients, \
    do_set_realm_name, get_realm_name, do_deactivate_realm, \
    do_add_subscription, do_remove_subscription, do_make_stream_private
from zerver.lib.alert_words import alert_words_in_realm, user_alert_words, \
    add_user_alert_words, remove_user_alert_words
from zerver.lib.notifications import handle_missedmessage_emails
from zerver.middleware import is_slow_query

from zerver.worker import queue_processors

from django.conf import settings
from django.core import mail
import datetime
import os
import re
import sys
import time
import ujson

def bail(msg):
    print '\nERROR: %s\n' % (msg,)
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

def find_dict(lst, k, v):
    for dct in lst:
        if dct[k] == v:
            return dct
    raise Exception('Cannot find element in list where key %s == %s' % (k, v))

class SlowQueryTest(TestCase):
    def test_is_slow_query(self):
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
        user_profile = get_user_profile_by_email(email)
        self.assertEqual(user_profile.realm.name, new_realm_name)

    def test_do_set_realm_name_caching(self):
        # The main complicated thing about setting realm names is fighting the
        # cache, and we start by populating the cache for Hamlet, and we end
        # by checking the cache to ensure that the new value is there.
        get_user_profile_by_email('hamlet@zulip.com')
        realm = Realm.objects.get(domain='zulip.com')
        new_name = 'Zed You Elle Eye Pea'
        do_set_realm_name(realm, new_name)
        self.assertEqual(get_realm_name(realm.domain), new_name)
        self.assert_user_profile_cache_gets_new_name('hamlet@zulip.com', new_name)

    def test_do_set_realm_name_events(self):
        realm = Realm.objects.get(domain='zulip.com')
        new_name = 'Puliz'
        events = []
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
        new_name = 'Mice will play while the cat is away'

        email = 'othello@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        do_change_is_admin(user_profile, False)

        req = dict(name=ujson.dumps(new_name))
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, 'Must be a realm administrator')

    def test_do_deactivate_realm(self):
        # The main complicated thing about deactivating realm names is updating the
        # cache, and we start by populating the cache for Hamlet, and we end
        # by checking the cache to ensure that his realm appears to be deactivated.
        # You can make this test fail by disabling cache.flush_realm().
        get_user_profile_by_email('hamlet@zulip.com')
        realm = Realm.objects.get(domain='zulip.com')
        do_deactivate_realm(realm)
        user = get_user_profile_by_email('hamlet@zulip.com')
        self.assertTrue(user.realm.deactivated)

class PermissionTest(AuthedTestCase):
    def test_get_admin_users(self):
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        do_change_is_admin(user_profile, False)
        admin_users = user_profile.realm.get_admin_users()
        self.assertFalse(user_profile in admin_users)
        do_change_is_admin(user_profile, True)
        admin_users = user_profile.realm.get_admin_users()
        self.assertTrue(user_profile in admin_users)

    def test_admin_api(self):
        self.login('hamlet@zulip.com')
        admin = get_user_profile_by_email('hamlet@zulip.com')
        user = get_user_profile_by_email('othello@zulip.com')
        realm = admin.realm
        do_change_is_admin(admin, True)

        # Make sure we see is_admin flag in /json/users
        result = self.client.get('/json/users')
        self.assert_json_success(result)
        members = ujson.loads(result.content)['members']
        hamlet = find_dict(members, 'email', 'hamlet@zulip.com')
        self.assertTrue(hamlet['is_admin'])
        othello = find_dict(members, 'email', 'othello@zulip.com')
        self.assertFalse(othello['is_admin'])

        # Giveth
        req = dict(is_admin=ujson.dumps(True))

        events = []
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

class WorkerTest(TestCase):
    class FakeClient:
        def __init__(self):
            self.consumers = {}
            self.queue = []

        def register_json_consumer(self, queue_name, callback):
            self.consumers[queue_name] = callback

        def start_consuming(self):
            for queue_name, data in self.queue:
                callback = self.consumers[queue_name]
                callback(data)


    def test_UserActivityWorker(self):
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
            worker.start()
            activity_records = UserActivity.objects.filter(
                    user_profile = user.id,
                    client = get_client('ios')
            )
            self.assertTrue(len(activity_records), 1)
            self.assertTrue(activity_records[0].count, 1)

    def test_error_handling(self):
        processed = []

        @queue_processors.assign_queue('flake')
        class FlakyWorker(queue_processors.QueueProcessingWorker):
            def consume(self, data):
                if data == 'freak out':
                    raise Exception('Freaking out!')
                processed.append(data)

            def _log_problem(self):
                # keep the tests quiet
                pass

        fake_client = self.FakeClient()
        for msg in ['good', 'fine', 'freak out', 'back to normal']:
            fake_client.queue.append(('flake', msg))

        fn = os.path.join(settings.QUEUE_ERROR_DIR, 'flake.errors')
        try:
            os.remove(fn)
        except OSError:
            pass

        with simulated_queue_client(lambda: fake_client):
            worker = FlakyWorker()
            worker.start()

        self.assertEqual(processed, ['good', 'fine', 'back to normal'])
        line = open(fn).readline().strip()
        event = ujson.loads(line.split('\t')[1])
        self.assertEqual(event, 'freak out')

class ActivityTest(AuthedTestCase):
    def test_activity(self):
        self.login("hamlet@zulip.com")
        client, _ = Client.objects.get_or_create(name='website')
        query = '/json/update_pointer'
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
            self.client.get('/activity')

        self.assert_length(queries, 12)

class UserProfileTest(TestCase):
    def test_get_emails_from_user_ids(self):
        hamlet = get_user_profile_by_email('hamlet@zulip.com')
        othello = get_user_profile_by_email('othello@zulip.com')
        dct = get_emails_from_user_ids([hamlet.id, othello.id])
        self.assertEqual(dct[hamlet.id], 'hamlet@zulip.com')
        self.assertEqual(dct[othello.id], 'othello@zulip.com')

class UserChangesTest(AuthedTestCase):
    def test_update_api_key(self):
        email = "hamlet@zulip.com"
        self.login(email)
        user = get_user_profile_by_email(email)
        old_api_key = user.api_key
        result = self.client.post('/json/users/me/api_key/regenerate')
        self.assert_json_success(result)
        new_api_key = ujson.loads(result.content)['api_key']
        self.assertNotEqual(old_api_key, new_api_key)
        user = get_user_profile_by_email(email)
        self.assertEqual(new_api_key, user.api_key)

class ActivateTest(AuthedTestCase):
    def test_basics(self):
        user = get_user_profile_by_email('hamlet@zulip.com')
        do_deactivate_user(user)
        self.assertFalse(user.is_active)
        do_reactivate_user(user)
        self.assertTrue(user.is_active)

    def test_api(self):
        admin = get_user_profile_by_email('othello@zulip.com')
        do_change_is_admin(admin, True)
        self.login('othello@zulip.com')

        user = get_user_profile_by_email('hamlet@zulip.com')
        self.assertTrue(user.is_active)

        result = self.client_delete('/json/users/hamlet@zulip.com')
        self.assert_json_success(result)
        user = get_user_profile_by_email('hamlet@zulip.com')
        self.assertFalse(user.is_active)

        result = self.client.post('/json/users/hamlet@zulip.com/reactivate')
        self.assert_json_success(result)
        user = get_user_profile_by_email('hamlet@zulip.com')
        self.assertTrue(user.is_active)

        # Can not deactivate a user as a bot
        result = self.client_delete('/json/bots/hamlet@zulip.com')
        self.assert_json_error(result, 'No such bot')

class BotTest(AuthedTestCase):
    def assert_num_bots_equal(self, count):
        result = self.client.get("/json/bots")
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(count, len(json['bots']))

    def create_bot(self, **extras):
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        bot_info.update(extras)
        result = self.client.post("/json/bots", bot_info)
        self.assert_json_success(result)
        return ujson.loads(result.content)

    def deactivate_bot(self):
        result = self.client_delete("/json/bots/hambot-bot@zulip.com")
        self.assert_json_success(result)

    def test_add_bot(self):
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        events = []
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

    def test_add_bot_with_default_sending_stream(self):
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_sending_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Denmark')

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.default_sending_stream.name, 'Denmark')

    def test_add_bot_with_default_sending_stream_not_subscribed(self):
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_sending_stream='Rome')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_sending_stream'], 'Rome')

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.default_sending_stream.name, 'Rome')

    def test_add_bot_with_default_sending_stream_private_allowed(self):
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_add_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        self.assert_num_bots_equal(0)
        events = []
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
        result = self.client.post("/json/bots", bot_info)
        self.assert_json_error(result, 'Insufficient permission')

    def test_add_bot_with_default_events_register_stream(self):
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_events_register_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_events_register_stream'], 'Denmark')

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.default_events_register_stream.name, 'Denmark')

    def test_add_bot_with_default_events_register_stream_private_allowed(self):
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_add_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        self.assert_num_bots_equal(0)
        events = []
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
        result = self.client.post("/json/bots", bot_info)
        self.assert_json_error(result, 'Insufficient permission')

    def test_add_bot_with_default_all_public_streams(self):
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        result = self.create_bot(default_all_public_streams=ujson.dumps(True))
        self.assert_num_bots_equal(1)
        self.assertTrue(result['default_all_public_streams'])

        profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(profile.default_all_public_streams, True)

    def test_deactivate_bot(self):
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)
        self.deactivate_bot()
        # You can deactivate the same bot twice.
        self.deactivate_bot()
        self.assert_num_bots_equal(0)

    def test_deactivate_bogus_bot(self):
        # Deleting a bogus bot will succeed silently.
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)
        result = self.client_delete("/json/bots/bogus-bot@zulip.com")
        self.assert_json_error(result, 'No such bot')
        self.assert_num_bots_equal(1)

    def test_bot_deactivation_attacks(self):
        # You cannot deactivate somebody else's bot.
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
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)

        # Have Othello try to mess with Hamlet's bots.
        self.login("othello@zulip.com")

        result = self.client.post("/json/bots/hambot-bot@zulip.com/api_key/regenerate")
        self.assert_json_error(result, 'Insufficient permission')

        bot_info = {
            'full_name': 'Fred',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'Insufficient permission')

    def get_bot(self):
        result = self.client.get("/json/bots")
        bots = ujson.loads(result.content)['bots']
        return bots[0]

    def test_update_api_key(self):
        self.login("hamlet@zulip.com")
        self.create_bot()
        bot = self.get_bot()
        old_api_key = bot['api_key']
        result = self.client.post('/json/bots/hambot-bot@zulip.com/api_key/regenerate')
        self.assert_json_success(result)
        new_api_key = ujson.loads(result.content)['api_key']
        self.assertNotEqual(old_api_key, new_api_key)
        bot = self.get_bot()
        self.assertEqual(new_api_key, bot['api_key'])

    def test_patch_bot_full_name(self):
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
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

    def test_patch_bot_to_stream(self):
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
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
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
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
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
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
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_add_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
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
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_remove_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
        self.assert_json_success(result)

        bot_info = {
            'default_sending_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'Insufficient permission')

    def test_patch_bot_to_stream_not_found(self):
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_sending_stream': 'missing',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'No such stream \'missing\'')

    def test_patch_bot_events_register_stream(self):
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
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
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_add_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
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
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        do_remove_subscription(user_profile, stream)
        do_make_stream_private(user_profile.realm, "Denmark")

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_events_register_stream': 'Denmark',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'Insufficient permission')

    def test_patch_bot_events_register_stream_none(self):
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
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
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'default_events_register_stream': 'missing',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'No such stream \'missing\'')

    def test_patch_bot_default_all_public_streams_true(self):
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
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
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
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
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'full_name': 'Fred',
            'method': 'PATCH'
        }
        result = self.client.post("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        full_name = ujson.loads(result.content)['full_name']
        self.assertEqual('Fred', full_name)

        bot = self.get_bot()
        self.assertEqual('Fred', bot['full_name'])

    def test_patch_bogus_bot(self):
        # Deleting a bogus bot will succeed silently.
        self.login("hamlet@zulip.com")
        self.create_bot()
        bot_info = {
            'full_name': 'Fred',
        }
        result = self.client_patch("/json/bots/nonexistent-bot@zulip.com", bot_info)
        self.assert_json_error(result, 'No such user')
        self.assert_num_bots_equal(1)

class ChangeSettingsTest(AuthedTestCase):

    def post_with_params(self, modified_params):
        post_params = {"full_name": "Foo Bar",
                  "old_password": initial_password("hamlet@zulip.com"),
                  "new_password": "foobar1", "confirm_password": "foobar1",
        }
        post_params.update(modified_params)
        return self.client.post("/json/settings/change", dict(post_params))

    def check_well_formed_change_settings_response(self, result):
        self.assertIn("full_name", result)

    def test_successful_change_settings(self):
        """
        A call to /json/settings/change with valid parameters changes the user's
        settings correctly and returns correct values.
        """
        self.login("hamlet@zulip.com")
        json_result = self.post_with_params({})
        self.assert_json_success(json_result)
        result = ujson.loads(json_result.content)
        self.check_well_formed_change_settings_response(result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                full_name, "Foo Bar")
        self.client.post('/accounts/logout/')
        self.login("hamlet@zulip.com", "foobar1")
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        self.assertEqual(self.client.session['_auth_user_id'], user_profile.id)

    def test_notify_settings(self):
        # This is basically a don't-explode test.
        self.login("hamlet@zulip.com")
        json_result = self.client.post("/json/notify_settings/change",
                                       {"enable_desktop_notifications": ujson.dumps(False)})
        self.assert_json_success(json_result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                enable_desktop_notifications, False)

    def test_ui_settings(self):
        self.login("hamlet@zulip.com")

        json_result = self.client.post("/json/ui_settings/change",
                                       {"autoscroll_forever": ujson.dumps(True)})
        self.assert_json_success(json_result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                enable_desktop_notifications, True)

        json_result = self.client.post("/json/ui_settings/change",
                                       {"autoscroll_forever": ujson.dumps(False)})
        self.assert_json_success(json_result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                         autoscroll_forever, False)

        json_result = self.client.post("/json/ui_settings/change",
                                       {"default_desktop_notifications": ujson.dumps(True)})
        self.assert_json_success(json_result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                default_desktop_notifications, True)

        json_result = self.client.post("/json/ui_settings/change",
                                       {"default_desktop_notifications": ujson.dumps(False)})
        self.assert_json_success(json_result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                default_desktop_notifications, False)

    def test_missing_params(self):
        """
        full_name is a required POST parameter for json_change_settings.
        (enable_desktop_notifications is false by default, and password is
        only required if you are changing it)
        """
        self.login("hamlet@zulip.com")

        result = self.client.post("/json/settings/change", {})
        self.assert_json_error(result,
                "Missing '%s' argument" % ("full_name",))

    def test_mismatching_passwords(self):
        """
        new_password and confirm_password must match
        """
        self.login("hamlet@zulip.com")
        result = self.post_with_params({"new_password": "mismatched_password"})
        self.assert_json_error(result,
                "New password must match confirmation password!")

    def test_wrong_old_password(self):
        """
        new_password and confirm_password must match
        """
        self.login("hamlet@zulip.com")
        result = self.post_with_params({"old_password": "bad_password"})
        self.assert_json_error(result, "Wrong password!")

class GetProfileTest(AuthedTestCase):

    def common_update_pointer(self, email, pointer):
        self.login(email)
        result = self.client.post("/json/update_pointer", {"pointer": pointer})
        self.assert_json_success(result)

    def common_get_profile(self, email):
        user_profile = get_user_profile_by_email(email)
        self.send_message(email, "Verona", Recipient.STREAM, "hello")

        result = self.client.get("/api/v1/users/me", **self.api_auth(email))

        max_id = most_recent_message(user_profile).id

        self.assert_json_success(result)
        json = ujson.loads(result.content)

        self.assertIn("client_id", json)
        self.assertIn("max_message_id", json)
        self.assertIn("pointer", json)

        self.assertEqual(json["max_message_id"], max_id)
        return json

    def test_cache_behavior(self):
        with queries_captured() as queries:
            with simulated_empty_cache() as cache_queries:
                user_profile = get_user_profile_by_email('hamlet@zulip.com')

        self.assert_length(queries, 1)
        self.assert_length(cache_queries, 1, exact=True)
        self.assertEqual(user_profile.email, 'hamlet@zulip.com')

    def test_api_get_empty_profile(self):
        """
        Ensure get_profile returns a max message id and returns successfully
        """
        json = self.common_get_profile("othello@zulip.com")
        self.assertEqual(json["pointer"], -1)

    def test_profile_with_pointer(self):
        """
        Ensure get_profile returns a proper pointer id after the pointer is updated
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

        result = self.client.post("/json/update_pointer", {"pointer": 99999999})
        self.assert_json_error(result, "Invalid message ID")

    def test_get_all_profiles_avatar_urls(self):
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        result = self.client.get("/api/v1/users", **self.api_auth('hamlet@zulip.com'))
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
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/get_active_statuses")

        self.assert_json_success(result)
        json = ujson.loads(result.content)
        for email, presence in json['presences'].items():
            self.assertEqual(presence, {})

    def test_set_idle(self):
        email = "hamlet@zulip.com"
        self.login(email)
        client = 'website'

        def test_result(result):
            self.assert_json_success(result)
            json = ujson.loads(result.content)
            self.assertEqual(json['presences'][email][client]['status'], 'idle')
            self.assertIn('timestamp', json['presences'][email][client])
            self.assertIsInstance(json['presences'][email][client]['timestamp'], int)
            self.assertEqual(json['presences'].keys(), ['hamlet@zulip.com'])
            return json['presences'][email][client]['timestamp']

        result = self.client.post("/json/update_active_status", {'status': 'idle'})
        test_result(result)

        result = self.client.post("/json/get_active_statuses", {})
        timestamp = test_result(result)

        email = "othello@zulip.com"
        self.login(email)
        self.client.post("/json/update_active_status", {'status': 'idle'})
        result = self.client.post("/json/get_active_statuses", {})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')
        self.assertEqual(json['presences'].keys(), ['hamlet@zulip.com', 'othello@zulip.com'])
        newer_timestamp = json['presences'][email][client]['timestamp']
        self.assertGreaterEqual(newer_timestamp, timestamp)

    def test_set_active(self):
        self.login("hamlet@zulip.com")
        client = 'website'

        self.client.post("/json/update_active_status", {'status': 'idle'})
        result = self.client.post("/json/get_active_statuses", {})

        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences']["hamlet@zulip.com"][client]['status'], 'idle')

        email = "othello@zulip.com"
        self.login("othello@zulip.com")
        self.client.post("/json/update_active_status", {'status': 'idle'})
        result = self.client.post("/json/get_active_statuses", {})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')

        self.client.post("/json/update_active_status", {'status': 'active'})
        result = self.client.post("/json/get_active_statuses", {})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'active')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')

    def test_no_mit(self):
        # MIT never gets a list of users
        self.login("espuser@mit.edu")
        result = self.client.post("/json/update_active_status", {'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'], {})

    def test_same_realm(self):
        self.login("espuser@mit.edu")
        self.client.post("/json/update_active_status", {'status': 'idle'})
        result = self.client.post("/accounts/logout/")

        # Ensure we don't see hamlet@zulip.com information leakage
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/update_active_status", {'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences']["hamlet@zulip.com"]["website"]['status'], 'idle')
        # We only want @zulip.com emails
        for email in json['presences'].keys():
            self.assertEqual(split_email_to_domain(email), 'zulip.com')

class AlertWordTests(AuthedTestCase):
    interesting_alert_word_list = ['alert', 'multi-word word', '☃'.decode("utf-8")]

    def test_internal_endpoint(self):
        email = "cordelia@zulip.com"
        self.login(email)

        params = {
            'alert_words': ujson.dumps(['milk', 'cookies'])
        }
        result = self.client.post('/json/set_alert_words', params)
        self.assert_json_success(result)
        user = get_user_profile_by_email(email)
        words = user_alert_words(user)
        self.assertEqual(words, ['milk', 'cookies'])


    def test_default_no_words(self):
        """
        Users start out with no alert words.
        """
        email = "cordelia@zulip.com"
        user = get_user_profile_by_email(email)

        words = user_alert_words(user)

        self.assertEqual(words, [])

    def test_add_word(self):
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
        self.assertEqual(realm_words.keys(), [user1.id, user2.id])
        self.assertEqual(realm_words[user1.id],
                         self.interesting_alert_word_list)
        self.assertEqual(realm_words[user2.id], ['another'])

    def test_json_list_default(self):
        self.login("hamlet@zulip.com")

        result = self.client.get('/json/users/me/alert_words')
        self.assert_json_success(result)

        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], [])

    def test_json_list_add(self):
        self.login("hamlet@zulip.com")

        result = self.client_patch('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)


        result = self.client.get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['one', 'two', 'three'])

    def test_json_list_remove(self):
        self.login("hamlet@zulip.com")

        result = self.client_patch('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)

        result = self.client_delete('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one'])})
        self.assert_json_success(result)

        result = self.client.get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['two', 'three'])

    def test_json_list_set(self):
        self.login("hamlet@zulip.com")

        result = self.client_patch('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)

        result = self.client_put('/json/users/me/alert_words', {'alert_words': ujson.dumps(['a', 'b', 'c'])})
        self.assert_json_success(result)

        result = self.client.get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['a', 'b', 'c'])

    def message_does_alert(self, user_profile, message):
        # Send a bunch of messages as othello, so Hamlet is notified
        self.send_message("othello@zulip.com", "Denmark", Recipient.STREAM, message)
        message = most_recent_usermessage(user_profile)
        return 'has_alert_word' in message.flags_list()

    def test_alert_flags(self):
        self.login("hamlet@zulip.com")
        user_profile_hamlet = get_user_profile_by_email("hamlet@zulip.com")

        result = self.client_patch('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)

        result = self.client.get('/json/users/me/alert_words')
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

class MutedTopicsTests(AuthedTestCase):
    def test_json_set(self):
        email = 'hamlet@zulip.com'
        self.login(email)

        url = '/json/set_muted_topics'
        data = {'muted_topics': '[["stream", "topic"]]'}
        result = self.client.post(url, data)
        self.assert_json_success(result)

        user = get_user_profile_by_email(email)
        self.assertEqual(ujson.loads(user.muted_topics), [["stream", "topic"]])

        url = '/json/set_muted_topics'
        data = {'muted_topics': '[["stream2", "topic2"]]'}
        result = self.client.post(url, data)
        self.assert_json_success(result)

        user = get_user_profile_by_email(email)
        self.assertEqual(ujson.loads(user.muted_topics), [["stream2", "topic2"]])

class ExtractedRecipientsTest(TestCase):
    def test_extract_recipients(self):
        # JSON list w/dups, empties, and trailing whitespace
        s = ujson.dumps([' alice@zulip.com ', ' bob@zulip.com ', '   ', 'bob@zulip.com'])
        self.assertItemsEqual(extract_recipients(s), ['alice@zulip.com', 'bob@zulip.com'])

        # simple string with one name
        s = 'alice@zulip.com    '
        self.assertItemsEqual(extract_recipients(s), ['alice@zulip.com'])

        # JSON-encoded string
        s = '"alice@zulip.com"'
        self.assertItemsEqual(extract_recipients(s), ['alice@zulip.com'])

        # bare comma-delimited string
        s = 'bob@zulip.com, alice@zulip.com'
        self.assertItemsEqual(extract_recipients(s), ['alice@zulip.com', 'bob@zulip.com'])

        # JSON-encoded, comma-delimited string
        s = '"bob@zulip.com,alice@zulip.com"'
        self.assertItemsEqual(extract_recipients(s), ['alice@zulip.com', 'bob@zulip.com'])


class TestMissedMessages(AuthedTestCase):
    def test_extra_context_in_missed_stream_messages(self):
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

        hamlet = get_user_profile_by_email('hamlet@zulip.com')
        handle_missedmessage_emails(hamlet.id, [{'message_id': msg_id}])

        def normalize_string(s):
            s = s.strip()
            return re.sub(r'\s+', ' ', s)

        self.assertEquals(len(mail.outbox), 1)
        self.assertIn(
            'Denmark > test Othello, the Moor of Venice 1 2 3 4 5 6 7 8 9 10 @**hamlet**',
            normalize_string(mail.outbox[0].body),
        )
