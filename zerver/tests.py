# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.test import TestCase
from django.test.simple import DjangoTestSuiteRunner
from django.utils.timezone import now
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.backends.util import CursorDebugWrapper

from zerver.models import Message, UserProfile, Stream, Recipient, Subscription, \
    get_display_recipient, Realm, Client, \
    PreregistrationUser, UserMessage, \
    get_user_profile_by_email, email_to_domain, get_realm, get_stream
from zerver.tornadoviews import json_get_updates, api_get_messages
from zerver.decorator import RespondAsynchronously, \
    RequestVariableConversionError, profiled, JsonableError
from zerver.lib.initial_password import initial_password
from zerver.lib.actions import check_send_message, gather_subscriptions, \
    create_stream_if_needed, do_add_subscription, compute_mit_user_fullname, \
    do_add_realm_emoji, do_remove_realm_emoji, check_message, do_create_user, \
    set_default_streams
from zerver.lib.rate_limiter import add_ratelimit_rule, remove_ratelimit_rule
from zerver.lib import bugdown
from zerver.lib.cache import bounce_key_prefix_for_testing
from zerver.lib.rate_limiter import clear_user_history
from zerver.lib.alert_words import alert_words_in_realm, user_alert_words, \
    add_user_alert_words, remove_user_alert_words
from zerver.forms import not_mit_mailing_list

import base64
from django.conf import settings
from django.db import connection
import datetime
import os
import random
import re
import sys
import time
import ujson
import urllib
import urllib2
from StringIO import StringIO

from boto.s3.connection import S3Connection
from boto.s3.key import Key
from contextlib import contextmanager
from zerver import tornado_callbacks

@contextmanager
def tornado_redirected_to_list(lst):
    real_tornado_callbacks_process_event = tornado_callbacks.process_event
    tornado_callbacks.process_event = lst.append
    yield
    tornado_callbacks.process_event = real_tornado_callbacks_process_event

@contextmanager
def queries_captured():
    '''
    Allow a user to capture just the queries executed during
    the with statement.
    '''

    queries = []

    def wrapper_execute(self, action, sql, params=()):
        self.set_dirty()
        start = time.time()
        try:
            return action(sql, params)
        finally:
            stop = time.time()
            duration = stop - start
            queries.append({
                    'sql': sql,
                    'time': "%.3f" % duration,
                    })

    old_settings = settings.DEBUG
    settings.DEBUG = True

    old_execute = CursorDebugWrapper.execute
    old_executemany = CursorDebugWrapper.executemany

    def cursor_execute(self, sql, params=()):
        return wrapper_execute(self, self.cursor.execute, sql, params)
    CursorDebugWrapper.execute = cursor_execute

    def cursor_executemany(self, sql, params=()):
        return wrapper_execute(self, self.cursor.executemany, sql, params)
    CursorDebugWrapper.executemany = cursor_executemany

    yield queries

    settings.DEBUG = old_settings
    CursorDebugWrapper.execute = old_execute
    CursorDebugWrapper.executemany = old_executemany


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

def find_key_by_email(address):
    from django.core.mail import outbox
    key_regex = re.compile("accounts/do_confirm/([a-f0-9]{40})>")
    for message in reversed(outbox):
        if address in message.to:
            return key_regex.search(message.body).groups()[0]

def message_ids(result):
    return set(message['id'] for message in result['messages'])

def message_stream_count(user_profile):
    return UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        count()

def get_user_messages(user_profile):
    query = UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        order_by('message')
    return [um.message for um in query]

def most_recent_message(user_profile):
    query = UserMessage.objects. \
        select_related("message"). \
        filter(user_profile=user_profile). \
        order_by('-message')
    return query[0].message # Django does LIMIT here

def slow(expected_run_time, slowness_reason):
    '''
    This is a decorate that annotates a test as being "known
    to be slow."  The decorator will set expected_run_time and slowness_reason
    as atributes of the function.  Other code can use this annotation
    as needed, e.g. to exclude these tests in "fast" mode.
    '''
    def decorator(f):
        f.expected_run_time = expected_run_time
        f.slowness_reason = slowness_reason
        return f

    return decorator

def is_known_slow_test(test_method):
    return hasattr(test_method, 'slowness_reason')

API_KEYS = {}

class AuthedTestCase(TestCase):
    def client_patch(self, url, info):
        # self.client.patch will be available in later versions of Django,
        # although we may still want our version for the url encoding
        info = urllib.urlencode(info)
        return self.client.generic('PATCH', url, info)

    def login(self, email, password=None):
        if password is None:
            password = initial_password(email)
        return self.client.post('/accounts/login/',
                                {'username':email, 'password':password})

    def register(self, username, password):
        self.client.post('/accounts/home/',
                         {'email': username + '@zulip.com'})
        return self.submit_reg_form_for_user(username, password)

    def submit_reg_form_for_user(self, username, password):
        """
        Stage two of the two-step registration process.

        If things are working correctly the account should be fully
        registered after this call.
        """
        return self.client.post('/accounts/register/',
                                {'full_name': username, 'password': password,
                                 'key': find_key_by_email(username + '@zulip.com'),
                                 'terms': True})

    def get_api_key(self, email):
        if email not in API_KEYS:
            API_KEYS[email] =  get_user_profile_by_email(email).api_key
        return API_KEYS[email]

    def api_auth(self, email):
        credentials = "%s:%s" % (email, self.get_api_key(email))
        return {
            'HTTP_AUTHORIZATION': 'Basic ' + base64.b64encode(credentials)
            }

    def get_streams(self, email):
        """
        Helper function to get the stream names for a user
        """
        user_profile = get_user_profile_by_email(email)
        subs = Subscription.objects.filter(
            user_profile    = user_profile,
            active          = True,
            recipient__type = Recipient.STREAM)
        return [get_display_recipient(sub.recipient) for sub in subs]

    def send_message(self, sender_name, recipient_name, message_type,
                     content="test content", subject="test"):
        sender = get_user_profile_by_email(sender_name)
        if message_type == Recipient.PERSONAL:
            message_type_name = "private"
        else:
            message_type_name = "stream"
        recipient_list = [recipient_name] # Doesn't work for group PMs.
        (sending_client, _) = Client.objects.get_or_create(name="test suite")

        return check_send_message(
            sender, sending_client, message_type_name, recipient_list, subject,
            content, forged=False, forged_timestamp=None,
            forwarder_user_profile=sender, realm=sender.realm)

    def get_old_messages(self, anchor=1, num_before=100, num_after=100):
        post_params = {"anchor": anchor, "num_before": num_before,
                       "num_after": num_after}
        result = self.client.post("/json/get_old_messages", dict(post_params))
        data = ujson.loads(result.content)
        return data['messages']

    def users_subscribed_to_stream(self, stream_name, realm_domain):
        realm = Realm.objects.get(domain=realm_domain)
        stream = Stream.objects.get(name=stream_name, realm=realm)
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        subscriptions = Subscription.objects.filter(recipient=recipient)

        return [subscription.user_profile for subscription in subscriptions]

    def assert_json_success(self, result):
        """
        Successful POSTs return a 200 and JSON of the form {"result": "success",
        "msg": ""}.
        """
        self.assertEqual(result.status_code, 200)
        json = ujson.loads(result.content)
        self.assertEqual(json.get("result"), "success")
        # We have a msg key for consistency with errors, but it typically has an
        # empty value.
        self.assertIn("msg", json)

    def get_json_error(self, result):
        self.assertEqual(result.status_code, 400)
        json = ujson.loads(result.content)
        self.assertEqual(json.get("result"), "error")
        return json['msg']

    def assert_json_error(self, result, msg):
        """
        Invalid POSTs return a 400 and JSON of the form {"result": "error",
        "msg": "reason"}.
        """
        self.assertEqual(self.get_json_error(result), msg)

    def assert_json_error_contains(self, result, msg_substring):
        self.assertIn(msg_substring, self.get_json_error(result))

    def fixture_data(self, type, action, file_type='json'):
        return open(os.path.join(os.path.dirname(__file__),
                                 "fixtures/%s/%s_%s.%s" % (type, type, action,file_type))).read()

    # Subscribe to a stream directly
    def subscribe_to_stream(self, email, stream_name):
        stream, _ = create_stream_if_needed(Realm.objects.get(domain="zulip.com"), stream_name)
        user_profile = get_user_profile_by_email(email)
        do_add_subscription(user_profile, stream, no_log=True)

    # Subscribe to a stream by making an API request
    def common_subscribe_to_streams(self, email, streams, extra_post_data = {}, invite_only=False):
        api_key = self.get_api_key(email)

        post_data = {'email': email,
                     'api-key': api_key,
                     'subscriptions': ujson.dumps([{"name": stream} for stream in streams]),
                     'invite_only': ujson.dumps(invite_only)}
        post_data.update(extra_post_data)

        result = self.client.post("/api/v1/subscriptions/add", post_data)
        return result

    def send_json_payload(self, email, url, payload, stream_name=None, **post_params):
        if stream_name != None:
            self.subscribe_to_stream(email, stream_name)

        result = self.client.post(url, payload, **post_params)
        self.assert_json_success(result)

        # Check the correct message was sent
        msg = Message.objects.filter().order_by('-id')[0]
        self.assertEqual(msg.sender.email, email)
        self.assertEqual(get_display_recipient(msg.recipient), stream_name)

        return msg

class PublicURLTest(TestCase):
    """
    Account creation URLs are accessible even when not logged in. Authenticated
    URLs redirect to a page.
    """

    def fetch(self, method, urls, expected_status):
        for url in urls:
            if method == "get":
                response = self.client.get(url)
            else:
                response = self.client.post(url)
            self.assertEqual(response.status_code, expected_status,
                             msg="Expected %d, received %d for %s to %s" % (
                    expected_status, response.status_code, method, url))

    def test_public_urls(self):
        """
        Test which views are accessible when not logged in.
        """
        # FIXME: We should also test the Tornado URLs -- this codepath
        # can't do so because this Django test mechanism doesn't go
        # through Tornado.
        get_urls = {200: ["/accounts/home/", "/accounts/login/"],
                    302: ["/"],
                }
        post_urls = {200: ["/accounts/login/"],
                     302: ["/accounts/logout/"],
                     401: ["/json/get_public_streams",
                           "/json/get_old_messages",
                           "/json/update_pointer",
                           "/json/send_message",
                           "/json/invite_users",
                           "/json/settings/change",
                           "/json/subscriptions/list",
                           "/json/subscriptions/remove",
                           "/json/subscriptions/exists",
                           "/json/subscriptions/add",
                           "/json/subscriptions/property",
                           "/json/get_subscribers",
                           "/json/fetch_api_key",
                           ],
                     400: ["/api/v1/get_profile",
                           "/api/v1/get_old_messages",
                           "/api/v1/get_public_streams",
                           "/api/v1/subscriptions/list",
                           "/api/v1/subscriptions/add",
                           "/api/v1/subscriptions/remove",
                           "/api/v1/get_subscribers",
                           "/api/v1/send_message",
                           "/api/v1/update_pointer",
                           "/api/v1/external/github",
                           "/api/v1/fetch_api_key",
                           ],
                }
        for status_code, url_set in get_urls.iteritems():
            self.fetch("get", url_set, status_code)
        for status_code, url_set in post_urls.iteritems():
            self.fetch("post", url_set, status_code)

class LoginTest(AuthedTestCase):
    """
    Logging in, registration, and logging out.
    """

    def test_login(self):
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        self.assertEqual(self.client.session['_auth_user_id'], user_profile.id)

    def test_login_bad_password(self):
        self.login("hamlet@zulip.com", "wrongpassword")
        self.assertIsNone(self.client.session.get('_auth_user_id', None))

    def test_register(self):
        realm = Realm.objects.get(domain="zulip.com")
        streams = ["stream_%s" % i for i in xrange(40)]
        for stream in streams:
            create_stream_if_needed(realm, stream)

        set_default_streams(realm, streams)
        with queries_captured() as queries:
            self.register("test", "test")
        # Ensure the number of queries we make is not O(streams)
        self.assertTrue(len(queries) <= 59)
        user_profile = get_user_profile_by_email('test@zulip.com')
        self.assertEqual(self.client.session['_auth_user_id'], user_profile.id)

    def test_logout(self):
        self.login("hamlet@zulip.com")
        self.client.post('/accounts/logout/')
        self.assertIsNone(self.client.session.get('_auth_user_id', None))

    def test_non_ascii_login(self):
        """
        You can log in even if your password contain non-ASCII characters.
        """
        email = "test@zulip.com"
        password = u"hümbüǵ"

        # Registering succeeds.
        self.register("test", password)
        user_profile = get_user_profile_by_email(email)
        self.assertEqual(self.client.session['_auth_user_id'], user_profile.id)
        self.client.post('/accounts/logout/')
        self.assertIsNone(self.client.session.get('_auth_user_id', None))

        # Logging in succeeds.
        self.client.post('/accounts/logout/')
        self.login(email, password)
        self.assertEqual(self.client.session['_auth_user_id'], user_profile.id)

class PersonalMessagesTest(AuthedTestCase):

    def test_auto_subbed_to_personals(self):
        """
        Newly created users are auto-subbed to the ability to receive
        personals.
        """
        self.register("test", "test")
        user_profile = get_user_profile_by_email('test@zulip.com')
        old_messages_count = message_stream_count(user_profile)
        self.send_message("test@zulip.com", "test@zulip.com", Recipient.PERSONAL)
        new_messages_count = message_stream_count(user_profile)
        self.assertEqual(new_messages_count, old_messages_count + 1)

        recipient = Recipient.objects.get(type_id=user_profile.id,
                                          type=Recipient.PERSONAL)
        self.assertEqual(most_recent_message(user_profile).recipient, recipient)

    @slow(0.36, "checks several profiles")
    def test_personal_to_self(self):
        """
        If you send a personal to yourself, only you see it.
        """
        old_user_profiles = list(UserProfile.objects.all())
        self.register("test1", "test1")

        old_messages = []
        for user_profile in old_user_profiles:
            old_messages.append(message_stream_count(user_profile))

        self.send_message("test1@zulip.com", "test1@zulip.com", Recipient.PERSONAL)

        new_messages = []
        for user_profile in old_user_profiles:
            new_messages.append(message_stream_count(user_profile))

        self.assertEqual(old_messages, new_messages)

        user_profile = get_user_profile_by_email("test1@zulip.com")
        recipient = Recipient.objects.get(type_id=user_profile.id, type=Recipient.PERSONAL)
        self.assertEqual(most_recent_message(user_profile).recipient, recipient)

    def assert_personal(self, sender_email, receiver_email, content="test content"):
        """
        Send a private message from `sender_email` to `receiver_email` and check
        that only those two parties actually received the message.
        """
        sender = get_user_profile_by_email(sender_email)
        receiver = get_user_profile_by_email(receiver_email)

        sender_messages = message_stream_count(sender)
        receiver_messages = message_stream_count(receiver)

        other_user_profiles = UserProfile.objects.filter(~Q(email=sender_email) &
                                                         ~Q(email=receiver_email))
        old_other_messages = []
        for user_profile in other_user_profiles:
            old_other_messages.append(message_stream_count(user_profile))

        self.send_message(sender_email, receiver_email, Recipient.PERSONAL, content)

        # Users outside the conversation don't get the message.
        new_other_messages = []
        for user_profile in other_user_profiles:
            new_other_messages.append(message_stream_count(user_profile))

        self.assertEqual(old_other_messages, new_other_messages)

        # The personal message is in the streams of both the sender and receiver.
        self.assertEqual(message_stream_count(sender),
                         sender_messages + 1)
        self.assertEqual(message_stream_count(receiver),
                         receiver_messages + 1)

        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        self.assertEqual(most_recent_message(sender).recipient, recipient)
        self.assertEqual(most_recent_message(receiver).recipient, recipient)

    @slow(0.28, "assert_personal checks several profiles")
    def test_personal(self):
        """
        If you send a personal, only you and the recipient see it.
        """
        self.login("hamlet@zulip.com")
        self.assert_personal("hamlet@zulip.com", "othello@zulip.com")

    @slow(0.28, "assert_personal checks several profiles")
    def test_non_ascii_personal(self):
        """
        Sending a PM containing non-ASCII characters succeeds.
        """
        self.login("hamlet@zulip.com")
        self.assert_personal("hamlet@zulip.com", "othello@zulip.com", u"hümbüǵ")

class StreamMessagesTest(AuthedTestCase):

    def assert_stream_message(self, stream_name, subject="test subject",
                              content="test content"):
        """
        Check that messages sent to a stream reach all subscribers to that stream.
        """
        subscribers = self.users_subscribed_to_stream(stream_name, "zulip.com")
        old_subscriber_messages = []
        for subscriber in subscribers:
            old_subscriber_messages.append(message_stream_count(subscriber))

        non_subscribers = [user_profile for user_profile in UserProfile.objects.all()
                           if user_profile not in subscribers]
        old_non_subscriber_messages = []
        for non_subscriber in non_subscribers:
            old_non_subscriber_messages.append(message_stream_count(non_subscriber))

        a_subscriber_email = subscribers[0].email
        self.login(a_subscriber_email)
        self.send_message(a_subscriber_email, stream_name, Recipient.STREAM,
                          subject, content)

        # Did all of the subscribers get the message?
        new_subscriber_messages = []
        for subscriber in subscribers:
           new_subscriber_messages.append(message_stream_count(subscriber))

        # Did non-subscribers not get the message?
        new_non_subscriber_messages = []
        for non_subscriber in non_subscribers:
            new_non_subscriber_messages.append(message_stream_count(non_subscriber))

        self.assertEqual(old_non_subscriber_messages, new_non_subscriber_messages)
        self.assertEqual(new_subscriber_messages, [elt + 1 for elt in old_subscriber_messages])

    def test_not_too_many_queries(self):
        recipient_list  = ['hamlet@zulip.com', 'iago@zulip.com', 'cordelia@zulip.com', 'othello@zulip.com']
        for email in recipient_list:
            self.subscribe_to_stream(email, "Denmark")

        sender_email = 'hamlet@zulip.com'
        sender = get_user_profile_by_email(sender_email)
        message_type_name = "stream"
        (sending_client, _) = Client.objects.get_or_create(name="test suite")
        stream = 'Denmark'
        subject = 'foo'
        content = 'whatever'
        realm = sender.realm

        def send_message():
            check_send_message(sender, sending_client, message_type_name, [stream],
                               subject, content, forwarder_user_profile=sender, realm=realm)

        send_message() # prime the caches
        with queries_captured() as queries:
            send_message()

        self.assertTrue(len(queries) <= 4)

    def test_message_mentions(self):
        user_profile = get_user_profile_by_email("iago@zulip.com")
        self.subscribe_to_stream(user_profile.email, "Denmark")
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM,
                          content="test @**Iago** rules")
        message = most_recent_message(user_profile)
        assert(UserMessage.objects.get(user_profile=user_profile, message=message).flags.mentioned.is_set)

    @slow(0.28, 'checks all users')
    def test_message_to_stream(self):
        """
        If you send a message to a stream, everyone subscribed to the stream
        receives the messages.
        """
        self.assert_stream_message("Scotland")

    @slow(0.37, 'checks all users')
    def test_non_ascii_stream_message(self):
        """
        Sending a stream message containing non-ASCII characters in the stream
        name, subject, or message body succeeds.
        """
        self.login("hamlet@zulip.com")

        # Subscribe everyone to a stream with non-ASCII characters.
        non_ascii_stream_name = u"hümbüǵ"
        realm = Realm.objects.get(domain="zulip.com")
        stream, _ = create_stream_if_needed(realm, non_ascii_stream_name)
        for user_profile in UserProfile.objects.filter(realm=realm):
            do_add_subscription(user_profile, stream, no_log=True)

        self.assert_stream_message(non_ascii_stream_name, subject=u"hümbüǵ",
                                   content=u"hümbüǵ")

class MessageDictTest(AuthedTestCase):
    @slow(1.6, 'builds lots of messages')
    def test_bulk_message_fetching(self):
        realm = Realm.objects.get(domain="zulip.com")
        sender = get_user_profile_by_email('othello@zulip.com')
        receiver = get_user_profile_by_email('hamlet@zulip.com')
        pm_recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        stream, _ = create_stream_if_needed(realm, 'devel')
        stream_recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        sending_client, _ = Client.objects.get_or_create(name="test suite")

        for i in range(300):
            for recipient in [pm_recipient, stream_recipient]:
                message = Message(
                    sender=sender,
                    recipient=recipient,
                    subject='whatever',
                    content='whatever %d' % i,
                    pub_date=datetime.datetime.now(),
                    sending_client=sending_client,
                    last_edit_time=datetime.datetime.now(),
                    edit_history='[]'
                )
                message.save()

        ids = [row['id'] for row in Message.objects.all().values('id')]
        num_ids = len(ids)
        self.assertTrue(num_ids >= 600)

        t = time.time()
        with queries_captured() as queries:
            rows = list(Message.get_raw_db_rows(ids))

            for row in rows:
                Message.build_dict_from_raw_db_row(row, False)

        delay = time.time() - t
        # Make sure we don't take longer than 1ms per message to extract messages.
        self.assertTrue(delay < 0.001 * num_ids)
        self.assertTrue(len(queries) <= 5)
        self.assertEqual(len(rows), num_ids)

    def test_applying_markdown(self):
        sender = get_user_profile_by_email('othello@zulip.com')
        receiver = get_user_profile_by_email('hamlet@zulip.com')
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        sending_client, _ = Client.objects.get_or_create(name="test suite")
        message = Message(
            sender=sender,
            recipient=recipient,
            subject='whatever',
            content='hello **world**',
            pub_date=datetime.datetime.now(),
            sending_client=sending_client,
            last_edit_time=datetime.datetime.now(),
            edit_history='[]'
        )
        message.save()

        # An important part of this test is to get the message through this exact code path,
        # because there is an ugly hack we need to cover.  So don't just say "row = message".
        row = Message.get_raw_db_rows([message.id])[0]
        dct = Message.build_dict_from_raw_db_row(row, apply_markdown=True)
        expected_content = '<p>hello <strong>world</strong></p>'
        self.assertEqual(dct['content'], expected_content)
        message = Message.objects.get(id=message.id)
        self.assertEqual(message.rendered_content, expected_content)
        self.assertEqual(message.rendered_content_version, bugdown.version)

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
        result = self.client.delete("/json/users/hambot-bot@zulip.com")
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
        result = self.client.delete("/json/users/bogus-bot@zulip.com")
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

        result = self.client.delete("/json/users/hamlet@zulip.com")
        self.assert_json_error(result, 'Insufficient permission')

        result = self.client.delete("/json/users/hambot-bot@zulip.com")
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
        api_key = self.get_api_key(email)
        self.assertEqual(get_user_profile_by_email(email).pointer, -1)
        msg_id = self.send_message("othello@zulip.com", "Verona", Recipient.STREAM)
        result = self.client.post("/api/v1/update_pointer", {"email": email,
                                                             "api-key": api_key,
                                                             "pointer": msg_id})
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

class MessagePOSTTest(AuthedTestCase):

    def test_message_to_self(self):
        """
        Sending a message to a stream to which you are subscribed is
        successful.
        """
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/send_message", {"type": "stream",
                                                         "to": "Verona",
                                                         "client": "test suite",
                                                         "content": "Test message",
                                                         "subject": "Test subject"})
        self.assert_json_success(result)

    def test_api_message_to_self(self):
        """
        Same as above, but for the API view
        """
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        result = self.client.post("/api/v1/send_message", {"type": "stream",
                                                           "to": "Verona",
                                                           "client": "test suite",
                                                           "content": "Test message",
                                                           "subject": "Test subject",
                                                           "email": email,
                                                           "api-key": api_key})
        self.assert_json_success(result)

    def test_message_to_nonexistent_stream(self):
        """
        Sending a message to a nonexistent stream fails.
        """
        self.login("hamlet@zulip.com")
        self.assertFalse(Stream.objects.filter(name="nonexistent_stream"))
        result = self.client.post("/json/send_message", {"type": "stream",
                                                         "to": "nonexistent_stream",
                                                         "client": "test suite",
                                                         "content": "Test message",
                                                         "subject": "Test subject"})
        self.assert_json_error(result, "Stream does not exist")

    def test_personal_message(self):
        """
        Sending a personal message to a valid username is successful.
        """
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/send_message", {"type": "private",
                                                         "content": "Test message",
                                                         "client": "test suite",
                                                         "to": "othello@zulip.com"})
        self.assert_json_success(result)

    def test_personal_message_to_nonexistent_user(self):
        """
        Sending a personal message to an invalid email returns error JSON.
        """
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/send_message", {"type": "private",
                                                         "content": "Test message",
                                                         "client": "test suite",
                                                         "to": "nonexistent"})
        self.assert_json_error(result, "Invalid email 'nonexistent'")

    def test_invalid_type(self):
        """
        Sending a message of unknown type returns error JSON.
        """
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/send_message", {"type": "invalid type",
                                                         "content": "Test message",
                                                         "client": "test suite",
                                                         "to": "othello@zulip.com"})
        self.assert_json_error(result, "Invalid message type")

    def test_empty_message(self):
        """
        Sending a message that is empty or only whitespace should fail
        """
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/send_message", {"type": "private",
                                                         "content": " ",
                                                         "client": "test suite",
                                                         "to": "othello@zulip.com"})
        self.assert_json_error(result, "Message must not be empty")


    def test_mirrored_huddle(self):
        """
        Sending a mirrored huddle message works
        """
        self.login("starnine@mit.edu")
        result = self.client.post("/json/send_message", {"type": "private",
                                                         "sender": "sipbtest@mit.edu",
                                                         "content": "Test message",
                                                         "client": "zephyr_mirror",
                                                         "to": ujson.dumps(["starnine@mit.edu",
                                                                            "espuser@mit.edu"])})
        self.assert_json_success(result)

    def test_mirrored_personal(self):
        """
        Sending a mirrored personal message works
        """
        self.login("starnine@mit.edu")
        result = self.client.post("/json/send_message", {"type": "private",
                                                         "sender": "sipbtest@mit.edu",
                                                         "content": "Test message",
                                                         "client": "zephyr_mirror",
                                                         "to": "starnine@mit.edu"})
        self.assert_json_success(result)

    def test_duplicated_mirrored_huddle(self):
        """
        Sending two mirrored huddles in the row return the same ID
        """
        msg = {"type": "private",
               "sender": "sipbtest@mit.edu",
               "content": "Test message",
               "client": "zephyr_mirror",
               "to": ujson.dumps(["sipbcert@mit.edu",
                                  "starnine@mit.edu"])}

        self.login("starnine@mit.edu")
        result1 = self.client.post("/json/send_message", msg)
        self.login("sipbcert@mit.edu")
        result2 = self.client.post("/json/send_message", msg)
        self.assertEqual(ujson.loads(result1.content)['id'],
                         ujson.loads(result2.content)['id'])

class SubscriptionPropertiesTest(AuthedTestCase):

    def test_get_stream_color(self):
        """
        A GET request to
        /json/subscriptions/property?property=color+stream_name=foo returns
        the color for stream foo.
        """
        test_email = "hamlet@zulip.com"
        self.login(test_email)
        subs = gather_subscriptions(get_user_profile_by_email(test_email))[0]
        result = self.client.get("/json/subscriptions/property",
                                  {"property": "color",
                                   "stream_name": subs[0]['name']})

        self.assert_json_success(result)
        json = ujson.loads(result.content)

        self.assertIn("stream_name", json)
        self.assertIn("value", json)
        self.assertIsInstance(json["stream_name"], basestring)
        self.assertIsInstance(json["value"],  basestring)
        self.assertEqual(json["stream_name"], subs[0]["name"])
        self.assertEqual(json["value"], subs[0]["color"])

    def test_set_stream_color(self):
        """
        A POST request to /json/subscriptions/property with stream_name and
        color data sets the stream color, and for that stream only.
        """
        test_email = "hamlet@zulip.com"
        self.login(test_email)

        old_subs, _ = gather_subscriptions(get_user_profile_by_email(test_email))
        sub = old_subs[0]
        stream_name = sub['name']
        new_color = "#ffffff" # TODO: ensure that this is different from old_color
        result = self.client.post("/json/subscriptions/property",
                                  {"property": "color",
                                   "stream_name": stream_name,
                                   "value": "#ffffff"})

        self.assert_json_success(result)

        new_subs = gather_subscriptions(get_user_profile_by_email(test_email))[0]
        found_sub = None
        for sub in new_subs:
            if sub['name'] == stream_name:
                found_sub = sub
                break

        self.assertIsNotNone(found_sub)
        self.assertEqual(found_sub['color'], new_color)

        new_subs.remove(found_sub)
        for sub in old_subs:
            if sub['name'] == stream_name:
                found_sub = sub
                break
        old_subs.remove(found_sub)
        self.assertEqual(old_subs, new_subs)

    def test_set_color_missing_stream_name(self):
        """
        Updating the color property requires a stream_name.
        """
        test_email = "hamlet@zulip.com"
        self.login(test_email)
        result = self.client.post("/json/subscriptions/property",
                                  {"property": "color",
                                   "value": "#ffffff"})

        self.assert_json_error(result, "Missing 'stream_name' argument")

    def test_set_color_missing_color(self):
        """
        Updating the color property requires a color.
        """
        test_email = "hamlet@zulip.com"
        self.login(test_email)
        subs = gather_subscriptions(get_user_profile_by_email(test_email))[0]
        result = self.client.post("/json/subscriptions/property",
                                  {"property": "color",
                                   "stream_name": subs[0]["name"]})

        self.assert_json_error(result, "Missing 'value' argument")

    def test_set_invalid_property(self):
        """
        Trying to set an invalid property returns a JSON error.
        """
        test_email = "hamlet@zulip.com"
        self.login(test_email)
        subs = gather_subscriptions(get_user_profile_by_email(test_email))[0]
        result = self.client.post("/json/subscriptions/property",
                                  {"property": "bad",
                                   "stream_name": subs[0]["name"]})

        self.assert_json_error(result,
                               "Unknown subscription property: bad")

class SubscriptionAPITest(AuthedTestCase):

    def setUp(self):
        """
        All tests will be logged in as hamlet. Also save various useful values
        as attributes that tests can access.
        """
        self.test_email = "hamlet@zulip.com"
        self.login(self.test_email)
        self.user_profile = get_user_profile_by_email(self.test_email)
        self.realm = self.user_profile.realm
        self.streams = self.get_streams(self.test_email)

    def make_random_stream_names(self, existing_stream_names):
        """
        Helper function to make up random stream names. It takes
        existing_stream_names and randomly appends a digit to the end of each,
        but avoids names that appear in the list names_to_avoid.
        """
        random_streams = []
        all_stream_names = [stream.name for stream in Stream.objects.filter(realm=self.realm)]
        for stream in existing_stream_names:
            random_stream = stream + str(random.randint(0, 9))
            if not random_stream in all_stream_names:
                random_streams.append(random_stream)
        return random_streams

    def test_successful_subscriptions_list(self):
        """
        Calling /json/subscriptions/list should successfully return your subscriptions.
        """
        result = self.client.post("/json/subscriptions/list", {})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("subscriptions", json)
        for stream in json["subscriptions"]:
            self.assertIsInstance(stream['name'], basestring)
            self.assertIsInstance(stream['color'], basestring)
            self.assertIsInstance(stream['invite_only'], bool)
            # check that the stream name corresponds to an actual stream
            try:
                Stream.objects.get(name__iexact=stream['name'], realm=self.realm)
            except Stream.DoesNotExist:
                self.fail("stream does not exist")
        list_streams = [stream['name'] for stream in json["subscriptions"]]
        # also check that this matches the list of your subscriptions
        self.assertItemsEqual(list_streams, self.streams)

    def helper_check_subs_before_and_after_add(self, subscriptions, other_params,
                                               subscribed, already_subscribed,
                                               email, new_subs, invite_only=False):
        """
        Check result of adding subscriptions.

        You can add subscriptions for yourself or possibly many
        principals, which is why e-mails map to subscriptions in the
        result.

        The result json is of the form

        {"msg": "",
         "result": "success",
         "already_subscribed": {"iago@zulip.com": ["Venice", "Verona"]},
         "subscribed": {"iago@zulip.com": ["Venice8"]}}
        """
        result = self.common_subscribe_to_streams(self.test_email, subscriptions,
                                                  other_params, invite_only=invite_only)
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertItemsEqual(subscribed, json["subscribed"][email])
        self.assertItemsEqual(already_subscribed, json["already_subscribed"][email])
        new_streams = self.get_streams(email)
        self.assertItemsEqual(new_streams, new_subs)

    def test_successful_subscriptions_add(self):
        """
        Calling /json/subscriptions/add should successfully add streams, and
        should determine which are new subscriptions vs which were already
        subscribed. We randomly generate stream names to add, because it
        doesn't matter whether the stream already exists.
        """
        self.assertNotEqual(len(self.streams), 0)  # necessary for full test coverage
        add_streams = self.make_random_stream_names(self.streams)
        self.assertNotEqual(len(add_streams), 0)  # necessary for full test coverage
        events = []
        with tornado_redirected_to_list(events):
            self.helper_check_subs_before_and_after_add(self.streams + add_streams, {},
                add_streams, self.streams, self.test_email, self.streams + add_streams)
        self.assertEqual(len(events), 1)

    def test_non_ascii_stream_subscription(self):
        """
        Subscribing to a stream name with non-ASCII characters succeeds.
        """
        self.helper_check_subs_before_and_after_add(self.streams + [u"hümbüǵ"], {},
            [u"hümbüǵ"], self.streams, self.test_email, self.streams + [u"hümbüǵ"])

    def test_subscriptions_add_too_long(self):
        """
        Calling /json/subscriptions/add on a stream whose name is >30
        characters should return a JSON error.
        """
        # character limit is 30 characters
        long_stream_name = "a" * 31
        result = self.common_subscribe_to_streams(self.test_email, [long_stream_name])
        self.assert_json_error(result,
                               "Stream name (%s) too long." % (long_stream_name,))

    def test_subscriptions_add_invalid_stream(self):
        """
        Calling /json/subscriptions/add on a stream whose name is invalid (as
        defined by valid_stream_name in zerver/views.py) should return a JSON
        error.
        """
        # currently, the only invalid name is the empty string
        invalid_stream_name = ""
        result = self.common_subscribe_to_streams(self.test_email, [invalid_stream_name])
        self.assert_json_error(result,
                               "Invalid stream name (%s)." % (invalid_stream_name,))

    def assert_adding_subscriptions_for_principal(self, invitee, streams, invite_only=False):
        """
        Calling /json/subscriptions/add on behalf of another principal (for
        whom you have permission to add subscriptions) should successfully add
        those subscriptions and send a message to the subscribee notifying
        them.
        """
        other_profile = get_user_profile_by_email(invitee)
        current_streams = self.get_streams(invitee)
        self.assertIsInstance(other_profile, UserProfile)
        self.assertNotEqual(len(current_streams), 0)  # necessary for full test coverage
        self.assertNotEqual(len(streams), 0)  # necessary for full test coverage
        streams_to_sub = streams[:1]  # just add one, to make the message easier to check
        streams_to_sub.extend(current_streams)
        self.helper_check_subs_before_and_after_add(streams_to_sub,
            {"principals": ujson.dumps([invitee])}, streams[:1], current_streams,
            invitee, streams_to_sub, invite_only=invite_only)
        # verify that the user was sent a message informing them about the subscription
        msg = Message.objects.latest('id')
        self.assertEqual(msg.recipient.type, msg.recipient.PERSONAL)
        self.assertEqual(msg.sender_id,
                get_user_profile_by_email("notification-bot@zulip.com").id)
        expected_msg = ("Hi there!  We thought you'd like to know that %s just "
                        "subscribed you to the %sstream '%s'"
                        % (self.user_profile.full_name,
                           '**invite-only** ' if invite_only else '',
                           streams[0]))

        if not Stream.objects.get(name=streams[0]).invite_only:
            expected_msg += ("\nYou can see historical content on a "
                             "non-invite-only stream by narrowing to it.")
        self.assertEqual(msg.content, expected_msg)
        recipients = get_display_recipient(msg.recipient)
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]['email'], invitee)

    def test_multi_user_subscription(self):
        email1 = 'cordelia@zulip.com'
        email2 = 'iago@zulip.com'
        realm = Realm.objects.get(domain="zulip.com")
        streams_to_sub = ['multi_user_stream']
        events = []
        with tornado_redirected_to_list(events):
            with queries_captured() as queries:
                self.common_subscribe_to_streams(
                    self.test_email,
                    streams_to_sub,
                    dict(principals=ujson.dumps([email1, email2])),
            )
        self.assertTrue(len(queries) <= 34)

        self.assertEqual(len(events), 2)
        for ev in events:
            self.assertEqual(ev['event']['op'], 'add')
            self.assertEqual(
                    set(ev['event']['subscriptions'][0]['subscribers']),
                    set([email1, email2])
            )

        stream = get_stream('multi_user_stream', realm)
        self.assertEqual(stream.num_subscribers(), 2)

        # Now add ourselves
        events = []
        with tornado_redirected_to_list(events):
            with queries_captured() as queries:
                self.common_subscribe_to_streams(
                        self.test_email,
                        streams_to_sub,
                        dict(principals=ujson.dumps([self.test_email])),
                )
        self.assertTrue(len(queries) <= 4)

        self.assertEqual(len(events), 2)
        add_event, add_peer_event = events
        self.assertEqual(add_event['event']['type'], 'subscriptions')
        self.assertEqual(add_event['event']['op'], 'add')
        self.assertEqual(add_event['users'], [get_user_profile_by_email(self.test_email).id])
        self.assertEqual(
                set(add_event['event']['subscriptions'][0]['subscribers']),
                set([email1, email2, self.test_email])
        )

        self.assertEqual(len(add_peer_event['users']), 2)
        self.assertEqual(add_peer_event['event']['type'], 'subscriptions')
        self.assertEqual(add_peer_event['event']['op'], 'peer_add')
        self.assertEqual(add_peer_event['event']['user_email'], self.test_email)

        stream = get_stream('multi_user_stream', realm)
        self.assertEqual(stream.num_subscribers(), 3)

        # Finally, add othello, exercising the do_add_subscription() code path.
        events = []
        email3 = 'othello@zulip.com'
        user_profile = get_user_profile_by_email(email3)
        stream = get_stream('multi_user_stream', realm)
        with tornado_redirected_to_list(events):
            do_add_subscription(user_profile, stream)

        self.assertEqual(len(events), 2)
        add_event, add_peer_event = events

        self.assertEqual(add_event['event']['type'], 'subscriptions')
        self.assertEqual(add_event['event']['op'], 'add')
        self.assertEqual(add_event['users'], [get_user_profile_by_email(email3).id])
        self.assertEqual(
                set(add_event['event']['subscriptions'][0]['subscribers']),
                set([email1, email2, email3, self.test_email])
        )

        self.assertEqual(len(add_peer_event['users']), 3)
        self.assertEqual(add_peer_event['event']['type'], 'subscriptions')
        self.assertEqual(add_peer_event['event']['op'], 'peer_add')
        self.assertEqual(add_peer_event['event']['user_email'], email3)


    def test_bulk_subscribe_MIT(self):
        realm = Realm.objects.get(domain="mit.edu")
        streams = ["stream_%s" % i for i in xrange(40)]
        for stream in streams:
            create_stream_if_needed(realm, stream)

        events = []
        with tornado_redirected_to_list(events):
            with queries_captured() as queries:
                self.common_subscribe_to_streams(
                        'starnine@mit.edu',
                        streams,
                        dict(principals=ujson.dumps(['starnine@mit.edu'])),
                )
        # Make sure MIT does not get any tornado subscription events
        self.assertEqual(len(events), 0)
        self.assertTrue(len(queries) <= 5)

    def test_bulk_subscribe_many(self):
        # Create a whole bunch of streams
        realm = Realm.objects.get(domain="zulip.com")
        streams = ["stream_%s" % i for i in xrange(20)]
        for stream in streams:
            create_stream_if_needed(realm, stream)

        with queries_captured() as queries:
                self.common_subscribe_to_streams(
                        self.test_email,
                        streams,
                        dict(principals=ujson.dumps([self.test_email])),
                )
        # Make sure we don't make O(streams) queries
        self.assertTrue(len(queries) <= 7)

    @slow(0.15, "common_subscribe_to_streams is slow")
    def test_subscriptions_add_for_principal(self):
        """
        You can subscribe other people to streams.
        """
        invitee = "iago@zulip.com"
        current_streams = self.get_streams(invitee)
        invite_streams = self.make_random_stream_names(current_streams)
        self.assert_adding_subscriptions_for_principal(invitee, invite_streams)

    @slow(0.15, "common_subscribe_to_streams is slow")
    def test_subscriptions_add_for_principal_invite_only(self):
        """
        You can subscribe other people to invite only streams.
        """
        invitee = "iago@zulip.com"
        current_streams = self.get_streams(invitee)
        invite_streams = self.make_random_stream_names(current_streams)
        self.assert_adding_subscriptions_for_principal(invitee, invite_streams,
                                                       invite_only=True)

    @slow(0.15, "common_subscribe_to_streams is slow")
    def test_non_ascii_subscription_for_principal(self):
        """
        You can subscribe other people to streams even if they containing
        non-ASCII characters.
        """
        self.assert_adding_subscriptions_for_principal("iago@zulip.com", [u"hümbüǵ"])

    def test_subscription_add_invalid_principal(self):
        """
        Calling subscribe on behalf of a principal that does not exist
        should return a JSON error.
        """
        invalid_principal = "rosencrantz-and-guildenstern@zulip.com"
        # verify that invalid_principal actually doesn't exist
        with self.assertRaises(UserProfile.DoesNotExist):
            get_user_profile_by_email(invalid_principal)
        result = self.common_subscribe_to_streams(self.test_email, self.streams,
                                                  {"principals": ujson.dumps([invalid_principal])})
        self.assert_json_error(result, "User not authorized to execute queries on behalf of '%s'"
                               % (invalid_principal,))

    def test_subscription_add_principal_other_realm(self):
        """
        Calling subscribe on behalf of a principal in another realm
        should return a JSON error.
        """
        principal = "starnine@mit.edu"
        profile = get_user_profile_by_email(principal)
        # verify that principal exists (thus, the reason for the error is the cross-realming)
        self.assertIsInstance(profile, UserProfile)
        result = self.common_subscribe_to_streams(self.test_email, self.streams,
                                                  {"principals": ujson.dumps([principal])})
        self.assert_json_error(result, "User not authorized to execute queries on behalf of '%s'"
                               % (principal,))

    def helper_check_subs_before_and_after_remove(self, subscriptions, json_dict,
                                                  email, new_subs):
        """
        Check result of removing subscriptions.

        Unlike adding subscriptions, you can only remove subscriptions
        for yourself, so the result format is different.

        {"msg": "",
         "removed": ["Denmark", "Scotland", "Verona"],
         "not_subscribed": ["Rome"], "result": "success"}
        """
        result = self.client.post("/json/subscriptions/remove",
                                  {"subscriptions": ujson.dumps(subscriptions)})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        for key, val in json_dict.iteritems():
            self.assertItemsEqual(val, json[key])  # we don't care about the order of the items
        new_streams = self.get_streams(email)
        self.assertItemsEqual(new_streams, new_subs)

    def test_successful_subscriptions_remove(self):
        """
        Calling /json/subscriptions/remove should successfully remove streams,
        and should determine which were removed vs which weren't subscribed to.
        We cannot randomly generate stream names because the remove code
        verifies whether streams exist.
        """
        if len(self.streams) < 2:
            self.fail()  # necesssary for full test coverage
        streams_to_remove = self.streams[1:]
        not_subbed = []
        for stream in Stream.objects.all():
            if not stream.name in self.streams:
                not_subbed.append(stream.name)
        random.shuffle(not_subbed)
        self.assertNotEqual(len(not_subbed), 0)  # necessary for full test coverage
        try_to_remove = not_subbed[:3]  # attempt to remove up to 3 streams not already subbed to
        streams_to_remove.extend(try_to_remove)
        self.helper_check_subs_before_and_after_remove(streams_to_remove,
            {"removed": self.streams[1:], "not_subscribed": try_to_remove},
            self.test_email, [self.streams[0]])

    def test_subscriptions_remove_fake_stream(self):
        """
        Calling /json/subscriptions/remove on a stream that doesn't exist
        should return a JSON error.
        """
        random_streams = self.make_random_stream_names(self.streams)
        self.assertNotEqual(len(random_streams), 0)  # necessary for full test coverage
        streams_to_remove = random_streams[:1]  # pick only one fake stream, to make checking the error message easy
        result = self.client.post("/json/subscriptions/remove",
                                  {"subscriptions": ujson.dumps(streams_to_remove)})
        self.assert_json_error(result, "Stream(s) (%s) do not exist" % (random_streams[0],))

    def helper_subscriptions_exists(self, stream, exists, subscribed):
        """
        A helper function that calls /json/subscriptions/exists on a stream and
        verifies that the returned JSON dictionary has the exists and
        subscribed values passed in as parameters. (If subscribed should not be
        present, pass in None.)
        """
        result = self.client.post("/json/subscriptions/exists",
                                  {"stream": stream})
        json = ujson.loads(result.content)
        self.assertIn("exists", json)
        self.assertEqual(json["exists"], exists)
        if exists:
            self.assert_json_success(result)
        else:
            self.assertEquals(result.status_code, 404)
        if not subscribed is None:
            self.assertIn("subscribed", json)
            self.assertEqual(json["subscribed"], subscribed)

    def test_successful_subscriptions_exists_subbed(self):
        """
        Calling /json/subscriptions/exist on a stream to which you are subbed
        should return that it exists and that you are subbed.
        """
        self.assertNotEqual(len(self.streams), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(self.streams[0], True, True)

    def test_successful_subscriptions_exists_not_subbed(self):
        """
        Calling /json/subscriptions/exist on a stream to which you are not
        subbed should return that it exists and that you are not subbed.
        """
        all_stream_names = [stream.name for stream in Stream.objects.filter(realm=self.realm)]
        streams_not_subbed = list(set(all_stream_names) - set(self.streams))
        self.assertNotEqual(len(streams_not_subbed), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(streams_not_subbed[0], True, False)

    def test_subscriptions_does_not_exist(self):
        """
        Calling /json/subscriptions/exist on a stream that doesn't exist should
        return that it doesn't exist.
        """
        random_streams = self.make_random_stream_names(self.streams)
        self.assertNotEqual(len(random_streams), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(random_streams[0], False, None)

    def test_subscriptions_exist_invalid_name(self):
        """
        Calling /json/subscriptions/exist on a stream whose name is invalid (as
        defined by valid_stream_name in zerver/views.py) should return a JSON
        error.
        """
        # currently, the only invalid stream name is the empty string
        invalid_stream_name = ""
        result = self.client.post("/json/subscriptions/exists",
                                  {"stream": invalid_stream_name})
        self.assert_json_error(result, "Invalid characters in stream name")

class GetOldMessagesTest(AuthedTestCase):

    def post_with_params(self, modified_params):
        post_params = {"anchor": 1, "num_before": 1, "num_after": 1}
        post_params.update(modified_params)
        result = self.client.post("/json/get_old_messages", dict(post_params))
        self.assert_json_success(result)
        return ujson.loads(result.content)

    def check_well_formed_messages_response(self, result):
        self.assertIn("messages", result)
        self.assertIsInstance(result["messages"], list)
        for message in result["messages"]:
            for field in ("content", "content_type", "display_recipient",
                          "avatar_url", "recipient_id", "sender_full_name",
                          "sender_short_name", "timestamp"):
                self.assertIn(field, message)
            # TODO: deprecate soon in favor of avatar_url
            self.assertIn('gravatar_hash', message)

    def test_successful_get_old_messages(self):
        """
        A call to /json/get_old_messages with valid parameters returns a list of
        messages.
        """
        self.login("hamlet@zulip.com")
        self.check_well_formed_messages_response(self.post_with_params({}))

    def test_get_old_messages_with_narrow_pm_with(self):
        """
        A request for old messages with a narrow by pm-with only returns
        conversations with that user.
        """
        me = 'hamlet@zulip.com'
        def dr_emails(dr):
            return ','.join(sorted(set([r['email'] for r in dr] + [me])))

        personals = [m for m in get_user_messages(get_user_profile_by_email(me))
            if m.recipient.type == Recipient.PERSONAL
            or m.recipient.type == Recipient.HUDDLE]
        if not personals:
            # FIXME: This is bad.  We should use test data that is guaranteed
            # to contain some personals for every user.  See #617.
            return
        emails = dr_emails(get_display_recipient(personals[0].recipient))

        self.login(me)
        result = self.post_with_params({"narrow": ujson.dumps(
                    [['pm-with', emails]])})
        self.check_well_formed_messages_response(result)

        for message in result["messages"]:
            self.assertEqual(dr_emails(message['display_recipient']), emails)

    def test_get_old_messages_with_narrow_stream(self):
        """
        A request for old messages with a narrow by stream only returns
        messages for that stream.
        """
        self.login("hamlet@zulip.com")
        # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        realm = Realm.objects.get(domain="zulip.com")
        stream, _ = create_stream_if_needed(realm, "Scotland")
        do_add_subscription(get_user_profile_by_email("hamlet@zulip.com"),
                            stream, no_log=True)
        self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM)
        messages = get_user_messages(get_user_profile_by_email("hamlet@zulip.com"))
        stream_messages = filter(lambda msg: msg.recipient.type == Recipient.STREAM,
                                 messages)
        stream_name = get_display_recipient(stream_messages[0].recipient)
        stream_id = stream_messages[0].recipient.id

        result = self.post_with_params({"narrow": ujson.dumps(
                    [['stream', stream_name]])})
        self.check_well_formed_messages_response(result)

        for message in result["messages"]:
            self.assertEqual(message["type"], "stream")
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_old_messages_with_narrow_sender(self):
        """
        A request for old messages with a narrow by sender only returns
        messages sent by that person.
        """
        self.login("hamlet@zulip.com")
        # We need to send a message here to ensure that we actually
        # have a stream message in this narrow view.
        self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM)
        self.send_message("othello@zulip.com", "Scotland", Recipient.STREAM)
        self.send_message("othello@zulip.com", "hamlet@zulip.com", Recipient.PERSONAL)
        self.send_message("iago@zulip.com", "Scotland", Recipient.STREAM)

        result = self.post_with_params({"narrow": ujson.dumps(
                    [['sender', "othello@zulip.com"]])})
        self.check_well_formed_messages_response(result)

        for message in result["messages"]:
            self.assertEqual(message["sender_email"], "othello@zulip.com")

    def test_missing_params(self):
        """
        anchor, num_before, and num_after are all required
        POST parameters for get_old_messages.
        """
        self.login("hamlet@zulip.com")

        required_args = (("anchor", 1), ("num_before", 1), ("num_after", 1))

        for i in range(len(required_args)):
            post_params = dict(required_args[:i] + required_args[i + 1:])
            result = self.client.post("/json/get_old_messages", post_params)
            self.assert_json_error(result,
                                   "Missing '%s' argument" % (required_args[i][0],))

    def test_bad_int_params(self):
        """
        num_before, num_after, and narrow must all be non-negative
        integers or strings that can be converted to non-negative integers.
        """
        self.login("hamlet@zulip.com")

        other_params = [("narrow", {}), ("anchor", 0)]
        int_params = ["num_before", "num_after"]

        bad_types = (False, "", "-1", -1)
        for idx, param in enumerate(int_params):
            for type in bad_types:
                # Rotate through every bad type for every integer
                # parameter, one at a time.
                post_params = dict(other_params + [(param, type)] + \
                                       [(other_param, 0) for other_param in \
                                            int_params[:idx] + int_params[idx + 1:]]
                                   )
                result = self.client.post("/json/get_old_messages", post_params)
                self.assert_json_error(result,
                                       "Bad value for '%s': %s" % (param, type))

    def test_bad_narrow_type(self):
        """
        narrow must be a list of string pairs.
        """
        self.login("hamlet@zulip.com")

        other_params = [("anchor", 0), ("num_before", 0), ("num_after", 0)]

        bad_types = (False, 0, '', '{malformed json,',
            '{foo: 3}', '[1,2]', '[["x","y","z"]]')
        for type in bad_types:
            post_params = dict(other_params + [("narrow", type)])
            result = self.client.post("/json/get_old_messages", post_params)
            self.assert_json_error(result,
                                   "Bad value for 'narrow': %s" % (type,))

    def test_old_empty_narrow(self):
        """
        '{}' is accepted to mean 'no narrow', for use by old mobile clients.
        """
        self.login("hamlet@zulip.com")
        all_result    = self.post_with_params({})
        narrow_result = self.post_with_params({'narrow': '{}'})

        for r in (all_result, narrow_result):
            self.check_well_formed_messages_response(r)

        self.assertEqual(message_ids(all_result), message_ids(narrow_result))

    def test_bad_narrow_operator(self):
        """
        Unrecognized narrow operators are rejected.
        """
        self.login("hamlet@zulip.com")
        for operator in ['', 'foo', 'stream:verona', '__init__']:
            params = dict(anchor=0, num_before=0, num_after=0,
                narrow=ujson.dumps([[operator, '']]))
            result = self.client.post("/json/get_old_messages", params)
            self.assert_json_error_contains(result,
                "Invalid narrow operator: unknown operator")

    def exercise_bad_narrow_operand(self, operator, operands, error_msg):
        other_params = [("anchor", 0), ("num_before", 0), ("num_after", 0)]
        for operand in operands:
            post_params = dict(other_params + [
                ("narrow", ujson.dumps([[operator, operand]]))])
            result = self.client.post("/json/get_old_messages", post_params)
            self.assert_json_error_contains(result, error_msg)

    def test_bad_narrow_stream_content(self):
        """
        If an invalid stream name is requested in get_old_messages, an error is
        returned.
        """
        self.login("hamlet@zulip.com")
        bad_stream_content = (0, [], ["x", "y"])
        self.exercise_bad_narrow_operand("stream", bad_stream_content,
            "Bad value for 'narrow'")

    def test_bad_narrow_one_on_one_email_content(self):
        """
        If an invalid 'pm-with' is requested in get_old_messages, an
        error is returned.
        """
        self.login("hamlet@zulip.com")
        bad_stream_content = (0, [], ["x","y"])
        self.exercise_bad_narrow_operand("pm-with", bad_stream_content,
            "Bad value for 'narrow'")

    def test_bad_narrow_nonexistent_stream(self):
        self.login("hamlet@zulip.com")
        self.exercise_bad_narrow_operand("stream", ['non-existent stream'],
            "Invalid narrow operator: unknown stream")

    def test_bad_narrow_nonexistent_email(self):
        self.login("hamlet@zulip.com")
        self.exercise_bad_narrow_operand("pm-with", ['non-existent-user@zulip.com'],
            "Invalid narrow operator: unknown user")

    def test_message_without_rendered_content(self):
        """Older messages may not have rendered_content in the database"""
        m = Message.objects.all().order_by('-id')[0]
        m.rendered_content = m.rendered_content_version = None
        m.content = 'test content'
        # Use to_dict_uncached directly to avoid having to deal with memcached
        d = m.to_dict_uncached(True)
        self.assertEqual(d['content'], '<p>test content</p>')

class EditMessageTest(AuthedTestCase):
    def check_message(self, msg_id, subject=None, content=None):
        msg = Message.objects.get(id=msg_id)
        cached = msg.to_dict(False)
        uncached = msg.to_dict_uncached(False)
        self.assertEqual(cached, uncached)
        if subject:
            self.assertEqual(msg.subject, subject)
        if content:
            self.assertEqual(msg.content, content)
        return msg

    def test_save_message(self):
        # This is also tested by a client test, but here we can verify
        # the cache against the database
        self.login("hamlet@zulip.com")
        msg_id = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
            subject="editing", content="before edit")
        result = self.client.post("/json/update_message", {
            'message_id': msg_id,
            'content': 'after edit'
        })
        self.assert_json_success(result)
        self.check_message(msg_id, content="after edit")

        result = self.client.post("/json/update_message", {
            'message_id': msg_id,
            'subject': 'edited'
        })
        self.assert_json_success(result)
        self.check_message(msg_id, subject="edited")

    def test_propagate_topic_forward(self):
        self.login("hamlet@zulip.com")
        id1 = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
            subject="topic1")
        id2 = self.send_message("iago@zulip.com", "Scotland", Recipient.STREAM,
            subject="topic1")
        id3 = self.send_message("iago@zulip.com", "Rome", Recipient.STREAM,
            subject="topic1")
        id4 = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
            subject="topic2")
        id5 = self.send_message("iago@zulip.com", "Scotland", Recipient.STREAM,
            subject="topic1")

        result = self.client.post("/json/update_message", {
            'message_id': id1,
            'subject': 'edited',
            'propagate_mode': 'change_later'
        })
        self.assert_json_success(result)

        self.check_message(id1, subject="edited")
        self.check_message(id2, subject="edited")
        self.check_message(id3, subject="topic1")
        self.check_message(id4, subject="topic2")
        self.check_message(id5, subject="edited")

    def test_propagate_all_topics(self):
        self.login("hamlet@zulip.com")
        id1 = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
            subject="topic1")
        id2 = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
            subject="topic1")
        id3 = self.send_message("iago@zulip.com", "Rome", Recipient.STREAM,
            subject="topic1")
        id4 = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
            subject="topic2")
        id5 = self.send_message("iago@zulip.com", "Scotland", Recipient.STREAM,
            subject="topic1")
        id6 = self.send_message("iago@zulip.com", "Scotland", Recipient.STREAM,
            subject="topic3")

        result = self.client.post("/json/update_message", {
            'message_id': id2,
            'subject': 'edited',
            'propagate_mode': 'change_all'
        })
        self.assert_json_success(result)

        self.check_message(id1, subject="edited")
        self.check_message(id2, subject="edited")
        self.check_message(id3, subject="topic1")
        self.check_message(id4, subject="topic2")
        self.check_message(id5, subject="edited")
        self.check_message(id6, subject="topic3")

class InviteUserTest(AuthedTestCase):

    def invite(self, users, streams):
        """
        Invites the specified users to Zulip with the specified streams.

        users should be a string containing the users to invite, comma or
            newline separated.

        streams should be a list of strings.
        """

        return self.client.post("/json/invite_users",
                {"invitee_emails": users,
                    "stream": streams})

    def check_sent_emails(self, correct_recipients):
        from django.core.mail import outbox
        self.assertEqual(len(outbox), len(correct_recipients))
        email_recipients = [email.recipients()[0] for email in outbox]
        self.assertItemsEqual(email_recipients, correct_recipients)

    def test_successful_invite_user(self):
        """
        A call to /json/invite_users with valid parameters causes an invitation
        email to be sent.
        """
        self.login("hamlet@zulip.com")
        invitee = "alice-test@zulip.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(invitee))
        self.check_sent_emails([invitee])

    def test_multi_user_invite(self):
        """
        Invites multiple users with a variety of delimiters.
        """
        self.login("hamlet@zulip.com")
        # Intentionally use a weird string.
        self.assert_json_success(self.invite(
"""bob-test@zulip.com,     carol-test@zulip.com,
dave-test@zulip.com


earl-test@zulip.com""", ["Denmark"]))
        for user in ("bob", "carol", "dave", "earl"):
            self.assertTrue(find_key_by_email("%s-test@zulip.com" % user))
        self.check_sent_emails(["bob-test@zulip.com", "carol-test@zulip.com",
                                "dave-test@zulip.com", "earl-test@zulip.com"])

    def test_missing_or_invalid_params(self):
        """
        Tests inviting with various missing or invalid parameters.
        """
        self.login("hamlet@zulip.com")
        self.assert_json_error(
            self.client.post("/json/invite_users", {"invitee_emails": "foo@zulip.com"}),
            "You must specify at least one stream for invitees to join.")

        for address in ("noatsign.com", "outsideyourdomain@example.net"):
            self.assert_json_error(
                self.invite(address, ["Denmark"]),
                "Some emails did not validate, so we didn't send any invitations.")
        self.check_sent_emails([])

    def test_invalid_stream(self):
        """
        Tests inviting to a non-existent stream.
        """
        self.login("hamlet@zulip.com")
        self.assert_json_error(self.invite("iago-test@zulip.com", ["NotARealStream"]),
                "Stream does not exist: NotARealStream. No invites were sent.")
        self.check_sent_emails([])

    def test_invite_existing_user(self):
        """
        If you invite an address already using Zulip, no invitation is sent.
        """
        self.login("hamlet@zulip.com")
        self.assert_json_error(
            self.client.post("/json/invite_users",
                             {"invitee_emails": "hamlet@zulip.com",
                              "stream": ["Denmark"]}),
            "We weren't able to invite anyone.")
        self.assertRaises(PreregistrationUser.DoesNotExist,
                          lambda: PreregistrationUser.objects.get(
                email="hamlet@zulip.com"))
        self.check_sent_emails([])

    def test_invite_some_existing_some_new(self):
        """
        If you invite a mix of already existing and new users, invitations are
        only sent to the new users.
        """
        self.login("hamlet@zulip.com")
        existing = ["hamlet@zulip.com", "othello@zulip.com"]
        new = ["foo-test@zulip.com", "bar-test@zulip.com"]

        result = self.client.post("/json/invite_users",
                                  {"invitee_emails": "\n".join(existing + new),
                                   "stream": ["Denmark"]})
        self.assert_json_error(result,
                               "Some of those addresses are already using Zulip, \
so we didn't send them an invitation. We did send invitations to everyone else!")

        # We only created accounts for the new users.
        for email in existing:
            self.assertRaises(PreregistrationUser.DoesNotExist,
                              lambda: PreregistrationUser.objects.get(
                    email=email))
        for email in new:
            self.assertTrue(PreregistrationUser.objects.get(email=email))

        # We only sent emails to the new users.
        self.check_sent_emails(new)

    @slow(0.20, 'inviting is slow')
    def test_invite_outside_domain_in_closed_realm(self):
        """
        In a realm with `restricted_to_domain = True`, you can't invite people
        with a different domain from that of the realm or your e-mail address.
        """
        zulip_realm = Realm.objects.get(domain="zulip.com")
        zulip_realm.restricted_to_domain = True
        zulip_realm.save()

        self.login("hamlet@zulip.com")
        external_address = "foo@example.com"

        self.assert_json_error(
            self.invite(external_address, ["Denmark"]),
            "Some emails did not validate, so we didn't send any invitations.")

    @slow(0.20, 'inviting is slow')
    def test_invite_outside_domain_in_open_realm(self):
        """
        In a realm with `restricted_to_domain = False`, you can invite people
        with a different domain from that of the realm or your e-mail address.
        """
        zulip_realm = Realm.objects.get(domain="zulip.com")
        zulip_realm.restricted_to_domain = False
        zulip_realm.save()

        self.login("hamlet@zulip.com")
        external_address = "foo@example.com"

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

    def test_invite_with_non_ascii_streams(self):
        """
        Inviting someone to streams with non-ASCII characters succeeds.
        """
        self.login("hamlet@zulip.com")
        invitee = "alice-test@zulip.com"

        stream_name = u"hümbüǵ"
        realm = Realm.objects.get(domain="zulip.com")
        stream, _ = create_stream_if_needed(realm, stream_name)

        # Make sure we're subscribed before inviting someone.
        do_add_subscription(
            get_user_profile_by_email("hamlet@zulip.com"),
            stream, no_log=True)

        self.assert_json_success(self.invite(invitee, [stream_name]))

class ChangeSettingsTest(AuthedTestCase):

    def post_with_params(self, modified_params):
        post_params = {"full_name": "Foo Bar",
                  "old_password": initial_password("hamlet@zulip.com"),
                  "new_password": "foobar1", "confirm_password": "foobar1",
                  "enable_desktop_notifications": "",
                  "enable_offline_email_notifications": "",
                  "enable_sounds": ""}
        post_params.update(modified_params)
        return self.client.post("/json/settings/change", dict(post_params))

    def check_well_formed_change_settings_response(self, result):
        self.assertIn("full_name", result)
        self.assertIn("enable_desktop_notifications", result)
        self.assertIn("enable_sounds", result)
        self.assertIn("enable_offline_email_notifications", result)

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
        self.assertEqual(get_user_profile_by_email("hamlet@zulip.com").
                enable_desktop_notifications, False)
        self.client.post('/accounts/logout/')
        self.login("hamlet@zulip.com", "foobar1")
        user_profile = get_user_profile_by_email('hamlet@zulip.com')
        self.assertEqual(self.client.session['_auth_user_id'], user_profile.id)

    def test_missing_params(self):
        """
        full_name, old_password, and new_password are all required POST
        parameters for json_change_settings. (enable_desktop_notifications is
        false by default)
        """
        self.login("hamlet@zulip.com")
        required_params = (("full_name", "Foo Bar"),
                  ("old_password", initial_password("hamlet@zulip.com")),
                  ("new_password", initial_password("hamlet@zulip.com")),
                  ("confirm_password", initial_password("hamlet@zulip.com")))
        for i in range(len(required_params)):
            post_params = dict(required_params[:i] + required_params[i + 1:])
            result = self.client.post("/json/settings/change", post_params)
            self.assert_json_error(result,
                    "Missing '%s' argument" % (required_params[i][0],))

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

class MITNameTest(TestCase):
    def test_valid_hesiod(self):
        self.assertEquals(compute_mit_user_fullname("starnine@mit.edu"), "Athena Consulting Exchange User")
        self.assertEquals(compute_mit_user_fullname("sipbexch@mit.edu"), "Exch Sipb")
    def test_invalid_hesiod(self):
        self.assertEquals(compute_mit_user_fullname("1234567890@mit.edu"), "1234567890@mit.edu")
        self.assertEquals(compute_mit_user_fullname("ec-discuss@mit.edu"), "ec-discuss@mit.edu")

    def test_mailinglist(self):
        self.assertRaises(ValidationError, not_mit_mailing_list, "1234567890@mit.edu")
        self.assertRaises(ValidationError, not_mit_mailing_list, "ec-discuss@mit.edu")
    def test_notmailinglist(self):
        self.assertTrue(not_mit_mailing_list("sipbexch@mit.edu"))

class S3Test(AuthedTestCase):
    test_uris = []

    @slow(2.6, "has to contact external S3 service")
    def test_file_upload(self):
        """
        A call to /json/upload_file should return a uri and actually create an object.
        """
        self.login("hamlet@zulip.com")
        fp = StringIO("zulip!")
        fp.name = "zulip.txt"

        result = self.client.post("/json/upload_file", {'file': fp})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("uri", json)
        uri = json["uri"]
        self.test_uris.append(uri)
        self.assertEquals("zulip!", urllib2.urlopen(uri).read().strip())

    def test_multiple_upload_failure(self):
        """
        Attempting to upload two files should fail.
        """
        self.login("hamlet@zulip.com")
        fp = StringIO("bah!")
        fp.name = "a.txt"
        fp2 = StringIO("pshaw!")
        fp2.name = "b.txt"

        result = self.client.post("/json/upload_file", {'f1': fp, 'f2': fp2})
        self.assert_json_error(result, "You may only upload one file at a time")

    def test_no_file_upload_failure(self):
        """
        Calling this endpoint with no files should fail.
        """
        self.login("hamlet@zulip.com")

        result = self.client.post("/json/upload_file")
        self.assert_json_error(result, "You must specify a file to upload")

    def tearDown(self):
        # clean up
        conn = S3Connection(settings.S3_KEY, settings.S3_SECRET_KEY)
        for uri in self.test_uris:
            key = Key(conn.get_bucket(settings.S3_BUCKET))
            key.name = urllib2.urlparse.urlparse(uri).path[1:]
            key.delete()
            self.test_uris.remove(uri)


class DummyStream:
    def closed(self):
        return False

class DummyObject:
    pass

class DummyTornadoRequest:
    def __init__(self):
        self.connection = DummyObject()
        self.connection.stream = DummyStream()

class DummyHandler(object):
    def __init__(self, assert_callback):
        self.assert_callback = assert_callback
        self.request = DummyTornadoRequest()

    # Mocks RequestHandler.async_callback, which wraps a callback to
    # handle exceptions.  We return the callback as-is.
    def async_callback(self, cb):
        return cb

    def write(self, response):
        raise NotImplemented

    def zulip_finish(self, response, *ignore):
        if self.assert_callback:
            self.assert_callback(response)


class DummySession(object):
    session_key = "0"

class POSTRequestMock(object):
    method = "POST"

    def __init__(self, post_data, user_profile, assert_callback=None):
        self.REQUEST = self.POST = post_data
        self.user = user_profile
        self._tornado_handler = DummyHandler(assert_callback)
        self.session = DummySession()
        self.META = {'PATH_INFO': 'test'}

class GetUpdatesTest(AuthedTestCase):

    def common_test_get_updates(self, view_func, extra_post_data = {}):
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        message_content = 'tornado test message'
        self.got_callback = False

        def callback(response):
            self.got_callback = True
            msg = response['messages'][0]
            if str(msg['content_type']) == 'text/html':
                self.assertEqual('<p>%s</p>' % message_content, msg['content'])
            else:
                self.assertEqual(message_content, msg['content'])

        post_data = {}
        post_data.update(extra_post_data)
        request = POSTRequestMock(post_data, user_profile, callback)
        self.assertEqual(view_func(request), RespondAsynchronously)
        self.send_message("hamlet@zulip.com", "hamlet@zulip.com",
                Recipient.PERSONAL, message_content)
        self.assertTrue(self.got_callback)


    def test_json_get_updates(self):
        """
        json_get_updates returns messages with IDs greater than the
        last_received ID.
        """
        self.login("hamlet@zulip.com")
        self.common_test_get_updates(json_get_updates)

    def test_api_get_messages(self):
        """
        Same as above, but for the API view
        """
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        self.common_test_get_updates(api_get_messages, {'email': email, 'api-key': api_key})

    def test_missing_last_received(self):
        """
        Calling json_get_updates without any arguments should work
        """
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")

        request = POSTRequestMock({}, user_profile)
        self.assertEqual(json_get_updates(request), RespondAsynchronously)

    def test_bad_input(self):
        """
        Specifying a bad value for 'pointer' should return an error
        """
        self.login("hamlet@zulip.com")
        user_profile = get_user_profile_by_email("hamlet@zulip.com")

        request = POSTRequestMock({'pointer': 'foo'}, user_profile)
        self.assertRaises(RequestVariableConversionError, json_get_updates, request)

class GetProfileTest(AuthedTestCase):

    def common_update_pointer(self, email, pointer):
        self.login(email)
        result = self.client.post("/json/update_pointer", {"pointer": pointer})
        self.assert_json_success(result)

    def common_get_profile(self, email):
        user_profile = get_user_profile_by_email(email)
        self.send_message(email, "Verona", Recipient.STREAM, "hello")

        api_key = self.get_api_key(email)
        result = self.client.post("/api/v1/get_profile", {'email': email, 'api-key': api_key})

        max_id = most_recent_message(user_profile).id

        self.assert_json_success(result)
        json = ujson.loads(result.content)

        self.assertIn("client_id", json)
        self.assertIn("max_message_id", json)
        self.assertIn("pointer", json)

        self.assertEqual(json["max_message_id"], max_id)
        return json

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

class GetPublicStreamsTest(AuthedTestCase):

    def test_public_streams(self):
        """
        Ensure that get_public_streams successfully returns a list of streams
        """
        email = 'hamlet@zulip.com'
        self.login(email)

        result = self.client.post("/json/get_public_streams")

        self.assert_json_success(result)
        json = ujson.loads(result.content)

        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

    def test_public_streams_api(self):
        """
        Ensure that get_public_streams successfully returns a list of streams
        """
        email = 'hamlet@zulip.com'
        self.login(email)

        # Check it correctly lists the user's subs with include_public=false
        result = self.client.get("/api/v1/streams?include_public=false", **self.api_auth(email))
        result2 = self.client.post("/json/subscriptions/list", {})

        self.assert_json_success(result)
        json = ujson.loads(result.content)

        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

        self.assert_json_success(result2)
        json2 = ujson.loads(result2.content)

        self.assertEqual(sorted([s["name"] for s in json["streams"]]),
                         sorted([s["name"] for s in json2["subscriptions"]]))

        # Check it correctly lists all public streams with include_subscribed=false
        result = self.client.get("/api/v1/streams?include_public=true&include_subscribed=false",
                                 **self.api_auth(email))
        self.assert_json_success(result)

        json = ujson.loads(result.content)
        all_streams = [stream.name for stream in
                       Stream.objects.filter(realm=get_user_profile_by_email(email).realm)]
        self.assertEqual(sorted(s["name"] for s in json["streams"]),
                         sorted(all_streams))

        # Check non-superuser can't use include_all_active
        result = self.client.get("/api/v1/streams?include_all_active=true",
                                 **self.api_auth(email))
        self.assertEqual(result.status_code, 400)

class InviteOnlyStreamTest(AuthedTestCase):
    def test_must_be_subbed_to_send(self):
        """
        If you try to send a message to an invite-only stream to which
        you aren't subscribed, you'll get a 400.
        """
        self.login("hamlet@zulip.com")
        # Create Saxony as an invite-only stream.
        self.assert_json_success(
            self.common_subscribe_to_streams("hamlet@zulip.com", ["Saxony"],
                                             invite_only=True))

        email = "cordelia@zulip.com"
        with self.assertRaises(JsonableError):
            self.send_message(email, "Saxony", Recipient.STREAM)

    def test_list_respects_invite_only_bit(self):
        """
        Make sure that /json/subscriptions/list properly returns
        the invite-only bit for streams that are invite-only
        """
        email = 'hamlet@zulip.com'
        self.login(email)

        result1 = self.common_subscribe_to_streams(email, ["Saxony"], invite_only=True)
        self.assert_json_success(result1)
        result2 = self.common_subscribe_to_streams(email, ["Normandy"], invite_only=False)
        self.assert_json_success(result2)
        result = self.client.post("/json/subscriptions/list", {})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertIn("subscriptions", json)
        for sub in json["subscriptions"]:
            if sub['name'] == "Normandy":
                self.assertEqual(sub['invite_only'], False, "Normandy was mistakenly marked invite-only")
            if sub['name'] == "Saxony":
                self.assertEqual(sub['invite_only'], True, "Saxony was not properly marked invite-only")

    @slow(0.15, "lots of queries")
    def test_inviteonly(self):
        # Creating an invite-only stream is allowed
        email = 'hamlet@zulip.com'

        result = self.common_subscribe_to_streams(email, ["Saxony"], invite_only=True)
        self.assert_json_success(result)

        json = ujson.loads(result.content)
        self.assertEqual(json["subscribed"], {email: ['Saxony']})
        self.assertEqual(json["already_subscribed"], {})

        # Subscribing oneself to an invite-only stream is not allowed
        email = "othello@zulip.com"
        self.login(email)
        result = self.common_subscribe_to_streams(email, ["Saxony"])
        self.assert_json_error(result, 'Unable to access stream (Saxony).')

        # authorization_errors_fatal=False works
        email = "othello@zulip.com"
        self.login(email)
        result = self.common_subscribe_to_streams(email, ["Saxony"],
                                                  extra_post_data={'authorization_errors_fatal': ujson.dumps(False)})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json["unauthorized"], ['Saxony'])
        self.assertEqual(json["subscribed"], {})
        self.assertEqual(json["already_subscribed"], {})

        # Inviting another user to an invite-only stream is allowed
        email = 'hamlet@zulip.com'
        self.login(email)
        result = self.common_subscribe_to_streams(
            email, ["Saxony"],
            extra_post_data={'principals': ujson.dumps(["othello@zulip.com"])})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json["subscribed"], {"othello@zulip.com": ['Saxony']})
        self.assertEqual(json["already_subscribed"], {})

        # Make sure both users are subscribed to this stream
        result = self.client.post("/api/v1/get_subscribers", {'email':email,
                                                            'api-key': self.get_api_key(email),
                                                            'stream': 'Saxony'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)

        self.assertTrue('othello@zulip.com' in json['subscribers'])
        self.assertTrue('hamlet@zulip.com' in json['subscribers'])

class GetSubscribersTest(AuthedTestCase):

    def setUp(self):
        self.email = "hamlet@zulip.com"
        self.api_key = self.get_api_key(self.email)
        self.user_profile = get_user_profile_by_email(self.email)
        self.login(self.email)

    def check_well_formed_result(self, result, stream_name, domain):
        """
        A successful call to get_subscribers returns the list of subscribers in
        the form:

        {"msg": "",
         "result": "success",
         "subscribers": ["hamlet@zulip.com", "prospero@zulip.com"]}
        """
        self.assertIn("subscribers", result)
        self.assertIsInstance(result["subscribers"], list)
        true_subscribers = [user_profile.email for user_profile in self.users_subscribed_to_stream(
                stream_name, domain)]
        self.assertItemsEqual(result["subscribers"], true_subscribers)

    def make_subscriber_request(self, stream_name):
        return self.client.post("/json/get_subscribers",
                                {'email': self.email, 'api-key': self.api_key,
                                 'stream': stream_name})

    def make_successful_subscriber_request(self, stream_name):
        result = self.make_subscriber_request(stream_name)
        self.assert_json_success(result)
        self.check_well_formed_result(ujson.loads(result.content),
                                      stream_name, self.user_profile.realm.domain)

    def test_subscriber(self):
        """
        get_subscribers returns the list of subscribers.
        """
        stream_name = gather_subscriptions(self.user_profile)[0][0]['name']
        self.make_successful_subscriber_request(stream_name)

    def test_nonsubscriber(self):
        """
        Even a non-subscriber to a public stream can query a stream's membership
        with get_subscribers.
        """
        # Create a stream for which Hamlet is the only subscriber.
        stream_name = "Saxony"
        self.common_subscribe_to_streams(self.email, [stream_name])
        other_email = "othello@zulip.com"

        # Fetch the subscriber list as a non-member.
        self.login(other_email)
        self.make_successful_subscriber_request(stream_name)

    def test_subscriber_private_stream(self):
        """
        A subscriber to a private stream can query that stream's membership.
        """
        stream_name = "Saxony"
        self.common_subscribe_to_streams(self.email, [stream_name],
                                         invite_only=True)
        self.make_successful_subscriber_request(stream_name)

    def test_nonsubscriber_private_stream(self):
        """
        A non-subscriber to a private stream can't query that stream's membership.
        """
        # Create a private stream for which Hamlet is the only subscriber.
        stream_name = "Saxony"
        self.common_subscribe_to_streams(self.email, [stream_name],
                                         invite_only=True)
        other_email = "othello@zulip.com"

        # Try to fetch the subscriber list as a non-member.
        self.login(other_email)
        result = self.make_subscriber_request(stream_name)
        self.assert_json_error(result,
                               "Unable to retrieve subscribers for invite-only stream")

def bugdown_convert(text):
    return bugdown.convert(text, "zulip.com")

class BugdownTest(TestCase):
    def common_bugdown_test(self, text, expected):
        converted = bugdown_convert(text)
        self.assertEqual(converted, expected)

    def test_codeblock_hilite(self):
        fenced_code = \
"""Hamlet said:
~~~~.python
def speak(self):
    x = 1
~~~~"""

        expected_convert = \
"""<p>Hamlet said:</p>
<div class="codehilite"><pre><span class="k">def</span> <span class="nf">\
speak</span><span class="p">(</span><span class="bp">self</span><span class="p">):</span>
    <span class="n">x</span> <span class="o">=</span> <span class="mi">1</span>
</pre></div>"""

        self.common_bugdown_test(fenced_code, expected_convert)

    def test_codeblock_multiline(self):
        fenced_code = \
"""Hamlet once said
~~~~
def func():
    x = 1

    y = 2

    z = 3
~~~~
And all was good."""

        expected_convert = \
"""<p>Hamlet once said</p>
<div class="codehilite"><pre>def func():
    x = 1

    y = 2

    z = 3
</pre></div>


<p>And all was good.</p>"""

        self.common_bugdown_test(fenced_code, expected_convert)


    def test_hanging_multi_codeblock(self):
        fenced_code = \
"""Hamlet said:
~~~~
def speak(self):
    x = 1
~~~~

Then he mentioned ````y = 4 + x**2```` and
~~~~
def foobar(self):
    return self.baz()"""

        expected_convert = \
"""<p>Hamlet said:</p>
<div class="codehilite"><pre>def speak(self):
    x = 1
</pre></div>


<p>Then he mentioned <code>y = 4 + x**2</code> and</p>
<div class="codehilite"><pre>def foobar(self):
    return self.baz()
</pre></div>"""
        self.common_bugdown_test(fenced_code, expected_convert)

    def test_fenced_quote(self):
        fenced_quote = \
"""Hamlet said:
~~~ quote
To be or **not** to be.

That is the question
~~~"""

        expected_convert = \
"""<p>Hamlet said:</p>
<blockquote>
<p>To be or <strong>not</strong> to be.</p>
<p>That is the question</p>
</blockquote>"""
        self.common_bugdown_test(fenced_quote, expected_convert)

    def test_fenced_nested_quote(self):
        fenced_quote = \
"""Hamlet said:
~~~ quote
Polonius said:
> This above all: to thine ownself be true,
And it must follow, as the night the day,
Thou canst not then be false to any man.

What good advice!
~~~"""

        expected_convert = \
"""<p>Hamlet said:</p>
<blockquote>
<p>Polonius said:</p>
<blockquote>
<p>This above all: to thine ownself be true,<br>
And it must follow, as the night the day,<br>
Thou canst not then be false to any man.</p>
</blockquote>
<p>What good advice!</p>
</blockquote>"""

        self.common_bugdown_test(fenced_quote, expected_convert)

    def test_dangerous_block(self):
        fenced_code = u'xxxxxx xxxxx xxxxxxxx xxxx. x xxxx xxxxxxxxxx:\n\n```\
"xxxx xxxx\\xxxxx\\xxxxxx"```\n\nxxx xxxx xxxxx:```xx.xxxxxxx(x\'^xxxx$\'\
, xx.xxxxxxxxx)```\n\nxxxxxxx\'x xxxx xxxxxxxxxx ```\'xxxx\'```, xxxxx \
xxxxxxxxx xxxxx ^ xxx $ xxxxxx xxxxx xxxxxxxxxxxx xxx xxxx xx x xxxx xx xxxx xx xxx xxxxx xxxxxx?'

        expected = """<p>xxxxxx xxxxx xxxxxxxx xxxx. x xxxx xxxxxxxxxx:</p>\n\
<p><code>"xxxx xxxx\\xxxxx\\xxxxxx"</code></p>\n<p>xxx xxxx xxxxx:<code>xx.xxxxxxx\
(x\'^xxxx$\', xx.xxxxxxxxx)</code></p>\n<p>xxxxxxx\'x xxxx xxxxxxxxxx <code>\'xxxx\'\
</code>, xxxxx xxxxxxxxx xxxxx ^ xxx $ xxxxxx xxxxx xxxxxxxxxxxx xxx xxxx xx x \
xxxx xx xxxx xx xxx xxxxx xxxxxx?</p>"""

        self.common_bugdown_test(fenced_code, expected)

        fenced_code = """``` one ```

``` two ```

~~~~
x = 1"""
        expected_convert = '<p><code>one</code></p>\n<p><code>two</code></p>\n<div class="codehilite"><pre>x = 1\n</pre></div>'
        self.common_bugdown_test(fenced_code, expected_convert)

    def test_ulist_standard(self):
        ulisted = """Some text with a list:

* One item
* Two items
* Three items"""

        expected = """<p>Some text with a list:</p>
<ul>
<li>One item</li>
<li>Two items</li>
<li>Three items</li>
</ul>"""
        self.common_bugdown_test(ulisted, expected)

    def test_ulist_hanging(self):
        ulisted = """Some text with a hanging list:
* One item
* Two items
* Three items"""

        expected = """<p>Some text with a hanging list:</p>
<ul>
<li>One item</li>
<li>Two items</li>
<li>Three items</li>
</ul>"""
        self.common_bugdown_test(ulisted, expected)

    def test_ulist_hanging_mixed(self):
        ulisted = """Plain list

* Alpha

* Beta

Then hang it off:
* Ypsilon
* Zeta"""

        expected = """<p>Plain list</p>
<ul>
<li>
<p>Alpha</p>
</li>
<li>
<p>Beta</p>
</li>
</ul>
<p>Then hang it off:</p>
<ul>
<li>Ypsilon</li>
<li>Zeta</li>
</ul>"""
        self.common_bugdown_test(ulisted, expected)

    def test_hanging_multi(self):
        ulisted = """Plain list
* Alpha
* Beta

And Again:
* A
* B
* C

Once more for feeling:
* Q
* E
* D"""

        expected = '<p>Plain list</p>\n<ul>\n<li>Alpha</li>\n<li>Beta\
</li>\n</ul>\n<p>And Again:</p>\n<ul>\n<li>A</li>\n<li>B</li>\n<li>C\
</li>\n</ul>\n<p>Once more for feeling:</p>\n<ul>\n<li>Q</li>\n<li>E\
</li>\n<li>D</li>\n</ul>'
        self.common_bugdown_test(ulisted, expected)

    def test_ulist_codeblock(self):
        ulisted_code = """~~~
int x = 3
* 4;
~~~"""

        expected = '<div class="codehilite"><pre>int x = 3\n* 4;\n</pre></div>'
        self.common_bugdown_test(ulisted_code, expected)

    def test_malformed_fence(self):
        bad =  "~~~~~~~~xxxxxxxxx:  xxxxxxxxxxxx xxxxx x xxxxxxxx~~~~~~"
        good = "<p>~~~~~~~~xxxxxxxxx:  xxxxxxxxxxxx xxxxx x xxxxxxxx~~~~~~</p>"
        self.common_bugdown_test(bad, good)

    def test_italic_bold(self):
        '''Italics (*foo*, _foo_) and bold syntax __foo__ are disabled.
           Bold **foo** still works.'''
        self.common_bugdown_test('_foo_',   '<p>_foo_</p>')
        self.common_bugdown_test('*foo*',   '<p>*foo*</p>')
        self.common_bugdown_test('__foo__', '<p>__foo__</p>')
        self.common_bugdown_test('**foo**', '<p><strong>foo</strong></p>')

    @slow(1.1, 'lots of examples')
    def test_linkify(self):
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

        conversions = \
        [
         # General linkification tests
         ('http://www.google.com',                     "<p>%s</p>",                         'http://www.google.com'),
         ('https://www.google.com',                    "<p>%s</p>",                         'https://www.google.com'),
         ('http://www.theregister.co.uk/foo/bar',      "<p>%s</p>",                         'http://www.theregister.co.uk/foo/bar'),
         (' some text https://www.google.com/',        "<p>some text %s</p>",               'https://www.google.com/'),
         ('with short example.com url',                "<p>with short %s url</p>",          'example.com'),
         ('t.co',                                      "<p>%s</p>",                         't.co'),
         ('go to views.org please',                    "<p>go to %s please</p>",            'views.org'),
         ('http://foo.com/blah_blah/',                 "<p>%s</p>",                         'http://foo.com/blah_blah/'),
         ('python class views.py is',                  "<p>python class views.py is</p>",   ''),
         ('with www www.zulip.com/foo ok?',            "<p>with www %s ok?</p>",            'www.zulip.com/foo'),
         ('allow questions like foo.com?',             "<p>allow questions like %s?</p>",   'foo.com'),
         ('"is.gd/foo/ "',                             "<p>\"%s \"</p>",                    'is.gd/foo/'),
         ('end of sentence https://t.co.',             "<p>end of sentence %s.</p>",        'https://t.co'),
         ('(Something like http://foo.com/blah_blah)', "<p>(Something like %s)</p>",        'http://foo.com/blah_blah'),
         ('"is.gd/foo/"',                              "<p>\"%s\"</p>",                     'is.gd/foo/'),
         ('end with a quote www.google.com"',          "<p>end with a quote %s\"</p>",      'www.google.com'),
         ('http://www.guardian.co.uk/foo/bar',         "<p>%s</p>",                         'http://www.guardian.co.uk/foo/bar'),
         ('from http://supervisord.org/running.html:', "<p>from %s:</p>",                   'http://supervisord.org/running.html'),
         ('http://raven.io',                           "<p>%s</p>",                         'http://raven.io'),
         ('at https://zulip.com/api. Check it!',       "<p>at %s. Check it!</p>",           'https://zulip.com/api'),
         ('goo.gl/abc',                                "<p>%s</p>",                         'goo.gl/abc'),
         ('I spent a year at ucl.ac.uk',               "<p>I spent a year at %s</p>",       'ucl.ac.uk'),
         ('http://a.cc/i/FMXO',                        "<p>%s</p>",                         'http://a.cc/i/FMXO'),
         ('http://fmota.eu/blog/test.html',            "<p>%s</p>",                         'http://fmota.eu/blog/test.html'),
         ('http://j.mp/14Hwm3X',                       "<p>%s</p>",                         'http://j.mp/14Hwm3X'),
         ('http://localhost:9991/?show_debug=1',       "<p>%s</p>",                         'http://localhost:9991/?show_debug=1'),
         ('anyone before? (http://a.cc/i/FMXO)',       "<p>anyone before? (%s)</p>",        'http://a.cc/i/FMXO'),
         ('(http://en.wikipedia.org/wiki/Each-way_(bet))',
            '<p>(%s)</p>',                   'http://en.wikipedia.org/wiki/Each-way_(bet)'),
         ('(http://en.wikipedia.org/wiki/Each-way_(bet)_(more_parens))',
            '<p>(%s)</p>',                   'http://en.wikipedia.org/wiki/Each-way_(bet)_(more_parens)'),
         ('http://en.wikipedia.org/wiki/Qt_(framework)', '<p>%s</p>', 'http://en.wikipedia.org/wiki/Qt_(framework)'),

         ('http://fr.wikipedia.org/wiki/Fichier:SMirC-facepalm.svg',
            '<p>%s</p>', 'http://fr.wikipedia.org/wiki/Fichier:SMirC-facepalm.svg'),
         # Changed to .mov from .png to avoid inline preview
         ('https://en.wikipedia.org/wiki/File:Methamphetamine_from_ephedrine_with_HI_en.mov', '<p>%s</p>',
            'https://en.wikipedia.org/wiki/File:Methamphetamine_from_ephedrine_with_HI_en.mov'),
         ('https://jira.atlassian.com/browse/JRA-31953?page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel',
            '<p>%s</p>', 'https://jira.atlassian.com/browse/JRA-31953?page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel'),
         ('http://web.archive.org/web/20120630032016/http://web.mit.edu/mitcard/idpolicies.html', '<p>%s</p>',
            'http://web.archive.org/web/20120630032016/http://web.mit.edu/mitcard/idpolicies.html'),
         ('https://www.dropbox.com/sh/7d0ved3h5kf7dj8/_aD5_ceDFY?lst#f:Zulip-062-subscriptions-page-3rd-ver.fw.png',
            '<p>%s</p>', 'https://www.dropbox.com/sh/7d0ved3h5kf7dj8/_aD5_ceDFY?lst#f:Zulip-062-subscriptions-page-3rd-ver.fw.png'),
         ('http://www.postgresql.org/message-id/14040.1364490185@sss.pgh.pa.us', '<p>%s</p>',
            'http://www.postgresql.org/message-id/14040.1364490185@sss.pgh.pa.us'),

         # XSS sanitization; URL is rendered as plain text
         ('javascript:alert(\'hi\');.com',             "<p>javascript:alert('hi');.com</p>", ''),
         ('javascript:foo.com',                        "<p>javascript:%s</p>",          'foo.com'),
         ('javascript://foo.com',                      "<p>javascript://foo.com</p>",        ''),
         ('foobarscript://foo.com',                    "<p>foobarscript://foo.com</p>",      ''),
         ('about:blank.com',                           "<p>about:%s</p>",               'blank.com'),
         ('[foo](javascript:foo.com)',                 "<p>[foo](javascript:%s)</p>",   'foo.com'),
         ('[foo](javascript://foo.com)',               "<p>[foo](javascript://foo.com)</p>", ''),

         # Other weird URL schemes are also blocked
         ('aim:addbuddy?screenname=foo',               "<p>aim:addbuddy?screenname=foo</p>", ''),
         ('itms://itunes.com/apps/appname',            "<p>itms://itunes.com/apps/appname</p>", ''),
         ('[foo](itms://itunes.com/apps/appname)',     "<p>[foo](itms://itunes.com/apps/appname)</p>", ''),
         ('1 [](foo://) 3 [](foo://) 5',               "<p>1 [](foo://) 3 [](foo://) 5</p>", ''),

         # Make sure we HTML-escape the invalid URL on output.
         # ' and " aren't escaped here, because we aren't in attribute context.
         ('javascript:<i>"foo&bar"</i>',
            '<p>javascript:&lt;i&gt;"foo&amp;bar"&lt;/i&gt;</p>', ''),
         ('[foo](javascript:<i>"foo&bar"</i>)',
            '<p>[foo](javascript:&lt;i&gt;"foo&amp;bar"&lt;/i&gt;)</p>', ''),

         # Emails
         ('a@b.com',                                    "<p>%s</p>",                         'a@b.com'),
         ('<a@b.com>',                                  "<p>&lt;%s&gt;</p>",                 'a@b.com'),
         ('a@b.com/foo',                                "<p>a@b.com/foo</p>",                ''),
         ('http://leo@foo.com/my/file',                 "<p>%s</p>",                         'http://leo@foo.com/my/file'),

         ('http://example.com/something?with,commas,in,url, but not at end',
                        "<p>%s, but not at end</p>",         'http://example.com/something?with,commas,in,url'),
         ('http://www.yelp.com/biz/taim-mobile-falafel-and-smoothie-truck-new-york#query',
                        "<p>%s</p>", 'http://www.yelp.com/biz/taim-mobile-falafel-and-smoothie-truck-new-york#query'),
         (' some text https://www.google.com/baz_(match)?with=foo&bar=baz with extras',
                        "<p>some text %s with extras</p>",  'https://www.google.com/baz_(match)?with=foo&amp;bar=baz'),
         ('hash it http://foo.com/blah_(wikipedia)_blah#cite-1',
                        "<p>hash it %s</p>",                'http://foo.com/blah_(wikipedia)_blah#cite-1'),

         # This last one was originally a .gif but was changed to .mov
         # to avoid triggering the inline image preview support
         ('http://technet.microsoft.com/en-us/library/Cc751099.rk20_25_big(l=en-us).mov',
                        "<p>%s</p>",
                        'http://technet.microsoft.com/en-us/library/Cc751099.rk20_25_big(l=en-us).mov'),

         # Just because it has a TLD and parentheses in it doesn't mean it's a link. Trac #1364
         ('a.commandstuff()', '<p>a.commandstuff()</p>', ''),
         ('love...it', '<p>love...it</p>', ''),
         ('sorry,http://example.com/', '<p>sorry,%s</p>', 'http://example.com/'),
         ]

        for inline_url, reference, url in conversions:
            try:
                match = replaced(reference, url, phrase=inline_url)
            except TypeError:
                match = reference
            converted = bugdown_convert(inline_url)
            self.assertEqual(match, converted)

    @slow(0.545, 'BugDown is slow, several items to test')
    def test_manual_links(self):
        # These are links that the default markdown XSS fails due to to : in the path
        urls = (('[Haskell NYC Meetup](http://www.meetsup.com/r/email/www/0/co1.1_grp/http://www.meetup.com/NY-Haskell/events/108707682/\
?a=co1.1_grp&rv=co1.1)', "<p><a href=\"http://www.meetsup.com/r/email/www/0/co1.1_grp/http://www.meetup.com/NY-Haskell/events/\
108707682/?a=co1.1_grp&amp;rv=co1.1\" target=\"_blank\" title=\"http://www.meetsup.com/r/email/www/0/co1.1_grp/http://www.meetup.com/\
NY-Haskell/events/108707682/?a=co1.1_grp&amp;rv=co1.1\">Haskell NYC Meetup</a></p>"),
                ('[link](http://htmlpreview.github.com/?https://github.com/becdot/jsset/index.html)',
                 '<p><a href="http://htmlpreview.github.com/?https://github.com/becdot/jsset/index.html" target="_blank" title=\
"http://htmlpreview.github.com/?https://github.com/becdot/jsset/index.html">link</a></p>'),
                ('[YOLO](http://en.wikipedia.org/wiki/YOLO_(motto))',
                 '<p><a href="http://en.wikipedia.org/wiki/YOLO_(motto)" target="_blank" title="http://en.wikipedia.org/wiki/YOLO_(motto)"\
>YOLO</a></p>'),
                ('Sent to http_something_real@zulip.com', '<p>Sent to <a href="mailto:http_something_real@zulip.com" \
title="mailto:http_something_real@zulip.com">http_something_real@zulip.com</a></p>'),
                ('Sent to othello@zulip.com', '<p>Sent to <a href="mailto:othello@zulip.com" title="mailto:othello@zulip.com">\
othello@zulip.com</a></p>')
                )

        for input, output in urls:
            converted = bugdown_convert(input)
            self.assertEqual(output, converted)

    def test_linkify_interference(self):
        # Check our auto links don't interfere with normal markdown linkification
        msg = 'link: xx, x xxxxx xx xxxx xx\n\n[xxxxx #xx](http://xxxxxxxxx:xxxx/xxx/xxxxxx%xxxxxx/xx/):\
**xxxxxxx**\n\nxxxxxxx xxxxx xxxx xxxxx:\n`xxxxxx`: xxxxxxx\n`xxxxxx`: xxxxx\n`xxxxxx`: xxxxx xxxxx'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>link: xx, x xxxxx xx xxxx xx</p>\n<p><a href="http://xxxxxxxxx:xxxx/\
xxx/xxxxxx%xxxxxx/xx/" target="_blank" title="http://xxxxxxxxx:xxxx/xxx/xxxxxx%xxxxxx/xx/">xxxxx #xx</a>:<strong>\
xxxxxxx</strong></p>\n<p>xxxxxxx xxxxx xxxx xxxxx:<br>\n<code>xxxxxx</code>: xxxxxxx<br>\n<code>xxxxxx</code>: xxxxx\
<br>\n<code>xxxxxx</code>: xxxxx xxxxx</p>')

    def test_inline_image(self):
        msg = 'Google logo today: https://www.google.com/images/srpr/logo4w.png\nKinda boring'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Google logo today: <a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png">https://www.google.com/images/srpr/logo4w.png</a><br>\nKinda boring</p>\n<div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png"><img src="https://www.google.com/images/srpr/logo4w.png"></a></div>')

        # If there are two images, both should be previewed.
        msg = 'Google logo today: https://www.google.com/images/srpr/logo4w.png\nKinda boringGoogle logo today: https://www.google.com/images/srpr/logo4w.png\nKinda boring'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Google logo today: <a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png">https://www.google.com/images/srpr/logo4w.png</a><br>\nKinda boringGoogle logo today: <a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png">https://www.google.com/images/srpr/logo4w.png</a><br>\nKinda boring</p>\n<div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png"><img src="https://www.google.com/images/srpr/logo4w.png"></a></div><div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png"><img src="https://www.google.com/images/srpr/logo4w.png"></a></div>')

        # http images should be converted to https via our Camo integration
        msg = 'Google logo today: http://www.google.com/images/srpr/logo4w.png'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Google logo today: <a href="http://www.google.com/images/srpr/logo4w.png" target="_blank" title="http://www.google.com/images/srpr/logo4w.png">http://www.google.com/images/srpr/logo4w.png</a></p>\n<div class="message_inline_image"><a href="http://www.google.com/images/srpr/logo4w.png" target="_blank" title="http://www.google.com/images/srpr/logo4w.png"><img src="https://external-content.zulipcdn.net/4882a845c6edd9a945bfe5f33734ce0aed8170f3/687474703a2f2f7777772e676f6f676c652e636f6d2f696d616765732f737270722f6c6f676f34772e706e67"></a></div>')

        # in mit.edu, https images should be converted to https via our Camo integration
        message = Message(sender=get_user_profile_by_email("starnine@mit.edu"))
        msg = 'Google logo today: https://www.google.com/images/srpr/logo4w.png'
        converted = bugdown.convert(msg, "mit.com", message=message)

        self.assertEqual(converted, '<p>Google logo today: <a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png">https://www.google.com/images/srpr/logo4w.png</a></p>\n<div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png"><img src="https://external-content.zulipcdn.net/cadb491a68c9272ffd7e571703d7f8c51542acc8/68747470733a2f2f7777772e676f6f676c652e636f6d2f696d616765732f737270722f6c6f676f34772e706e67"></a></div>')

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

    def test_inline_interesting_links(self):
        def make_link(url):
            return '<a href="%s" target="_blank" title="%s">%s</a>' % (url, url, url)

        def make_inline_twitter_preview(url):
            ## As of right now, all previews are mocked to be the exact same tweet
            return """<div class="inline-preview-twitter"><div class="twitter-tweet"><a href="%s" target="_blank"><img class="twitter-avatar" src="https://si0.twimg.com/profile_images/1380912173/Screen_shot_2011-06-03_at_7.35.36_PM_normal.png"></a><p>@twitter meets @seepicturely at #tcdisrupt cc.@boscomonkey @episod http://t.co/6J2EgYM</p><span>- Eoin McMillan  (@imeoin)</span></div></div>""" % (url, )

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
                                                       make_inline_twitter_preview('http://www.twitter.com/wdaher/status/287977969287315456')))

        msg = 'https://www.twitter.com/wdaher/status/287977969287315456'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (make_link('https://www.twitter.com/wdaher/status/287977969287315456'),
                                                       make_inline_twitter_preview('https://www.twitter.com/wdaher/status/287977969287315456')))

        msg = 'http://twitter.com/wdaher/status/287977969287315456'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s</p>\n%s' % (make_link('http://twitter.com/wdaher/status/287977969287315456'),
                                                       make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315456')))

        # Only one should get converted
        msg = 'http://twitter.com/wdaher/status/287977969287315456 http://twitter.com/wdaher/status/287977969287315457'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>%s %s</p>\n%s' % (make_link('http://twitter.com/wdaher/status/287977969287315456'),
                                                          make_link('http://twitter.com/wdaher/status/287977969287315457'),
                                                          make_inline_twitter_preview('http://twitter.com/wdaher/status/287977969287315456')))


    def test_emoji(self):
        def emoji_img(name, filename=None):
            if filename == None:
                filename = name[1:-1]
            return '<img alt="%s" class="emoji" src="static/third/gemoji/images/emoji/%s.png" title="%s">' % (name, filename, name)

        # Spot-check a few emoji
        test_cases = [ (':poop:', emoji_img(':poop:')),
                       (':hankey:', emoji_img(':hankey:')),
                       (':whale:', emoji_img(':whale:')),
                       (':fakeemoji:', ':fakeemoji:'),
                       (':even faker smile:', ':even faker smile:'),
                       ]

        # Check a random sample of our 800+ emojis to make
        # sure that bugdown builds the correct image tag.
        emojis = bugdown.emoji_list
        emojis = random.sample(emojis, 15)
        for img in emojis:
            emoji_text = ":%s:" % (img,)
            test_cases.append((emoji_text, emoji_img(emoji_text)))

        for input, expected in test_cases:
            self.assertEqual(bugdown_convert(input), '<p>%s</p>' % expected)

        # Comprehensive test of a bunch of things together
        msg = 'test :smile: again :poop:\n:) foo:)bar x::y::z :wasted waste: :fakeemojithisshouldnotrender:'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>test ' + emoji_img(':smile:') + ' again ' + emoji_img(':poop:') + '<br>\n'
                                  + ':) foo:)bar x::y::z :wasted waste: :fakeemojithisshouldnotrender:</p>')

        msg = ':smile:, :smile:; :smile:'
        converted = bugdown_convert(msg)
        self.assertEqual(converted,
            '<p>' +
            emoji_img(':smile:') +
            ', ' +
            emoji_img(':smile:') +
            '; ' +
            emoji_img(':smile:') +
            '</p>')

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

    def test_multiline_strong(self):
        msg = "Welcome to **the jungle**"
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Welcome to <strong>the jungle</strong></p>')

        msg = """You can check out **any time you'd like
But you can never leave**"""
        converted = bugdown_convert(msg)
        self.assertEqual(converted, "<p>You can check out **any time you'd like<br>\nBut you can never leave**</p>")

    def test_realm_patterns(self):
        msg = "We should fix #224 and #115, but not issue#124 or #1124z or [trac #15](https://trac.zulip.net/ticket/16) today."
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>We should fix <a href="https://trac.zulip.net/ticket/224" target="_blank" title="https://trac.zulip.net/ticket/224">#224</a> and <a href="https://trac.zulip.net/ticket/115" target="_blank" title="https://trac.zulip.net/ticket/115">#115</a>, but not issue#124 or #1124z or <a href="https://trac.zulip.net/ticket/16" target="_blank" title="https://trac.zulip.net/ticket/16">trac #15</a> today.</p>')

class UserPresenceTests(AuthedTestCase):

    def common_init(self, email):
        self.login(email)
        api_key = self.get_api_key(email)
        return api_key

    def test_get_empty(self):
        email = "hamlet@zulip.com"
        api_key = self.common_init(email)

        result = self.client.post("/json/get_active_statuses", {'email': email, 'api-key': api_key})

        self.assert_json_success(result)
        json = ujson.loads(result.content)
        for email, presence in json['presences'].items():
            self.assertEqual(presence, {})

    def test_set_idle(self):
        email = "hamlet@zulip.com"
        api_key = self.common_init(email)
        client = 'website'

        def test_result(result):
            self.assert_json_success(result)
            json = ujson.loads(result.content)
            self.assertEqual(json['presences'][email][client]['status'], 'idle')
            self.assertIn('timestamp', json['presences'][email][client])
            self.assertIsInstance(json['presences'][email][client]['timestamp'], int)
            self.assertEqual(json['presences'].keys(), ['hamlet@zulip.com'])
            return json['presences'][email][client]['timestamp']

        result = self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        test_result(result)

        result = self.client.post("/json/get_active_statuses", {'email': email, 'api-key': api_key})
        timestamp = test_result(result)

        email = "othello@zulip.com"
        api_key = self.common_init(email)
        self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        result = self.client.post("/json/get_active_statuses", {'email': email, 'api-key': api_key})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')
        self.assertEqual(json['presences'].keys(), ['hamlet@zulip.com', 'othello@zulip.com'])
        newer_timestamp = json['presences'][email][client]['timestamp']
        self.assertGreaterEqual(newer_timestamp, timestamp)

    def test_set_active(self):
        email = "hamlet@zulip.com"
        api_key = self.common_init(email)
        client = 'website'

        self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        result = self.client.post("/json/get_active_statuses", {'email': email, 'api-key': api_key})

        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')

        email = "othello@zulip.com"
        api_key = self.common_init(email)
        self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        result = self.client.post("/json/get_active_statuses", {'email': email, 'api-key': api_key})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')

        self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'active'})
        result = self.client.post("/json/get_active_statuses", {'email': email, 'api-key': api_key})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'active')
        self.assertEqual(json['presences']['hamlet@zulip.com'][client]['status'], 'idle')

    def test_no_mit(self):
        # MIT never gets a list of users
        email = "espuser@mit.edu"
        api_key = self.common_init(email)
        result = self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'], {})

    def test_same_realm(self):
        email = "espuser@mit.edu"
        api_key = self.common_init(email)
        client = 'website'

        self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        result = self.client.post("/accounts/logout/")

        # Ensure we don't see hamlet@zulip.com information leakage
        email = "hamlet@zulip.com"
        api_key = self.common_init(email)

        result = self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        self.assert_json_success(result)
        json = ujson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        # We only want @zulip.com emails
        for email in json['presences'].keys():
            self.assertEqual(email_to_domain(email), 'zulip.com')

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

        result = self.client.post("/json/update_message_flags", {"messages": ujson.dumps([1, 2]),
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

class StarTests(AuthedTestCase):

    def change_star(self, messages, add=True):
        return self.client.post("/json/update_message_flags",
                                {"messages": ujson.dumps(messages),
                                 "op": "add" if add else "remove",
                                 "flag": "starred"})

    def test_change_star(self):
        """
        You can set a message as starred/un-starred through
        /json/update_message_flags.
        """
        self.login("hamlet@zulip.com")
        message_ids = [1, 2]

        # Star a few messages.
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        for msg in self.get_old_messages():
            if msg['id'] in message_ids:
                self.assertEqual(msg['flags'], ['read', 'starred'])
            else:
                self.assertEqual(msg['flags'], ['read'])

        result = self.change_star(message_ids, False)
        self.assert_json_success(result)

        # Remove the stars.
        for msg in self.get_old_messages():
            if msg['id'] in message_ids:
                self.assertEqual(msg['flags'], ['read'])

    def test_new_message(self):
        """
        New messages aren't starred.
        """
        test_email = "hamlet@zulip.com"
        self.login(test_email)
        content = "Test message for star"
        self.send_message(test_email, "Verona", Recipient.STREAM,
                          content=content)

        sent_message = UserMessage.objects.filter(
            user_profile=get_user_profile_by_email(test_email)
            ).order_by("id").reverse()[0]
        self.assertEqual(sent_message.message.content, content)
        self.assertFalse(sent_message.flags.starred)

class JiraHookTests(AuthedTestCase):

    def send_jira_message(self, action):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        url = "/api/v1/external/jira?api_key=%s" % (api_key,)
        return self.send_json_payload(email,
                                      url,
                                      self.fixture_data('jira', action),
                                      stream_name="jira",
                                      content_type="application/json")

    def test_unknown(self):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        url = "/api/v1/external/jira?api_key=%s" % (api_key,)

        result = self.client.post(url, self.fixture_data('jira', 'unknown'),
                                  stream_name="jira",
                                  content_type="application/json")

        self.assert_json_error(result, 'Unknown JIRA event type')

    def test_custom_stream(self):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        action = 'created'
        url = "/api/v1/external/jira?api_key=%s&stream=jira_custom" % (api_key,)
        msg = self.send_json_payload(email, url,
                                     self.fixture_data('jira', action),
                                     stream_name="jira_custom",
                                     content_type="application/json")
        self.assertEqual(msg.subject, "BUG-15: New bug with hook")
        self.assertEqual(msg.content, """Leo Franchi **created** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) priority Major, assigned to **no one**:

> New bug with hook""")

    def test_created(self):
        msg = self.send_jira_message('created')
        self.assertEqual(msg.subject, "BUG-15: New bug with hook")
        self.assertEqual(msg.content, """Leo Franchi **created** [BUG-15](http://lfranchi.com:8080/browse/BUG-15) priority Major, assigned to **no one**:

> New bug with hook""")

    def test_created_assignee(self):
        msg = self.send_jira_message('created_assignee')
        self.assertEqual(msg.subject, "TEST-4: Test Created Assignee")
        self.assertEqual(msg.content, """Leonardo Franchi [Administrator] **created** [TEST-4](https://zulipp.atlassian.net/browse/TEST-4) priority Major, assigned to **Leonardo Franchi [Administrator]**:

> Test Created Assignee""")

    def test_commented(self):
        msg = self.send_jira_message('commented')
        self.assertEqual(msg.subject, "BUG-15: New bug with hook")
        self.assertEqual(msg.content, """Leo Franchi **updated** [BUG-15](http://lfranchi.com:8080/browse/BUG-15):


~~~ quote
Adding a comment. Oh, what a comment it is!
~~~""")

    def test_deleted(self):
        msg = self.send_jira_message('deleted')
        self.assertEqual(msg.subject, "BUG-15: New bug with hook")
        self.assertEqual(msg.content, "Leo Franchi **deleted** [BUG-15](http://lfranchi.com:8080/browse/BUG-15)!")

    def test_reassigned(self):
        msg = self.send_jira_message('reassigned')
        self.assertEqual(msg.subject, "BUG-15: New bug with hook")
        self.assertEqual(msg.content, """Leo Franchi **updated** [BUG-15](http://lfranchi.com:8080/browse/BUG-15):

* Changed assignee from **None** to **Leo Franchi**
""")

    def test_reopened(self):
        msg = self.send_jira_message('reopened')
        self.assertEqual(msg.subject, "BUG-7: More cowbell polease")
        self.assertEqual(msg.content, """Leo Franchi **updated** [BUG-7](http://lfranchi.com:8080/browse/BUG-7):

* Changed status from **Resolved** to **Reopened**

~~~ quote
Re-opened yeah!
~~~""")

    def test_resolved(self):
        msg = self.send_jira_message('resolved')

        self.assertEqual(msg.subject, "BUG-13: Refreshing the page loses the user's current posi...")
        self.assertEqual(msg.content, """Leo Franchi **updated** [BUG-13](http://lfranchi.com:8080/browse/BUG-13):

* Changed status from **Open** to **Resolved**
* Changed assignee from **None** to **Leo Franchi**

~~~ quote
Fixed it, finally!
~~~""")

    def test_workflow_postfuncion(self):
        msg = self.send_jira_message('postfunction_hook')

        self.assertEqual(msg.subject, "TEST-5: PostTest")
        self.assertEqual(msg.content, """Leo Franchi [Administrator] **transitioned** [TEST-5](https://lfranchi-test.atlassian.net/browse/TEST-5) from Resolved to Reopened""")

    def test_workflow_postfunction(self):
        msg = self.send_jira_message('postfunction_hook')

        self.assertEqual(msg.subject, "TEST-5: PostTest")
        self.assertEqual(msg.content, """Leo Franchi [Administrator] **transitioned** [TEST-5](https://lfranchi-test.atlassian.net/browse/TEST-5) from Resolved to Reopened""")

    def test_workflow_postfunction_started(self):
        msg = self.send_jira_message('postfunction_started')

        self.assertEqual(msg.subject, "TEST-7: Gluttony of Post Functions")
        self.assertEqual(msg.content, """Leo Franchi [Administrator] **transitioned** [TEST-7](https://lfranchi-test.atlassian.net/browse/TEST-7) from Open to Underway""")

    def test_workflow_postfunction_resolved(self):
        msg = self.send_jira_message('postfunction_resolved')

        self.assertEqual(msg.subject, "TEST-7: Gluttony of Post Functions")
        self.assertEqual(msg.content, """Leo Franchi [Administrator] **transitioned** [TEST-7](https://lfranchi-test.atlassian.net/browse/TEST-7) from Open to Resolved""")

class BeanstalkHookTests(AuthedTestCase):

    def http_auth(self, username, password):
        import base64
        credentials = base64.b64encode('%s:%s' % (username, password))
        auth_string = 'Basic %s' % (credentials,)
        return auth_string

    def send_beanstalk_message(self, action):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        data = {'payload': self.fixture_data('beanstalk', action)}
        return self.send_json_payload(email, "/api/v1/external/beanstalk",
                                      data,
                                      stream_name="commits",
                                      HTTP_AUTHORIZATION=self.http_auth(email, api_key))

    def test_git_single(self):
        msg = self.send_beanstalk_message('git_singlecommit')
        self.assertEqual(msg.subject, "work-test")
        self.assertEqual(msg.content, """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) to branch master

* [e50508d](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/e50508df): add some stuff
""")

    @slow(0.20, "lots of queries")
    def test_git_multiple(self):
        msg = self.send_beanstalk_message('git_multiple')
        self.assertEqual(msg.subject, "work-test")
        self.assertEqual(msg.content, """Leo Franchi [pushed](http://lfranchi-svn.beanstalkapp.com/work-test) to branch master

* [edf529c](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/edf529c7): Added new file
* [c2a191b](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/c2a191b9): Filled in new file with some stuff
* [2009815](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/20098158): More work to fix some bugs
""")

    def test_svn_addremove(self):
        msg = self.send_beanstalk_message('svn_addremove')
        self.assertEqual(msg.subject, "svn r3")
        self.assertEqual(msg.content, """Leo Franchi pushed [revision 3](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/3):

> Removed a file and added another one!""")

    def test_svn_changefile(self):
        msg = self.send_beanstalk_message('svn_changefile')
        self.assertEqual(msg.subject, "svn r2")
        self.assertEqual(msg.content, """Leo Franchi pushed [revision 2](http://lfranchi-svn.beanstalkapp.com/work-test/changesets/2):

> Added some code""")

class GithubHookTests(AuthedTestCase):

    push_content = """zbenjamin [pushed](https://github.com/zbenjamin/zulip-test/compare/4f9adc4777d5...b95449196980) to branch master

* [48c329a](https://github.com/zbenjamin/zulip-test/commit/48c329a0b68a9a379ff195ee3f1c1f4ab0b2a89e): Add baz
* [06ebe5f](https://github.com/zbenjamin/zulip-test/commit/06ebe5f472a32f6f31fd2a665f0c7442b69cce72): Baz needs to be longer
* [b954491](https://github.com/zbenjamin/zulip-test/commit/b95449196980507f08209bdfdc4f1d611689b7a8): Final edit to baz, I swear
"""

    def test_spam_branch_is_ignored(self):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        stream = 'commits'
        data = ujson.loads(self.fixture_data('github', 'push'))
        data.update({'email': email,
                     'api-key': api_key,
                     'branches': 'dev,staging',
                     'stream': stream,
                     'payload': ujson.dumps(data['payload'])})
        url = '/api/v1/external/github'

        # We subscribe to the stream in this test, even though
        # it won't get written, to avoid failing for the wrong
        # reason.
        self.subscribe_to_stream(email, stream)

        prior_count = Message.objects.count()

        result = self.client.post(url, data)
        self.assert_json_success(result)

        after_count = Message.objects.count()
        self.assertEqual(prior_count, after_count)


    def basic_test(self, fixture_name, stream_name, expected_subject, expected_content, send_stream=False, branches=None):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        data = ujson.loads(self.fixture_data('github', fixture_name))
        data.update({'email': email,
                     'api-key': api_key,
                     'payload': ujson.dumps(data['payload'])})
        if send_stream:
            data['stream'] = stream_name
        if branches is not None:
            data['branches'] = branches
        msg = self.send_json_payload(email, "/api/v1/external/github",
                                     data,
                                     stream_name=stream_name)
        self.assertEqual(msg.subject, expected_subject)
        self.assertEqual(msg.content, expected_content)

    def test_user_specified_branches(self):
        self.basic_test('push', 'my_commits', 'zulip-test', self.push_content,
                        send_stream=True, branches="master,staging")

    def test_user_specified_stream(self):
        # Around May 2013 the github webhook started to specify the stream.
        # Before then, the stream was hard coded to "commits".
        self.basic_test('push', 'my_commits', 'zulip-test', self.push_content,
                        send_stream=True)

    def test_legacy_hook(self):
        self.basic_test('push', 'commits', 'zulip-test', self.push_content)

    def test_issues_opened(self):
        self.basic_test('issues_opened', 'issues',
                        "zulip-test: issue 5: The frobnicator doesn't work",
                        "zbenjamin opened [issue 5](https://github.com/zbenjamin/zulip-test/issues/5)\n\n~~~ quote\nI tried changing the widgets, but I got:\r\n\r\nPermission denied: widgets are immutable\n~~~")

    def test_issue_comment(self):
        self.basic_test('issue_comment', 'issues',
                        "zulip-test: issue 5: The frobnicator doesn't work",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/issues/5#issuecomment-23374280) on [issue 5](https://github.com/zbenjamin/zulip-test/issues/5)\n\n~~~ quote\nWhoops, I did something wrong.\r\n\r\nI'm sorry.\n~~~")

    def test_issues_closed(self):
        self.basic_test('issues_closed', 'issues',
                        "zulip-test: issue 5: The frobnicator doesn't work",
                        "zbenjamin closed [issue 5](https://github.com/zbenjamin/zulip-test/issues/5)")

    def test_pull_request_opened(self):
        self.basic_test('pull_request_opened', 'commits',
                        "zulip-test: pull request 7: Counting is hard.",
                        "lfaraone opened [pull request 7](https://github.com/zbenjamin/zulip-test/pull/7)\n\n~~~ quote\nOmitted something I think?\n~~~")

    def test_pull_request_closed(self):
        self.basic_test('pull_request_closed', 'commits',
                        "zulip-test: pull request 7: Counting is hard.",
                        "lfaraone closed [pull request 7](https://github.com/zbenjamin/zulip-test/pull/7)")

    def test_pull_request_comment(self):
        self.basic_test('pull_request_comment', 'commits',
                        "zulip-test: pull request 9: Less cowbell.",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/pull/9#issuecomment-24771110) on [pull request 9](https://github.com/zbenjamin/zulip-test/pull/9)\n\n~~~ quote\nYeah, who really needs more cowbell than we already have?\n~~~")

    def test_pull_request_comment_user_specified_stream(self):
        self.basic_test('pull_request_comment', 'my_commits',
                        "zulip-test: pull request 9: Less cowbell.",
                        "zbenjamin [commented](https://github.com/zbenjamin/zulip-test/pull/9#issuecomment-24771110) on [pull request 9](https://github.com/zbenjamin/zulip-test/pull/9)\n\n~~~ quote\nYeah, who really needs more cowbell than we already have?\n~~~",
                        send_stream=True)

class PivotalHookTests(AuthedTestCase):

    def send_pivotal_message(self, name):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        return self.send_json_payload(email, "/api/v1/external/pivotal?api_key=%s&stream=%s" % (api_key,"pivotal"),
                                      self.fixture_data('pivotal', name, file_type='xml'),
                                      stream_name="pivotal",
                                      content_type="application/xml")

    def test_accepted(self):
        msg = self.send_pivotal_message('accepted')
        self.assertEqual(msg.subject, 'My new Feature story')
        self.assertEqual(msg.content, 'Leo Franchi accepted "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)')

    def test_commented(self):
        msg = self.send_pivotal_message('commented')
        self.assertEqual(msg.subject, 'Comment added')
        self.assertEqual(msg.content, 'Leo Franchi added comment: "FIX THIS NOW" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)')

    def test_created(self):
        msg = self.send_pivotal_message('created')
        self.assertEqual(msg.subject, 'My new Feature story')
        self.assertEqual(msg.content, 'Leo Franchi added "My new Feature story" \
(unscheduled feature):\n\n~~~ quote\nThis is my long description\n~~~\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)')

    def test_delivered(self):
        msg = self.send_pivotal_message('delivered')
        self.assertEqual(msg.subject, 'Another new story')
        self.assertEqual(msg.content, 'Leo Franchi delivered "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)')

    def test_finished(self):
        msg = self.send_pivotal_message('finished')
        self.assertEqual(msg.subject, 'Another new story')
        self.assertEqual(msg.content, 'Leo Franchi finished "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)')

    def test_moved(self):
        msg = self.send_pivotal_message('moved')
        self.assertEqual(msg.subject, 'My new Feature story')
        self.assertEqual(msg.content, 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)')

    def test_rejected(self):
        msg = self.send_pivotal_message('rejected')
        self.assertEqual(msg.subject, 'Another new story')
        self.assertEqual(msg.content, 'Leo Franchi rejected "Another new story" with comments: \
"Not good enough, sorry" [(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)')

    def test_started(self):
        msg = self.send_pivotal_message('started')
        self.assertEqual(msg.subject, 'Another new story')
        self.assertEqual(msg.content, 'Leo Franchi started "Another new story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)')

    def test_created_estimate(self):
        msg = self.send_pivotal_message('created_estimate')
        self.assertEqual(msg.subject, 'Another new story')
        self.assertEqual(msg.content, 'Leo Franchi added "Another new story" \
(unscheduled feature worth 2 story points):\n\n~~~ quote\nSome loong description\n~~~\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)')

    def test_type_changed(self):
        msg = self.send_pivotal_message('type_changed')
        self.assertEqual(msg.subject, 'My new Feature story')
        self.assertEqual(msg.content, 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)')

class NewRelicHookTests(AuthedTestCase):
    def send_new_relic_message(self, name):
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        return self.send_json_payload(email, "/api/v1/external/newrelic?api_key=%s&stream=%s" % (api_key,"newrelic"),
                                      self.fixture_data('newrelic', name, file_type='txt'),
                                      stream_name="newrelic",
                                      content_type="application/x-www-form-urlencoded")

    def test_alert(self):
        msg = self.send_new_relic_message('alert')
        self.assertEqual(msg.subject, "Apdex score fell below critical level of 0.90")
        self.assertEqual(msg.content, 'Alert opened on [application name]: \
Apdex score fell below critical level of 0.90\n\
[View alert](https://rpm.newrelc.com/accounts/[account_id]/applications/[application_id]/incidents/[incident_id])')

    def test_deployment(self):
        msg = self.send_new_relic_message('deployment')
        self.assertEqual(msg.subject, 'Test App deploy')
        self.assertEqual(msg.content, '`1242` deployed by **Zulip Test**\n\
Description sent via curl\n\nChangelog string')

class RateLimitTests(AuthedTestCase):

    def setUp(self):
        settings.RATE_LIMITING = True
        add_ratelimit_rule(1, 5)


    def tearDown(self):
        settings.RATE_LIMITING = False
        remove_ratelimit_rule(1, 5)

    def send_api_message(self, email, api_key, content):
        return self.client.post("/api/v1/send_message", {"type": "stream",
                                                                   "to": "Verona",
                                                                   "client": "test suite",
                                                                   "content": content,
                                                                   "subject": "Test subject",
                                                                   "email": email,
                                                                   "api-key": api_key})
    def test_headers(self):
        email = "hamlet@zulip.com"
        user = get_user_profile_by_email(email)
        clear_user_history(user)
        api_key = self.get_api_key(email)

        result = self.send_api_message(email, api_key, "some stuff")
        self.assertTrue('X-RateLimit-Remaining' in result)
        self.assertTrue('X-RateLimit-Limit' in result)
        self.assertTrue('X-RateLimit-Reset' in result)

    def test_ratelimit_decrease(self):
        email = "hamlet@zulip.com"
        user = get_user_profile_by_email(email)
        clear_user_history(user)
        api_key = self.get_api_key(email)
        result = self.send_api_message(email, api_key, "some stuff")
        limit = int(result['X-RateLimit-Remaining'])

        result = self.send_api_message(email, api_key, "some stuff 2")
        newlimit = int(result['X-RateLimit-Remaining'])
        self.assertEqual(limit, newlimit + 1)

    @slow(1.1, 'has to sleep to work')
    def test_hit_ratelimits(self):
        email = "cordelia@zulip.com"
        user = get_user_profile_by_email(email)
        clear_user_history(user)

        api_key = self.get_api_key(email)
        for i in range(6):
            result = self.send_api_message(email, api_key, "some stuff %s" % (i,))

        self.assertEqual(result.status_code, 403)
        json = ujson.loads(result.content)
        self.assertEqual(json.get("result"), "error")
        self.assertIn("API usage exceeded rate limit, try again in", json.get("msg"))

        # We actually wait a second here, rather than force-clearing our history,
        # to make sure the rate-limiting code automatically forgives a user
        # after some time has passed.
        time.sleep(1)

        result = self.send_api_message(email, api_key, "Good message")

        self.assert_json_success(result)

class AlertWordTests(AuthedTestCase):
    def test_default_no_words(self):
        email = "cordelia@zulip.com"
        user = get_user_profile_by_email(email)

        words = user_alert_words(user)

        self.assertEqual(words, [])

    def test_add_word(self):
        email = "cordelia@zulip.com"
        user = get_user_profile_by_email(email)

        add_user_alert_words(user, ['alert', 'word'])
        words = user_alert_words(user)

        self.assertEqual(words, ['alert', 'word'])

    def test_remove_word(self):
        email = "cordelia@zulip.com"
        user = get_user_profile_by_email(email)

        add_user_alert_words(user, ['alert', 'word'])
        remove_user_alert_words(user, ['alert'])
        words = user_alert_words(user)

        self.assertEqual(words, ['word'])

    def test_realm_words(self):
        email = "cordelia@zulip.com"
        user1 = get_user_profile_by_email(email)

        add_user_alert_words(user1, ['alert', 'word'])

        email = "othello@zulip.com"
        user2 = get_user_profile_by_email(email)
        add_user_alert_words(user2, ['another'])

        realm_words = alert_words_in_realm(user2.realm)
        self.assertEqual(len(realm_words), 2)
        self.assertEqual(realm_words.keys(), [user1, user2])
        self.assertEqual(realm_words[user1], ['alert', 'word'])
        self.assertEqual(realm_words[user2], ['another'])

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

        data = urllib.urlencode({'alert_words': ujson.dumps(['one'])})
        result = self.client.delete('/json/users/me/alert_words', data)
        self.assert_json_success(result)

        result = self.client.get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['two', 'three'])

    def test_json_list_set(self):
        self.login("hamlet@zulip.com")

        result = self.client_patch('/json/users/me/alert_words', {'alert_words': ujson.dumps(['one', 'two', 'three'])})
        self.assert_json_success(result)

        data = urllib.urlencode({'alert_words': ujson.dumps(['a', 'b', 'c'])})
        result = self.client.put('/json/users/me/alert_words', data)
        self.assert_json_success(result)

        result = self.client.get('/json/users/me/alert_words')
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['alert_words'], ['a', 'b', 'c'])

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

class CheckMessageTest(AuthedTestCase):
    def test_basic_check_message_call(self):
        sender = get_user_profile_by_email('othello@zulip.com')
        client, _ = Client.objects.get_or_create(name="test suite")
        stream_name = 'integration'
        stream, _ = create_stream_if_needed(Realm.objects.get(domain="zulip.com"), stream_name)
        message_type_name = 'stream'
        message_to = None
        message_to = [stream_name]
        subject_name = 'issue'
        message_content = 'whatever'
        ret = check_message(sender, client, message_type_name, message_to,
                      subject_name, message_content)
        self.assertEqual(ret['message'].sender.email, 'othello@zulip.com')

    def test_bot_pm_feature(self):
        # We send a PM to a bot's owner if their bot sends a message to
        # an unsubscribed stream
        parent = get_user_profile_by_email('othello@zulip.com')
        bot = do_create_user(
                email='othello-bot@zulip.com',
                password='',
                realm=parent.realm,
                full_name='',
                short_name='',
                active=True,
                bot=True,
                bot_owner=parent
        )
        bot.last_reminder = None

        sender = bot
        client, _ = Client.objects.get_or_create(name="test suite")
        stream_name = 'integration'
        stream, _ = create_stream_if_needed(Realm.objects.get(domain="zulip.com"), stream_name)
        message_type_name = 'stream'
        message_to = None
        message_to = [stream_name]
        subject_name = 'issue'
        message_content = 'whatever'
        old_count = message_stream_count(parent)
        ret = check_message(sender, client, message_type_name, message_to,
                      subject_name, message_content)
        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 1)
        self.assertEqual(ret['message'].sender.email, 'othello-bot@zulip.com')

def full_test_name(test):
    test_class = test.__class__.__name__
    test_method = test._testMethodName
    return '%s/%s' % (test_class, test_method)

def get_test_method(test):
    return getattr(test, test._testMethodName)

def enforce_timely_test_completion(test_method, test_name, delay):
    if hasattr(test_method, 'expected_run_time'):
        # Allow for tests to run 50% slower than normal due
        # to random variations.
        max_delay = 1.5 * test_method.expected_run_time
    else:
        max_delay = 0.180 # seconds

    # Further adjustments for slow laptops:
    max_delay = max_delay * 3

    if delay > max_delay:
        print 'Test is TOO slow: %s (%.3f s)' % (test_name, delay)

def fast_tests_only():
    return os.environ.get('FAST_TESTS_ONLY', False)

def run_test(test):
    test_method = get_test_method(test)

    if fast_tests_only() and is_known_slow_test(test_method):
        return

    test_name = full_test_name(test)

    bounce_key_prefix_for_testing(test_name)

    print 'Running %s' % (test_name,)
    test._pre_setup()

    start_time = time.time()

    test.setUp()
    test_method()
    test.tearDown()

    delay = time.time() - start_time
    enforce_timely_test_completion(test_method, test_name, delay)

    test._post_teardown()

class Runner(DjangoTestSuiteRunner):
    option_list = ()

    def __init__(self, *args, **kwargs):
        DjangoTestSuiteRunner.__init__(self, *args, **kwargs)

    def run_suite(self, suite):
        for test in suite:
            run_test(test)

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        self.setup_test_environment()
        suite = self.build_suite(test_labels, extra_tests)
        self.run_suite(suite)
        self.teardown_test_environment()
        print 'DONE!'
        print
