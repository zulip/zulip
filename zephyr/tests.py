from django.contrib.auth.models import User
from django.test import TestCase
from django.utils.timezone import utc
from django.db.models import Q

from zephyr.models import Message, UserProfile, Stream, Recipient, Subscription, \
    filter_by_subscriptions, Realm, do_send_message
from zephyr.views import json_get_updates
from zephyr.decorator import TornadoAsyncException

import datetime
import simplejson
import subprocess
subprocess.call("zephyr/tests/generate-fixtures");
from django.conf import settings
import re

settings.MESSAGE_LOG = "/tmp/test-message-log"
settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'


def find_key_by_email(address):
    from django.core.mail import outbox
    key_regex = re.compile("accounts/do_confirm/([a-f0-9]{40})>")
    for message in reversed(outbox):
        if address in message.to:
            return key_regex.search(message.body).groups()[0]

class AuthedTestCase(TestCase):
    def login(self, username, password):
        return self.client.post('/accounts/login/',
                                {'username':username, 'password':password})

    def register(self, username, password):
        self.client.post('/accounts/home/',
                         {'email': username + '@humbughq.com'})
        return self.client.post('/accounts/register/',
                                {'full_name':username, 'short_name':username,
                                 'key': find_key_by_email(username + '@humbughq.com'),
                                 'username':username, 'password':password,
                                 'domain':'humbughq.com'})

    def get_userprofile(self, email):
        """
        Given an email address, return the UserProfile object for the
        User that has that email.
        """
        # Usernames are unique, even across Realms.
        return UserProfile.objects.get(user__email=email)

    def send_message(self, sender_name, recipient_name, message_type):
        sender = self.get_userprofile(sender_name)
        if message_type == Recipient.PERSONAL:
            recipient = self.get_userprofile(recipient_name)
        else:
            recipient = Stream.objects.get(name=recipient_name, realm=sender.realm)
        recipient = Recipient.objects.get(type_id=recipient.id, type=message_type)
        pub_date = datetime.datetime.utcnow().replace(tzinfo=utc)
        do_send_message(Message(sender=sender, recipient=recipient, subject="test", pub_date=pub_date),
                       synced_from_mit=True)

    def users_subscribed_to_stream(self, stream_name, realm_domain):
        realm = Realm.objects.get(domain=realm_domain)
        stream = Stream.objects.get(name=stream_name, realm=realm)
        recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        subscriptions = Subscription.objects.filter(recipient=recipient)

        return [subscription.userprofile.user for subscription in subscriptions]

    def message_stream(self, user):
        return filter_by_subscriptions(Message.objects.all(), user)

    def assert_json_success(self, result):
        """
        Successful POSTs return a 200 and JSON of the form {"result": "success",
        "msg": ""}.
        """
        self.assertEquals(result.status_code, 200)
        json = simplejson.loads(result.content)
        self.assertEquals(json.get("result"), "success")
        # We have a msg key for consistency with errors, but it typically has an
        # empty value.
        self.assertTrue("msg" in json)

    def assert_json_error(self, result, msg):
        """
        Invalid POSTs return a 400 and JSON of the form {"result": "error",
        "msg": "reason"}.
        """
        self.assertEquals(result.status_code, 400)
        json = simplejson.loads(result.content)
        self.assertEquals(json.get("result"), "error")
        self.assertEquals(json.get("msg"), msg)

class PublicURLTest(TestCase):
    """
    Account creation URLs are accessible even when not logged in. Authenticated
    URLs redirect to a page.
    """
    def fetch(self, urls, expected_status):
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, expected_status,
                             msg="Expected %d, received %d for %s" % (
                    expected_status, response.status_code, url))

    def test_public_urls(self):
        """
        Pages that should return a 200 when not logged in.
        """
        urls = {200: ["/accounts/home/", "/accounts/login/", "/accounts/logout/"],
                302: ["/", "/json/send_message/", "/json/subscriptions/list",
                      "/json/subscriptions/remove", "/json/subscriptions/add"],
                400: ["/accounts/register/"],
                }
        for status_code, url_set in urls.iteritems():
            self.fetch(url_set, status_code)


class LoginTest(AuthedTestCase):
    """
    Logging in, registration, and logging out.
    """
    fixtures = ['messages.json']

    def test_login(self):
        self.login("hamlet@humbughq.com", "hamlet")
        user = User.objects.get(email='hamlet@humbughq.com')
        self.assertEqual(self.client.session['_auth_user_id'], user.id)

    def test_login_bad_password(self):
        self.login("hamlet@humbughq.com", "wrongpassword")
        self.assertIsNone(self.client.session.get('_auth_user_id', None))

    def test_register(self):
        self.register("test", "test")
        user = User.objects.get(email='test@humbughq.com')
        self.assertEqual(self.client.session['_auth_user_id'], user.id)

    def test_logout(self):
        self.login("hamlet@humbughq.com", "hamlet")
        self.client.post('/accounts/logout/')
        self.assertIsNone(self.client.session.get('_auth_user_id', None))


class PersonalMessagesTest(AuthedTestCase):
    fixtures = ['messages.json']

    def test_auto_subbed_to_personals(self):
        """
        Newly created users are auto-subbed to the ability to receive
        personals.
        """
        self.register("test", "test")
        user = User.objects.get(email='test@humbughq.com')
        old_messages = self.message_stream(user)
        self.send_message("test@humbughq.com", "test@humbughq.com", Recipient.PERSONAL)
        new_messages = self.message_stream(user)
        self.assertEqual(len(new_messages) - len(old_messages), 1)

        recipient = Recipient.objects.get(type_id=user.id, type=Recipient.PERSONAL)
        self.assertEqual(new_messages[-1].recipient, recipient)

    def test_personal_to_self(self):
        """
        If you send a personal to yourself, only you see it.
        """
        old_users = list(User.objects.all())
        self.register("test1", "test1")

        old_messages = []
        for user in old_users:
            old_messages.append(len(self.message_stream(user)))

        self.send_message("test1@humbughq.com", "test1@humbughq.com", Recipient.PERSONAL)

        new_messages = []
        for user in old_users:
            new_messages.append(len(self.message_stream(user)))

        self.assertEqual(old_messages, new_messages)

        user = User.objects.get(email="test1@humbughq.com")
        recipient = Recipient.objects.get(type_id=user.id, type=Recipient.PERSONAL)
        self.assertEqual(self.message_stream(user)[-1].recipient, recipient)

    def test_personal(self):
        """
        If you send a personal, only you and the recipient see it.
        """
        self.login("hamlet@humbughq.com", "hamlet")

        old_sender = User.objects.filter(email="hamlet@humbughq.com")
        old_sender_messages = len(self.message_stream(old_sender))

        old_recipient = User.objects.filter(email="othello@humbughq.com")
        old_recipient_messages = len(self.message_stream(old_recipient))

        other_users = User.objects.filter(~Q(email="hamlet@humbughq.com") & ~Q(email="othello@humbughq.com"))
        old_other_messages = []
        for user in other_users:
            old_other_messages.append(len(self.message_stream(user)))

        self.send_message("hamlet@humbughq.com", "othello@humbughq.com", Recipient.PERSONAL)

        # Users outside the conversation don't get the message.
        new_other_messages = []
        for user in other_users:
            new_other_messages.append(len(self.message_stream(user)))

        self.assertEqual(old_other_messages, new_other_messages)

        # The personal message is in the streams of both the sender and receiver.
        self.assertEqual(len(self.message_stream(old_sender)),
                         old_sender_messages + 1)
        self.assertEqual(len(self.message_stream(old_recipient)),
                         old_recipient_messages + 1)

        sender = User.objects.get(email="hamlet@humbughq.com")
        receiver = User.objects.get(email="othello@humbughq.com")
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        self.assertEqual(self.message_stream(sender)[-1].recipient, recipient)
        self.assertEqual(self.message_stream(receiver)[-1].recipient, recipient)

    def test_personal_to_nonexistent_person(self):
        """
        """

class StreamMessagesTest(AuthedTestCase):
    fixtures = ['messages.json']

    def test_message_to_stream(self):
        """
        If you send a message to a stream, everyone subscribed to the stream
        receives the messages.
        """
        subscribers = self.users_subscribed_to_stream("Scotland", "humbughq.com")
        old_subscriber_messages = []
        for subscriber in subscribers:
            old_subscriber_messages.append(len(self.message_stream(subscriber)))

        non_subscribers = [user for user in User.objects.all() if user not in subscribers]
        old_non_subscriber_messages = []
        for non_subscriber in non_subscribers:
            old_non_subscriber_messages.append(len(self.message_stream(non_subscriber)))

        a_subscriber = subscribers[0].username
        a_subscriber_email = subscribers[0].email
        self.login(a_subscriber_email, a_subscriber)
        self.send_message(a_subscriber_email, "Scotland", Recipient.STREAM)

        new_subscriber_messages = []
        for subscriber in subscribers:
           new_subscriber_messages.append(len(self.message_stream(subscriber)))

        new_non_subscriber_messages = []
        for non_subscriber in non_subscribers:
            new_non_subscriber_messages.append(len(self.message_stream(non_subscriber)))

        self.assertEqual(old_non_subscriber_messages, new_non_subscriber_messages)
        self.assertEqual(new_subscriber_messages, [elt + 1 for elt in old_subscriber_messages])

class PointerTest(AuthedTestCase):
    fixtures = ['messages.json']

    def test_update_pointer(self):
        """
        Posting a pointer to /update (in the form {"pointer": pointer}) changes
        the pointer we store for your UserProfile.
        """
        self.login("hamlet@humbughq.com", "hamlet")
        self.assertEquals(self.get_userprofile("hamlet@humbughq.com").pointer, -1)
        result = self.client.post("/json/update_pointer", {"pointer": 1})
        self.assert_json_success(result)
        self.assertEquals(self.get_userprofile("hamlet@humbughq.com").pointer, 1)

    def test_missing_pointer(self):
        """
        Posting json to /json/update_pointer which does not contain a pointer key/value pair
        returns a 400 and error message.
        """
        self.login("hamlet@humbughq.com", "hamlet")
        self.assertEquals(self.get_userprofile("hamlet@humbughq.com").pointer, -1)
        result = self.client.post("/json/update_pointer", {"foo": 1})
        self.assert_json_error(result, "Missing pointer")
        self.assertEquals(self.get_userprofile("hamlet@humbughq.com").pointer, -1)

    def test_invalid_pointer(self):
        """
        Posting json to /json/update_pointer with an invalid pointer returns a 400 and error
        message.
        """
        self.login("hamlet@humbughq.com", "hamlet")
        self.assertEquals(self.get_userprofile("hamlet@humbughq.com").pointer, -1)
        result = self.client.post("/json/update_pointer", {"pointer": "foo"})
        self.assert_json_error(result, "Invalid pointer: must be an integer")
        self.assertEquals(self.get_userprofile("hamlet@humbughq.com").pointer, -1)

    def test_pointer_out_of_range(self):
        """
        Posting json to /json/update_pointer with an out of range (< 0) pointer returns a 400
        and error message.
        """
        self.login("hamlet@humbughq.com", "hamlet")
        self.assertEquals(self.get_userprofile("hamlet@humbughq.com").pointer, -1)
        result = self.client.post("/json/update_pointer", {"pointer": -2})
        self.assert_json_error(result, "Invalid pointer value")
        self.assertEquals(self.get_userprofile("hamlet@humbughq.com").pointer, -1)

class MessagePOSTTest(AuthedTestCase):
    fixtures = ['messages.json']

    def test_message_to_self(self):
        """
        Sending a message to a stream to which you are subscribed is
        successful.
        """
        self.login("hamlet@humbughq.com", "hamlet")
        result = self.client.post("/json/send_message/", {"type": "stream",
                                                          "stream": "Verona",
                                                          "content": "Test message",
                                                          "subject": "Test subject"})
        self.assert_json_success(result)

    def test_message_to_nonexistent_stream(self):
        """
        Sending a message to a nonexistent stream creates the stream and
        is successful.
        """
        self.login("hamlet@humbughq.com", "hamlet")
        self.assertFalse(Stream.objects.filter(name="nonexistent_stream"))
        result = self.client.post("/json/send_message/", {"type": "stream",
                                                          "stream": "nonexistent_stream",
                                                          "content": "Test message",
                                                          "subject": "Test subject"})
        self.assert_json_success(result)
        self.assertTrue(Stream.objects.filter(name="nonexistent_stream"))

    def test_personal_message(self):
        """
        Sending a personal message to a valid username is successful.
        """
        self.login("hamlet@humbughq.com", "hamlet")
        result = self.client.post("/json/send_message/", {"type": "personal",
                                                          "content": "Test message",
                                                          "recipient": "othello@humbughq.com"})
        self.assert_json_success(result)

    def test_personal_message_to_nonexistent_user(self):
        """
        Sending a personal message to an invalid email returns error JSON.
        """
        self.login("hamlet@humbughq.com", "hamlet")
        result = self.client.post("/json/send_message/", {"type": "personal",
                                                          "content": "Test message",
                                                          "recipient": "nonexistent"})
        self.assert_json_error(result, "Invalid email 'nonexistent'")

    def test_invalid_type(self):
        """
        Sending a message of unknown type returns error JSON.
        """
        self.login("hamlet@humbughq.com", "hamlet")
        result = self.client.post("/json/send_message/", {"type": "invalid type",
                                                          "content": "Test message",
                                                          "recipient": "othello@humbughq.com"})
        self.assert_json_error(result, "Invalid message type")

class DummyHandler(object):
    def __init__(self, callback):
        self.callback = callback

    def async_callback(self, _):
        return self.callback

    def finish(self, _):
        return

class POSTRequestMock(object):
    method = "POST"

    def __init__(self, post_data, user, assert_callback):
        self.POST = post_data
        self.user = user
        self._tornado_handler = DummyHandler(assert_callback)

class GetUpdatesTest(AuthedTestCase):
    fixtures = ['messages.json']

    def test_json_get_updates(self):
        """
        json_get_updates returns messages with IDs greater than the
        last_received ID.
        """
        self.login("hamlet@humbughq.com", "hamlet")
        user = User.objects.get(email="hamlet@humbughq.com")

        def callback(messages):
            correct_messages = filter_by_subscriptions(Message.objects.all(), user)
            for message in messages:
                self.assertTrue(message in correct_messages)
                self.assertTrue(message.id > 1)

        request = POSTRequestMock({"last": str(1), "first": str(1)}, user, callback)
        # json_get_updates returns None, which raises an exception in the
        # @asynchronous decorator, which raises a TornadoAsyncException. So this
        # is expected, but should probably change.
        self.assertRaises(TornadoAsyncException, json_get_updates, request)

    def test_beyond_last_message(self):
        """
        If your last_received message is greater than the greatest Message ID, you
        don't get any new messages.
        """
        self.login("hamlet@humbughq.com", "hamlet")
        user = User.objects.get(email="hamlet@humbughq.com")
        last_received = max(message.id for message in Message.objects.all()) + 100
        messages = []

        def callback(data):
            # We can't make asserts in this nested function, so save the data
            # and assert in the parent.
            #
            # TODO: Find out how to make this blocking so assertEquals below
            # runs after us.
            messages.extend(data)

        request = POSTRequestMock({"last": str(last_received), "first": "1"}, user, callback)
        self.assertRaises(TornadoAsyncException, json_get_updates, request)
        self.assertEquals(len(messages), 0)

    def test_missing_last_received(self):
        """
        Calling json_get_updates without a last_received key/value pair
        returns a 400 and error message.
        """
        self.login("hamlet@humbughq.com", "hamlet")
        user = User.objects.get(email="hamlet@humbughq.com")

        def callback(messages):
            correct_messages = filter_by_subscriptions(Message.objects.all(), user)
            for message in messages:
                self.assertTrue(message in correct_messages)
                self.assertTrue(message.id > 1)

        request = POSTRequestMock({}, user, callback)
        self.assert_json_error(json_get_updates(request), "Missing message range")
