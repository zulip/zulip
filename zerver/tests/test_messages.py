# -*- coding: utf-8 -*-
from __future__ import absolute_import
from django.db.models import Q
from django.conf import settings
from django.test import TestCase
from zerver.lib import bugdown
from zerver.decorator import JsonableError
from zerver.lib.test_runner import slow
from zilencer.models import Deployment

from zerver.lib.test_helpers import (
    AuthedTestCase,
    get_user_messages,
    message_ids, message_stream_count,
    most_recent_message,
    queries_captured,
)

from zerver.models import (
    MAX_MESSAGE_LENGTH, MAX_SUBJECT_LENGTH,
    Client, Message, Realm, Recipient, Stream, UserMessage, UserProfile, Attachment,
    get_realm, get_stream, get_user_profile_by_email,
)

from zerver.lib.actions import (
    check_message, check_send_message,
    create_stream_if_needed,
    do_add_subscription, do_create_user,
)

from zerver.lib.upload import create_attachment

import datetime
import DNS
import mock
import time
import ujson
from six.moves import range

class TestCrossRealmPMs(AuthedTestCase):
    def setUp(self):
        settings.CROSS_REALM_BOT_EMAILS.add('test-og-bot@zulip.com')
        dep = Deployment()
        dep.base_api_url = "https://zulip.com/api/"
        dep.base_site_url = "https://zulip.com/"
        # We need to save the object before we can access
        # the many-to-many relationship 'realms'
        dep.save()
        dep.realms = [get_realm("zulip.com")]
        dep.save()

    def create_user(self, email):
        username, domain = email.split('@')
        self.register(username, 'test', domain=domain)
        return get_user_profile_by_email(email)

    def test_same_realm(self):
        """Users on the same realm can PM each other"""
        r1 = Realm.objects.create(domain='1.example.com')
        deployment = Deployment.objects.filter()[0]
        deployment.realms.add(r1)

        user1_email = 'user1@1.example.com'
        user1 = self.create_user(user1_email)
        user2_email = 'user2@1.example.com'
        user2 = self.create_user(user2_email)

        self.send_message(user1_email, user2_email, Recipient.PERSONAL)

        messages = get_user_messages(user2)
        self.assertEqual(len(messages), 1)
        self.assertEquals(messages[0].sender.pk, user1.pk)

    def test_different_realms(self):
        """Users on the different realms can not PM each other"""
        r1 = Realm.objects.create(domain='1.example.com')
        r2 = Realm.objects.create(domain='2.example.com')
        deployment = Deployment.objects.filter()[0]
        deployment.realms.add(r1)
        deployment.realms.add(r2)

        user1_email = 'user1@1.example.com'
        self.create_user(user1_email)
        user2_email = 'user2@2.example.com'
        self.create_user(user2_email)

        with self.assertRaisesRegexp(JsonableError,
                                     'You can\'t send private messages outside of your organization.'):
            self.send_message(user1_email, user2_email, Recipient.PERSONAL)

    def test_three_different_realms(self):
        """Users on three different realms can not PM each other"""
        r1 = Realm.objects.create(domain='1.example.com')
        r2 = Realm.objects.create(domain='2.example.com')
        r3 = Realm.objects.create(domain='3.example.com')
        deployment = Deployment.objects.filter()[0]
        deployment.realms.add(r1)
        deployment.realms.add(r2)
        deployment.realms.add(r3)

        user1_email = 'user1@1.example.com'
        self.create_user(user1_email)
        user2_email = 'user2@2.example.com'
        self.create_user(user2_email)
        user3_email = 'user3@2.example.com'
        self.create_user(user3_email)

        with self.assertRaisesRegexp(JsonableError,
                                     'You can\'t send private messages outside of your organization.'):
            self.send_message(user1_email, [user2_email, user3_email], Recipient.PERSONAL)

    def test_from_zulip_realm(self):
        """OG Users in the zulip.com realm can PM any realm"""
        r1 = Realm.objects.create(domain='1.example.com')
        deployment = Deployment.objects.filter()[0]
        deployment.realms.add(r1)

        user1_email = 'test-og-bot@zulip.com'
        user1 = self.create_user(user1_email)
        user2_email = 'user2@1.example.com'
        user2 = self.create_user(user2_email)

        self.send_message(user1_email, user2_email, Recipient.PERSONAL)

        messages = get_user_messages(user2)
        self.assertEqual(len(messages), 1)
        self.assertEquals(messages[0].sender.pk, user1.pk)

    def test_to_zulip_realm(self):
        """All users can PM users in the zulip.com realm"""
        r1 = Realm.objects.create(domain='1.example.com')
        deployment = Deployment.objects.filter()[0]
        deployment.realms.add(r1)

        user1_email = 'user1@1.example.com'
        user1 = self.create_user(user1_email)
        user2_email = 'test-og-bot@zulip.com'
        user2 = self.create_user(user2_email)

        self.send_message(user1_email, user2_email, Recipient.PERSONAL)

        messages = get_user_messages(user2)
        self.assertEqual(len(messages), 1)
        self.assertEquals(messages[0].sender.pk, user1.pk)

    def test_zulip_realm_can_not_join_realms(self):
        """Adding a zulip.com user to a PM will not let you cross realms"""
        r1 = Realm.objects.create(domain='1.example.com')
        r2 = Realm.objects.create(domain='2.example.com')
        deployment = Deployment.objects.filter()[0]
        deployment.realms.add(r1)
        deployment.realms.add(r2)

        user1_email = 'user1@1.example.com'
        self.create_user(user1_email)
        user2_email = 'user2@2.example.com'
        self.create_user(user2_email)
        user3_email = 'test-og-bot@zulip.com'
        self.create_user(user3_email)

        with self.assertRaisesRegexp(JsonableError,
                                     'You can\'t send private messages outside of your organization.'):
            self.send_message(user1_email, [user2_email, user3_email],
                              Recipient.PERSONAL)

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

        self.assert_length(queries, 7)

    def test_message_mentions(self):
        user_profile = get_user_profile_by_email("iago@zulip.com")
        self.subscribe_to_stream(user_profile.email, "Denmark")
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM,
                          content="test @**Iago** rules")
        message = most_recent_message(user_profile)
        assert(UserMessage.objects.get(user_profile=user_profile, message=message).flags.mentioned.is_set)

    def test_stream_message_mirroring(self):
        from zerver.lib.actions import do_change_is_admin
        user_profile = get_user_profile_by_email("iago@zulip.com")

        do_change_is_admin(user_profile, True, 'api_super_user')
        result = self.client.post("/api/v1/send_message", {"type": "stream",
                                                           "to": "Verona",
                                                           "sender": "cordelia@zulip.com",
                                                           "client": "test suite",
                                                           "subject": "announcement",
                                                           "content": "Everyone knows Iago rules",
                                                           "forged": "true",
                                                           "email": user_profile.email,
                                                           "api-key": user_profile.api_key})
        self.assert_json_success(result)
        do_change_is_admin(user_profile, False, 'api_super_user')
        result = self.client.post("/api/v1/send_message", {"type": "stream",
                                                           "to": "Verona",
                                                           "sender": "cordelia@zulip.com",
                                                           "client": "test suite",
                                                           "subject": "announcement",
                                                           "content": "Everyone knows Iago rules",
                                                           "forged": "true",
                                                           "email": user_profile.email,
                                                           "api-key": user_profile.api_key})
        self.assert_json_error(result, "User not authorized for this query")

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
        realm = get_realm("zulip.com")
        stream, _ = create_stream_if_needed(realm, non_ascii_stream_name)
        for user_profile in UserProfile.objects.filter(realm=realm):
            do_add_subscription(user_profile, stream, no_log=True)

        self.assert_stream_message(non_ascii_stream_name, subject=u"hümbüǵ",
                                   content=u"hümbüǵ")

class MessageDictTest(AuthedTestCase):
    @slow(1.6, 'builds lots of messages')
    def test_bulk_message_fetching(self):
        realm = get_realm("zulip.com")
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
        self.assert_length(queries, 7)
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

class MessagePOSTTest(AuthedTestCase):

    def test_message_to_self(self):
        """
        Sending a message to a stream to which you are subscribed is
        successful.
        """
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/messages", {"type": "stream",
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

    def test_api_message_with_default_to(self):
        """
        Sending messages without a to field should be sent to the default
        stream for the user_profile.
        """
        email = "hamlet@zulip.com"
        api_key = self.get_api_key(email)
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        user_profile.default_sending_stream = get_stream('Verona', user_profile.realm)
        user_profile.save()
        result = self.client.post("/api/v1/send_message", {"type": "stream",
                                                           "client": "test suite",
                                                           "content": "Test message no to",
                                                           "subject": "Test subject",
                                                           "email": email,
                                                           "api-key": api_key})
        self.assert_json_success(result)

        sent_message = self.get_last_message()
        self.assertEqual(sent_message.content, "Test message no to")

    def test_message_to_nonexistent_stream(self):
        """
        Sending a message to a nonexistent stream fails.
        """
        self.login("hamlet@zulip.com")
        self.assertFalse(Stream.objects.filter(name="nonexistent_stream"))
        result = self.client.post("/json/messages", {"type": "stream",
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
        result = self.client.post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": "othello@zulip.com"})
        self.assert_json_success(result)

    def test_personal_message_to_nonexistent_user(self):
        """
        Sending a personal message to an invalid email returns error JSON.
        """
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": "nonexistent"})
        self.assert_json_error(result, "Invalid email 'nonexistent'")

    def test_invalid_type(self):
        """
        Sending a message of unknown type returns error JSON.
        """
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/messages", {"type": "invalid type",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": "othello@zulip.com"})
        self.assert_json_error(result, "Invalid message type")

    def test_empty_message(self):
        """
        Sending a message that is empty or only whitespace should fail
        """
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/messages", {"type": "private",
                                                     "content": " ",
                                                     "client": "test suite",
                                                     "to": "othello@zulip.com"})
        self.assert_json_error(result, "Message must not be empty")

    def test_mirrored_huddle(self):
        """
        Sending a mirrored huddle message works
        """
        self.login("starnine@mit.edu")
        result = self.client.post("/json/messages", {"type": "private",
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
        result = self.client.post("/json/messages", {"type": "private",
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
               "to": ujson.dumps(["sipbexch@mit.edu",
                                  "starnine@mit.edu"])}

        with mock.patch('DNS.dnslookup', return_value=[['starnine:*:84233:101:Athena Consulting Exchange User,,,:/mit/starnine:/bin/bash']]):
            self.login("starnine@mit.edu")
            result1 = self.client.post("/json/messages", msg)
        with mock.patch('DNS.dnslookup', return_value=[['sipbexch:*:87824:101:Exch Sipb,,,:/mit/sipbexch:/bin/athena/bash']]):
            self.login("sipbexch@mit.edu")
            result2 = self.client.post("/json/messages", msg)
        self.assertEqual(ujson.loads(result1.content)['id'],
                         ujson.loads(result2.content)['id'])

    def test_long_message(self):
        """
        Sending a message longer than the maximum message length succeeds but is
        truncated.
        """
        self.login("hamlet@zulip.com")
        long_message = "A" * (MAX_MESSAGE_LENGTH + 1)
        post_data = {"type": "stream", "to": "Verona", "client": "test suite",
                     "content": long_message, "subject": "Test subject"}
        result = self.client.post("/json/messages", post_data)
        self.assert_json_success(result)

        sent_message = self.get_last_message()
        self.assertEquals(sent_message.content,
                          "A" * (MAX_MESSAGE_LENGTH - 3) + "...")

    def test_long_topic(self):
        """
        Sending a message with a topic longer than the maximum topic length
        succeeds, but the topic is truncated.
        """
        self.login("hamlet@zulip.com")
        long_topic = "A" * (MAX_SUBJECT_LENGTH + 1)
        post_data = {"type": "stream", "to": "Verona", "client": "test suite",
                     "content": "test content", "subject": long_topic}
        result = self.client.post("/json/messages", post_data)
        self.assert_json_success(result)

        sent_message = self.get_last_message()
        self.assertEquals(sent_message.subject,
                          "A" * (MAX_SUBJECT_LENGTH - 3) + "...")

    def test_send_forged_message_as_not_superuser(self):
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "subject": "Test subject",
                                                     "forged": True})
        self.assert_json_error(result, "User not authorized for this query")

    def test_send_message_as_not_superuser_to_different_domain(self):
        self.login("hamlet@zulip.com")
        result = self.client.post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "subject": "Test subject",
                                                     "domain": "mit.edu"})
        self.assert_json_error(result, "User not authorized for this query")

    def test_send_message_as_superuser_to_domain_that_dont_exist(self):
        email = "emailgateway@zulip.com"
        user = get_user_profile_by_email(email)
        password = "test_password"
        user.set_password(password)
        user.is_api_super_user = True
        user.save()
        self.login(email, password)
        result = self.client.post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "subject": "Test subject",
                                                     "domain": "non-existing"})
        user.is_api_super_user = False
        user.save()
        self.assert_json_error(result, "Unknown domain non-existing")

    def test_send_message_when_sender_is_not_set(self):
        self.login("starnine@mit.edu")
        result = self.client.post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": "starnine@mit.edu"})
        self.assert_json_error(result, "Missing sender")

    def test_send_message_as_not_superuser_when_type_is_not_private(self):
        self.login("starnine@mit.edu")
        result = self.client.post("/json/messages", {"type": "not-private",
                                                     "sender": "sipbtest@mit.edu",
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": "starnine@mit.edu"})
        self.assert_json_error(result, "User not authorized for this query")

    @mock.patch("zerver.views.messages.create_mirrored_message_users")
    def test_send_message_create_mirrored_message_user_returns_invalid_input(self, create_mirrored_message_users_mock):
        create_mirrored_message_users_mock.return_value = (False, True)
        self.login("starnine@mit.edu")
        result = self.client.post("/json/messages", {"type": "private",
                                                     "sender": "sipbtest@mit.edu",
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": "starnine@mit.edu"})
        self.assert_json_error(result, "Invalid mirrored message")

    @mock.patch("zerver.views.messages.create_mirrored_message_users")
    def test_send_message_when_client_is_zephyr_mirror_but_domain_is_not_mit_edu(self, create_mirrored_message_users_mock):
        create_mirrored_message_users_mock.return_value = (True, True)
        email = "starnine@mit.edu"
        user = get_user_profile_by_email(email)
        domain = user.realm.domain
        user.realm.domain = 'not_mit.edu'
        user.realm.save()
        self.login("starnine@mit.edu")
        result = self.client.post("/json/messages", {"type": "private",
                                                     "sender": "sipbtest@mit.edu",
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": "starnine@mit.edu"}, name='gownooo')
        self.assert_json_error(result, "Invalid mirrored realm")
        user.realm.domain = domain
        user.realm.save()

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

class StarTests(AuthedTestCase):

    def change_star(self, messages, add=True):
        return self.client.post("/json/messages/flags",
                                {"messages": ujson.dumps(messages),
                                 "op": "add" if add else "remove",
                                 "flag": "starred"})

    def test_change_star(self):
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        self.login("hamlet@zulip.com")
        message_ids = [self.send_message("hamlet@zulip.com", "hamlet@zulip.com",
                                         Recipient.PERSONAL, "test")]

        # Star a message.
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        for msg in self.get_old_messages():
            if msg['id'] in message_ids:
                self.assertEqual(msg['flags'], ['starred'])
            else:
                self.assertEqual(msg['flags'], ['read'])

        result = self.change_star(message_ids, False)
        self.assert_json_success(result)

        # Remove the stars.
        for msg in self.get_old_messages():
            if msg['id'] in message_ids:
                self.assertEqual(msg['flags'], [])

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

class AttachmentTest(AuthedTestCase):
    def test_basics(self):
        self.assertFalse(Message.content_has_attachment('whatever'))
        self.assertFalse(Message.content_has_attachment('yo http://foo.com'))
        self.assertTrue(Message.content_has_attachment('yo\n https://staging.zulip.com/user_uploads/'))
        self.assertTrue(Message.content_has_attachment('yo\n /user_uploads/1/wEAnI-PEmVmCjo15xxNaQbnj/photo-10.jpg foo'))
        self.assertTrue(Message.content_has_attachment('https://humbug-user-uploads.s3.amazonaws.com/sX_TIQx/screen-shot.jpg'))
        self.assertTrue(Message.content_has_attachment('https://humbug-user-uploads-test.s3.amazonaws.com/sX_TIQx/screen-shot.jpg'))

        self.assertFalse(Message.content_has_image('whatever'))
        self.assertFalse(Message.content_has_image('yo http://foo.com'))
        self.assertFalse(Message.content_has_image('yo\n /user_uploads/1/wEAnI-PEmVmCjo15xxNaQbnj/photo-10.pdf foo'))
        for ext in [".bmp", ".gif", ".jpg", "jpeg", ".png", ".webp", ".JPG"]:
            content = 'yo\n /user_uploads/1/wEAnI-PEmVmCjo15xxNaQbnj/photo-10.%s foo' % (ext,)
            self.assertTrue(Message.content_has_image(content))
        self.assertTrue(Message.content_has_image('https://humbug-user-uploads.s3.amazonaws.com/sX_TIQx/screen-shot.jpg'))
        self.assertTrue(Message.content_has_image('https://humbug-user-uploads-test.s3.amazonaws.com/sX_TIQx/screen-shot.jpg'))

        self.assertFalse(Message.content_has_link('whatever'))
        self.assertTrue(Message.content_has_link('yo\n http://foo.com'))
        self.assertTrue(Message.content_has_link('yo\n https://example.com?spam=1&eggs=2'))
        self.assertTrue(Message.content_has_link('yo /user_uploads/1/wEAnI-PEmVmCjo15xxNaQbnj/photo-10.pdf foo'))
        self.assertTrue(Message.content_has_link('https://humbug-user-uploads.s3.amazonaws.com/sX_TIQx/screen-shot.jpg'))
        self.assertTrue(Message.content_has_link('https://humbug-user-uploads-test.s3.amazonaws.com/sX_TIQx/screen-shot.jpg'))

    def test_claim_attachment(self):
        # Create dummy DB entry
        sender_email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(sender_email)
        dummy_files = [
                        ('zulip.txt', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt'),
                        ('temp_file.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py'),
                        ('abc.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py')
                    ]

        for file_name, path_id in dummy_files:
            create_attachment(file_name, path_id, user_profile)

        # Send message referring the attachment
        self.subscribe_to_stream(sender_email, "Denmark")

        body = "Some files here ...[zulip.txt](http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)" +  \
        "http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py.... Some more...." + \
        "http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py"

        self.send_message(sender_email, "Denmark", Recipient.STREAM, body, "test")

        for file_name, path_id in dummy_files:
            attachment = Attachment.objects.get(path_id=path_id)
            self.assertTrue(attachment.is_claimed())

class CheckMessageTest(AuthedTestCase):
    def test_basic_check_message_call(self):
        sender = get_user_profile_by_email('othello@zulip.com')
        client, _ = Client.objects.get_or_create(name="test suite")
        stream_name = 'integration'
        stream, _ = create_stream_if_needed(get_realm("zulip.com"), stream_name)
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
                bot_type=UserProfile.DEFAULT_BOT,
                bot_owner=parent
        )
        bot.last_reminder = None

        sender = bot
        client, _ = Client.objects.get_or_create(name="test suite")
        stream_name = 'integration'
        stream, _ = create_stream_if_needed(get_realm("zulip.com"), stream_name)
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

