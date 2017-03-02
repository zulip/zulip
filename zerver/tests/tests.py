# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple, TypeVar, Text
from mock import patch, MagicMock

from django.http import HttpResponse
from django.test import TestCase, override_settings

from zerver.lib.test_helpers import (
    queries_captured, simulated_empty_cache,
    simulated_queue_client, tornado_redirected_to_list,
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
    Message, get_unique_open_realm, completely_open

from zerver.lib.avatar import avatar_url
from zerver.lib.initial_password import initial_password
from zerver.lib.email_mirror import create_missed_message_address
from zerver.lib.actions import \
    get_emails_from_user_ids, do_deactivate_user, do_reactivate_user, \
    do_change_is_admin, extract_recipients, \
    do_set_realm_name, do_deactivate_realm, \
    do_change_stream_invite_only
from zerver.lib.notifications import handle_missedmessage_emails
from zerver.lib.session_user import get_session_dict_user
from zerver.middleware import is_slow_query
from zerver.lib.utils import split_by

from zerver.worker import queue_processors

from django.conf import settings
from django.core import mail
from six.moves import range, urllib
import os
import re
import sys
import time
import ujson
import random
import filecmp
import subprocess

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

class RealmTest(ZulipTestCase):
    def assert_user_profile_cache_gets_new_name(self, email, new_realm_name):
        # type: (Text, Text) -> None
        user_profile = get_user_profile_by_email(email)
        self.assertEqual(user_profile.realm.name, new_realm_name)

    def test_do_set_realm_name_caching(self):
        # type: () -> None
        """The main complicated thing about setting realm names is fighting the
        cache, and we start by populating the cache for Hamlet, and we end
        by checking the cache to ensure that the new value is there."""
        get_user_profile_by_email('hamlet@zulip.com')
        realm = get_realm('zulip')
        new_name = 'Zed You Elle Eye Pea'
        do_set_realm_name(realm, new_name)
        self.assertEqual(get_realm(realm.string_id).name, new_name)
        self.assert_user_profile_cache_gets_new_name('hamlet@zulip.com', new_name)

    def test_do_set_realm_name_events(self):
        # type: () -> None
        realm = get_realm('zulip')
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

    def test_update_realm_api(self):
        # type: () -> None
        new_name = 'Zulip: Worldwide Exporter of APIs'

        email = 'cordelia@zulip.com'
        self.login(email)
        user_profile = get_user_profile_by_email(email)
        do_change_is_admin(user_profile, True)

        def set_up_db(attr, value):
            # type: (str, Any) -> None
            realm = get_realm('zulip')
            setattr(realm, attr, value)
            realm.save()

        def update_with_api(**kwarg):
            # type: (**Any) -> Realm
            params = {k: ujson.dumps(v) for k, v in kwarg.items()}
            result = self.client_patch('/json/realm', params)
            self.assert_json_success(result)
            return get_realm('zulip') # refresh data

        # name
        realm = update_with_api(name=new_name)
        self.assertEqual(realm.name, new_name)

        # restricted
        set_up_db('restricted_to_domain', False)
        realm = update_with_api(restricted_to_domain=True)
        self.assertEqual(realm.restricted_to_domain, True)
        realm = update_with_api(restricted_to_domain=False)
        self.assertEqual(realm.restricted_to_domain, False)

        # invite_required
        set_up_db('invite_required', False)
        realm = update_with_api(invite_required=True)
        self.assertEqual(realm.invite_required, True)
        realm = update_with_api(invite_required=False)
        self.assertEqual(realm.invite_required, False)

        # invite_by_admins_only
        set_up_db('invite_by_admins_only', False)
        realm = update_with_api(invite_by_admins_only=True)
        self.assertEqual(realm.invite_by_admins_only, True)
        realm = update_with_api(invite_by_admins_only=False)
        self.assertEqual(realm.invite_by_admins_only, False)

        # create_stream_by_admins_only
        set_up_db('create_stream_by_admins_only', False)
        realm = update_with_api(create_stream_by_admins_only=True)
        self.assertEqual(realm.create_stream_by_admins_only, True)
        realm = update_with_api(create_stream_by_admins_only=False)
        self.assertEqual(realm.create_stream_by_admins_only, False)

        # add_emoji_by_admins_only
        set_up_db('add_emoji_by_admins_only', False)
        realm = update_with_api(add_emoji_by_admins_only=True)
        self.assertEqual(realm.add_emoji_by_admins_only, True)
        realm = update_with_api(add_emoji_by_admins_only=False)
        self.assertEqual(realm.add_emoji_by_admins_only, False)

        # allow_message_editing
        set_up_db('allow_message_editing', False)
        set_up_db('message_content_edit_limit_seconds', 0)
        realm = update_with_api(allow_message_editing=True,
                                message_content_edit_limit_seconds=100)
        self.assertEqual(realm.allow_message_editing, True)
        self.assertEqual(realm.message_content_edit_limit_seconds, 100)
        realm = update_with_api(allow_message_editing=False)
        self.assertEqual(realm.allow_message_editing, False)
        self.assertEqual(realm.message_content_edit_limit_seconds, 100)
        realm = update_with_api(message_content_edit_limit_seconds=200)
        self.assertEqual(realm.allow_message_editing, False)
        self.assertEqual(realm.message_content_edit_limit_seconds, 200)

        # waiting_period_threshold
        set_up_db('waiting_period_threshold', 10)
        realm = update_with_api(waiting_period_threshold=20)
        self.assertEqual(realm.waiting_period_threshold, 20)
        realm = update_with_api(waiting_period_threshold=10)
        self.assertEqual(realm.waiting_period_threshold, 10)

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
        realm = get_realm('zulip')
        do_deactivate_realm(realm)
        user = get_user_profile_by_email('hamlet@zulip.com')
        self.assertTrue(user.realm.deactivated)

    def test_do_set_realm_default_language(self):
        # type: () -> None
        new_lang = "de"
        realm = get_realm('zulip')
        self.assertNotEqual(realm.default_language, new_lang)
        # we need an admin user.
        email = 'iago@zulip.com'
        self.login(email)

        req = dict(default_language=ujson.dumps(new_lang))
        result = self.client_patch('/json/realm', req)
        self.assert_json_success(result)
        realm = get_realm('zulip')
        self.assertEqual(realm.default_language, new_lang)

        # Test to make sure that when invalid languages are passed
        # as the default realm language, correct validation error is
        # raised and the invalid language is not saved in db
        invalid_lang = "invalid_lang"
        req = dict(default_language=ujson.dumps(invalid_lang))
        result = self.client_patch('/json/realm', req)
        self.assert_json_error(result, "Invalid language '%s'" % (invalid_lang,))
        realm = get_realm('zulip')
        self.assertNotEqual(realm.default_language, invalid_lang)


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

class ZephyrTest(ZulipTestCase):
    def test_webathena_kerberos_login(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)

        def post(**kwargs):
            # type: (**Any) -> HttpResponse
            params = {k: ujson.dumps(v) for k, v in kwargs.items()}
            return self.client_post('/accounts/webathena_kerberos_login/', params)

        result = post()
        self.assert_json_error(result, 'Could not find Kerberos credential')

        result = post(cred='whatever')
        self.assert_json_error(result, 'Webathena login not enabled')

        email = 'starnine@mit.edu'
        self.login(email)

        def ccache_mock(**kwargs):
            # type: (**Any) -> Any
            return patch('zerver.views.zephyr.make_ccache', **kwargs)

        def ssh_mock(**kwargs):
            # type: (**Any) -> Any
            return patch('zerver.views.zephyr.subprocess.check_call', **kwargs)

        def mirror_mock():
            # type: () -> Any
            return self.settings(PERSONAL_ZMIRROR_SERVER='server')

        def logging_mock():
            # type: () -> Any
            return patch('logging.exception')

        cred = dict(cname=dict(nameString=['starnine']))

        with ccache_mock(side_effect=KeyError('foo')):
            result = post(cred=cred)
        self.assert_json_error(result, 'Invalid Kerberos cache')

        with \
                ccache_mock(return_value=b'1234'), \
                ssh_mock(side_effect=KeyError('foo')), \
                logging_mock() as log:
            result = post(cred=cred)

        self.assert_json_error(result, 'We were unable to setup mirroring for you')
        log.assert_called_with("Error updating the user's ccache")

        with ccache_mock(return_value=b'1234'), mirror_mock(), ssh_mock() as ssh:
            result = post(cred=cred)

        self.assert_json_success(result)
        ssh.assert_called_with([
            'ssh',
            'server',
            '--',
            '/home/zulip/zulip/bots/process_ccache',
            'starnine',
            get_user_profile_by_email(email).api_key,
            'MTIzNA=='])

        # Accounts whose Kerberos usernames are known not to match their
        # zephyr accounts are hardcoded, and should be handled properly.

        def kerberos_alter_egos_mock():
            # type: () -> Any
            return patch(
                'zerver.views.zephyr.kerberos_alter_egos',
                {'kerberos_alter_ego': 'starnine'})

        cred = dict(cname=dict(nameString=['kerberos_alter_ego']))
        with \
                ccache_mock(return_value=b'1234'), \
                mirror_mock(), \
                ssh_mock() as ssh, \
                kerberos_alter_egos_mock():
            result = post(cred=cred)

        self.assert_json_success(result)
        ssh.assert_called_with([
            'ssh',
            'server',
            '--',
            '/home/zulip/zulip/bots/process_ccache',
            'starnine',
            get_user_profile_by_email(email).api_key,
            'MTIzNA=='])

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

class UserChangesTest(ZulipTestCase):
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

class BotTest(ZulipTestCase):
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

        bot = get_user_profile_by_email('hambot-bot@zulip.com')

        event = [e for e in events if e['event']['type'] == 'realm_bot'][0]
        self.assertEqual(
            dict(
                type='realm_bot',
                op='add',
                bot=dict(email='hambot-bot@zulip.com',
                         user_id=bot.id,
                         full_name='The Bot of Hamlet',
                         is_active=True,
                         api_key=result['api_key'],
                         avatar_url=result['avatar_url'],
                         default_sending_stream=None,
                         default_events_register_stream=None,
                         default_all_public_streams=False,
                         owner='hamlet@zulip.com')
            ),
            event['event']
        )

        users_result = self.client_get('/json/users')
        members = ujson.loads(users_result.content)['members']
        bots = [m for m in members if m['email'] == 'hambot-bot@zulip.com']
        self.assertEqual(len(bots), 1)
        bot = bots[0]
        self.assertEqual(bot['bot_owner'], 'hamlet@zulip.com')
        self.assertEqual(bot['user_id'], get_user_profile_by_email('hambot-bot@zulip.com').id)

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
        with get_test_image_file('img.png') as fp:
            self.create_bot(file=fp)
            profile = get_user_profile_by_email('hambot-bot@zulip.com')
            # Make sure that avatar image that we've uploaded is same with avatar image in the server
            self.assertTrue(filecmp.cmp(fp.name,
                                        os.path.splitext(avatar_disk_path(profile))[0] +
                                        ".original"))
        self.assert_num_bots_equal(1)

        self.assertEqual(profile.avatar_source, UserProfile.AVATAR_FROM_USER)
        self.assertTrue(os.path.exists(avatar_disk_path(profile)))

    def test_add_bot_with_too_many_files(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        self.assert_num_bots_equal(0)
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.gif') as fp2:
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

    def test_bot_add_subscription(self):
        # type: () -> None
        """
        Calling POST /json/users/me/subscriptions should successfully add
        streams, and a stream to the
        list of subscriptions and confirm the right number of events
        are generated.
        When 'principals' has a bot, no notification message event or invitation email
        is sent when add_subscriptions_backend is called in the above api call.
        """
        self.login("hamlet@zulip.com")

        # Normal user i.e. not a bot.
        request_data = {
            'principals': '["iago@zulip.com"]'
        }
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.common_subscribe_to_streams("hamlet@zulip.com", ['Rome'], request_data)
            self.assert_json_success(result)

        msg_event = [e for e in events if e['event']['type'] == 'message']
        self.assert_length(msg_event, 1) # Notification message event is sent.

        # Create a bot.
        self.assert_num_bots_equal(0)
        result = self.create_bot()
        self.assert_num_bots_equal(1)

        # A bot
        bot_request_data = {
            'principals': '["hambot-bot@zulip.com"]'
        }
        events_bot = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events_bot):
            result = self.common_subscribe_to_streams("hamlet@zulip.com", ['Rome'], bot_request_data)
            self.assert_json_success(result)

        # No notification message event or invitation email is sent because of bot.
        msg_event = [e for e in events_bot if e['event']['type'] == 'message']
        self.assert_length(msg_event, 0)
        self.assertEqual(len(events_bot), len(events) - 1)

        # Test runner automatically redirects all sent email to a dummy 'outbox'.
        self.assertEqual(len(mail.outbox), 0)

    def test_add_bot_with_default_sending_stream_private_allowed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        self.subscribe_to_stream(user_profile.email, stream.name)
        do_change_stream_invite_only(stream, True)

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
                         user_id=profile.id,
                         full_name='The Bot of Hamlet',
                         is_active=True,
                         api_key=result['api_key'],
                         avatar_url=result['avatar_url'],
                         default_sending_stream='Denmark',
                         default_events_register_stream=None,
                         default_all_public_streams=False,
                         owner='hamlet@zulip.com')
            ),
            event['event']
        )
        self.assertEqual(event['users'], (user_profile.id,))

    def test_add_bot_with_default_sending_stream_private_denied(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        self.unsubscribe_from_stream("hamlet@zulip.com", "Denmark")
        do_change_stream_invite_only(stream, True)

        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
            'default_sending_stream': 'Denmark',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, "Invalid stream name 'Denmark'")

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
        stream = self.subscribe_to_stream(user_profile.email, 'Denmark')
        do_change_stream_invite_only(stream, True)

        self.assert_num_bots_equal(0)
        events = [] # type: List[Dict[str, Any]]
        with tornado_redirected_to_list(events):
            result = self.create_bot(default_events_register_stream='Denmark')
        self.assert_num_bots_equal(1)
        self.assertEqual(result['default_events_register_stream'], 'Denmark')

        bot_profile = get_user_profile_by_email('hambot-bot@zulip.com')
        self.assertEqual(bot_profile.default_events_register_stream.name, 'Denmark')

        event = [e for e in events if e['event']['type'] == 'realm_bot'][0]
        self.assertEqual(
            dict(
                type='realm_bot',
                op='add',
                bot=dict(email='hambot-bot@zulip.com',
                         full_name='The Bot of Hamlet',
                         user_id=bot_profile.id,
                         is_active=True,
                         api_key=result['api_key'],
                         avatar_url=result['avatar_url'],
                         default_sending_stream=None,
                         default_events_register_stream='Denmark',
                         default_all_public_streams=False,
                         owner='hamlet@zulip.com')
            ),
            event['event']
        )
        self.assertEqual(event['users'], (user_profile.id,))

    def test_add_bot_with_default_events_register_stream_private_denied(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = get_stream("Denmark", user_profile.realm)
        self.unsubscribe_from_stream("hamlet@zulip.com", "Denmark")
        do_change_stream_invite_only(stream, True)

        self.assert_num_bots_equal(0)
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
            'default_events_register_stream': 'Denmark',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_error(result, "Invalid stream name 'Denmark'")

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

    def test_patch_bot_owner(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)
        bot_info = {
            'bot_owner': 'othello@zulip.com',
        }
        result = self.client_patch("/json/bots/hambot-bot@zulip.com", bot_info)
        self.assert_json_success(result)

        # Test bot's owner has been changed successfully.
        bot_owner = ujson.loads(result.content)['bot_owner']
        self.assertEqual(bot_owner, 'othello@zulip.com')

        self.login('othello@zulip.com')
        bot = self.get_bot()
        self.assertEqual('The Bot of Hamlet', bot['full_name'])

    @override_settings(LOCAL_UPLOADS_DIR='var/bot_avatar')
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
        with get_test_image_file('img.png') as fp1, \
                get_test_image_file('img.gif') as fp2:
            result = self.client_patch_multipart(
                '/json/bots/hambot-bot@zulip.com',
                dict(file1=fp1, file2=fp2))
        self.assert_json_error(result, 'You may only upload one file at a time')

        profile = get_user_profile_by_email("hambot-bot@zulip.com")
        self.assertEqual(profile.avatar_version, 1)

        # HAPPY PATH
        with get_test_image_file('img.png') as fp:
            result = self.client_patch_multipart(
                '/json/bots/hambot-bot@zulip.com',
                dict(file=fp))
            profile = get_user_profile_by_email('hambot-bot@zulip.com')
            self.assertEqual(profile.avatar_version, 2)
            # Make sure that avatar image that we've uploaded is same with avatar image in the server
            self.assertTrue(filecmp.cmp(fp.name,
                                        os.path.splitext(avatar_disk_path(profile))[0] +
                                        ".original"))
        self.assert_json_success(result)

        self.assertEqual(profile.avatar_source, UserProfile.AVATAR_FROM_USER)
        self.assertTrue(os.path.exists(avatar_disk_path(profile)))

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

        default_sending_stream = get_user_profile_by_email(
            "hambot-bot@zulip.com").default_sending_stream
        self.assertEqual(None, default_sending_stream)

        bot = self.get_bot()
        self.assertEqual(None, bot['default_sending_stream'])

    def test_patch_bot_to_stream_private_allowed(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        stream = self.subscribe_to_stream(user_profile.email, "Denmark")
        do_change_stream_invite_only(stream, True)

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
        self.unsubscribe_from_stream("hamlet@zulip.com", "Denmark")
        do_change_stream_invite_only(stream, True)

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
        self.assert_json_error(result, "Invalid stream name 'Denmark'")

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
        self.assert_json_error(result, "Invalid stream name 'missing'")

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
        stream = self.subscribe_to_stream(user_profile.email, "Denmark")
        do_change_stream_invite_only(stream, True)

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
        self.unsubscribe_from_stream("hamlet@zulip.com", "Denmark")
        do_change_stream_invite_only(stream, True)

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
        self.assert_json_error(result, "Invalid stream name 'Denmark'")

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

        default_events_register_stream = get_user_profile_by_email(
            "hambot-bot@zulip.com").default_events_register_stream
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
        self.assert_json_error(result, "Invalid stream name 'missing'")

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

class ChangeSettingsTest(ZulipTestCase):

    def check_well_formed_change_settings_response(self, result):
        # type: (Dict[str, Any]) -> None
        self.assertIn("full_name", result)

    # DEPRECATED, to be deleted after all uses of check_for_toggle_param
    # are converted into check_for_toggle_param_patch.
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

    # TODO: requires method consolidation, right now, there's no alternative
    # for check_for_toggle_param for PATCH.
    def check_for_toggle_param_patch(self, pattern, param):
        # type: (str, str) -> None
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        json_result = self.client_patch(pattern,
                                        {param: ujson.dumps(True)})
        self.assert_json_success(json_result)
        # refetch user_profile object to correctly handle caching
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        self.assertEqual(getattr(user_profile, param), True)

        json_result = self.client_patch(pattern,
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
        json_result = self.client_post(
            "/json/settings/change",
            dict(
                full_name='Foo Bar',
                old_password=initial_password('hamlet@zulip.com'),
                new_password='foobar1',
                confirm_password='foobar1',
            ))
        self.assert_json_success(json_result)
        result = ujson.loads(json_result.content)
        self.check_well_formed_change_settings_response(result)
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                         full_name, "Foo Bar")
        self.client_post('/accounts/logout/')
        self.login("hamlet@zulip.com", "foobar1")
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        self.assertEqual(get_session_dict_user(self.client.session), user_profile.id)

    def test_illegal_name_changes(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)
        user = get_user_profile_by_email(email)
        full_name = user.full_name

        with self.settings(NAME_CHANGES_DISABLED=True):
            json_result = self.client_post("/json/settings/change",
                                           dict(full_name='Foo Bar'))

        # We actually fail silently here, since this only happens if
        # somebody is trying to game our API, and there's no reason to
        # give them the courtesy of an error reason.
        self.assert_json_success(json_result)

        user = get_user_profile_by_email(email)
        self.assertEqual(user.full_name, full_name)

        # Now try a too-long name
        json_result = self.client_post("/json/settings/change",
                                       dict(full_name='x' * 1000))
        self.assert_json_error(json_result, 'Name too long!')

    def test_illegal_characters_in_name_changes(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)

        # Now try a name with invalid characters
        json_result = self.client_post("/json/settings/change",
                                       dict(full_name='Opheli*'))
        self.assert_json_error(json_result, 'Invalid characters in name!')

    # This is basically a don't-explode test.
    def test_notify_settings(self):
        # type: () -> None
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_desktop_notifications")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_stream_desktop_notifications")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_stream_sounds")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_sounds")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_offline_email_notifications")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_offline_push_notifications")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_online_push_notifications")
        self.check_for_toggle_param_patch("/json/settings/notifications", "enable_digest_emails")
        self.check_for_toggle_param_patch("/json/settings/notifications", "pm_content_in_desktop_notifications")

    def test_ui_settings(self):
        # type: () -> None
        self.check_for_toggle_param_patch("/json/settings/ui", "autoscroll_forever")
        self.check_for_toggle_param_patch("/json/settings/ui", "default_desktop_notifications")

    def test_toggling_left_side_userlist(self):
        # type: () -> None
        self.check_for_toggle_param_patch("/json/settings/display", "left_side_userlist")

    def test_toggling_emoji_alt_code(self):
        # type: () -> None
        self.check_for_toggle_param_patch("/json/settings/display", "emoji_alt_code")

    def test_time_setting(self):
        # type: () -> None
        self.check_for_toggle_param_patch("/json/settings/display", "twenty_four_hour_time")

    def test_enter_sends_setting(self):
        # type: () -> None
        self.check_for_toggle_param('/json/users/me/enter-sends', "enter_sends")

    def test_mismatching_passwords(self):
        # type: () -> None
        """
        new_password and confirm_password must match
        """
        self.login("hamlet@zulip.com")
        result = self.client_post(
            "/json/settings/change",
            dict(
                new_password="mismatched_password",
                confirm_password="not_the_same",
            ))
        self.assert_json_error(result,
                               "New password must match confirmation password!")

    def test_wrong_old_password(self):
        # type: () -> None
        """
        new_password and confirm_password must match
        """
        self.login("hamlet@zulip.com")
        result = self.client_post(
            "/json/settings/change",
            dict(
                old_password='bad_password',
                new_password="ignored",
                confirm_password="ignored",
            ))
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
                                  dict(old_password='ignored',))
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
        result = self.client_patch("/json/settings/display", data)
        self.assert_json_success(result)
        user_profile = get_user_profile_by_email(email)
        self.assertEqual(user_profile.default_language, german)

        # Test to make sure invalid languages are not accepted
        # and saved in the db.
        invalid_lang = "invalid_lang"
        data = dict(default_language=ujson.dumps(invalid_lang))
        result = self.client_patch("/json/settings/display", data)
        self.assert_json_error(result, "Invalid language '%s'" % (invalid_lang,))
        user_profile = get_user_profile_by_email(email)
        self.assertNotEqual(user_profile.default_language, invalid_lang)

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

class HomeTest(ZulipTestCase):
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
            'Manage streams',
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
            "attachments",
            "autoscroll_forever",
            "avatar_source",
            "avatar_url",
            "avatar_url_medium",
            "bot_list",
            "can_create_streams",
            "cross_realm_bots",
            "debug_mode",
            "default_desktop_notifications",
            "default_language",
            "default_language_name",
            "desktop_notifications_enabled",
            "development_environment",
            "domain",
            "domains",
            "email",
            "emoji_alt_code",
            "enable_digest_emails",
            "enable_offline_email_notifications",
            "enable_offline_push_notifications",
            "enable_online_push_notifications",
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
            "language_list_dbl_col",
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
            "pm_content_in_desktop_notifications",
            "poll_timeout",
            "product_name",
            "prompt_for_invites",
            "realm_add_emoji_by_admins_only",
            "realm_allow_message_editing",
            "realm_authentication_methods",
            "realm_create_stream_by_admins_only",
            "realm_default_language",
            "realm_default_streams",
            "realm_emoji",
            "realm_filters",
            "realm_icon_source",
            "realm_icon_url",
            "realm_invite_by_admins_only",
            "realm_invite_required",
            "realm_message_content_edit_limit_seconds",
            "realm_name",
            "realm_presence_disabled",
            "realm_restricted_to_domain",
            "realm_uri",
            "realm_waiting_period_threshold",
            "referrals",
            "save_stacktraces",
            "server_generation",
            "server_uri",
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
            "use_websockets",
            "user_id",
            "zulip_version",
        ]

        email = "hamlet@zulip.com"

        # Verify fails if logged-out
        result = self.client_get('/')
        self.assertEqual(result.status_code, 302)

        self.login(email)

        # Create bot for bot_list testing. Must be done before fetching home_page.
        bot_info = {
            'full_name': 'The Bot of Hamlet',
            'short_name': 'hambot',
        }
        self.client_post("/json/bots", bot_info)

        # Verify succeeds once logged-in
        result = self._get_home_page(stream='Denmark')
        html = result.content.decode('utf-8')

        for html_bit in html_bits:
            if html_bit not in html:
                self.fail('%s not in result' % (html_bit,))

        page_params = self._get_page_params(result)

        actual_keys = sorted([str(k) for k in page_params.keys()])

        self.assertEqual(actual_keys, expected_keys)

        # TODO: Inspect the page_params data further.
        # print(ujson.dumps(page_params, indent=2))
        bot_list_expected_keys = [
            'api_key',
            'avatar_url',
            'default_all_public_streams',
            'default_events_register_stream',
            'default_sending_stream',
            'email',
            'full_name',
            'is_active',
            'owner',
            'user_id',
        ]

        bot_list_actual_keys = sorted([str(key) for key in page_params['bot_list'][0].keys()])
        self.assertEqual(bot_list_actual_keys, bot_list_expected_keys)

    def _get_home_page(self, **kwargs):
        # type: (**Any) -> HttpResponse
        with \
                patch('zerver.lib.events.request_event_queue', return_value=42), \
                patch('zerver.lib.events.get_user_events', return_value=[]):
            result = self.client_get('/', dict(**kwargs))
        return result

    def _get_page_params(self, result):
        # type: (HttpResponse) -> Dict[str, Any]
        html = result.content.decode('utf-8')
        lines = html.split('\n')
        page_params_line = [l for l in lines if l.startswith('var page_params')][0]
        page_params_json = page_params_line.split(' = ')[1].rstrip(';')
        page_params = ujson.loads(page_params_json)
        return page_params

    def _sanity_check(self, result):
        # type: (HttpResponse) -> None
        '''
        Use this for tests that are geared toward specific edge cases, but
        which still want the home page to load properly.
        '''
        html = result.content.decode('utf-8')
        if 'Compose your message' not in html:
            self.fail('Home page probably did not load.')

    def test_terms_of_service(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)

        for user_tos_version in [None, '1.1', '2.0.3.4']:
            user = get_user_profile_by_email(email)
            user.tos_version = user_tos_version
            user.save()

            with \
                    self.settings(TERMS_OF_SERVICE='whatever'), \
                    self.settings(TOS_VERSION='99.99'):

                result = self.client_get('/', dict(stream='Denmark'))

            html = result.content.decode('utf-8')
            self.assertIn('There are new Terms of Service', html)

    def test_bad_narrow(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)
        with patch('logging.exception') as mock:
            result = self._get_home_page(stream='Invalid Stream')
        mock.assert_called_once_with('Narrow parsing')
        self._sanity_check(result)

    def test_bad_pointer(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        user_profile = get_user_profile_by_email(email)
        user_profile.pointer = 999999
        user_profile.save()

        self.login(email)
        with patch('logging.warning') as mock:
            result = self._get_home_page()
        mock.assert_called_once_with('hamlet@zulip.com has invalid pointer 999999')
        self._sanity_check(result)

    def test_topic_narrow(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)
        result = self._get_home_page(stream='Denmark', topic='lunch')
        self._sanity_check(result)
        html = result.content.decode('utf-8')
        self.assertIn('lunch', html)

    def test_notifications_stream(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        realm = get_realm('zulip')
        realm.notifications_stream = get_stream('Denmark', realm)
        realm.save()
        self.login(email)
        result = self._get_home_page()
        page_params = self._get_page_params(result)
        self.assertEqual(page_params['notifications_stream'], 'Denmark')

    def test_people(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)
        result = self._get_home_page()
        page_params = self._get_page_params(result)
        for params in ['people_list', 'bot_list']:
            users = page_params['people_list']
            self.assertTrue(len(users) >= 3)
            for user in users:
                self.assertEqual(user['user_id'],
                                 get_user_profile_by_email(user['email']).id)

        cross_bots = page_params['cross_realm_bots']
        self.assertEqual(len(cross_bots), 2)
        cross_bots.sort(key=lambda d: d['email'])
        self.assertEqual(cross_bots, [
            dict(
                user_id=get_user_profile_by_email('feedback@zulip.com').id,
                is_admin=False,
                email='feedback@zulip.com',
                full_name='Zulip Feedback Bot',
                is_bot=True
            ),
            dict(
                user_id=get_user_profile_by_email('notification-bot@zulip.com').id,
                is_admin=False,
                email='notification-bot@zulip.com',
                full_name='Notification Bot',
                is_bot=True
            ),
        ])

    def test_new_stream(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        stream_name = 'New stream'
        self.subscribe_to_stream(email, stream_name)
        self.login(email)
        result = self._get_home_page(stream=stream_name)
        page_params = self._get_page_params(result)
        self.assertEqual(page_params['narrow_stream'], stream_name)
        self.assertEqual(page_params['narrow'], [dict(operator='stream', operand=stream_name)])
        self.assertEqual(page_params['initial_pointer'], -1)
        self.assertEqual(page_params['max_message_id'], -1)
        self.assertEqual(page_params['have_initial_messages'], False)

    def test_invites_by_admins_only(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        user_profile = get_user_profile_by_email(email)

        realm = user_profile.realm
        realm.invite_by_admins_only = True
        realm.save()

        self.login(email)
        self.assertFalse(user_profile.is_realm_admin)
        result = self._get_home_page()
        html = result.content.decode('utf-8')
        self.assertNotIn('Invite more users', html)

        user_profile.is_realm_admin = True
        user_profile.save()
        result = self._get_home_page()
        html = result.content.decode('utf-8')
        self.assertIn('Invite more users', html)

    def test_desktop_home(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)
        result = self.client_get("/desktop_home")
        self.assertEqual(result.status_code, 301)
        self.assertTrue(result["Location"].endswith("/desktop_home/"))
        result = self.client_get("/desktop_home/")
        self.assertEqual(result.status_code, 302)
        path = urllib.parse.urlparse(result['Location']).path
        self.assertEqual(path, "/")

    def test_generate_204(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        self.login(email)
        result = self.client_get("/api/v1/generate_204")
        self.assertEqual(result.status_code, 204)

class AuthorsPageTest(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        """ Manual installation which did not execute `tools/provision`
        would not have the `static/generated/github-contributors.json` fixture
        file.
        """
        if not os.path.exists(settings.CONTRIBUTORS_DATA):
            # Copy the fixture file in `zerver/fixtures` to `static/generated`
            update_script = os.path.join(os.path.dirname(__file__),
                                         '../../tools/update-authors-json')
            subprocess.check_call([update_script, '--use-fixture'])

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

        msg = mail.outbox[0]
        reply_to_addresses = [settings.EMAIL_GATEWAY_PATTERN % (u'mm' + t) for t in tokens]
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

        mit_realm = get_realm("mit")
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
