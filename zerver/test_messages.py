# -*- coding: utf-8 -*-
from __future__ import absolute_import
from django.db.models import Q
from django.conf import settings
from sqlalchemy.sql import (
    and_, select, column, compiler
)
from django.test import TestCase
from zerver.lib import bugdown
from zerver.decorator import JsonableError
from zerver.lib.test_runner import slow
from zerver.views.messages import (
    exclude_muting_conditions, get_sqlalchemy_connection,
    get_old_messages_backend, ok_to_include_history,
    NarrowBuilder,
)
from zilencer.models import Deployment

from zerver.lib.test_helpers import (
    AuthedTestCase, POSTRequestMock,
    get_user_messages,
    message_ids, message_stream_count,
    most_recent_message,
    queries_captured,
)

from zerver.models import (
    MAX_MESSAGE_LENGTH, MAX_SUBJECT_LENGTH,
    Client, Message, Realm, Recipient, Stream, Subscription, UserMessage, UserProfile,
    get_display_recipient, get_recipient, get_realm, get_stream, get_user_profile_by_email,
)

from zerver.lib.actions import (
    check_message, check_send_message,
    create_stream_if_needed,
    do_add_subscription, do_create_user,
)

import datetime
import time
import re
import ujson
from six.moves import range


def get_sqlalchemy_query_params(query):
    dialect = get_sqlalchemy_connection().dialect
    comp = compiler.SQLCompiler(dialect, query)
    comp.compile()
    return comp.params

def fix_ws(s):
    return re.sub('\s+', ' ', str(s)).strip()

def get_recipient_id_for_stream_name(realm, stream_name):
    stream = get_stream(stream_name, realm)
    return get_recipient(Recipient.STREAM, stream.id).id

def mute_stream(realm, user_profile, stream_name):
    stream = Stream.objects.get(realm=realm, name=stream_name)
    recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
    subscription = Subscription.objects.get(recipient=recipient, user_profile=user_profile)
    subscription.in_home_view = False
    subscription.save()

class NarrowBuilderTest(AuthedTestCase):
    def test_add_term(self):
        realm = get_realm('zulip.com')
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        builder = NarrowBuilder(user_profile, column('id'))
        raw_query = select([column("id")], None, "zerver_message")

        def check(term, where_clause):
            query = builder.add_term(raw_query, term)
            self.assertTrue(where_clause in str(query))

        term = dict(operator='stream', operand='Scotland')
        check(term, 'WHERE recipient_id = :recipient_id_1')

        term = dict(operator='is', operand='private')
        check(term, 'WHERE type = :type_1 OR type = :type_2')

        for operand in ['starred', 'mentioned', 'alerted']:
            term = dict(operator='is', operand=operand)
            check(term, 'WHERE (flags & :flags_1) != :param_1')

        term = dict(operator='topic', operand='lunch')
        check(term, 'WHERE upper(subject) = upper(:param_1)')

        term = dict(operator='sender', operand='othello@zulip.com')
        check(term, 'WHERE sender_id = :param_1')

        term = dict(operator='pm-with', operand='othello@zulip.com')
        check(term, 'WHERE sender_id = :sender_id_1 AND recipient_id = :recipient_id_1 OR sender_id = :sender_id_2 AND recipient_id = :recipient_id_2')

        term = dict(operator='id', operand=555)
        check(term, 'WHERE id = :param_1')

        term = dict(operator='search', operand='"french fries"')
        check(term, 'WHERE (lower(content) LIKE lower(:content_1) OR lower(subject) LIKE lower(:subject_1)) AND (search_tsvector @@ plainto_tsquery(:param_2, :param_3))')

        term = dict(operator='has', operand='attachment')
        check(term, 'WHERE has_attachment')

        term = dict(operator='has', operand='image')
        check(term, 'WHERE has_image')

        term = dict(operator='has', operand='link')
        check(term, 'WHERE has_link')

        mute_stream(realm, user_profile, 'Verona')
        term = dict(operator='in', operand='home')
        check(term, 'WHERE recipient_id NOT IN (:recipient_id_1)')

class IncludeHistoryTest(AuthedTestCase):
    def test_ok_to_include_history(self):
        realm = get_realm('zulip.com')
        create_stream_if_needed(realm, 'public_stream')

        # Negated stream searches should not include history.
        narrow = [
            dict(operator='stream', operand='public_stream', negated=True),
        ]
        self.assertFalse(ok_to_include_history(narrow, realm))

        # Definitely forbid seeing history on private streams.
        narrow = [
            dict(operator='stream', operand='private_stream'),
        ]
        self.assertFalse(ok_to_include_history(narrow, realm))

        # History doesn't apply to PMs.
        narrow = [
            dict(operator='is', operand='private'),
        ]
        self.assertFalse(ok_to_include_history(narrow, realm))

        # If we are looking for something like starred messages, there is
        # no point in searching historical messages.
        narrow = [
            dict(operator='stream', operand='public_stream'),
            dict(operator='is', operand='starred'),
        ]
        self.assertFalse(ok_to_include_history(narrow, realm))

        # simple True case
        narrow = [
            dict(operator='stream', operand='public_stream'),
        ]
        self.assertTrue(ok_to_include_history(narrow, realm))

        narrow = [
            dict(operator='stream', operand='public_stream'),
            dict(operator='topic', operand='whatever'),
            dict(operator='search', operand='needle in haystack'),
        ]
        self.assertTrue(ok_to_include_history(narrow, realm))

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

        sent_message = Message.objects.all().order_by('-id')[0]
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
               "to": ujson.dumps(["sipbcert@mit.edu",
                                  "starnine@mit.edu"])}

        self.login("starnine@mit.edu")
        result1 = self.client.post("/json/messages", msg)
        self.login("sipbcert@mit.edu")
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

        sent_message = Message.objects.all().order_by('-id')[0]
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

        sent_message = Message.objects.all().order_by('-id')[0]
        self.assertEquals(sent_message.subject,
                          "A" * (MAX_SUBJECT_LENGTH - 3) + "...")

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

    def get_query_ids(self):
        hamlet_user = get_user_profile_by_email('hamlet@zulip.com')
        othello_user = get_user_profile_by_email('othello@zulip.com')

        query_ids = {}

        scotland_stream = get_stream('Scotland', hamlet_user.realm)
        query_ids['scotland_recipient'] = get_recipient(Recipient.STREAM, scotland_stream.id).id
        query_ids['hamlet_id'] = hamlet_user.id
        query_ids['othello_id'] = othello_user.id
        query_ids['hamlet_recipient'] = get_recipient(Recipient.PERSONAL, hamlet_user.id).id
        query_ids['othello_recipient'] = get_recipient(Recipient.PERSONAL, othello_user.id).id

        return query_ids

    def test_successful_get_old_messages(self):
        """
        A call to /json/get_old_messages with valid parameters returns a list of
        messages.
        """
        self.login("hamlet@zulip.com")
        result = self.post_with_params(dict())
        self.check_well_formed_messages_response(result)

        # We have to support the legacy tuple style while there are old
        # clients around, which might include third party home-grown bots.
        narrow = [['pm-with', 'othello@zulip.com']]
        result = self.post_with_params(dict(narrow=ujson.dumps(narrow)))
        self.check_well_formed_messages_response(result)

        narrow = [dict(operator='pm-with', operand='othello@zulip.com')]
        result = self.post_with_params(dict(narrow=ujson.dumps(narrow)))
        self.check_well_formed_messages_response(result)

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
        narrow = [dict(operator='pm-with', operand=emails)]
        result = self.post_with_params(dict(narrow=ujson.dumps(narrow)))
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
        realm = get_realm("zulip.com")
        stream, _ = create_stream_if_needed(realm, "Scotland")
        do_add_subscription(get_user_profile_by_email("hamlet@zulip.com"),
                            stream, no_log=True)
        self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM)
        messages = get_user_messages(get_user_profile_by_email("hamlet@zulip.com"))
        stream_messages = [msg for msg in messages if msg.recipient.type == Recipient.STREAM]
        stream_name = get_display_recipient(stream_messages[0].recipient)
        stream_id = stream_messages[0].recipient.id

        narrow = [dict(operator='stream', operand=stream_name)]
        result = self.post_with_params(dict(narrow=ujson.dumps(narrow)))
        self.check_well_formed_messages_response(result)

        for message in result["messages"]:
            self.assertEqual(message["type"], "stream")
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_old_messages_with_narrow_stream_mit_unicode_regex(self):
        """
        A request for old messages for a user in the mit.edu relam with unicode
        stream name should be correctly escaped in the database query.
        """
        self.login("starnine@mit.edu")
        # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        realm = get_realm("mit.edu")
        lambda_stream, _ = create_stream_if_needed(realm, u"\u03bb-stream")
        do_add_subscription(get_user_profile_by_email("starnine@mit.edu"),
                            lambda_stream, no_log=True)

        lambda_stream_d, _ = create_stream_if_needed(realm, u"\u03bb-stream.d")
        do_add_subscription(get_user_profile_by_email("starnine@mit.edu"),
                            lambda_stream_d, no_log=True)

        self.send_message("starnine@mit.edu", u"\u03bb-stream", Recipient.STREAM)
        self.send_message("starnine@mit.edu", u"\u03bb-stream.d", Recipient.STREAM)

        narrow = [dict(operator='stream', operand=u'\u03bb-stream')]
        result = self.post_with_params(dict(num_after=2, narrow=ujson.dumps(narrow)))
        self.check_well_formed_messages_response(result)

        messages = get_user_messages(get_user_profile_by_email("starnine@mit.edu"))
        stream_messages = [msg for msg in messages if msg.recipient.type == Recipient.STREAM]

        self.assertEqual(len(result["messages"]), 2)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            stream_id = stream_messages[i].recipient.id
            self.assertEqual(message["recipient_id"], stream_id)

    def test_get_old_messages_with_narrow_topic_mit_unicode_regex(self):
        """
        A request for old messages for a user in the mit.edu relam with unicode
        topic name should be correctly escaped in the database query.
        """
        self.login("starnine@mit.edu")
        # We need to susbcribe to a stream and then send a message to
        # it to ensure that we actually have a stream message in this
        # narrow view.
        realm = get_realm("mit.edu")
        stream, _ = create_stream_if_needed(realm, "Scotland")
        do_add_subscription(get_user_profile_by_email("starnine@mit.edu"),
                            stream, no_log=True)

        self.send_message("starnine@mit.edu", "Scotland", Recipient.STREAM,
                          subject=u"\u03bb-topic")
        self.send_message("starnine@mit.edu", "Scotland", Recipient.STREAM,
                          subject=u"\u03bb-topic.d")

        narrow = [dict(operator='topic', operand=u'\u03bb-topic')]
        result = self.post_with_params(dict(num_after=2, narrow=ujson.dumps(narrow)))
        self.check_well_formed_messages_response(result)

        messages = get_user_messages(get_user_profile_by_email("starnine@mit.edu"))
        stream_messages = [msg for msg in messages if msg.recipient.type == Recipient.STREAM]
        self.assertEqual(len(result["messages"]), 2)
        for i, message in enumerate(result["messages"]):
            self.assertEqual(message["type"], "stream")
            stream_id = stream_messages[i].recipient.id
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

        narrow = [dict(operator='sender', operand='othello@zulip.com')]
        result = self.post_with_params(dict(narrow=ujson.dumps(narrow)))
        self.check_well_formed_messages_response(result)

        for message in result["messages"]:
            self.assertEqual(message["sender_email"], "othello@zulip.com")

    def test_get_old_messages_with_only_searching_anchor(self):
        """
        Test that specifying an anchor but 0 for num_before and num_after
        returns at most 1 message.
        """
        self.login("cordelia@zulip.com")
        anchor = self.send_message("cordelia@zulip.com", "Scotland", Recipient.STREAM)

        narrow = [dict(operator='sender', operand='cordelia@zulip.com')]
        result = self.post_with_params(dict(narrow=ujson.dumps(narrow),
                                            anchor=anchor, num_before=0,
                                            num_after=0))
        self.check_well_formed_messages_response(result)
        self.assertEqual(len(result['messages']), 1)

        narrow = [dict(operator='is', operand='mentioned')]
        result = self.post_with_params(dict(narrow=ujson.dumps(narrow),
                                            anchor=anchor, num_before=0,
                                            num_after=0))
        self.check_well_formed_messages_response(result)
        self.assertEqual(len(result['messages']), 0)

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
            narrow = [dict(operator=operator, operand='')]
            params = dict(anchor=0, num_before=0, num_after=0, narrow=ujson.dumps(narrow))
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
        bad_stream_content = (0, [], ["x", "y"])
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

    def common_check_get_old_messages_query(self, query_params, expected):
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        request = POSTRequestMock(query_params, user_profile)
        with queries_captured() as queries:
            get_old_messages_backend(request, user_profile)

        for query in queries:
            if "/* get_old_messages */" in query['sql']:
                sql = query['sql'].replace(" /* get_old_messages */", '')
                self.assertEqual(sql, expected)
                return
        self.fail("get_old_messages query not found")

    def test_use_first_unread_anchor(self):
        realm = get_realm('zulip.com')
        create_stream_if_needed(realm, 'devel')
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        user_profile.muted_topics = ujson.dumps([['Scotland', 'golf'], ['devel', 'css'], ['bogus', 'bogus']])
        user_profile.save()

        query_params = dict(
            use_first_unread_anchor='true',
            anchor=0,
            num_before=0,
            num_after=0,
            narrow='[["stream", "Scotland"]]'
        )
        request = POSTRequestMock(query_params, user_profile)

        with queries_captured() as queries:
            get_old_messages_backend(request, user_profile)

        queries = [q for q in queries if q['sql'].startswith("SELECT message_id, flags")]

        ids = {}
        for stream_name in ['Scotland']:
            stream = get_stream(stream_name, realm)
            ids[stream_name] = get_recipient(Recipient.STREAM, stream.id).id

        cond = '''AND NOT (recipient_id = {Scotland} AND upper(subject) = upper('golf'))'''
        cond = cond.format(**ids)
        self.assertTrue(cond in queries[0]['sql'])

    def test_exclude_muting_conditions(self):
        realm = get_realm('zulip.com')
        create_stream_if_needed(realm, 'devel')
        user_profile = get_user_profile_by_email("hamlet@zulip.com")
        user_profile.muted_topics = ujson.dumps([['Scotland', 'golf'], ['devel', 'css'], ['bogus', 'bogus']])
        user_profile.save()

        narrow = [
            dict(operator='stream', operand='Scotland'),
        ]

        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        query = select([column("id").label("message_id")], None, "zerver_message")
        query = query.where(*muting_conditions)
        expected_query = '''
            SELECT id AS message_id
            FROM zerver_message
            WHERE NOT (recipient_id = :recipient_id_1 AND upper(subject) = upper(:upper_1))
            '''
        self.assertEqual(fix_ws(query), fix_ws(expected_query))
        params = get_sqlalchemy_query_params(query)

        self.assertEqual(params['recipient_id_1'], get_recipient_id_for_stream_name(realm, 'Scotland'))
        self.assertEqual(params['upper_1'], 'golf')

        mute_stream(realm, user_profile, 'Verona')
        narrow = []
        muting_conditions = exclude_muting_conditions(user_profile, narrow)
        query = select([column("id")], None, "zerver_message")
        query = query.where(and_(*muting_conditions))

        expected_query = '''
            SELECT id
            FROM zerver_message
            WHERE recipient_id NOT IN (:recipient_id_1)
            AND NOT
               (recipient_id = :recipient_id_2 AND upper(subject) = upper(:upper_1) OR
                recipient_id = :recipient_id_3 AND upper(subject) = upper(:upper_2))'''
        self.assertEqual(fix_ws(query), fix_ws(expected_query))
        params = get_sqlalchemy_query_params(query)
        self.assertEqual(params['recipient_id_1'], get_recipient_id_for_stream_name(realm, 'Verona'))
        self.assertEqual(params['recipient_id_2'], get_recipient_id_for_stream_name(realm, 'Scotland'))
        self.assertEqual(params['upper_1'], 'golf')
        self.assertEqual(params['recipient_id_3'], get_recipient_id_for_stream_name(realm, 'devel'))
        self.assertEqual(params['upper_2'], 'css')

    def test_get_old_messages_queries(self):
        query_ids = self.get_query_ids()

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 11) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10}, sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id <= 100 ORDER BY message_id DESC \n LIMIT 11) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 100, 'num_before': 10, 'num_after': 0}, sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM ((SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id <= 99 ORDER BY message_id DESC \n LIMIT 10) UNION ALL (SELECT message_id, flags \nFROM zerver_usermessage \nWHERE user_profile_id = {hamlet_id} AND message_id >= 100 ORDER BY message_id ASC \n LIMIT 11)) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 100, 'num_before': 10, 'num_after': 10}, sql)

    def test_get_old_messages_with_narrow_queries(self):
        query_ids = self.get_query_ids()

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (sender_id = {othello_id} AND recipient_id = {hamlet_recipient} OR sender_id = {hamlet_id} AND recipient_id = {othello_recipient}) AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["pm-with", "othello@zulip.com"]]'},
                                                 sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (flags & 2) != 0 AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["is", "starred"]]'},
                                                 sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND sender_id = {othello_id} AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["sender", "othello@zulip.com"]]'},
                                                sql)

        sql_template = 'SELECT anon_1.message_id \nFROM (SELECT id AS message_id \nFROM zerver_message \nWHERE recipient_id = {scotland_recipient} AND zerver_message.id >= 0 ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["stream", "Scotland"]]'},
                                                 sql)

        sql_template = "SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND upper(subject) = upper('blah') AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["topic", "blah"]]'},
                                                 sql)

        sql_template = "SELECT anon_1.message_id \nFROM (SELECT id AS message_id \nFROM zerver_message \nWHERE recipient_id = {scotland_recipient} AND upper(subject) = upper('blah') AND zerver_message.id >= 0 ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["stream", "Scotland"], ["topic", "blah"]]'},
                                                 sql)

        # Narrow to pms with yourself
        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND sender_id = {hamlet_id} AND recipient_id = {hamlet_recipient} AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["pm-with", "hamlet@zulip.com"]]'},
                                                sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags \nFROM (SELECT message_id, flags \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND recipient_id = {scotland_recipient} AND (flags & 2) != 0 AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["stream", "Scotland"], ["is", "starred"]]'},
                                                 sql)

    def test_get_old_messages_with_search_queries(self):
        query_ids = self.get_query_ids()

        sql_template = "SELECT anon_1.message_id, anon_1.flags, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.subject_matches \nFROM (SELECT message_id, flags, subject, rendered_content, ts_match_locs_array('zulip.english_us_search', rendered_content, plainto_tsquery('zulip.english_us_search', 'jumping')) AS content_matches, ts_match_locs_array('zulip.english_us_search', escape_html(subject), plainto_tsquery('zulip.english_us_search', 'jumping')) AS subject_matches \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (search_tsvector @@ plainto_tsquery('zulip.english_us_search', 'jumping')) AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["search", "jumping"]]'},
                                                 sql)

        sql_template = "SELECT anon_1.message_id, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.subject_matches \nFROM (SELECT id AS message_id, subject, rendered_content, ts_match_locs_array('zulip.english_us_search', rendered_content, plainto_tsquery('zulip.english_us_search', 'jumping')) AS content_matches, ts_match_locs_array('zulip.english_us_search', escape_html(subject), plainto_tsquery('zulip.english_us_search', 'jumping')) AS subject_matches \nFROM zerver_message \nWHERE recipient_id = {scotland_recipient} AND (search_tsvector @@ plainto_tsquery('zulip.english_us_search', 'jumping')) AND zerver_message.id >= 0 ORDER BY zerver_message.id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC"
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["stream", "Scotland"], ["search", "jumping"]]'},
                                                 sql)

        sql_template = 'SELECT anon_1.message_id, anon_1.flags, anon_1.subject, anon_1.rendered_content, anon_1.content_matches, anon_1.subject_matches \nFROM (SELECT message_id, flags, subject, rendered_content, ts_match_locs_array(\'zulip.english_us_search\', rendered_content, plainto_tsquery(\'zulip.english_us_search\', \'"jumping" quickly\')) AS content_matches, ts_match_locs_array(\'zulip.english_us_search\', escape_html(subject), plainto_tsquery(\'zulip.english_us_search\', \'"jumping" quickly\')) AS subject_matches \nFROM zerver_usermessage JOIN zerver_message ON zerver_usermessage.message_id = zerver_message.id \nWHERE user_profile_id = {hamlet_id} AND (content ILIKE \'%jumping%\' OR subject ILIKE \'%jumping%\') AND (search_tsvector @@ plainto_tsquery(\'zulip.english_us_search\', \'"jumping" quickly\')) AND message_id >= 0 ORDER BY message_id ASC \n LIMIT 10) AS anon_1 ORDER BY message_id ASC'
        sql = sql_template.format(**query_ids)
        self.common_check_get_old_messages_query({'anchor': 0, 'num_before': 0, 'num_after': 10,
                                                  'narrow': '[["search", "\\"jumping\\" quickly"]]'},
                                                 sql)


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

class AttachmentTest(TestCase):
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
                bot=True,
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

