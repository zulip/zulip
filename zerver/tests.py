# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.test import TestCase

from zerver.lib.test_helpers import (
    queries_captured, simulated_empty_cache,
    simulated_queue_client, tornado_redirected_to_list, AuthedTestCase,
    most_recent_usermessage, POSTRequestMock, most_recent_message,
)

from zerver.models import Message, UserProfile, Recipient, \
    Realm, Client, UserActivity, \
    UserMessage, \
    get_user_profile_by_email, split_email_to_domain, get_realm, \
    get_stream, get_client, RealmFilter
from zerver.decorator import \
    REQ, has_request_variables, json_to_list, RequestVariableMissingError, \
    RequestVariableConversionError, JsonableError
from zerver.lib.initial_password import initial_password
from zerver.lib.actions import \
    fetch_initial_state_data, apply_events, do_add_alert_words, \
    do_set_muted_topics, \
    do_remove_alert_words, do_remove_subscription, do_add_realm_filter, \
    do_remove_realm_filter, do_change_full_name, create_stream_if_needed, \
    do_add_realm_emoji, \
    do_remove_realm_emoji, \
    get_emails_from_user_ids, do_deactivate_user, do_reactivate_user, \
    do_change_is_admin, do_rename_stream, do_change_stream_description,  \
    do_set_realm_name, get_realm_name, do_deactivate_realm
from zerver.lib import bugdown
from zerver.lib.event_queue import allocate_client_descriptor
from zerver.lib.alert_words import alert_words_in_realm, user_alert_words, \
    add_user_alert_words, remove_user_alert_words
from zerver.lib.validator import check_string, check_list, check_dict, \
    check_bool, check_int
from zerver.middleware import is_slow_query

from zerver.worker import queue_processors

from django.conf import settings
import datetime
import os
import sys
import time
import ujson

from collections import OrderedDict

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

class DecoratorTestCase(TestCase):
    def test_REQ_converter(self):

        @has_request_variables
        def get_total(request, numbers=REQ(converter=json_to_list)):
            return sum(numbers)

        class Request:
            pass

        request = Request()
        request.REQUEST = {}

        with self.assertRaises(RequestVariableMissingError):
            get_total(request)

        request.REQUEST['numbers'] = 'bad_value'
        with self.assertRaises(RequestVariableConversionError) as cm:
            get_total(request)
        self.assertEqual(str(cm.exception), "Bad value for 'numbers': bad_value")

        request.REQUEST['numbers'] = ujson.dumps([1,2,3,4,5,6])
        result = get_total(request)
        self.assertEqual(result, 21)

    def test_REQ_validator(self):

        @has_request_variables
        def get_total(request, numbers=REQ(validator=check_list(check_int))):
            return sum(numbers)

        class Request:
            pass

        request = Request()
        request.REQUEST = {}

        with self.assertRaises(RequestVariableMissingError):
            get_total(request)

        request.REQUEST['numbers'] = 'bad_value'
        with self.assertRaises(JsonableError) as cm:
            get_total(request)
        self.assertEqual(str(cm.exception), 'argument "numbers" is not valid json.')

        request.REQUEST['numbers'] = ujson.dumps([1,2,"what?",4,5,6])
        with self.assertRaises(JsonableError) as cm:
            get_total(request)
        self.assertEqual(str(cm.exception), 'numbers[2] is not an integer')

        request.REQUEST['numbers'] = ujson.dumps([1,2,3,4,5,6])
        result = get_total(request)
        self.assertEqual(result, 21)

class ValidatorTestCase(TestCase):
    def test_check_string(self):
        x = "hello"
        self.assertEqual(check_string('x', x), None)

        x = 4
        self.assertEqual(check_string('x', x), 'x is not a string')

    def test_check_bool(self):
        x = True
        self.assertEqual(check_bool('x', x), None)

        x = 4
        self.assertEqual(check_bool('x', x), 'x is not a boolean')

    def test_check_int(self):
        x = 5
        self.assertEqual(check_int('x', x), None)

        x = [{}]
        self.assertEqual(check_int('x', x), 'x is not an integer')

    def test_check_list(self):
        x = 999
        error = check_list(check_string)('x', x)
        self.assertEqual(error, 'x is not a list')

        x = ["hello", 5]
        error = check_list(check_string)('x', x)
        self.assertEqual(error, 'x[1] is not a string')

        x = [["yo"], ["hello", "goodbye", 5]]
        error = check_list(check_list(check_string))('x', x)
        self.assertEqual(error, 'x[1][2] is not a string')

        x = ["hello", "goodbye", "hello again"]
        error = check_list(check_string, length=2)('x', x)
        self.assertEqual(error, 'x should have exactly 2 items')

    def test_check_dict(self):
        keys = [
            ('names', check_list(check_string)),
            ('city', check_string),
        ]

        x = {
            'names': ['alice', 'bob'],
            'city': 'Boston',
        }
        error = check_dict(keys)('x', x)
        self.assertEqual(error, None)

        x = 999
        error = check_dict(keys)('x', x)
        self.assertEqual(error, 'x is not a dict')

        x = {}
        error = check_dict(keys)('x', x)
        self.assertEqual(error, 'names key is missing from x')

        x = {
            'names': ['alice', 'bob', {}]
        }
        error = check_dict(keys)('x', x)
        self.assertEqual(error, 'x["names"][2] is not a string')

        x = {
            'names': ['alice', 'bob'],
            'city': 5
        }
        error = check_dict(keys)('x', x)
        self.assertEqual(error, 'x["city"] is not a string')

    def test_encapsulation(self):
        # There might be situations where we want deep
        # validation, but the error message should be customized.
        # This is an example.
        def check_person(val):
            error = check_dict([
                ['name', check_string],
                ['age', check_int],
            ])('_', val)
            if error:
                return 'This is not a valid person'

        person = {'name': 'King Lear', 'age': 42}
        self.assertEqual(check_person(person), None)

        person = 'misconfigured data'
        self.assertEqual(check_person(person), 'This is not a valid person')

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

class BotTest(AuthedTestCase):
    def assert_num_bots_equal(self, count):
        result = self.client.post("/json/get_bots")
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(count, len(json['bots']))

    def create_bot(self):
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/create_bot", bot_info)
        self.assert_json_success(result)

    def deactivate_bot(self):
        result = self.client_delete("/json/users/hambot-bot@zulip.com")
        self.assert_json_success(result)

    def test_add_bot(self):
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        self.create_bot()
        self.assert_num_bots_equal(1)

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
        result = self.client_delete("/json/users/bogus-bot@zulip.com")
        self.assert_json_error(result, 'No such user')
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

        result = self.client_delete("/json/users/hamlet@zulip.com")
        self.assert_json_error(result, 'Insufficient permission')

        result = self.client_delete("/json/users/hambot-bot@zulip.com")
        self.assert_json_error(result, 'Insufficient permission')

        # But we don't actually deactivate the other person's bot.
        self.login("hamlet@zulip.com")
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
        result = self.client.post("/json/get_bots")
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
        result = self.client.post("/json/create_bot", bot_info)
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

    def test_patch_bot_via_post(self):
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client.post("/json/create_bot", bot_info)
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

class PointerTest(AuthedTestCase):

    def test_update_pointer(self):
        """
        Posting a pointer to /update (in the form {"pointer": pointer}) changes
        the pointer we store for your UserProfile.
        """
        self.login("hamlet@zulip.com")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)
        msg_id = self.send_message("othello@zulip.com", "Verona", Recipient.STREAM)
        result = self.client.post("/json/update_pointer", {"pointer": msg_id})
        self.assert_json_success(result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, msg_id)

    def test_api_update_pointer(self):
        """
        Same as above, but for the API view
        """
        email = "hamlet@zulip.com"
        self.assertEqual(get_user_profile_by_email(email).pointer, -1)
        msg_id = self.send_message("othello@zulip.com", "Verona", Recipient.STREAM)
        result = self.client_put("/api/v1/users/me/pointer", {"pointer": msg_id},
                                 **self.api_auth(email))
        self.assert_json_success(result)
        self.assertEqual(get_user_profile_by_email(email).pointer, msg_id)

    def test_missing_pointer(self):
        """
        Posting json to /json/update_pointer which does not contain a pointer key/value pair
        returns a 400 and error message.
        """
        self.login("hamlet@zulip.com")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)
        result = self.client.post("/json/update_pointer", {"foo": 1})
        self.assert_json_error(result, "Missing 'pointer' argument")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)

    def test_invalid_pointer(self):
        """
        Posting json to /json/update_pointer with an invalid pointer returns a 400 and error
        message.
        """
        self.login("hamlet@zulip.com")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)
        result = self.client.post("/json/update_pointer", {"pointer": "foo"})
        self.assert_json_error(result, "Bad value for 'pointer': foo")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)

    def test_pointer_out_of_range(self):
        """
        Posting json to /json/update_pointer with an out of range (< 0) pointer returns a 400
        and error message.
        """
        self.login("hamlet@zulip.com")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)
        result = self.client.post("/json/update_pointer", {"pointer": -2})
        self.assert_json_error(result, "Bad value for 'pointer': -2")
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").pointer, -1)

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
        json_result = self.client.post("/json/notify_settings/change", {})
        self.assert_json_success(json_result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                enable_desktop_notifications, False)

    def test_ui_settings(self):
        self.login("hamlet@zulip.com")

        json_result = self.client.post("/json/ui_settings/change", {"autoscroll_forever": "on"})
        self.assert_json_success(json_result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                enable_desktop_notifications, True)

        json_result = self.client.post("/json/ui_settings/change", {})
        self.assert_json_success(json_result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                autoscroll_forever, False)

        json_result = self.client.post("/json/ui_settings/change", {"default_desktop_notifications": "on"})
        self.assert_json_success(json_result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                default_desktop_notifications, True)

        json_result = self.client.post("/json/ui_settings/change", {})
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

from zerver.tornadoviews import get_events_backend
class GetEventsTest(AuthedTestCase):
    def tornado_call(self, view_func, user_profile, post_data,
                     callback=None):
        request = POSTRequestMock(post_data, user_profile, callback)
        return view_func(request, user_profile)

    def test_get_events(self):
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
    maxDiff = None
    user_profile = get_user_profile_by_email("hamlet@zulip.com")

    def do_test(self, action, event_types=None, matcher=None):
        client = allocate_client_descriptor(self.user_profile.id, self.user_profile.realm.id,
                                            event_types,
                                            get_client("website"), True, False, 600, [])
        # hybrid_state = initial fetch state + re-applying events triggered by our action
        # normal_state = do action then fetch at the end (the "normal" code path)
        hybrid_state = fetch_initial_state_data(self.user_profile, event_types, "")
        action()
        events = client.event_queue.contents()
        apply_events(hybrid_state, events, self.user_profile)

        normal_state = fetch_initial_state_data(self.user_profile, event_types, "")

        if matcher is None:
            matcher = self.assertEqual

        matcher(hybrid_state, normal_state)

    def match_with_reorder(self, a, b, field):
        # We need to use an OrderedDict to turn these into strings consistently
        self.assertEqual(set(ujson.dumps(OrderedDict(x.items())) for x in a[field]),
                         set(ujson.dumps(OrderedDict(x.items())) for x in b[field]))
        a[field] = []
        b[field] = []
        self.assertEqual(a, b)

    def test_send_message_events(self):
        self.do_test(lambda: self.send_message("hamlet@zulip.com", "Verona", Recipient.STREAM, "hello"))

    def test_pointer_events(self):
        self.do_test(lambda: self.client.post("/json/update_pointer", {"pointer": 150}))

    def test_register_events(self):
        self.do_test(lambda: self.register("test1", "test1"),
                     matcher=lambda a, b: self.match_with_reorder(a, b, "realm_users"))

    def test_alert_words_events(self):
        self.do_test(lambda: do_add_alert_words(self.user_profile, ["alert_word"]))
        self.do_test(lambda: do_remove_alert_words(self.user_profile, ["alert_word"]))

    def test_muted_topics_events(self):
        self.do_test(lambda: do_set_muted_topics(self.user_profile, [["Denmark", "topic"]]))

    def test_change_full_name(self):
        self.do_test(lambda: do_change_full_name(self.user_profile, 'Sir Hamlet'))

    def test_change_realm_name(self):
        self.do_test(lambda: do_set_realm_name(self.user_profile.realm, 'New Realm Name'))

    def test_change_is_admin(self):
        # The first False is probably a noop, then we get transitions in both directions.
        for is_admin in [False, True, False]:
            self.do_test(lambda: do_change_is_admin(self.user_profile, is_admin))

    def test_realm_emoji_events(self):
        self.do_test(lambda: do_add_realm_emoji(get_realm("zulip.com"), "my_emoji",
                                                "https://realm.com/my_emoji"))
        self.do_test(lambda: do_remove_realm_emoji(get_realm("zulip.com"), "my_emoji"))

    def test_realm_filter_events(self):
        self.do_test(lambda: do_add_realm_filter(get_realm("zulip.com"), "#[123]",
                                                "https://realm.com/my_realm_filter/%(id)s"))
        self.do_test(lambda: do_remove_realm_filter(get_realm("zulip.com"), "#[123]"))

    def test_rename_stream(self):
        realm = get_realm('zulip.com')
        stream, _ = create_stream_if_needed(realm, 'old_name')
        new_name = 'stream with a brand new name'
        self.do_test(lambda: do_rename_stream(realm, stream.name, new_name))

    def test_subscribe_events(self):
        self.do_test(lambda: self.subscribe_to_stream("hamlet@zulip.com", "test_stream"),
                     matcher=lambda a, b: self.match_with_reorder(a, b, "subscriptions"))
        self.do_test(lambda: self.subscribe_to_stream("othello@zulip.com", "test_stream"),
                     matcher=lambda a, b: self.match_with_reorder(a, b, "subscriptions"))
        stream = get_stream("test_stream", self.user_profile.realm)
        self.do_test(lambda: do_remove_subscription(get_user_profile_by_email("othello@zulip.com"), stream),
                     matcher=lambda a, b: self.match_with_reorder(a, b, "subscriptions"))
        self.do_test(lambda: do_remove_subscription(get_user_profile_by_email("hamlet@zulip.com"), stream),
                     matcher=lambda a, b: self.match_with_reorder(a, b, "unsubscribed"))
        self.do_test(lambda: self.subscribe_to_stream("hamlet@zulip.com", "test_stream"),
                     matcher=lambda a, b: self.match_with_reorder(a, b, "subscriptions"))
        self.do_test(lambda: do_change_stream_description(get_realm('zulip.com'), 'test_stream',
                                                          'new description'),
                     matcher=lambda a, b: self.match_with_reorder(a, b, "subscriptions"))

from zerver.lib.event_queue import EventQueue
class EventQueueTest(TestCase):
    def test_one_event(self):
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
        queue = EventQueue("1")
        for pointer_val in xrange(1, 10):
            queue.push({"type": "pointer",
                        "pointer": pointer_val,
                        "timestamp": str(pointer_val)})
        self.assertEqual(queue.contents(),
                         [{'id': 8,
                           'type': 'pointer',
                           "pointer": 9,
                           "timestamp": "9"}])

        queue = EventQueue("2")
        for pointer_val in xrange(1, 10):
            queue.push({"type": "pointer",
                        "pointer": pointer_val,
                        "timestamp": str(pointer_val)})
        queue.push({"type": "unknown"})
        queue.push({"type": "restart", "server_generation": "1"})
        for pointer_val in xrange(11, 20):
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
        for pointer_val in xrange(21, 23):
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
                           "messages": [1,2,3,4,5,6],
                           "timestamp": "1"}])

    def test_flag_remove_collapsing(self):
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
                           "messages": [1,2,3,4,5,6],
                           "timestamp": "1"}])

    def test_collapse_event(self):
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

class FencedBlockPreprocessorTest(TestCase):
    def test_simple_quoting(self):
        processor = bugdown.fenced_code.FencedBlockPreprocessor(None)
        markdown = [
            '~~~ quote',
            'hi',
            'bye',
            '',
            ''
        ]
        expected = [
            '',
            '> hi',
            '> bye',
            '',
            '',
            ''
        ]
        lines = processor.run(markdown)
        self.assertEqual(lines, expected)

    def test_serial_quoting(self):
        processor = bugdown.fenced_code.FencedBlockPreprocessor(None)
        markdown = [
            '~~~ quote',
            'hi',
            '~~~',
            '',
            '~~~ quote',
            'bye',
            '',
            ''
        ]
        expected = [
            '',
            '> hi',
            '',
            '',
            '',
            '> bye',
            '',
            '',
            ''
        ]
        lines = processor.run(markdown)
        self.assertEqual(lines, expected)

    def test_serial_code(self):
        processor = bugdown.fenced_code.FencedBlockPreprocessor(None)

        # Simulate code formatting.
        processor.format_code = lambda lang, code: lang + ':' + code
        processor.placeholder = lambda s: '**' + s.strip('\n') + '**'

        markdown = [
            '``` .py',
            'hello()',
            '```',
            '',
            '``` .py',
            'goodbye()',
            '```',
            '',
            ''
        ]
        expected = [
            '',
            '**py:hello()**',
            '',
            '',
            '',
            '**py:goodbye()**',
            '',
            '',
            ''
        ]
        lines = processor.run(markdown)
        self.assertEqual(lines, expected)

    def test_nested_code(self):
        processor = bugdown.fenced_code.FencedBlockPreprocessor(None)

        # Simulate code formatting.
        processor.format_code = lambda lang, code: lang + ':' + code
        processor.placeholder = lambda s: '**' + s.strip('\n') + '**'

        markdown = [
            '~~~ quote',
            'hi',
            '``` .py',
            'hello()',
            '```',
            '',
            ''
        ]
        expected = [
            '',
            '> hi',
            '',
            '> **py:hello()**',
            '',
            '',
            ''
        ]
        lines = processor.run(markdown)
        self.assertEqual(lines, expected)

def bugdown_convert(text):
    return bugdown.convert(text, "zulip.com")

class BugdownTest(TestCase):
    def common_bugdown_test(self, text, expected):
        converted = bugdown_convert(text)
        self.assertEqual(converted, expected)

    def load_bugdown_tests(self):
        test_fixtures = {}
        data_file = open(os.path.join(os.path.dirname(__file__), 'fixtures/bugdown-data.json'), 'r')
        data = ujson.loads('\n'.join(data_file.readlines()))
        for test in data['regular_tests']:
            test_fixtures[test['name']] = test

        return test_fixtures, data['linkify_tests']

    def test_bugdown_fixtures(self):
        format_tests, linkify_tests = self.load_bugdown_tests()

        for name, test in format_tests.iteritems():
            converted = bugdown_convert(test['input'])

            print "Running Bugdown test %s" % (name,)
            self.assertEqual(converted, test['expected_output'])

        def replaced(payload, url, phrase=''):
            target = " target=\"_blank\""
            if url[:4] == 'http':
                href = url
            elif '@' in url:
                href = 'mailto:' + url
                target = ""
            else:
                href = 'http://' + url
            return payload % ("<a href=\"%s\"%s title=\"%s\">%s</a>" % (href, target, href, url),)


        print "Running Bugdown Linkify tests"
        for inline_url, reference, url in linkify_tests:
            try:
                match = replaced(reference, url, phrase=inline_url)
            except TypeError:
                match = reference
            converted = bugdown_convert(inline_url)
            self.assertEqual(match, converted)

    def test_inline_youtube(self):
        msg = 'Check out the debate: http://www.youtube.com/watch?v=hx1mjT73xYE'
        converted = bugdown_convert(msg)

        if settings.USING_EMBEDLY:
            self.assertEqual(converted, '<p>Check out the debate: <a href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE">http://www.youtube.com/watch?v=hx1mjT73xYE</a></p>\n<iframe width="250" height="141" src="http://www.youtube.com/embed/hx1mjT73xYE?feature=oembed" frameborder="0" allowfullscreen></iframe>')
        else:
            self.assertEqual(converted, '<p>Check out the debate: <a href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE">http://www.youtube.com/watch?v=hx1mjT73xYE</a></p>\n<div class="message_inline_image"><a href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE"><img src="https://i.ytimg.com/vi/hx1mjT73xYE/default.jpg"></a></div>')

    def test_inline_dropbox(self):
        msg = 'Look at how hilarious our old office was: https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Look at how hilarious our old office was: <a href="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG" target="_blank" title="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG">https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG" target="_blank" title="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG"><img src="https://www.dropbox.com/s/ymdijjcg67hv2ta/IMG_0923.JPG?dl=1"></a></div>')

        msg = 'Look at my hilarious drawing: https://www.dropbox.com/sh/inlugx9d25r314h/JYwv59v4Jv/credit_card_rushmore.jpg'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Look at my hilarious drawing: <a href="https://www.dropbox.com/sh/inlugx9d25r314h/JYwv59v4Jv/credit_card_rushmore.jpg" target="_blank" title="https://www.dropbox.com/sh/inlugx9d25r314h/JYwv59v4Jv/credit_card_rushmore.jpg">https://www.dropbox.com/sh/inlugx9d25r314h/JYwv59v4Jv/credit_card_rushmore.jpg</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/sh/inlugx9d25r314h/JYwv59v4Jv/credit_card_rushmore.jpg" target="_blank" title="https://www.dropbox.com/sh/inlugx9d25r314h/JYwv59v4Jv/credit_card_rushmore.jpg"><img src="https://www.dropbox.com/sh/inlugx9d25r314h/JYwv59v4Jv/credit_card_rushmore.jpg?dl=1"></a></div>')


        # Make sure we're not overzealous in our conversion:
        msg = 'Look at the new dropbox logo: https://www.dropbox.com/static/images/home_logo.png'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Look at the new dropbox logo: <a href="https://www.dropbox.com/static/images/home_logo.png" target="_blank" title="https://www.dropbox.com/static/images/home_logo.png">https://www.dropbox.com/static/images/home_logo.png</a></p>\n<div class="message_inline_image"><a href="https://www.dropbox.com/static/images/home_logo.png" target="_blank" title="https://www.dropbox.com/static/images/home_logo.png"><img src="https://www.dropbox.com/static/images/home_logo.png"></a></div>')

    def test_twitter_id_extraction(self):
        self.assertEqual(bugdown.get_tweet_id('http://twitter.com/#!/VizzQuotes/status/409030735191097344'), '409030735191097344')
        self.assertEqual(bugdown.get_tweet_id('http://twitter.com/VizzQuotes/status/409030735191097344'), '409030735191097344')
        self.assertEqual(bugdown.get_tweet_id('http://twitter.com/VizzQuotes/statuses/409030735191097344'), '409030735191097344')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/wdaher/status/1017581858'), '1017581858')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/wdaher/status/1017581858/'), '1017581858')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/windyoona/status/410766290349879296/photo/1'), '410766290349879296')
        self.assertEqual(bugdown.get_tweet_id('https://twitter.com/windyoona/status/410766290349879296/'), '410766290349879296')

    def test_inline_interesting_links(self):
        def make_link(url):
            return '<a href="%s" target="_blank" title="%s">%s</a>' % (url, url, url)

        normal_tweet_html = """<a href="https://twitter.com/twitter" target="_blank" title="https://twitter.com/twitter">@twitter</a> meets <a href="https://twitter.com/seepicturely" target="_blank" title="https://twitter.com/seepicturely">@seepicturely</a> at #tcdisrupt cc.<a href="https://twitter.com/boscomonkey" target="_blank" title="https://twitter.com/boscomonkey">@boscomonkey</a> <a href="https://twitter.com/episod" target="_blank" title="https://twitter.com/episod">@episod</a> <a href="http://t.co/6J2EgYM" target="_blank" title="http://t.co/6J2EgYM">http://instagram.com/p/MuW67/</a>"""

        mention_in_link_tweet_html = """<a href="http://t.co/@foo" target="_blank" title="http://t.co/@foo">http://foo.com</a>"""

        media_tweet_html = """<a href="http://t.co/xo7pAhK6n3" target="_blank" title="http://t.co/xo7pAhK6n3">http://twitter.com/NEVNBoston/status/421654515616849920/photo/1</a>"""

        def make_inline_twitter_preview(url, tweet_html, image_html=''):
            ## As of right now, all previews are mocked to be the exact same tweet
            return """<div class="inline-preview-twitter"><div class="twitter-tweet"><a href="%s" target="_blank"><img class="twitter-avatar" src="https://si0.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png"></a><p>%s</p><span>- Eoin McMillan  (@imeoin)</span>%s</div></div>""" % (url, tweet_html, image_html)

        msg = 'http://www.twitter.com'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>' % make_link('http://www.twitter.com'))

        msg = 'http://www.twitter.com/wdaher/'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>' % make_link('http://www.twitter.com/wdaher/'))

        msg = 'http://www.twitter.com/wdaher/status/3'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>' % make_link('http://www.twitter.com/wdaher/status/3'))

        # id too long
        msg = 'http://www.twitter.com/wdaher/status/2879779692873154569'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>' % make_link('http://www.twitter.com/wdaher/status/2879779692873154569'))

        # id too large (i.e. tweet doesn't exist)
        msg = 'http://www.twitter.com/wdaher/status/999999999999999999'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>' % make_link('http://www.twitter.com/wdaher/status/999999999999999999'))

        msg = 'http://www.twitter.com/wdaher/status/287977969287315456'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (make_link('http://www.twitter.com/wdaher/status/287977969287315456'),
                                                       make_inline_twitter_preview('http://www.twitter.com/wdaher/status/287977969287315456', normal_tweet_html)))

        msg = 'https://www.twitter.com/wdaher/status/287977969287315456'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (make_link('https://www.twitter.com/wdaher/status/287977969287315456'),
                                                       make_inline_twitter_preview('https://www.twitter.com/wdaher/status/287977969287315456', normal_tweet_html)))

        msg = 'http://twitter.com/wdaher/status/287977969287315456'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (make_link('http://twitter.com/wdaher/status/287977969287315456'),
                                                       make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315456', normal_tweet_html)))

        # A max of 3 will be converted
        msg = 'http://twitter.com/wdaher/status/287977969287315456 http://twitter.com/wdaher/status/287977969287315457 http://twitter.com/wdaher/status/287977969287315457 http://twitter.com/wdaher/status/287977969287315457'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s %s %s %s</p>\n%s%s%s' % (make_link('http://twitter.com/wdaher/status/287977969287315456'),
                                                          make_link('http://twitter.com/wdaher/status/287977969287315457'),
                                                          make_link('http://twitter.com/wdaher/status/287977969287315457'),
                                                          make_link('http://twitter.com/wdaher/status/287977969287315457'),
                                                          make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315456', normal_tweet_html),
                                                          make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315457', normal_tweet_html),
                                                          make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315457', normal_tweet_html)))

        # Tweet has a mention in a URL, only the URL is linked
        msg = 'http://twitter.com/wdaher/status/287977969287315458'

        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (make_link('http://twitter.com/wdaher/status/287977969287315458'),
                                                       make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315458', mention_in_link_tweet_html)))

        # Tweet with an image
        msg = 'http://twitter.com/wdaher/status/287977969287315459'

        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (make_link('http://twitter.com/wdaher/status/287977969287315459'),
                                                       make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315459', media_tweet_html, """<div class="twitter-image"><a href="http://t.co/xo7pAhK6n3" target="_blank" title="http://t.co/xo7pAhK6n3"><img src="https://pbs.twimg.com/media/BdoEjD4IEAIq86Z.jpg:small"></a></div>""")))

    def test_realm_emoji(self):
        def emoji_img(name, url):
            return '<img alt="%s" class="emoji" src="%s" title="%s">' % (name, url, name)

        zulip_realm = get_realm('zulip.com')
        url = "https://zulip.com/test_realm_emoji.png"
        do_add_realm_emoji(zulip_realm, "test", url)

        # Needs to mock an actual message because that's how bugdown obtains the realm
        msg = Message(sender=get_user_profile_by_email("hamlet@zulip.com"))
        converted = bugdown.convert(":test:", "zulip.com", msg)
        self.assertEqual(converted, '<p>%s</p>' %(emoji_img(':test:', url)))

        do_remove_realm_emoji(zulip_realm, 'test')
        converted = bugdown.convert(":test:", "zulip.com", msg)
        self.assertEqual(converted, '<p>:test:</p>')

    def test_realm_patterns(self):
        RealmFilter(realm=get_realm('zulip.com'), pattern=r"#(?P<id>[0-9]{2,8})",
                    url_format_string=r"https://trac.zulip.net/ticket/%(id)s").save()
        msg = Message(sender=get_user_profile_by_email("othello@zulip.com"))

        content = "We should fix #224 and #115, but not issue#124 or #1124z or [trac #15](https://trac.zulip.net/ticket/16) today."
        converted = bugdown.convert(content, realm_domain='zulip.com', message=msg)

        self.assertEqual(converted, '<p>We should fix <a href="https://trac.zulip.net/ticket/224" target="_blank" title="https://trac.zulip.net/ticket/224">#224</a> and <a href="https://trac.zulip.net/ticket/115" target="_blank" title="https://trac.zulip.net/ticket/115">#115</a>, but not issue#124 or #1124z or <a href="https://trac.zulip.net/ticket/16" target="_blank" title="https://trac.zulip.net/ticket/16">trac #15</a> today.</p>')

    def test_stream_subscribe_button_simple(self):
        msg = '!_stream_subscribe_button(simple)'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<span class="inline-subscribe" data-stream-name="simple">'
            '<button class="inline-subscribe-button zulip-button">Subscribe to simple</button>'
            '<span class="inline-subscribe-error"></span>'
            '</span>'
            '</p>'
        )

    def test_stream_subscribe_button_in_name(self):
        msg = '!_stream_subscribe_button(simple (not\\))'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<span class="inline-subscribe" data-stream-name="simple (not)">'
            '<button class="inline-subscribe-button zulip-button">Subscribe to simple (not)</button>'
            '<span class="inline-subscribe-error"></span>'
            '</span>'
            '</p>'
        )

    def test_stream_subscribe_button_after_name(self):
        msg = '!_stream_subscribe_button(simple) (not)'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<span class="inline-subscribe" data-stream-name="simple">'
            '<button class="inline-subscribe-button zulip-button">Subscribe to simple</button>'
            '<span class="inline-subscribe-error"></span>'
            '</span>'
            ' (not)</p>'
        )

    def test_stream_subscribe_button_slash(self):
        msg = '!_stream_subscribe_button(simple\\\\)'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<span class="inline-subscribe" data-stream-name="simple\\">'
            '<button class="inline-subscribe-button zulip-button">Subscribe to simple\\</button>'
            '<span class="inline-subscribe-error"></span>'
            '</span>'
            '</p>'
        )

    def test_in_app_modal_link(self):
        msg = '!modal_link(#settings, Settings page)'
        converted = bugdown_convert(msg)
        self.assertEqual(
            converted,
            '<p>'
            '<a data-toggle="modal" href="#settings" title="#settings">Settings page</a>'
            '</p>'
        )

    def test_mit_rendering(self):
        msg = "**test**"
        converted = bugdown.convert(msg, "mit.edu/zephyr_mirror")
        self.assertEqual(
            converted,
            "<p>**test**</p>",
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

class UnreadCountTests(AuthedTestCase):
    def setUp(self):
        self.unread_msg_ids = [self.send_message(
                "iago@zulip.com", "hamlet@zulip.com", Recipient.PERSONAL, "hello"),
                               self.send_message(
                "iago@zulip.com", "hamlet@zulip.com", Recipient.PERSONAL, "hello2")]

    def test_new_message(self):
        # Sending a new message results in unread UserMessages being created
        self.login("hamlet@zulip.com")
        content = "Test message for unset read bit"
        last_msg = self.send_message("hamlet@zulip.com", "Verona", Recipient.STREAM, content)
        user_messages = list(UserMessage.objects.filter(message=last_msg))
        self.assertEqual(len(user_messages) > 0, True)
        for um in user_messages:
            self.assertEqual(um.message.content, content)
            if um.user_profile.email != "hamlet@zulip.com":
                self.assertFalse(um.flags.read)

    def test_update_flags(self):
        self.login("hamlet@zulip.com")

        result = self.client.post("/json/update_message_flags",
                                  {"messages": ujson.dumps(self.unread_msg_ids),
                                   "op": "add",
                                   "flag": "read"})
        self.assert_json_success(result)

        # Ensure we properly set the flags
        found = 0
        for msg in self.get_old_messages():
            if msg['id'] in self.unread_msg_ids:
                self.assertEqual(msg['flags'], ['read'])
                found += 1
        self.assertEqual(found, 2)

        result = self.client.post("/json/update_message_flags",
                                  {"messages": ujson.dumps([self.unread_msg_ids[1]]),
                                   "op": "remove", "flag": "read"})
        self.assert_json_success(result)

        # Ensure we properly remove just one flag
        for msg in self.get_old_messages():
            if msg['id'] == self.unread_msg_ids[0]:
                self.assertEqual(msg['flags'], ['read'])
            elif msg['id'] == self.unread_msg_ids[1]:
                self.assertEqual(msg['flags'], [])

    def test_update_all_flags(self):
        self.login("hamlet@zulip.com")

        message_ids = [self.send_message("hamlet@zulip.com", "iago@zulip.com",
                                         Recipient.PERSONAL, "test"),
                       self.send_message("hamlet@zulip.com", "cordelia@zulip.com",
                                         Recipient.PERSONAL, "test2")]

        result = self.client.post("/json/update_message_flags", {"messages": ujson.dumps(message_ids),
                                                                 "op": "add",
                                                                 "flag": "read"})
        self.assert_json_success(result)

        result = self.client.post("/json/update_message_flags", {"messages": ujson.dumps([]),
                                                                 "op": "remove",
                                                                 "flag": "read",
                                                                 "all": ujson.dumps(True)})
        self.assert_json_success(result)

        for msg in self.get_old_messages():
            self.assertEqual(msg['flags'], [])

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

