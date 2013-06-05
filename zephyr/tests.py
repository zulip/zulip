# -*- coding: utf-8 -*-
from __future__ import absolute_import

from django.test import TestCase
from django.test.simple import DjangoTestSuiteRunner
from django.utils.timezone import now
from django.db.models import Q

from zephyr.models import Message, UserProfile, Stream, Recipient, Subscription, \
    filter_by_subscriptions, get_display_recipient, Realm, Client, \
    PreregistrationUser, UserMessage
from zephyr.tornadoviews import json_get_updates, api_get_messages
from zephyr.decorator import RespondAsynchronously, RequestVariableConversionError
from zephyr.lib.initial_password import initial_password
from zephyr.lib.actions import do_send_message, gather_subscriptions, \
    create_stream_if_needed, do_add_subscription
from zephyr.lib.rate_limiter import add_ratelimit_rule, remove_ratelimit_rule
from zephyr.lib import bugdown

import simplejson
import subprocess
import optparse
from django.conf import settings
import re
import sys
import random
import os
import urllib2
from StringIO import StringIO

from boto.s3.connection import S3Connection
from boto.s3.key import Key

def bail(msg):
    print '\nERROR: %s\n' % (msg,)
    sys.exit(1)

try:
    settings.TEST_SUITE
except:
    bail('Test suite only runs correctly with --settings=humbug.test_settings')

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

class AuthedTestCase(TestCase):
    def login(self, email, password=None):
        if password is None:
            password = initial_password(email)
        return self.client.post('/accounts/login/',
                                {'username':email, 'password':password})

    def register(self, username, password):
        self.client.post('/accounts/home/',
                         {'email': username + '@humbughq.com'})
        return self.submit_reg_form_for_user(username, password)

    def submit_reg_form_for_user(self, username, password):
        """
        Stage two of the two-step registration process.

        If things are working correctly the account should be fully
        registered after this call.
        """
        return self.client.post('/accounts/register/',
                                {'full_name': username, 'password': password,
                                 'key': find_key_by_email(username + '@humbughq.com'),
                                 'terms': True})

    def get_api_key(self, email):
        return self.get_user_profile(email).api_key

    def get_user_profile(self, email):
        """
        Given an email address, return the UserProfile object for the
        User that has that email.
        """
        # Usernames are unique, even across Realms.
        # We use this rather than get_user_profile_by_email to circumvent memcached (I think?)
        return UserProfile.objects.get(email__iexact=email)

    def get_streams(self, email):
        """
        Helper function to get the stream names for a user
        """
        user_profile = self.get_user_profile(email)
        subs = Subscription.objects.filter(
            user_profile    = user_profile,
            active          = True,
            recipient__type = Recipient.STREAM)
        return [get_display_recipient(sub.recipient) for sub in subs]

    def send_message(self, sender_name, recipient_name, message_type,
                     content="test content", subject="test"):
        sender = self.get_user_profile(sender_name)
        if message_type == Recipient.PERSONAL:
            recipient = self.get_user_profile(recipient_name)
        else:
            recipient = Stream.objects.get(name=recipient_name, realm=sender.realm)
        recipient = Recipient.objects.get(type_id=recipient.id, type=message_type)
        pub_date = now()
        (sending_client, _) = Client.objects.get_or_create(name="test suite")
        # Subject field is unused by PMs.
        do_send_message(Message(sender=sender, recipient=recipient, subject=subject,
                                pub_date=pub_date, sending_client=sending_client,
                                content=content))

    def get_old_messages(self, anchor=1, num_before=1, num_after=1):
        post_params = {"anchor": anchor, "num_before": num_before,
                       "num_after": num_after}
        result = self.client.post("/json/get_old_messages", dict(post_params))
        data = simplejson.loads(result.content)
        return data['messages']

    def users_subscribed_to_stream(self, stream_name, realm_domain):
        realm = Realm.objects.get(domain=realm_domain)
        stream = Stream.objects.get(name=stream_name, realm=realm)
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        subscriptions = Subscription.objects.filter(recipient=recipient)

        return [subscription.user_profile for subscription in subscriptions]

    def message_stream(self, user_profile):
        return filter_by_subscriptions(Message.objects.all(), user_profile)

    def assert_json_success(self, result):
        """
        Successful POSTs return a 200 and JSON of the form {"result": "success",
        "msg": ""}.
        """
        self.assertEqual(result.status_code, 200)
        json = simplejson.loads(result.content)
        self.assertEqual(json.get("result"), "success")
        # We have a msg key for consistency with errors, but it typically has an
        # empty value.
        self.assertIn("msg", json)

    def get_json_error(self, result):
        self.assertEqual(result.status_code, 400)
        json = simplejson.loads(result.content)
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

    def subscribe_to_stream(self, email, stream_name):
        stream, _ = create_stream_if_needed(Realm.objects.get(domain="humbughq.com"), stream_name)
        user_profile = self.get_user_profile(email)
        do_add_subscription(user_profile, stream, no_log=True)

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
    fixtures = ['messages.json']

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
    fixtures = ['messages.json']

    def test_login(self):
        self.login("hamlet@humbughq.com")
        user_profile = self.get_user_profile('hamlet@humbughq.com')
        self.assertEqual(self.client.session['_auth_user_id'], user_profile.id)

    def test_login_bad_password(self):
        self.login("hamlet@humbughq.com", "wrongpassword")
        self.assertIsNone(self.client.session.get('_auth_user_id', None))

    def test_register(self):
        self.register("test", "test")
        user_profile = self.get_user_profile('test@humbughq.com')
        self.assertEqual(self.client.session['_auth_user_id'], user_profile.id)

    def test_logout(self):
        self.login("hamlet@humbughq.com")
        self.client.post('/accounts/logout/')
        self.assertIsNone(self.client.session.get('_auth_user_id', None))

    def test_non_ascii_login(self):
        """
        You can log in even if your password contain non-ASCII characters.
        """
        email = "test@humbughq.com"
        password = u"hümbüǵ"

        # Registering succeeds.
        self.register("test", password)
        user_profile = self.get_user_profile(email)
        self.assertEqual(self.client.session['_auth_user_id'], user_profile.id)
        self.client.post('/accounts/logout/')
        self.assertIsNone(self.client.session.get('_auth_user_id', None))

        # Logging in succeeds.
        self.client.post('/accounts/logout/')
        self.login(email, password)
        self.assertEqual(self.client.session['_auth_user_id'], user_profile.id)

class PersonalMessagesTest(AuthedTestCase):
    fixtures = ['messages.json']

    def test_auto_subbed_to_personals(self):
        """
        Newly created users are auto-subbed to the ability to receive
        personals.
        """
        self.register("test", "test")
        user_profile = self.get_user_profile('test@humbughq.com')
        old_messages = self.message_stream(user_profile)
        self.send_message("test@humbughq.com", "test@humbughq.com", Recipient.PERSONAL)
        new_messages = self.message_stream(user_profile)
        self.assertEqual(len(new_messages) - len(old_messages), 1)

        recipient = Recipient.objects.get(type_id=user_profile.id,
                                          type=Recipient.PERSONAL)
        self.assertEqual(new_messages[-1].recipient, recipient)

    def test_personal_to_self(self):
        """
        If you send a personal to yourself, only you see it.
        """
        old_user_profiles = list(UserProfile.objects.all())
        self.register("test1", "test1")

        old_messages = []
        for user_profile in old_user_profiles:
            old_messages.append(len(self.message_stream(user_profile)))

        self.send_message("test1@humbughq.com", "test1@humbughq.com", Recipient.PERSONAL)

        new_messages = []
        for user_profile in old_user_profiles:
            new_messages.append(len(self.message_stream(user_profile)))

        self.assertEqual(old_messages, new_messages)

        user_profile = self.get_user_profile("test1@humbughq.com")
        recipient = Recipient.objects.get(type_id=user_profile.id, type=Recipient.PERSONAL)
        self.assertEqual(self.message_stream(user_profile)[-1].recipient, recipient)

    def assert_personal(self, sender_email, receiver_email, content="test content"):
        """
        Send a private message from `sender_email` to `receiver_email` and check
        that only those two parties actually received the message.
        """
        sender = self.get_user_profile(sender_email)
        receiver = self.get_user_profile(receiver_email)

        sender_messages = len(self.message_stream(sender))
        receiver_messages = len(self.message_stream(receiver))

        other_user_profiles = UserProfile.objects.filter(~Q(email=sender_email) &
                                                         ~Q(email=receiver_email))
        old_other_messages = []
        for user_profile in other_user_profiles:
            old_other_messages.append(len(self.message_stream(user_profile)))

        self.send_message(sender_email, receiver_email, Recipient.PERSONAL, content)

        # Users outside the conversation don't get the message.
        new_other_messages = []
        for user_profile in other_user_profiles:
            new_other_messages.append(len(self.message_stream(user_profile)))

        self.assertEqual(old_other_messages, new_other_messages)

        # The personal message is in the streams of both the sender and receiver.
        self.assertEqual(len(self.message_stream(sender)),
                         sender_messages + 1)
        self.assertEqual(len(self.message_stream(receiver)),
                         receiver_messages + 1)

        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        self.assertEqual(self.message_stream(sender)[-1].recipient, recipient)
        self.assertEqual(self.message_stream(receiver)[-1].recipient, recipient)

    def test_personal(self):
        """
        If you send a personal, only you and the recipient see it.
        """
        self.login("hamlet@humbughq.com")
        self.assert_personal("hamlet@humbughq.com", "othello@humbughq.com")

    def test_non_ascii_personal(self):
        """
        Sending a PM containing non-ASCII characters succeeds.
        """
        self.login("hamlet@humbughq.com")
        self.assert_personal("hamlet@humbughq.com", "othello@humbughq.com", u"hümbüǵ")

class StreamMessagesTest(AuthedTestCase):
    fixtures = ['messages.json']

    def assert_stream_message(self, stream_name, subject="test subject",
                              content="test content"):
        """
        Check that messages sent to a stream reach all subscribers to that stream.
        """
        subscribers = self.users_subscribed_to_stream(stream_name, "humbughq.com")
        old_subscriber_messages = []
        for subscriber in subscribers:
            old_subscriber_messages.append(len(self.message_stream(subscriber)))

        non_subscribers = [user_profile for user_profile in UserProfile.objects.all()
                           if user_profile not in subscribers]
        old_non_subscriber_messages = []
        for non_subscriber in non_subscribers:
            old_non_subscriber_messages.append(len(self.message_stream(non_subscriber)))

        a_subscriber_email = subscribers[0].email
        self.login(a_subscriber_email)
        self.send_message(a_subscriber_email, stream_name, Recipient.STREAM,
                          subject, content)

        # Did all of the subscribers get the message?
        new_subscriber_messages = []
        for subscriber in subscribers:
           new_subscriber_messages.append(len(self.message_stream(subscriber)))

        # Did non-subscribers not get the message?
        new_non_subscriber_messages = []
        for non_subscriber in non_subscribers:
            new_non_subscriber_messages.append(len(self.message_stream(non_subscriber)))

        self.assertEqual(old_non_subscriber_messages, new_non_subscriber_messages)
        self.assertEqual(new_subscriber_messages, [elt + 1 for elt in old_subscriber_messages])

    def test_message_to_stream(self):
        """
        If you send a message to a stream, everyone subscribed to the stream
        receives the messages.
        """
        self.assert_stream_message("Scotland")

    def test_non_ascii_stream_message(self):
        """
        Sending a stream message containing non-ASCII characters in the stream
        name, subject, or message body succeeds.
        """
        self.login("hamlet@humbughq.com")

        # Subscribe everyone to a stream with non-ASCII characters.
        non_ascii_stream_name = u"hümbüǵ"
        realm = Realm.objects.get(domain="humbughq.com")
        stream, _ = create_stream_if_needed(realm, non_ascii_stream_name)
        for user_profile in UserProfile.objects.filter(realm=realm):
            do_add_subscription(user_profile, stream, no_log=True)

        self.assert_stream_message(non_ascii_stream_name, subject=u"hümbüǵ",
                                   content=u"hümbüǵ")

class PointerTest(AuthedTestCase):
    fixtures = ['messages.json']

    def test_update_pointer(self):
        """
        Posting a pointer to /update (in the form {"pointer": pointer}) changes
        the pointer we store for your UserProfile.
        """
        self.login("hamlet@humbughq.com")
        self.assertEqual(self.get_user_profile("hamlet@humbughq.com").pointer, -1)
        result = self.client.post("/json/update_pointer", {"pointer": 1})
        self.assert_json_success(result)
        self.assertEqual(self.get_user_profile("hamlet@humbughq.com").pointer, 1)

    def test_api_update_pointer(self):
        """
        Same as above, but for the API view
        """
        email = "hamlet@humbughq.com"
        api_key = self.get_api_key(email)
        self.assertEqual(self.get_user_profile(email).pointer, -1)
        result = self.client.post("/api/v1/update_pointer", {"email": email,
                                                             "api-key": api_key,
                                                             "pointer": 1})
        self.assert_json_success(result)
        self.assertEqual(self.get_user_profile(email).pointer, 1)

    def test_missing_pointer(self):
        """
        Posting json to /json/update_pointer which does not contain a pointer key/value pair
        returns a 400 and error message.
        """
        self.login("hamlet@humbughq.com")
        self.assertEqual(self.get_user_profile("hamlet@humbughq.com").pointer, -1)
        result = self.client.post("/json/update_pointer", {"foo": 1})
        self.assert_json_error(result, "Missing 'pointer' argument")
        self.assertEqual(self.get_user_profile("hamlet@humbughq.com").pointer, -1)

    def test_invalid_pointer(self):
        """
        Posting json to /json/update_pointer with an invalid pointer returns a 400 and error
        message.
        """
        self.login("hamlet@humbughq.com")
        self.assertEqual(self.get_user_profile("hamlet@humbughq.com").pointer, -1)
        result = self.client.post("/json/update_pointer", {"pointer": "foo"})
        self.assert_json_error(result, "Bad value for 'pointer': foo")
        self.assertEqual(self.get_user_profile("hamlet@humbughq.com").pointer, -1)

    def test_pointer_out_of_range(self):
        """
        Posting json to /json/update_pointer with an out of range (< 0) pointer returns a 400
        and error message.
        """
        self.login("hamlet@humbughq.com")
        self.assertEqual(self.get_user_profile("hamlet@humbughq.com").pointer, -1)
        result = self.client.post("/json/update_pointer", {"pointer": -2})
        self.assert_json_error(result, "Bad value for 'pointer': -2")
        self.assertEqual(self.get_user_profile("hamlet@humbughq.com").pointer, -1)

class MessagePOSTTest(AuthedTestCase):
    fixtures = ['messages.json']

    def test_message_to_self(self):
        """
        Sending a message to a stream to which you are subscribed is
        successful.
        """
        self.login("hamlet@humbughq.com")
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
        email = "hamlet@humbughq.com"
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
        self.login("hamlet@humbughq.com")
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
        self.login("hamlet@humbughq.com")
        result = self.client.post("/json/send_message", {"type": "private",
                                                         "content": "Test message",
                                                         "client": "test suite",
                                                         "to": "othello@humbughq.com"})
        self.assert_json_success(result)

    def test_personal_message_to_nonexistent_user(self):
        """
        Sending a personal message to an invalid email returns error JSON.
        """
        self.login("hamlet@humbughq.com")
        result = self.client.post("/json/send_message", {"type": "private",
                                                         "content": "Test message",
                                                         "client": "test suite",
                                                         "to": "nonexistent"})
        self.assert_json_error(result, "Invalid email 'nonexistent'")

    def test_invalid_type(self):
        """
        Sending a message of unknown type returns error JSON.
        """
        self.login("hamlet@humbughq.com")
        result = self.client.post("/json/send_message", {"type": "invalid type",
                                                         "content": "Test message",
                                                         "client": "test suite",
                                                         "to": "othello@humbughq.com"})
        self.assert_json_error(result, "Invalid message type")

    def test_mirrored_huddle(self):
        """
        Sending a mirrored huddle message works
        """
        self.login("starnine@mit.edu")
        result = self.client.post("/json/send_message", {"type": "private",
                                                         "sender": "sipbtest@mit.edu",
                                                         "content": "Test message",
                                                         "client": "zephyr_mirror",
                                                         "to": simplejson.dumps(["starnine@mit.edu",
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

class SubscriptionPropertiesTest(AuthedTestCase):
    fixtures = ['messages.json']

    def test_get_stream_color(self):
        """
        A GET request to
        /json/subscriptions/property?property=color+stream_name=foo returns
        the color for stream foo.
        """
        test_email = "hamlet@humbughq.com"
        self.login(test_email)
        subs = gather_subscriptions(self.get_user_profile(test_email))
        result = self.client.get("/json/subscriptions/property",
                                  {"property": "color",
                                   "stream_name": subs[0]['name']})

        self.assert_json_success(result)
        json = simplejson.loads(result.content)

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
        test_email = "hamlet@humbughq.com"
        self.login(test_email)

        old_subs = gather_subscriptions(self.get_user_profile(test_email))
        sub = old_subs[0]
        stream_name = sub['name']
        old_color = sub['color']
        invite_only = sub['invite_only']
        new_color = "#ffffff" # TODO: ensure that this is different from old_color
        result = self.client.post("/json/subscriptions/property",
                                  {"property": "color",
                                   "stream_name": stream_name,
                                   "value": "#ffffff"})

        self.assert_json_success(result)

        new_subs = gather_subscriptions(self.get_user_profile(test_email))
        sub = {'name': stream_name, 'in_home_view': True, 'color': new_color,
               'invite_only': invite_only, 'notifications': False}
        self.assertIn(sub, new_subs)

        new_subs.remove(sub)
        sub['color'] = old_color
        old_subs.remove(sub)
        self.assertEqual(old_subs, new_subs)

    def test_set_color_missing_stream_name(self):
        """
        Updating the color property requires a stream_name.
        """
        test_email = "hamlet@humbughq.com"
        self.login(test_email)
        result = self.client.post("/json/subscriptions/property",
                                  {"property": "color",
                                   "value": "#ffffff"})

        self.assert_json_error(result, "Missing 'stream_name' argument")

    def test_set_color_missing_color(self):
        """
        Updating the color property requires a color.
        """
        test_email = "hamlet@humbughq.com"
        self.login(test_email)
        subs = gather_subscriptions(self.get_user_profile(test_email))
        result = self.client.post("/json/subscriptions/property",
                                  {"property": "color",
                                   "stream_name": subs[0]["name"]})

        self.assert_json_error(result, "Missing 'value' argument")

    def test_set_invalid_property(self):
        """
        Trying to set an invalid property returns a JSON error.
        """
        test_email = "hamlet@humbughq.com"
        self.login(test_email)
        subs = gather_subscriptions(self.get_user_profile(test_email))
        result = self.client.post("/json/subscriptions/property",
                                  {"property": "bad",
                                   "stream_name": subs[0]["name"]})

        self.assert_json_error(result,
                               "Unknown subscription property: bad")

class SubscriptionAPITest(AuthedTestCase):
    fixtures = ['messages.json']

    def setUp(self):
        """
        All tests will be logged in as hamlet. Also save various useful values
        as attributes that tests can access.
        """
        self.test_email = "hamlet@humbughq.com"
        self.login(self.test_email)
        self.user_profile = self.get_user_profile(self.test_email)
        self.realm = self.user_profile.realm
        self.streams = self.get_streams(self.test_email)

    def make_random_stream_names(self, existing_stream_names, names_to_avoid):
        """
        Helper function to make up random stream names. It takes
        existing_stream_names and randomly appends a digit to the end of each,
        but avoids names that appear in the list names_to_avoid.
        """
        random_streams = []
        for stream in existing_stream_names:
            random_stream = stream + str(random.randint(0, 9))
            if not random_stream in names_to_avoid:
                random_streams.append(random_stream)
        return random_streams

    def test_successful_subscriptions_list(self):
        """
        Calling /json/subscriptions/list should successfully return your subscriptions.
        """
        result = self.client.post("/json/subscriptions/list", {})
        self.assert_json_success(result)
        json = simplejson.loads(result.content)
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

    def helper_check_subs_before_and_after_add(self, url, subscriptions, other_params,
                                               json_dict, email, new_subs):
        """
        Check result of adding subscriptions.

        You can add subscriptions for yourself or possibly many
        principals, which is why e-mails map to subscriptions in the
        result.

        The result json is of the form

        {"msg": "",
         "result": "success",
         "already_subscribed": {"iago@humbughq.com": ["Venice", "Verona"]},
         "subscribed": {"iago@humbughq.com": ["Venice8"]}}
        """
        data = {"subscriptions": simplejson.dumps(subscriptions)}
        data.update(other_params)
        result = self.client.post(url, data)
        self.assert_json_success(result)
        json = simplejson.loads(result.content)
        for subscription_status, val in json_dict.iteritems():
            # keys are subscribed, already_subscribed.
            # vals are a dict mapping e-mails to streams.
            self.assertIn(subscription_status, json)
            for email, streams in val.iteritems():
                self.assertItemsEqual(streams, json[subscription_status][email])
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
        add_streams = self.make_random_stream_names(self.streams, self.streams)
        self.assertNotEqual(len(add_streams), 0)  # necessary for full test coverage
        self.helper_check_subs_before_and_after_add(
            "/json/subscriptions/add", self.streams + add_streams, {},
            {"subscribed": {self.test_email: add_streams},
             "already_subscribed": {self.test_email: self.streams}},
            self.test_email, self.streams + add_streams)

    def test_non_ascii_stream_subscription(self):
        """
        Subscribing to a stream name with non-ASCII characters succeeds.
        """
        self.helper_check_subs_before_and_after_add(
            "/json/subscriptions/add", self.streams + [u"hümbüǵ"], {},
            {"subscribed": {self.test_email: [u"hümbüǵ"]},
             "already_subscribed": {self.test_email: self.streams}},
            self.test_email, self.streams + [u"hümbüǵ"])

    def test_subscriptions_add_too_long(self):
        """
        Calling /json/subscriptions/add on a stream whose name is >30
        characters should return a JSON error.
        """
        # character limit is 30 characters
        long_stream_name = "a" * 31
        result = self.client.post("/json/subscriptions/add",
                                   {"subscriptions": simplejson.dumps([long_stream_name])})
        self.assert_json_error(result,
                               "Stream name (%s) too long." % (long_stream_name,))

    def test_subscriptions_add_invalid_stream(self):
        """
        Calling /json/subscriptions/add on a stream whose name is invalid (as
        defined by valid_stream_name in zephyr/views.py) should return a JSON
        error.
        """
        # currently, the only invalid name is the empty string
        invalid_stream_name = ""
        result = self.client.post("/json/subscriptions/add",
                                   {"subscriptions": simplejson.dumps([invalid_stream_name])})
        self.assert_json_error(result,
                               "Invalid stream name (%s)." % (invalid_stream_name,))

    def assert_adding_subscriptions_for_principal(self, invitee, streams):
        """
        Calling /json/subscriptions/add on behalf of another principal (for
        whom you have permission to add subscriptions) should successfully add
        those subscriptions and send a message to the subscribee notifying
        them.
        """
        other_profile = self.get_user_profile(invitee)
        current_streams = self.get_streams(invitee)
        self.assertIsInstance(other_profile, UserProfile)
        self.assertNotEqual(len(current_streams), 0)  # necessary for full test coverage
        self.assertNotEqual(len(streams), 0)  # necessary for full test coverage
        streams_to_sub = streams[:1]  # just add one, to make the message easier to check
        streams_to_sub.extend(current_streams)
        self.helper_check_subs_before_and_after_add(
            "/json/subscriptions/add", streams_to_sub,
            {"principals": simplejson.dumps([invitee])},
            {"subscribed": {invitee: streams[:1]},
             "already_subscribed": {invitee: current_streams}},
            invitee, streams_to_sub)
        # verify that the user was sent a message informing them about the subscription
        msg = Message.objects.latest('id')
        self.assertEqual(msg.recipient.type, msg.recipient.PERSONAL)
        self.assertEqual(msg.sender_id,
                self.get_user_profile("humbug+notifications@humbughq.com").id)
        expected_msg = ("Hi there!  We thought you'd like to know that %s just "
                        "subscribed you to the stream '%s'\nYou can see historical "
                        "content on a non-invite-only stream by narrowing to it."
                        % (self.user_profile.full_name, streams[0]))
        self.assertEqual(msg.content, expected_msg)
        recipients = get_display_recipient(msg.recipient)
        self.assertEqual(len(recipients), 1)
        self.assertEqual(recipients[0]['email'], invitee)

    def test_subscriptions_add_for_principal(self):
        """
        You can subscribe other people to streams.
        """
        invitee = "iago@humbughq.com"
        current_streams = self.get_streams(invitee)
        invite_streams = self.make_random_stream_names(current_streams, current_streams)
        self.assert_adding_subscriptions_for_principal(invitee, invite_streams)

    def test_non_ascii_subscription_for_principal(self):
        """
        You can subscribe other people to streams even if they containing
        non-ASCII characters.
        """
        self.assert_adding_subscriptions_for_principal("iago@humbughq.com", [u"hümbüǵ"])

    def test_subscription_add_invalid_principal(self):
        """
        Calling /json/subscriptions/add on behalf of a principal that does not
        exist should return a JSON error.
        """
        invalid_principal = "rosencrantz-and-guildenstern@humbughq.com"
        # verify that invalid_principal actually doesn't exist
        with self.assertRaises(UserProfile.DoesNotExist):
            self.get_user_profile(invalid_principal)
        result = self.client.post("/json/subscriptions/add",
                                   {"subscriptions": simplejson.dumps(self.streams),
                                    "principals": simplejson.dumps([invalid_principal])})
        self.assert_json_error(result, "User not authorized to execute queries on behalf of '%s'"
                               % (invalid_principal,))

    def test_subscription_add_principal_other_realm(self):
        """
        Calling /json/subscriptions/add on behalf of a principal in another
        realm should return a JSON error.
        """
        principal = "starnine@mit.edu"
        profile = self.get_user_profile(principal)
        # verify that principal exists (thus, the reason for the error is the cross-realming)
        self.assertIsInstance(profile, UserProfile)
        result = self.client.post("/json/subscriptions/add",
                                   {"subscriptions": simplejson.dumps(self.streams),
                                    "principals": simplejson.dumps([principal])})
        self.assert_json_error(result, "User not authorized to execute queries on behalf of '%s'"
                               % (principal,))

    def helper_check_subs_before_and_after_remove(self, url, subscriptions, other_params,
                                               json_dict, email, new_subs):
        """
        Check result of removing subscriptions.

        Unlike adding subscriptions, you can only remove subscriptions
        for yourself, so the result format is different.

        {"msg": "",
         "removed": ["Denmark", "Scotland", "Verona"],
         "not_subscribed": ["Rome"], "result": "success"}
        """
        data = {"subscriptions": simplejson.dumps(subscriptions)}
        data.update(other_params)
        result = self.client.post(url, data)
        self.assert_json_success(result)
        json = simplejson.loads(result.content)
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
        self.helper_check_subs_before_and_after_remove(
            "/json/subscriptions/remove", streams_to_remove, {},
            {"removed": self.streams[1:], "not_subscribed": try_to_remove},
            self.test_email, [self.streams[0]])

    def test_subscriptions_remove_fake_stream(self):
        """
        Calling /json/subscriptions/remove on a stream that doesn't exist
        should return a JSON error.
        """
        all_stream_names = [stream.name for stream in Stream.objects.filter(realm=self.realm)]
        random_streams = self.make_random_stream_names(self.streams, all_stream_names)
        self.assertNotEqual(len(random_streams), 0)  # necessary for full test coverage
        streams_to_remove = random_streams[:1]  # pick only one fake stream, to make checking the error message easy
        result = self.client.post("/json/subscriptions/remove",
                                  {"subscriptions": simplejson.dumps(streams_to_remove)})
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
        json = simplejson.loads(result.content)
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
        all_stream_names = [stream.name for stream in Stream.objects.filter(realm=self.realm)]
        random_streams = self.make_random_stream_names(self.streams, all_stream_names)
        self.assertNotEqual(len(random_streams), 0)  # necessary for full test coverage
        self.helper_subscriptions_exists(random_streams[0], False, None)

    def test_subscriptions_exist_invalid_name(self):
        """
        Calling /json/subscriptions/exist on a stream whose name is invalid (as
        defined by valid_stream_name in zephyr/views.py) should return a JSON
        error.
        """
        # currently, the only invalid stream name is the empty string
        invalid_stream_name = ""
        result = self.client.post("/json/subscriptions/exists",
                                  {"stream": invalid_stream_name})
        self.assert_json_error(result, "Invalid characters in stream name")

class GetOldMessagesTest(AuthedTestCase):
    fixtures = ['messages.json']

    def post_with_params(self, modified_params):
        post_params = {"anchor": 1, "num_before": 1, "num_after": 1}
        post_params.update(modified_params)
        result = self.client.post("/json/get_old_messages", dict(post_params))
        self.assert_json_success(result)
        return simplejson.loads(result.content)

    def check_well_formed_messages_response(self, result):
        self.assertIn("messages", result)
        self.assertIsInstance(result["messages"], list)
        for message in result["messages"]:
            for field in ("content", "content_type", "display_recipient",
                          "gravatar_hash", "recipient_id", "sender_full_name",
                          "sender_short_name", "timestamp"):
                self.assertIn(field, message)

    def test_successful_get_old_messages(self):
        """
        A call to /json/get_old_messages with valid parameters returns a list of
        messages.
        """
        self.login("hamlet@humbughq.com")
        self.check_well_formed_messages_response(self.post_with_params({}))

    def test_get_old_messages_with_narrow_pm_with(self):
        """
        A request for old messages with a narrow by pm-with only returns
        conversations with that user.
        """
        me = 'hamlet@humbughq.com'
        def dr_emails(dr):
            return ','.join(sorted(set([r['email'] for r in dr] + [me])))

        personals = [m for m in self.message_stream(self.get_user_profile(me))
            if m.recipient.type == Recipient.PERSONAL
            or m.recipient.type == Recipient.HUDDLE]
        if not personals:
            # FIXME: This is bad.  We should use test data that is guaranteed
            # to contain some personals for every user.  See #617.
            return
        emails = dr_emails(get_display_recipient(personals[0].recipient))

        self.login(me)
        result = self.post_with_params({"narrow": simplejson.dumps(
                    [['pm-with', emails]])})
        self.check_well_formed_messages_response(result)

        for message in result["messages"]:
            self.assertEqual(dr_emails(message['display_recipient']), emails)

    def test_get_old_messages_with_narrow_stream(self):
        """
        A request for old messages with a narrow by stream only returns
        messages for that stream.
        """
        self.login("hamlet@humbughq.com")
        # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        realm = Realm.objects.get(domain="humbughq.com")
        stream, _ = create_stream_if_needed(realm, "Scotland")
        do_add_subscription(self.get_user_profile("hamlet@humbughq.com"),
                            stream, no_log=True)
        self.send_message("hamlet@humbughq.com", "Scotland", Recipient.STREAM)
        messages = self.message_stream(self.get_user_profile("hamlet@humbughq.com"))
        stream_messages = filter(lambda msg: msg.recipient.type == Recipient.STREAM,
                                 messages)
        stream_name = get_display_recipient(stream_messages[0].recipient)
        stream_id = stream_messages[0].recipient.id

        result = self.post_with_params({"narrow": simplejson.dumps(
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
        self.login("hamlet@humbughq.com")
        # We need to send a message here to ensure that we actually
        # have a stream message in this narrow view.
        self.send_message("hamlet@humbughq.com", "Scotland", Recipient.STREAM)
        self.send_message("othello@humbughq.com", "Scotland", Recipient.STREAM)
        self.send_message("othello@humbughq.com", "hamlet@humbughq.com", Recipient.PERSONAL)
        self.send_message("iago@humbughq.com", "Scotland", Recipient.STREAM)

        result = self.post_with_params({"narrow": simplejson.dumps(
                    [['sender', "othello@humbughq.com"]])})
        self.check_well_formed_messages_response(result)

        for message in result["messages"]:
            self.assertEqual(message["sender_email"], "othello@humbughq.com")

    def test_missing_params(self):
        """
        anchor, num_before, and num_after are all required
        POST parameters for get_old_messages.
        """
        self.login("hamlet@humbughq.com")

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
        self.login("hamlet@humbughq.com")

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
        self.login("hamlet@humbughq.com")

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
        self.login("hamlet@humbughq.com")
        all_result    = self.post_with_params({})
        narrow_result = self.post_with_params({'narrow': '{}'})

        for r in (all_result, narrow_result):
            self.check_well_formed_messages_response(r)

        self.assertEqual(message_ids(all_result), message_ids(narrow_result))

    def test_bad_narrow_operator(self):
        """
        Unrecognized narrow operators are rejected.
        """
        self.login("hamlet@humbughq.com")
        for operator in ['', 'foo', 'stream:verona', '__init__']:
            params = dict(anchor=0, num_before=0, num_after=0,
                narrow=simplejson.dumps([[operator, '']]))
            result = self.client.post("/json/get_old_messages", params)
            self.assert_json_error_contains(result,
                "Invalid narrow operator: unknown operator")

    def exercise_bad_narrow_operand(self, operator, operands, error_msg):
        other_params = [("anchor", 0), ("num_before", 0), ("num_after", 0)]
        for operand in operands:
            post_params = dict(other_params + [
                ("narrow", simplejson.dumps([[operator, operand]]))])
            result = self.client.post("/json/get_old_messages", post_params)
            self.assert_json_error_contains(result, error_msg)

    def test_bad_narrow_stream_content(self):
        """
        If an invalid stream name is requested in get_old_messages, an error is
        returned.
        """
        self.login("hamlet@humbughq.com")
        bad_stream_content = (0, [], ["x", "y"])
        self.exercise_bad_narrow_operand("stream", bad_stream_content,
            "Bad value for 'narrow'")

    def test_bad_narrow_one_on_one_email_content(self):
        """
        If an invalid 'pm-with' is requested in get_old_messages, an
        error is returned.
        """
        self.login("hamlet@humbughq.com")
        bad_stream_content = (0, [], ["x","y"])
        self.exercise_bad_narrow_operand("pm-with", bad_stream_content,
            "Bad value for 'narrow'")

    def test_bad_narrow_nonexistent_stream(self):
        self.login("hamlet@humbughq.com")
        self.exercise_bad_narrow_operand("stream", ['non-existent stream'],
            "Invalid narrow operator: unknown stream")

    def test_bad_narrow_nonexistent_email(self):
        self.login("hamlet@humbughq.com")
        self.exercise_bad_narrow_operand("pm-with", ['non-existent-user@humbughq.com'],
            "Invalid narrow operator: unknown user")

class InviteUserTest(AuthedTestCase):
    fixtures = ['messages.json']

    def invite(self, users, streams):
        """
        Invites the specified users to Humbug with the specified streams.

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
        self.login("hamlet@humbughq.com")
        invitee = "alice-test@humbughq.com"
        self.assert_json_success(self.invite(invitee, ["Denmark"]))
        self.assertTrue(find_key_by_email(invitee))
        self.check_sent_emails([invitee])

    def test_multi_user_invite(self):
        """
        Invites multiple users with a variety of delimiters.
        """
        self.login("hamlet@humbughq.com")
        # Intentionally use a weird string.
        self.assert_json_success(self.invite(
"""bob-test@humbughq.com,     carol-test@humbughq.com,
dave-test@humbughq.com


earl-test@humbughq.com""", ["Denmark"]))
        for user in ("bob", "carol", "dave", "earl"):
            self.assertTrue(find_key_by_email("%s-test@humbughq.com" % user))
        self.check_sent_emails(["bob-test@humbughq.com", "carol-test@humbughq.com",
                                "dave-test@humbughq.com", "earl-test@humbughq.com"])

    def test_missing_or_invalid_params(self):
        """
        Tests inviting with various missing or invalid parameters.
        """
        self.login("hamlet@humbughq.com")
        self.assert_json_error(
            self.client.post("/json/invite_users", {"invitee_emails": "foo@humbughq.com"}),
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
        self.login("hamlet@humbughq.com")
        self.assert_json_error(self.invite("iago-test@humbughq.com", ["NotARealStream"]),
                "Stream does not exist: NotARealStream. No invites were sent.")
        self.check_sent_emails([])

    def test_invite_existing_user(self):
        """
        If you invite an address already using Humbug, no invitation is sent.
        """
        self.login("hamlet@humbughq.com")
        self.assert_json_error(
            self.client.post("/json/invite_users",
                             {"invitee_emails": "hamlet@humbughq.com",
                              "stream": ["Denmark"]}),
            "We weren't able to invite anyone.")
        self.assertRaises(PreregistrationUser.DoesNotExist,
                          lambda: PreregistrationUser.objects.get(
                email="hamlet@humbughq.com"))
        self.check_sent_emails([])

    def test_invite_some_existing_some_new(self):
        """
        If you invite a mix of already existing and new users, invitations are
        only sent to the new users.
        """
        self.login("hamlet@humbughq.com")
        existing = ["hamlet@humbughq.com", "othello@humbughq.com"]
        new = ["foo-test@humbughq.com", "bar-test@humbughq.com"]

        result = self.client.post("/json/invite_users",
                                  {"invitee_emails": "\n".join(existing + new),
                                   "stream": ["Denmark"]})
        self.assert_json_error(result,
                               "Some of those addresses are already using Humbug, \
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

    def test_invite_outside_domain_in_open_realm(self):
        """
        In a realm with `restricted_to_domain = False`, you can invite people
        with a different domain from that of the realm or your e-mail address.
        """
        self.login("hamlet@humbughq.com")
        external_address = "foo@example.com"

        self.assert_json_error(
            self.invite(external_address, ["Denmark"]),
            "Some emails did not validate, so we didn't send any invitations.")

        humbug_realm = Realm.objects.get(domain="humbughq.com")
        humbug_realm.restricted_to_domain = False
        humbug_realm.save()

        self.assert_json_success(self.invite(external_address, ["Denmark"]))
        self.check_sent_emails([external_address])

    def test_invite_with_non_ascii_streams(self):
        """
        Inviting someone to streams with non-ASCII characters succeeds.
        """
        self.login("hamlet@humbughq.com")
        invitee = "alice-test@humbughq.com"

        stream_name = u"hümbüǵ"
        realm = Realm.objects.get(domain="humbughq.com")
        stream, _ = create_stream_if_needed(realm, stream_name)

        # Make sure we're subscribed before inviting someone.
        do_add_subscription(
            self.get_user_profile("hamlet@humbughq.com"),
            stream, no_log=True)

        self.assert_json_success(self.invite(invitee, [stream_name]))

class ChangeSettingsTest(AuthedTestCase):
    fixtures = ['messages.json']

    def post_with_params(self, modified_params):
        post_params = {"full_name": "Foo Bar",
                  "old_password": initial_password("hamlet@humbughq.com"),
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
        self.login("hamlet@humbughq.com")
        json_result = self.post_with_params({})
        self.assert_json_success(json_result)
        result = simplejson.loads(json_result.content)
        self.check_well_formed_change_settings_response(result)
        self.assertEqual(self.get_user_profile("hamlet@humbughq.com").
                full_name, "Foo Bar")
        self.assertEqual(self.get_user_profile("hamlet@humbughq.com").
                enable_desktop_notifications, False)
        self.client.post('/accounts/logout/')
        self.login("hamlet@humbughq.com", "foobar1")
        user_profile = self.get_user_profile('hamlet@humbughq.com')
        self.assertEqual(self.client.session['_auth_user_id'], user_profile.id)

    def test_missing_params(self):
        """
        full_name, old_password, and new_password are all required POST
        parameters for json_change_settings. (enable_desktop_notifications is
        false by default)
        """
        self.login("hamlet@humbughq.com")
        required_params = (("full_name", "Foo Bar"),
                  ("old_password", initial_password("hamlet@humbughq.com")),
                  ("new_password", initial_password("hamlet@humbughq.com")),
                  ("confirm_password", initial_password("hamlet@humbughq.com")))
        for i in range(len(required_params)):
            post_params = dict(required_params[:i] + required_params[i + 1:])
            result = self.client.post("/json/settings/change", post_params)
            self.assert_json_error(result,
                    "Missing '%s' argument" % (required_params[i][0],))

    def test_mismatching_passwords(self):
        """
        new_password and confirm_password must match
        """
        self.login("hamlet@humbughq.com")
        result = self.post_with_params({"new_password": "mismatched_password"})
        self.assert_json_error(result,
                "New password must match confirmation password!")

    def test_wrong_old_password(self):
        """
        new_password and confirm_password must match
        """
        self.login("hamlet@humbughq.com")
        result = self.post_with_params({"old_password": "bad_password"})
        self.assert_json_error(result, "Wrong password!")

class S3Test(AuthedTestCase):
    fixtures = ['messages.json']
    test_uris = []

    def test_file_upload(self):
        """
        A call to /json/upload_file should return a uri and actually create an object.
        """
        self.login("hamlet@humbughq.com")
        fp = StringIO("humbug!")
        fp.name = "humbug.txt"

        result = self.client.post("/json/upload_file", {'file': fp})
        self.assert_json_success(result)
        json = simplejson.loads(result.content)
        self.assertIn("uri", json)
        uri = json["uri"]
        self.test_uris.append(uri)
        self.assertEquals("humbug!", urllib2.urlopen(uri).read().strip())

    def test_multiple_upload_failure(self):
        """
        Attempting to upload two files should fail.
        """
        self.login("hamlet@humbughq.com")
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
        self.login("hamlet@humbughq.com")

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



class DummyHandler(object):
    def __init__(self, assert_callback):
        self.assert_callback = assert_callback

    # Mocks RequestHandler.async_callback, which wraps a callback to
    # handle exceptions.  We return the callback as-is.
    def async_callback(self, cb):
        return cb

    def write(self, response):
        raise NotImplemented

    def finish(self, response):
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
    fixtures = ['messages.json']

    def common_test_get_updates(self, view_func, extra_post_data = {}):
        user_profile = self.get_user_profile("hamlet@humbughq.com")

        def callback(response):
            correct_message_ids = [m.id for m in
                filter_by_subscriptions(Message.objects.all(), user_profile)]
            for message in response['messages']:
                self.assertGreater(message['id'], 1)
                self.assertIn(message['id'], correct_message_ids)

        post_data = {}
        post_data.update(extra_post_data)
        request = POSTRequestMock(post_data, user_profile, callback)
        self.assertEqual(view_func(request), RespondAsynchronously)

    def test_json_get_updates(self):
        """
        json_get_updates returns messages with IDs greater than the
        last_received ID.
        """
        self.login("hamlet@humbughq.com")
        self.common_test_get_updates(json_get_updates)

    def test_api_get_messages(self):
        """
        Same as above, but for the API view
        """
        email = "hamlet@humbughq.com"
        api_key = self.get_api_key(email)
        self.common_test_get_updates(api_get_messages, {'email': email, 'api-key': api_key})

    def test_missing_last_received(self):
        """
        Calling json_get_updates without any arguments should work
        """
        self.login("hamlet@humbughq.com")
        user_profile = self.get_user_profile("hamlet@humbughq.com")

        request = POSTRequestMock({}, user_profile)
        self.assertEqual(json_get_updates(request), RespondAsynchronously)

    def test_bad_input(self):
        """
        Specifying a bad value for 'pointer' should return an error
        """
        self.login("hamlet@humbughq.com")
        user_profile = self.get_user_profile("hamlet@humbughq.com")

        request = POSTRequestMock({'pointer': 'foo'}, user_profile)
        self.assertRaises(RequestVariableConversionError, json_get_updates, request)

class GetProfileTest(AuthedTestCase):
    fixtures = ['messages.json']

    def common_update_pointer(self, email, pointer):
        self.login(email)
        result = self.client.post("/json/update_pointer", {"pointer": 1})
        self.assert_json_success(result)

    def common_get_profile(self, email):
        user_profile = self.get_user_profile(email)

        api_key = self.get_api_key(email)
        result = self.client.post("/api/v1/get_profile", {'email': email, 'api-key': api_key})

        stream = self.message_stream(user_profile)
        max_id = -1
        if len(stream) > 0:
            max_id = stream[-1].id

        self.assert_json_success(result)
        json = simplejson.loads(result.content)

        self.assertIn("client_id", json)
        self.assertIn("max_message_id", json)
        self.assertIn("pointer", json)

        self.assertEqual(json["max_message_id"], max_id)
        return json

    def test_api_get_empty_profile(self):
        """
        Ensure get_profile returns a max message id and returns successfully
        """
        json = self.common_get_profile("othello@humbughq.com")
        self.assertEqual(json["pointer"], -1)

    def test_profile_with_pointer(self):
        """
        Ensure get_profile returns a proper pointer id after the pointer is updated
        """
        json = self.common_get_profile("hamlet@humbughq.com")

        self.common_update_pointer("hamlet@humbughq.com", 1)
        json = self.common_get_profile("hamlet@humbughq.com")
        self.assertEqual(json["pointer"], 1)

        self.common_update_pointer("hamlet@humbughq.com", 0)
        json = self.common_get_profile("hamlet@humbughq.com")
        self.assertEqual(json["pointer"], 1)

class GetPublicStreamsTest(AuthedTestCase):
    fixtures = ['messages.json']

    def test_public_streams(self):
        """
        Ensure that get_public_streams successfully returns a list of streams
        """
        email = 'hamlet@humbughq.com'
        self.login(email)

        api_key = self.get_api_key(email)
        result = self.client.post("/json/get_public_streams", {'email': email, 'api-key': api_key})

        self.assert_json_success(result)
        json = simplejson.loads(result.content)

        self.assertIn("streams", json)
        self.assertIsInstance(json["streams"], list)

class InviteOnlyStreamTest(AuthedTestCase):
    fixtures = ['messages.json']

    def common_subscribe_to_stream(self, email, streams, extra_post_data = {}, invite_only=False):
        api_key = self.get_api_key(email)

        post_data = {'email': email,
                     'api-key': api_key,
                     'subscriptions': streams,
                     'invite_only': simplejson.dumps(invite_only)}
        post_data.update(extra_post_data)

        result = self.client.post("/api/v1/subscriptions/add", post_data)
        return result

    def test_list_respects_invite_only_bit(self):
        """
        Make sure that /json/subscriptions/list properly returns
        the invite-only bit for streams that are invite-only
        """
        email = 'hamlet@humbughq.com'
        self.login(email)

        result1 = self.common_subscribe_to_stream(email, '["Saxony"]', invite_only=True)
        self.assert_json_success(result1)
        result2 = self.common_subscribe_to_stream(email, '["Normandy"]', invite_only=False)
        self.assert_json_success(result2)
        result = self.client.post("/json/subscriptions/list", {})
        self.assert_json_success(result)
        json = simplejson.loads(result.content)
        self.assertIn("subscriptions", json)
        for sub in json["subscriptions"]:
            if sub['name'] == "Normandy":
                self.assertEqual(sub['invite_only'], False, "Normandy was mistakenly marked invite-only")
            if sub['name'] == "Saxony":
                self.assertEqual(sub['invite_only'], True, "Saxony was not properly marked invite-only")

    def test_inviteonly(self):
        # Creating an invite-only stream is allowed
        email = 'hamlet@humbughq.com'

        result = self.common_subscribe_to_stream(email, '["Saxony"]', invite_only=True)
        self.assert_json_success(result)

        json = simplejson.loads(result.content)
        self.assertEqual(json["subscribed"], {email: ['Saxony']})
        self.assertEqual(json["already_subscribed"], {})

        # Subscribing oneself to an invite-only stream is not allowed
        email = "othello@humbughq.com"
        self.login(email)
        result = self.common_subscribe_to_stream(email, '["Saxony"]')
        self.assert_json_error(result, 'Unable to access invite-only stream (Saxony).')

        # Inviting another user to an invite-only stream is allowed
        email = 'hamlet@humbughq.com'
        self.login(email)
        result = self.common_subscribe_to_stream(
            email, '["Saxony"]',
            extra_post_data={'principals': simplejson.dumps(["othello@humbughq.com"])})
        json = simplejson.loads(result.content)
        self.assertEqual(json["subscribed"], {"othello@humbughq.com": ['Saxony']})
        self.assertEqual(json["already_subscribed"], {})

        # Make sure both users are subscribed to this stream
        result = self.client.post("/api/v1/get_subscribers", {'email':email,
                                                            'api-key': self.get_api_key(email),
                                                            'stream': 'Saxony'})
        self.assert_json_success(result)
        json = simplejson.loads(result.content)

        self.assertTrue('othello@humbughq.com' in json['subscribers'])
        self.assertTrue('hamlet@humbughq.com' in json['subscribers'])

class GetSubscribersTest(AuthedTestCase):
    fixtures = ['messages.json']

    def setUp(self):
        self.email = "hamlet@humbughq.com"
        self.api_key = self.get_api_key(self.email)
        self.user_profile = self.get_user_profile(self.email)
        self.login(self.email)

    def check_well_formed_result(self, result, stream_name, domain):
        """
        A successful call to get_subscribers returns the list of subscribers in
        the form:

        {"msg": "",
         "result": "success",
         "subscribers": ["hamlet@humbughq.com", "prospero@humbughq.com"]}
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
        self.check_well_formed_result(simplejson.loads(result.content),
                                      stream_name, self.user_profile.realm.domain)

    def test_subscriber(self):
        """
        get_subscribers returns the list of subscribers.
        """
        stream_name = gather_subscriptions(self.user_profile)[0]['name']
        self.make_successful_subscriber_request(stream_name)

    def test_nonsubscriber(self):
        """
        Even a non-subscriber to a public stream can query a stream's membership
        with get_subscribers.
        """
        # Create a stream for which Hamlet is the only subscriber.
        stream_name = "Saxony"
        self.client.post("/json/subscriptions/add",
                         {"subscriptions": simplejson.dumps([stream_name])})
        other_email = "othello@humbughq.com"

        # Fetch the subscriber list as a non-member.
        self.login(other_email)
        self.make_successful_subscriber_request(stream_name)

    def test_subscriber_private_stream(self):
        """
        A subscriber to a private stream can query that stream's membership.
        """
        stream_name = "Saxony"
        self.client.post("/json/subscriptions/add",
                         {"subscriptions": simplejson.dumps([stream_name]),
                          "invite_only": simplejson.dumps(True)})
        self.make_successful_subscriber_request(stream_name)

    def test_nonsubscriber_private_stream(self):
        """
        A non-subscriber to a private stream can't query that stream's membership.
        """
        # Create a private stream for which Hamlet is the only subscriber.
        stream_name = "Saxony"
        self.client.post("/json/subscriptions/add",
                         {"subscriptions": simplejson.dumps([stream_name]),
                          "invite_only": simplejson.dumps(True)})
        other_email = "othello@humbughq.com"

        # Try to fetch the subscriber list as a non-member.
        self.login(other_email)
        result = self.make_subscriber_request(stream_name)
        self.assert_json_error(result,
                               "Unable to retrieve subscribers for invite-only stream")

def bugdown_convert(text):
    return bugdown.convert(text, "humbughq.com")

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

    def test_linkify(self):
        def replaced(payload, url, phrase=''):
            if url[:4] == 'http':
                href = url
            elif '@' in url:
                href = 'mailto:' + url
            else:
                href = 'http://' + url
            return payload % ("<a href=\"%s\" target=\"_blank\" title=\"%s\">%s</a>" % (href, href, url),)

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
         ('with www www.humbughq.com/foo ok?',         "<p>with www %s ok?</p>",            'www.humbughq.com/foo'),
         ('allow questions like foo.com?',             "<p>allow questions like %s?</p>",   'foo.com'),
         ('"is.gd/foo/ "',                             "<p>\"%s \"</p>",                    'is.gd/foo/'),
         ('end of sentence https://t.co.',             "<p>end of sentence %s.</p>",        'https://t.co'),
         ('(Something like http://foo.com/blah_blah)', "<p>(Something like %s)</p>",        'http://foo.com/blah_blah'),
         ('"is.gd/foo/"',                              "<p>\"%s\"</p>",                     'is.gd/foo/'),
         ('end with a quote www.google.com"',          "<p>end with a quote %s\"</p>",      'www.google.com'),
         ('http://www.guardian.co.uk/foo/bar',         "<p>%s</p>",                         'http://www.guardian.co.uk/foo/bar'),
         ('from http://supervisord.org/running.html:', "<p>from %s:</p>",                   'http://supervisord.org/running.html'),
         ('http://raven.io',                           "<p>%s</p>",                         'http://raven.io'),
         ('at https://humbughq.com/api. Check it!',    "<p>at %s. Check it!</p>",           'https://humbughq.com/api'),
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
         ('https://www.dropbox.com/sh/7d0ved3h5kf7dj8/_aD5_ceDFY?lst#f:Humbug-062-subscriptions-page-3rd-ver.fw.png',
            '<p>%s</p>', 'https://www.dropbox.com/sh/7d0ved3h5kf7dj8/_aD5_ceDFY?lst#f:Humbug-062-subscriptions-page-3rd-ver.fw.png'),
         ('http://www.postgresql.org/message-id/14040.1364490185@sss.pgh.pa.us', '<p>%s</p>',
            'http://www.postgresql.org/message-id/14040.1364490185@sss.pgh.pa.us'),

         # XSS sanitization; URL is rendered as plain text
         ('javascript:alert(\'hi\');.com',             "<p>javascript:alert('hi');.com</p>", ''),
         ('javascript:foo.com',                        "<p>javascript:foo.com</p>",          ''),
         ('javascript://foo.com',                      "<p>javascript://foo.com</p>",        ''),
         ('foobarscript://foo.com',                    "<p>foobarscript://foo.com</p>",      ''),
         ('about:blank.com',                           "<p>about:blank.com</p>",             ''),
         ('[foo](javascript:foo.com)',                 "<p>[foo](javascript:foo.com)</p>",   ''),
         ('[foo](javascript://foo.com)',               "<p>[foo](javascript://foo.com)</p>", ''),

         # Other weird URL schemes are also blocked
         ('aim:addbuddy?screenname=foo',               "<p>aim:addbuddy?screenname=foo</p>", ''),
         ('itms://itunes.com/apps/appname',            "<p>itms://itunes.com/apps/appname</p>", ''),
         ('[foo](itms://itunes.com/apps/appname)',     "<p>[foo](itms://itunes.com/apps/appname)</p>", ''),

         # Make sure we HTML-escape the invalid URL on output.
         # ' and " aren't escaped here, because we aren't in attribute context.
         ('javascript:<i>"foo&bar"</i>',
            '<p>javascript:&lt;i&gt;"foo&amp;bar"&lt;/i&gt;</p>', ''),
         ('[foo](javascript:<i>"foo&bar"</i>)',
            '<p>[foo](javascript:&lt;i&gt;"foo&amp;bar"&lt;/i&gt;)</p>', ''),

         # Emails
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
                        'http://technet.microsoft.com/en-us/library/Cc751099.rk20_25_big(l=en-us).mov')]

        for inline_url, reference, url in conversions:
            try:
                match = replaced(reference, url, phrase=inline_url)
            except TypeError:
                match = reference
            converted = bugdown_convert(inline_url)
            self.assertEqual(match, converted)

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
                ('Sent to http_something_real@humbughq.com', '<p>Sent to <a href="mailto:http_something_real@humbughq.com" \
title="mailto:http_something_real@humbughq.com">http_something_real@humbughq.com</a></p>'),
                ('Sent to othello@humbughq.com', '<p>Sent to <a href="mailto:othello@humbughq.com" title="mailto:othello@humbughq.com">\
othello@humbughq.com</a></p>')
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

        # If thre are two images, both should be previewed.
        msg = 'Google logo today: https://www.google.com/images/srpr/logo4w.png\nKinda boringGoogle logo today: https://www.google.com/images/srpr/logo4w.png\nKinda boring'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Google logo today: <a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png">https://www.google.com/images/srpr/logo4w.png</a><br>\nKinda boringGoogle logo today: <a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png">https://www.google.com/images/srpr/logo4w.png</a><br>\nKinda boring</p>\n<div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png"><img src="https://www.google.com/images/srpr/logo4w.png"></a></div><div class="message_inline_image"><a href="https://www.google.com/images/srpr/logo4w.png" target="_blank" title="https://www.google.com/images/srpr/logo4w.png"><img src="https://www.google.com/images/srpr/logo4w.png"></a></div>')


    def test_inline_youtube(self):
        msg = 'Check out the debate: http://www.youtube.com/watch?v=hx1mjT73xYE'
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Check out the debate: <a href="http://www.youtube.com/watch?v=hx1mjT73xYE" target="_blank" title="http://www.youtube.com/watch?v=hx1mjT73xYE">http://www.youtube.com/watch?v=hx1mjT73xYE</a></p>\n<iframe width="250" height="141" src="http://www.youtube.com/embed/hx1mjT73xYE?feature=oembed" frameborder="0" allowfullscreen></iframe>')

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

        # Check every single emoji
        for img in bugdown.emoji_list:
            emoji_text = ":%s:" % img
            test_cases.append((emoji_text, emoji_img(emoji_text)))

        for input, expected in test_cases:
            self.assertEqual(bugdown_convert(input), '<p>%s</p>' % expected)

        # Comprehensive test of a bunch of things together
        msg = 'test :smile: again :poop:\n:) foo:)bar x::y::z :wasted waste: :fakeemojithisshouldnotrender:'
        converted = bugdown_convert(msg)
        self.assertEqual(converted, '<p>test ' + emoji_img(':smile:') + ' again ' + emoji_img(':poop:') + '<br>\n'
                                  + ':) foo:)bar x::y::z :wasted waste: :fakeemojithisshouldnotrender:</p>')


    def test_multiline_strong(self):
        msg = "Welcome to **the jungle**"
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>Welcome to <strong>the jungle</strong></p>')

        msg = """You can check out **any time you'd like
But you can never leave**"""
        converted = bugdown_convert(msg)
        self.assertEqual(converted, "<p>You can check out **any time you'd like<br>\nBut you can never leave**</p>")

    def test_realm_patterns(self):
        msg = "We should fix trac #224 and Trac #115, but not Ztrac #124 or trac #1124Z today."
        converted = bugdown_convert(msg)

        self.assertEqual(converted, '<p>We should fix <a href="https://trac.humbughq.com/ticket/224" target="_blank" title="https://trac.humbughq.com/ticket/224">trac #224</a> and <a href="https://trac.humbughq.com/ticket/115" target="_blank" title="https://trac.humbughq.com/ticket/115">Trac #115</a>, but not Ztrac #124 or trac #1124Z today.</p>')

class UserPresenceTests(AuthedTestCase):
    fixtures = ['messages.json']

    def common_init(self, email):
        self.login(email)
        api_key = self.get_api_key(email)
        return api_key

    def test_get_empty(self):
        email = "hamlet@humbughq.com"
        api_key = self.common_init(email)

        result = self.client.post("/json/get_active_statuses", {'email': email, 'api-key': api_key})

        self.assert_json_success(result)
        json = simplejson.loads(result.content)
        for email, presence in json['presences'].items():
            self.assertEqual(presence, {})

    def test_set_idle(self):
        email = "hamlet@humbughq.com"
        api_key = self.common_init(email)
        client = 'website'

        def test_result(result):
            self.assert_json_success(result)
            json = simplejson.loads(result.content)
            self.assertEqual(json['presences'][email][client]['status'], 'idle')
            self.assertIn('timestamp', json['presences'][email][client])
            self.assertIsInstance(json['presences'][email][client]['timestamp'], int)
            self.assertEqual(json['presences'].keys(), ['hamlet@humbughq.com'])
            return json['presences'][email][client]['timestamp']

        result = self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        test_result(result)

        result = self.client.post("/json/get_active_statuses", {'email': email, 'api-key': api_key})
        timestamp = test_result(result)

        email = "othello@humbughq.com"
        api_key = self.common_init(email)
        self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        result = self.client.post("/json/get_active_statuses", {'email': email, 'api-key': api_key})
        self.assert_json_success(result)
        json = simplejson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences']['hamlet@humbughq.com'][client]['status'], 'idle')
        self.assertEqual(json['presences'].keys(), ['hamlet@humbughq.com', 'othello@humbughq.com'])
        newer_timestamp = json['presences'][email][client]['timestamp']
        self.assertGreaterEqual(newer_timestamp, timestamp)

    def test_set_active(self):
        email = "hamlet@humbughq.com"
        api_key = self.common_init(email)
        client = 'website'

        self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        result = self.client.post("/json/get_active_statuses", {'email': email, 'api-key': api_key})

        self.assert_json_success(result)
        json = simplejson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')

        email = "othello@humbughq.com"
        api_key = self.common_init(email)
        self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        result = self.client.post("/json/get_active_statuses", {'email': email, 'api-key': api_key})
        self.assert_json_success(result)
        json = simplejson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        self.assertEqual(json['presences']['hamlet@humbughq.com'][client]['status'], 'idle')

        self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'active'})
        result = self.client.post("/json/get_active_statuses", {'email': email, 'api-key': api_key})
        self.assert_json_success(result)
        json = simplejson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'active')
        self.assertEqual(json['presences']['hamlet@humbughq.com'][client]['status'], 'idle')

    def test_no_mit(self):
        # MIT never gets a list of users
        email = "espuser@mit.edu"
        api_key = self.common_init(email)
        result = self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        self.assert_json_success(result)
        json = simplejson.loads(result.content)
        self.assertEqual(json['presences'], {})

    def test_same_realm(self):
        email = "espuser@mit.edu"
        api_key = self.common_init(email)
        client = 'website'

        self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        result = self.client.post("/accounts/logout/")

        # Ensure we don't see hamlet@humbughq.com information leakage
        email = "hamlet@humbughq.com"
        api_key = self.common_init(email)

        result = self.client.post("/json/update_active_status", {'email': email, 'api-key': api_key, 'status': 'idle'})
        self.assert_json_success(result)
        json = simplejson.loads(result.content)
        self.assertEqual(json['presences'][email][client]['status'], 'idle')
        # We only want @humbughq.com emails
        for email in json['presences'].keys():
            self.assertEqual(email.split('@')[1], 'humbughq.com')

class UnreadCountTests(AuthedTestCase):
    fixtures = ['messages.json']

    def test_initial_counts(self):
        # All test users have a pointer at -1, so all messages are read
        for user in UserProfile.objects.all():
            for message in UserMessage.objects.filter(user_profile=user):
                self.assertTrue(message.flags.read)

        self.login('hamlet@humbughq.com')
        for msg in self.get_old_messages():
            self.assertEqual(msg['flags'], ['read'])

    def test_new_message(self):
        # Sending a new message results in unread UserMessages being created
        self.login("hamlet@humbughq.com")
        content = "Test message for unset read bit"
        self.client.post("/json/send_message", {"type": "stream",
                                                         "to": "Verona",
                                                         "client": "test suite",
                                                         "content": content,
                                                         "subject": "Test subject"})
        msgs = Message.objects.all().order_by("id")
        last = msgs[len(msgs) - 1]
        self.assertEqual(last.content, "Test message for unset read bit")
        for um in UserMessage.objects.filter(message=last):
            self.assertEqual(um.message.content, content)
            if um.user_profile.email != "hamlet@humbughq.com":
                self.assertFalse(um.flags.read)

    def test_update_flags(self):
        self.login("hamlet@humbughq.com")

        result = self.client.post("/json/update_message_flags", {"messages": simplejson.dumps([1, 2]),
                                                                 "op": "add",
                                                                 "flag": "read"})
        self.assert_json_success(result)

        # Ensure we properly set the flags
        for msg in self.get_old_messages():
            if msg['id'] == 1:
                self.assertEqual(msg['flags'], ['read'])
            elif msg['id'] == 2:
                self.assertEqual(msg['flags'], ['read'])

        result = self.client.post("/json/update_message_flags", {"messages": simplejson.dumps([2]),
                                                                 "op": "remove",
                                                                 "flag": "read"})
        self.assert_json_success(result)

        # Ensure we properly remove just one flag
        for msg in self.get_old_messages():
            if msg['id'] == 1:
                self.assertEqual(msg['flags'], ['read'])
            elif msg['id'] == 2:
                self.assertEqual(msg['flags'], [])

    def test_update_all_flags(self):
        self.login("hamlet@humbughq.com")

        result = self.client.post("/json/update_message_flags", {"messages": simplejson.dumps([1, 2]),
                                                                 "op": "add",
                                                                 "flag": "read"})
        self.assert_json_success(result)

        result = self.client.post("/json/update_message_flags", {"messages": simplejson.dumps([]),
                                                                 "op": "remove",
                                                                 "flag": "read",
                                                                 "all": simplejson.dumps(True)})
        self.assert_json_success(result)

        for msg in self.get_old_messages():
            self.assertEqual(msg['flags'], [])

class StarTests(AuthedTestCase):
    fixtures = ['messages.json']

    def change_star(self, messages, add=True):
        return self.client.post("/json/update_message_flags",
                                {"messages": simplejson.dumps(messages),
                                 "op": "add" if add else "remove",
                                 "flag": "starred"})

    def test_change_star(self):
        """
        You can set a message as starred/un-starred through
        /json/update_message_flags.
        """
        self.login("hamlet@humbughq.com")
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
        test_email = "hamlet@humbughq.com"
        self.login(test_email)
        content = "Test message for star"
        self.send_message(test_email, "Verona", Recipient.STREAM,
                          content=content)

        sent_message = UserMessage.objects.filter(
            user_profile=self.get_user_profile(test_email)
            ).order_by("id").reverse()[0]
        self.assertEqual(sent_message.message.content, content)
        self.assertFalse(sent_message.flags.starred)

class JiraHookTests(AuthedTestCase):
    fixtures = ['messages.json']

    def send_jira_message(self, action):
        email = "hamlet@humbughq.com"
        api_key = self.get_api_key(email)
        url = "/api/v1/external/jira?api_key=%s" % api_key
        return self.send_json_payload(email,
                                      url,
                                      self.fixture_data('jira', action),
                                      stream_name="jira",
                                      content_type="application/json")

    def test_unknown(self):
        email = "hamlet@humbughq.com"
        api_key = self.get_api_key(email)
        url = "/api/v1/external/jira?api_key=%s" % api_key

        result = self.client.post(url, self.fixture_data('jira', 'unknown'),
                                  stream_name="jira",
                                  content_type="application/json")

        self.assert_json_error(result, 'Unknown JIRA event type')

    def test_custom_stream(self):
        email = "hamlet@humbughq.com"
        api_key = self.get_api_key(email)
        action = 'created'
        url = "/api/v1/external/jira?api_key=%s&stream=jira_custom" % api_key
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

    def test_commented(self):
        msg = self.send_jira_message('commented')
        self.assertEqual(msg.subject, "BUG-15: New bug with hook")
        self.assertEqual(msg.content, """Leo Franchi **updated** [BUG-15](http://lfranchi.com:8080/browse/BUG-15):


> Adding a comment. Oh, what a comment it is!""")

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

> Re-opened yeah!""")

    def test_resolved(self):
        msg = self.send_jira_message('resolved')

        self.assertEqual(msg.subject, "BUG-13: Refreshing the page loses the user's current posi...")
        self.assertEqual(msg.content, """Leo Franchi **updated** [BUG-13](http://lfranchi.com:8080/browse/BUG-13):

* Changed status from **Open** to **Resolved**
* Changed assignee from **None** to **Leo Franchi**

> Fixed it, finally!""")

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
    fixtures = ['messages.json']

    def http_auth(self, username, password):
        import base64
        credentials = base64.b64encode('%s:%s' % (username, password))
        auth_string = 'Basic %s' % credentials
        return auth_string

    def send_beanstalk_message(self, action):
        email = "hamlet@humbughq.com"
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
    fixtures = ['messages.json']

    def assert_content(self, msg):
        self.assertEqual(msg.content, """rtomayko [pushed](http://github.com/mojombo/grit/compare/4c8124f...a47fd41) to branch master

* [06f63b4](http://github.com/mojombo/grit/commit/06f63b43050935962f84fe54473a7c5de7977325): stub git call for Grit#heads test f:15 Case#1
* [5057e76](http://github.com/mojombo/grit/commit/5057e76a11abd02e83b7d3d3171c4b68d9c88480): clean up heads test f:2hrs
* [a47fd41](http://github.com/mojombo/grit/commit/a47fd41f3aa4610ea527dcc1669dfdb9c15c5425): add more comments throughout
""")

    def test_spam_branch_is_ignored(self):
        email = "hamlet@humbughq.com"
        api_key = self.get_api_key(email)
        stream = 'commits'
        data = {'email': email,
                'api-key': api_key,
                'branches': 'dev,staging',
                'stream': stream,
                'event': 'push',
                'payload': self.fixture_data('github', 'sample')}
        url = '/api/v1/external/github'

        # We subscribe to the stream in this test, even though
        # it won't get written, to avoid failing for the wrong
        # reason.
        self.subscribe_to_stream(email, stream)

        prior_count = len(Message.objects.filter())

        result = self.client.post(url, data)
        self.assert_json_success(result)

        after_count = len(Message.objects.filter())
        self.assertEqual(prior_count, after_count)


    def test_user_specified_branches(self):
        email = "hamlet@humbughq.com"
        api_key = self.get_api_key(email)
        stream = 'my_commits'
        data = {'email': email,
                'api-key': api_key,
                'stream': stream,
                'branches': 'master,staging',
                'event': 'push',
                'payload': self.fixture_data('github', 'sample')}
        msg = self.send_json_payload(email, "/api/v1/external/github",
                                     data,
                                     stream_name=stream)
        self.assertEqual(msg.subject, "grit")
        self.assert_content(msg)

    def test_user_specified_stream(self):
        # Around May 2013 the github webhook started to specify the stream.
        # Before then, the stream was hard coded to "commits".
        email = "hamlet@humbughq.com"
        api_key = self.get_api_key(email)
        stream = 'my_commits'
        data = {'email': email,
                'api-key': api_key,
                'stream': stream,
                'event': 'push',
                'payload': self.fixture_data('github', 'sample')}
        msg = self.send_json_payload(email, "/api/v1/external/github",
                                     data,
                                     stream_name=stream)
        self.assertEqual(msg.subject, "grit")
        self.assert_content(msg)

    def test_legacy_hook(self):
        email = "hamlet@humbughq.com"
        api_key = self.get_api_key(email)
        data = {'email': email,
                'api-key': api_key,
                'event': 'push',
                'payload': self.fixture_data('github', 'sample')}
        msg = self.send_json_payload(email, "/api/v1/external/github",
                                     data,
                                     stream_name="commits")
        self.assertEqual(msg.subject, "grit")
        self.assert_content(msg)

class PivotalHookTests(AuthedTestCase):
    fixtures = ['messages.json']

    def send_pivotal_message(self, name):
        email = "hamlet@humbughq.com"
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
(unscheduled feature):\n\n> This is my long description\n\n \
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
(unscheduled feature worth 2 story points):\n\n> Some loong description\n\n \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48278289)')

    def test_type_changed(self):
        msg = self.send_pivotal_message('type_changed')
        self.assertEqual(msg.subject, 'My new Feature story')
        self.assertEqual(msg.content, 'Leo Franchi edited "My new Feature story" \
[(view)](https://www.pivotaltracker.com/s/projects/807213/stories/48276573)')

class RateLimitTests(AuthedTestCase):
    fixtures = ['messages.json']

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
        email = "hamlet@humbughq.com"
        api_key = self.get_api_key(email)
        result = self.send_api_message(email, api_key, "some stuff")
        self.assertTrue('X-RateLimit-Remaining' in result)
        self.assertTrue('X-RateLimit-Limit' in result)
        self.assertTrue('X-RateLimit-Reset' in result)

    def test_ratelimit_decrease(self):
        email = "hamlet@humbughq.com"
        api_key = self.get_api_key(email)
        result = self.send_api_message(email, api_key, "some stuff")
        limit = int(result['X-RateLimit-Remaining'])

        result = self.send_api_message(email, api_key, "some stuff 2")
        newlimit = int(result['X-RateLimit-Remaining'])
        self.assertEqual(limit, newlimit + 1)

    def test_hit_ratelimits(self):
        email = "cordelia@humbughq.com"
        api_key = self.get_api_key(email)
        for i in range(10):
            result = self.send_api_message(email, api_key, "some stuff %s" % (i,))

        self.assertEqual(result.status_code, 403)
        json = simplejson.loads(result.content)
        self.assertEqual(json.get("result"), "error")
        self.assertIn("API usage exceeded rate limit, try again in", json.get("msg"))

        # Sleep 5 seconds and succeed again
        import time
        time.sleep(1)
        result = self.send_api_message(email, api_key, "Good message")

        self.assert_json_success(result)

class Runner(DjangoTestSuiteRunner):
    option_list = ()

    def __init__(self, *args, **kwargs):
        DjangoTestSuiteRunner.__init__(self, *args, **kwargs)
