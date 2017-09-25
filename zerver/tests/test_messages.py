# -*- coding: utf-8 -*-
from __future__ import absolute_import
from django.db.models import Q, Max
from django.conf import settings
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.utils.timezone import now as timezone_now
from zerver.lib import bugdown
from zerver.decorator import JsonableError
from zerver.lib.test_runner import slow
from zerver.lib.cache import get_stream_cache_key, cache_delete
from zerver.lib.str_utils import force_text
from zilencer.models import Deployment

from zerver.lib.addressee import Addressee

from zerver.lib.actions import (
    do_send_messages,
    get_userids_for_missed_messages,
    internal_send_private_message,
)

from zerver.lib.message import (
    MessageDict,
    message_to_dict,
)

from zerver.lib.test_helpers import (
    get_user_messages,
    make_client,
    message_stream_count,
    most_recent_message,
    most_recent_usermessage,
    queries_captured,
)

from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.lib.soft_deactivation import add_missing_messages, do_soft_deactivate_users, \
    maybe_catch_up_soft_deactivated_user

from zerver.models import (
    MAX_MESSAGE_LENGTH, MAX_SUBJECT_LENGTH,
    Message, Realm, Recipient, Stream, UserMessage, UserProfile, Attachment,
    RealmAuditLog, RealmDomain, get_realm, UserPresence, Subscription,
    get_stream, get_recipient, get_system_bot, get_user, Reaction,
    sew_messages_and_reactions, flush_per_request_caches
)

from zerver.lib.actions import (
    check_message,
    check_send_message,
    do_deactivate_user,
    do_set_realm_property,
    extract_recipients,
    do_create_user,
    get_client,
    do_add_alert_words,
)

from zerver.lib.upload import create_attachment

from zerver.views.messages import create_mirrored_message_users

import datetime
import DNS
import mock
import time
import ujson
from six.moves import range
from typing import Any, Dict, List, Optional, Text

from collections import namedtuple

class TopicHistoryTest(ZulipTestCase):
    def test_topics_history(self):
        # type: () -> None
        # verified: int(UserMessage.flags.read) == 1
        user_profile = self.example_user('iago')
        email = user_profile.email
        stream_name = 'Verona'
        self.login(email)

        stream = get_stream(stream_name, user_profile.realm)
        recipient = get_recipient(Recipient.STREAM, stream.id)

        def create_test_message(topic):
            # type: (str) -> int

            hamlet = self.example_user('hamlet')
            message = Message.objects.create(
                sender=hamlet,
                recipient=recipient,
                subject=topic,
                content='whatever',
                pub_date=timezone_now(),
                sending_client=get_client('whatever'),
            )

            UserMessage.objects.create(
                user_profile=user_profile,
                message=message,
                flags=0,
            )

            return message.id

        # our most recent topics are topic0, topic1, topic2

        # Create old messages with strange spellings.
        create_test_message('topic2')
        create_test_message('toPIc1')
        create_test_message('toPIc0')
        create_test_message('topic2')
        create_test_message('topic2')
        create_test_message('Topic2')

        # Create new messages
        topic2_msg_id = create_test_message('topic2')
        create_test_message('topic1')
        create_test_message('topic1')
        topic1_msg_id = create_test_message('topic1')
        topic0_msg_id = create_test_message('topic0')

        endpoint = '/json/users/me/%d/topics' % (stream.id,)
        result = self.client_get(endpoint, dict())
        self.assert_json_success(result)
        history = result.json()['topics']

        # We only look at the most recent three topics, because
        # the prior fixture data may be unreliable.
        history = history[:3]

        self.assertEqual([topic['name'] for topic in history], [
            'topic0',
            'topic1',
            'topic2',
        ])

        self.assertEqual([topic['max_id'] for topic in history], [
            topic0_msg_id,
            topic1_msg_id,
            topic2_msg_id,
        ])

    def test_bad_stream_id(self):
        # type: () -> None
        email = self.example_email("iago")
        self.login(email)

        # non-sensible stream id
        endpoint = '/json/users/me/9999999999/topics'
        result = self.client_get(endpoint, dict())
        self.assert_json_error(result, 'Invalid stream id')

        # out of realm
        bad_stream = self.make_stream(
            'mit_stream',
            realm=get_realm('zephyr')
        )
        endpoint = '/json/users/me/%s/topics' % (bad_stream.id,)
        result = self.client_get(endpoint, dict())
        self.assert_json_error(result, 'Invalid stream id')

        # private stream to which I am not subscribed
        private_stream = self.make_stream(
            'private_stream',
            invite_only=True
        )
        endpoint = '/json/users/me/%s/topics' % (private_stream.id,)
        result = self.client_get(endpoint, dict())
        self.assert_json_error(result, 'Invalid stream id')


class TestCrossRealmPMs(ZulipTestCase):
    def make_realm(self, domain):
        # type: (Text) -> Realm
        realm = Realm.objects.create(string_id=domain, invite_required=False)
        RealmDomain.objects.create(realm=realm, domain=domain)
        return realm

    def setUp(self):
        # type: () -> None
        dep = Deployment()
        dep.base_api_url = "https://zulip.com/api/"
        dep.base_site_url = "https://zulip.com/"
        # We need to save the object before we can access
        # the many-to-many relationship 'realms'
        dep.save()
        dep.realms = [get_realm("zulip")]
        dep.save()

    def create_user(self, email):
        # type: (Text) -> UserProfile
        subdomain = email.split("@")[1]
        self.register(email, 'test', subdomain=subdomain)
        return get_user(email, get_realm(subdomain))

    @override_settings(CROSS_REALM_BOT_EMAILS=['feedback@zulip.com',
                                               'support@3.example.com'])
    def test_realm_scenarios(self):
        # type: () -> None
        r1 = self.make_realm('1.example.com')
        r2 = self.make_realm('2.example.com')
        r3 = self.make_realm('3.example.com')
        deployment = Deployment.objects.filter()[0]
        deployment.realms.add(r1)
        deployment.realms.add(r2)
        deployment.realms.add(r3)

        def assert_message_received(to_user, from_user):
            # type: (UserProfile, UserProfile) -> None
            messages = get_user_messages(to_user)
            self.assertEqual(messages[-1].sender.pk, from_user.pk)

        def assert_invalid_email():
            # type: () -> Any
            return self.assertRaisesRegex(
                JsonableError,
                'Invalid email ')

        user1_email = 'user1@1.example.com'
        user1a_email = 'user1a@1.example.com'
        user2_email = 'user2@2.example.com'
        user3_email = 'user3@3.example.com'
        feedback_email = 'feedback@zulip.com'
        support_email = 'support@3.example.com'  # note: not zulip.com

        user1 = self.create_user(user1_email)
        user1a = self.create_user(user1a_email)
        user2 = self.create_user(user2_email)
        self.create_user(user3_email)
        feedback_bot = get_system_bot(feedback_email)
        support_bot = self.create_user(support_email)

        # Users can PM themselves
        self.send_message(user1_email, user1_email, Recipient.PERSONAL)
        assert_message_received(user1, user1)

        # Users on the same realm can PM each other
        self.send_message(user1_email, user1a_email, Recipient.PERSONAL)
        assert_message_received(user1a, user1)

        # Cross-realm bots in the zulip.com realm can PM any realm
        # (They need lower level APIs to do this.)
        internal_send_private_message(
            realm=r2,
            sender=get_system_bot(feedback_email),
            recipient_user=get_user(user2_email, r2),
            content='bla',
        )
        assert_message_received(user2, feedback_bot)

        # All users can PM cross-realm bots in the zulip.com realm
        self.send_message(user1_email, feedback_email, Recipient.PERSONAL)
        assert_message_received(feedback_bot, user1)

        # Users can PM cross-realm bots on non-zulip realms.
        # (The support bot represents some theoretical bot that we may
        # create in the future that does not have zulip.com as its realm.)
        self.send_message(user1_email, [support_email], Recipient.PERSONAL)
        assert_message_received(support_bot, user1)

        # Allow sending PMs to two different cross-realm bots simultaneously.
        # (We don't particularly need this feature, but since users can
        # already individually send PMs to cross-realm bots, we shouldn't
        # prevent them from sending multiple bots at once.  We may revisit
        # this if it's a nuisance for huddles.)
        self.send_message(user1_email, [feedback_email, support_email],
                          Recipient.PERSONAL)
        assert_message_received(feedback_bot, user1)
        assert_message_received(support_bot, user1)

        # Prevent old loophole where I could send PMs to other users as long
        # as I copied a cross-realm bot from the same realm.
        with assert_invalid_email():
            self.send_message(user1_email, [user3_email, support_email], Recipient.PERSONAL)

        # Users on three different realms can't PM each other,
        # even if one of the users is a cross-realm bot.
        with assert_invalid_email():
            self.send_message(user1_email, [user2_email, feedback_email],
                              Recipient.PERSONAL)

        with assert_invalid_email():
            self.send_message(feedback_email, [user1_email, user2_email],
                              Recipient.PERSONAL)

        # Users on the different realms can not PM each other
        with assert_invalid_email():
            self.send_message(user1_email, user2_email, Recipient.PERSONAL)

        # Users on non-zulip realms can't PM "ordinary" Zulip users
        with assert_invalid_email():
            self.send_message(user1_email, "hamlet@zulip.com", Recipient.PERSONAL)

        # Users on three different realms can not PM each other
        with assert_invalid_email():
            self.send_message(user1_email, [user2_email, user3_email], Recipient.PERSONAL)

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

class PersonalMessagesTest(ZulipTestCase):

    def test_auto_subbed_to_personals(self):
        # type: () -> None
        """
        Newly created users are auto-subbed to the ability to receive
        personals.
        """
        test_email = self.nonreg_email('test')
        self.register(test_email, "test")
        user_profile = self.nonreg_user('test')
        old_messages_count = message_stream_count(user_profile)
        self.send_message(test_email, test_email, Recipient.PERSONAL)
        new_messages_count = message_stream_count(user_profile)
        self.assertEqual(new_messages_count, old_messages_count + 1)

        recipient = Recipient.objects.get(type_id=user_profile.id,
                                          type=Recipient.PERSONAL)
        message = most_recent_message(user_profile)
        self.assertEqual(message.recipient, recipient)

        with mock.patch('zerver.models.get_display_recipient', return_value='recip'):
            self.assertEqual(str(message),
                             u'<Message: recip /  / '
                             '<UserProfile: test@zulip.com <Realm: zulip 1>>>')

            user_message = most_recent_usermessage(user_profile)
            self.assertEqual(str(user_message),
                             u'<UserMessage: recip / test@zulip.com ([])>'
                             )

    @slow("checks several profiles")
    def test_personal_to_self(self):
        # type: () -> None
        """
        If you send a personal to yourself, only you see it.
        """
        old_user_profiles = list(UserProfile.objects.all())
        test_email = self.nonreg_email('test1')
        self.register(test_email, "test1")

        old_messages = []
        for user_profile in old_user_profiles:
            old_messages.append(message_stream_count(user_profile))

        self.send_message(test_email, test_email, Recipient.PERSONAL)

        new_messages = []
        for user_profile in old_user_profiles:
            new_messages.append(message_stream_count(user_profile))

        self.assertEqual(old_messages, new_messages)

        user_profile = self.nonreg_user('test1')
        recipient = Recipient.objects.get(type_id=user_profile.id, type=Recipient.PERSONAL)
        self.assertEqual(most_recent_message(user_profile).recipient, recipient)

    def assert_personal(self, sender_email, receiver_email, content="test content"):
        # type: (Text, Text, Text) -> None
        """
        Send a private message from `sender_email` to `receiver_email` and check
        that only those two parties actually received the message.
        """
        realm = get_realm('zulip')  # Assume realm is always 'zulip'
        sender = get_user(sender_email, realm)
        receiver = get_user(receiver_email, realm)

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

    @slow("assert_personal checks several profiles")
    def test_personal(self):
        # type: () -> None
        """
        If you send a personal, only you and the recipient see it.
        """
        self.login(self.example_email("hamlet"))
        self.assert_personal(self.example_email("hamlet"), self.example_email("othello"))

    @slow("assert_personal checks several profiles")
    def test_non_ascii_personal(self):
        # type: () -> None
        """
        Sending a PM containing non-ASCII characters succeeds.
        """
        self.login(self.example_email("hamlet"))
        self.assert_personal(self.example_email("hamlet"), self.example_email("othello"), u"hümbüǵ")

class StreamMessagesTest(ZulipTestCase):

    def assert_stream_message(self, stream_name, subject="test subject",
                              content="test content"):
        # type: (Text, Text, Text) -> None
        """
        Check that messages sent to a stream reach all subscribers to that stream.
        """
        realm = get_realm('zulip')
        subscribers = self.users_subscribed_to_stream(stream_name, realm)

        # Outgoing webhook bots don't store UserMessage rows; they will be processed later.
        subscribers = [subscriber for subscriber in subscribers
                       if subscriber.bot_type != UserProfile.OUTGOING_WEBHOOK_BOT]

        old_subscriber_messages = []
        for subscriber in subscribers:
            old_subscriber_messages.append(message_stream_count(subscriber))

        non_subscribers = [user_profile for user_profile in UserProfile.objects.all()
                           if user_profile not in subscribers]
        old_non_subscriber_messages = []
        for non_subscriber in non_subscribers:
            old_non_subscriber_messages.append(message_stream_count(non_subscriber))

        non_bot_subscribers = [user_profile for user_profile in subscribers
                               if not user_profile.is_bot]
        a_subscriber_email = non_bot_subscribers[0].email
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

    def test_performance(self):
        # type: () -> None
        '''
        This test is part of the automated test suite, but
        it is more intended as an aid to measuring the
        performance of do_send_messages() with consistent
        data setup across different commits.  You can modify
        the values below and run just this test, and then
        comment out the print statement toward the bottom.
        '''
        num_messages = 2
        num_extra_users = 10

        sender = self.example_user('cordelia')
        realm = sender.realm
        message_content = 'whatever'
        stream = get_stream('Denmark', realm)
        subject = 'lunch'
        recipient = get_recipient(Recipient.STREAM, stream.id)
        sending_client = make_client(name="test suite")

        for i in range(num_extra_users):
            # Make every other user be idle.
            long_term_idle = i % 2 > 0

            email = 'foo%d@example.com' % (i,)
            user = UserProfile.objects.create(
                realm=realm,
                email=email,
                pointer=0,
                long_term_idle=long_term_idle,
            )
            Subscription.objects.create(
                user_profile=user,
                recipient=recipient
            )

        def send_test_message():
            # type: () -> None
            message = Message(
                sender=sender,
                recipient=recipient,
                subject=subject,
                content=message_content,
                pub_date=timezone_now(),
                sending_client=sending_client,
            )
            do_send_messages([dict(message=message)])

        before_um_count = UserMessage.objects.count()

        t = time.time()
        for i in range(num_messages):
            send_test_message()

        delay = time.time() - t
        assert(delay)  # quiet down lint
        # print(delay)

        after_um_count = UserMessage.objects.count()
        ums_created = after_um_count - before_um_count

        num_active_users = num_extra_users / 2
        self.assertTrue(ums_created > (num_active_users * num_messages))

    def test_not_too_many_queries(self):
        # type: () -> None
        recipient_list  = [self.example_user("hamlet"), self.example_user("iago"),
                           self.example_user("cordelia"), self.example_user("othello")]
        for user_profile in recipient_list:
            self.subscribe(user_profile, "Denmark")

        sender = self.example_user('hamlet')
        message_type_name = "stream"
        sending_client = make_client(name="test suite")
        stream = 'Denmark'
        subject = 'foo'
        content = 'whatever'
        realm = sender.realm

        def send_message():
            # type: () -> None
            check_send_message(sender, sending_client, message_type_name, [stream],
                               subject, content, forwarder_user_profile=sender, realm=realm)

        # To get accurate count of the queries, we should make sure that
        # caches don't come into play. If we count queries while caches are
        # filled, we will get a lower count. Caches are not supposed to be
        # persistent, so our test can also fail if cache is invalidated
        # during the course of the unit test.
        flush_per_request_caches()
        cache_delete(get_stream_cache_key(stream, realm.id))
        with queries_captured() as queries:
            send_message()

        self.assert_length(queries, 12)

    def test_stream_message_dict(self):
        # type: () -> None
        user_profile = self.example_user('iago')
        self.subscribe(user_profile, "Denmark")
        self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM,
                          content="whatever", subject="my topic")
        message = most_recent_message(user_profile)
        row = Message.get_raw_db_rows([message.id])[0]
        dct = MessageDict.build_dict_from_raw_db_row(row, apply_markdown=True)
        self.assertEqual(dct['display_recipient'], 'Denmark')

        stream = get_stream('Denmark', user_profile.realm)
        self.assertEqual(dct['stream_id'], stream.id)

    def test_stream_message_unicode(self):
        # type: () -> None
        user_profile = self.example_user('iago')
        self.subscribe(user_profile, "Denmark")
        self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM,
                          content="whatever", subject="my topic")
        message = most_recent_message(user_profile)
        self.assertEqual(str(message),
                         u'<Message: Denmark / my topic / '
                         '<UserProfile: hamlet@zulip.com <Realm: zulip 1>>>')

    def test_message_mentions(self):
        # type: () -> None
        user_profile = self.example_user('iago')
        self.subscribe(user_profile, "Denmark")
        self.send_message(self.example_email("hamlet"), "Denmark", Recipient.STREAM,
                          content="test @**Iago** rules")
        message = most_recent_message(user_profile)
        assert(UserMessage.objects.get(user_profile=user_profile, message=message).flags.mentioned.is_set)

    def test_stream_message_mirroring(self):
        # type: () -> None
        from zerver.lib.actions import do_change_is_admin
        user_profile = self.example_user('iago')
        email = user_profile.email

        do_change_is_admin(user_profile, True, 'api_super_user')
        result = self.client_post("/api/v1/messages", {"type": "stream",
                                                       "to": "Verona",
                                                       "sender": self.example_email("cordelia"),
                                                       "client": "test suite",
                                                       "subject": "announcement",
                                                       "content": "Everyone knows Iago rules",
                                                       "forged": "true"},
                                  **self.api_auth(email))
        self.assert_json_success(result)
        do_change_is_admin(user_profile, False, 'api_super_user')
        result = self.client_post("/api/v1/messages", {"type": "stream",
                                                       "to": "Verona",
                                                       "sender": self.example_email("cordelia"),
                                                       "client": "test suite",
                                                       "subject": "announcement",
                                                       "content": "Everyone knows Iago rules",
                                                       "forged": "true"},
                                  **self.api_auth(email))
        self.assert_json_error(result, "User not authorized for this query")

    @slow('checks all users')
    def test_message_to_stream(self):
        # type: () -> None
        """
        If you send a message to a stream, everyone subscribed to the stream
        receives the messages.
        """
        self.assert_stream_message("Scotland")

    @slow('checks all users')
    def test_non_ascii_stream_message(self):
        # type: () -> None
        """
        Sending a stream message containing non-ASCII characters in the stream
        name, subject, or message body succeeds.
        """
        self.login(self.example_email("hamlet"))

        # Subscribe everyone to a stream with non-ASCII characters.
        non_ascii_stream_name = u"hümbüǵ"
        realm = get_realm("zulip")
        stream = self.make_stream(non_ascii_stream_name)
        for user_profile in UserProfile.objects.filter(realm=realm):
            self.subscribe(user_profile, stream.name)

        self.assert_stream_message(non_ascii_stream_name, subject=u"hümbüǵ",
                                   content=u"hümbüǵ")

class MessageDictTest(ZulipTestCase):
    @slow('builds lots of messages')
    def test_bulk_message_fetching(self):
        # type: () -> None
        sender = self.example_user('othello')
        receiver = self.example_user('hamlet')
        pm_recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        stream_name = u'Çiğdem'
        stream = self.make_stream(stream_name)
        stream_recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        sending_client = make_client(name="test suite")

        ids = []
        for i in range(300):
            for recipient in [pm_recipient, stream_recipient]:
                message = Message(
                    sender=sender,
                    recipient=recipient,
                    subject='whatever',
                    content='whatever %d' % i,
                    pub_date=timezone_now(),
                    sending_client=sending_client,
                    last_edit_time=timezone_now(),
                    edit_history='[]'
                )
                message.save()
                ids.append(message.id)

                Reaction.objects.create(user_profile=sender, message=message,
                                        emoji_name='simple_smile')

        num_ids = len(ids)
        self.assertTrue(num_ids >= 600)

        flush_per_request_caches()
        t = time.time()
        with queries_captured() as queries:
            rows = list(Message.get_raw_db_rows(ids))

            for row in rows:
                MessageDict.build_dict_from_raw_db_row(row, False)

        delay = time.time() - t
        # Make sure we don't take longer than 1.5ms per message to
        # extract messages.  Note that we increased this from 1ms to
        # 1.5ms to handle tests running in parallel being a bit
        # slower.
        error_msg = "Number of ids: {}. Time delay: {}".format(num_ids, delay)
        self.assertTrue(delay < 0.0015 * num_ids, error_msg)
        self.assert_length(queries, 5)
        self.assertEqual(len(rows), num_ids)

    def test_applying_markdown(self):
        # type: () -> None
        sender = self.example_user('othello')
        receiver = self.example_user('hamlet')
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        sending_client = make_client(name="test suite")
        message = Message(
            sender=sender,
            recipient=recipient,
            subject='whatever',
            content='hello **world**',
            pub_date=timezone_now(),
            sending_client=sending_client,
            last_edit_time=timezone_now(),
            edit_history='[]'
        )
        message.save()

        # An important part of this test is to get the message through this exact code path,
        # because there is an ugly hack we need to cover.  So don't just say "row = message".
        row = Message.get_raw_db_rows([message.id])[0]
        dct = MessageDict.build_dict_from_raw_db_row(row, apply_markdown=True)
        expected_content = '<p>hello <strong>world</strong></p>'
        self.assertEqual(dct['content'], expected_content)
        message = Message.objects.get(id=message.id)
        self.assertEqual(message.rendered_content, expected_content)
        self.assertEqual(message.rendered_content_version, bugdown.version)

    @mock.patch("zerver.lib.message.bugdown.convert")
    def test_applying_markdown_invalid_format(self, convert_mock):
        # type: (Any) -> None
        # pretend the converter returned an invalid message without raising an exception
        convert_mock.return_value = None
        sender = self.example_user('othello')
        receiver = self.example_user('hamlet')
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        sending_client = make_client(name="test suite")
        message = Message(
            sender=sender,
            recipient=recipient,
            subject='whatever',
            content='hello **world**',
            pub_date=timezone_now(),
            sending_client=sending_client,
            last_edit_time=timezone_now(),
            edit_history='[]'
        )
        message.save()

        # An important part of this test is to get the message through this exact code path,
        # because there is an ugly hack we need to cover.  So don't just say "row = message".
        row = Message.get_raw_db_rows([message.id])[0]
        dct = MessageDict.build_dict_from_raw_db_row(row, apply_markdown=True)
        error_content = '<p>[Zulip note: Sorry, we could not understand the formatting of your message]</p>'
        self.assertEqual(dct['content'], error_content)

    def test_reaction(self):
        # type: () -> None
        sender = self.example_user('othello')
        receiver = self.example_user('hamlet')
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        sending_client = make_client(name="test suite")
        message = Message(
            sender=sender,
            recipient=recipient,
            subject='whatever',
            content='hello **world**',
            pub_date=timezone_now(),
            sending_client=sending_client,
            last_edit_time=timezone_now(),
            edit_history='[]'
        )
        message.save()

        reaction = Reaction.objects.create(
            message=message, user_profile=sender,
            emoji_name='simple_smile')
        row = Message.get_raw_db_rows([message.id])[0]
        msg_dict = MessageDict.build_dict_from_raw_db_row(
            row, apply_markdown=True)
        self.assertEqual(msg_dict['reactions'][0]['emoji_name'],
                         reaction.emoji_name)
        self.assertEqual(msg_dict['reactions'][0]['user']['id'],
                         sender.id)
        self.assertEqual(msg_dict['reactions'][0]['user']['email'],
                         sender.email)
        self.assertEqual(msg_dict['reactions'][0]['user']['full_name'],
                         sender.full_name)


class SewMessageAndReactionTest(ZulipTestCase):
    def test_sew_messages_and_reaction(self):
        # type: () -> None
        sender = self.example_user('othello')
        receiver = self.example_user('hamlet')
        pm_recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        stream_name = u'Çiğdem'
        stream = self.make_stream(stream_name)
        stream_recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        sending_client = make_client(name="test suite")

        needed_ids = []
        for i in range(5):
            for recipient in [pm_recipient, stream_recipient]:
                message = Message(
                    sender=sender,
                    recipient=recipient,
                    subject='whatever',
                    content='whatever %d' % i,
                    pub_date=timezone_now(),
                    sending_client=sending_client,
                    last_edit_time=timezone_now(),
                    edit_history='[]'
                )
                message.save()
                needed_ids.append(message.id)
                reaction = Reaction(user_profile=sender, message=message,
                                    emoji_name='simple_smile')
                reaction.save()

        messages = Message.objects.filter(id__in=needed_ids).values(
            *['id', 'content'])
        reactions = Reaction.get_raw_db_rows(needed_ids)
        tied_data = sew_messages_and_reactions(messages, reactions)
        for data in tied_data:
            self.assertEqual(len(data['reactions']), 1)
            self.assertEqual(data['reactions'][0]['emoji_name'],
                             'simple_smile')
            self.assertTrue(data['id'])
            self.assertTrue(data['content'])


class MessagePOSTTest(ZulipTestCase):

    def test_message_to_self(self):
        # type: () -> None
        """
        Sending a message to a stream to which you are subscribed is
        successful.
        """
        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "subject": "Test subject"})
        self.assert_json_success(result)

    def test_api_message_to_self(self):
        # type: () -> None
        """
        Same as above, but for the API view
        """
        email = self.example_email("hamlet")
        result = self.client_post("/api/v1/messages", {"type": "stream",
                                                       "to": "Verona",
                                                       "client": "test suite",
                                                       "content": "Test message",
                                                       "subject": "Test subject"},
                                  **self.api_auth(email))
        self.assert_json_success(result)

    def test_api_message_with_default_to(self):
        # type: () -> None
        """
        Sending messages without a to field should be sent to the default
        stream for the user_profile.
        """
        user_profile = self.example_user('hamlet')
        email = user_profile.email
        user_profile.default_sending_stream = get_stream('Verona', user_profile.realm)
        user_profile.save()
        result = self.client_post("/api/v1/messages", {"type": "stream",
                                                       "client": "test suite",
                                                       "content": "Test message no to",
                                                       "subject": "Test subject"},
                                  **self.api_auth(email))
        self.assert_json_success(result)

        sent_message = self.get_last_message()
        self.assertEqual(sent_message.content, "Test message no to")

    def test_message_to_nonexistent_stream(self):
        # type: () -> None
        """
        Sending a message to a nonexistent stream fails.
        """
        self.login(self.example_email("hamlet"))
        self.assertFalse(Stream.objects.filter(name="nonexistent_stream"))
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "nonexistent_stream",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "subject": "Test subject"})
        self.assert_json_error(result, "Stream 'nonexistent_stream' does not exist")

    def test_message_to_nonexistent_stream_with_bad_characters(self):
        # type: () -> None
        """
        Nonexistent stream name with bad characters should be escaped properly.
        """
        self.login(self.example_email("hamlet"))
        self.assertFalse(Stream.objects.filter(name="""&<"'><non-existent>"""))
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": """&<"'><non-existent>""",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "subject": "Test subject"})
        self.assert_json_error(result, "Stream '&amp;&lt;&quot;&#39;&gt;&lt;non-existent&gt;' does not exist")

    def test_personal_message(self):
        # type: () -> None
        """
        Sending a personal message to a valid username is successful.
        """
        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": self.example_email("othello")})
        self.assert_json_success(result)

    def test_personal_message_copying_self(self):
        # type: () -> None
        """
        Sending a personal message to yourself plus another user is succesful,
        and counts as a message just to that user.
        """
        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/messages", {
            "type": "private",
            "content": "Test message",
            "client": "test suite",
            "to": ujson.dumps([self.example_email("othello"),
                               self.example_email("hamlet")])})
        self.assert_json_success(result)
        msg = self.get_last_message()
        # Verify that we're not actually on the "recipient list"
        self.assertNotIn("Hamlet", str(msg.recipient))

    def test_personal_message_to_nonexistent_user(self):
        # type: () -> None
        """
        Sending a personal message to an invalid email returns error JSON.
        """
        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": "nonexistent"})
        self.assert_json_error(result, "Invalid email 'nonexistent'")

    def test_personal_message_to_deactivated_user(self):
        # type: () -> None
        """
        Sending a personal message to a deactivated user returns error JSON.
        """
        target_user_profile = self.example_user("othello")
        do_deactivate_user(target_user_profile)
        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/messages", {
            "type": "private",
            "content": "Test message",
            "client": "test suite",
            "to": self.example_email("othello")})
        self.assert_json_error(result, "'othello@zulip.com' is no longer using Zulip.")

        result = self.client_post("/json/messages", {
            "type": "private",
            "content": "Test message",
            "client": "test suite",
            "to": ujson.dumps([self.example_email("othello"),
                               self.example_email("cordelia")])})
        self.assert_json_error(result, "'othello@zulip.com' is no longer using Zulip.")

    def test_invalid_type(self):
        # type: () -> None
        """
        Sending a message of unknown type returns error JSON.
        """
        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/messages", {"type": "invalid type",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": self.example_email("othello")})
        self.assert_json_error(result, "Invalid message type")

    def test_empty_message(self):
        # type: () -> None
        """
        Sending a message that is empty or only whitespace should fail
        """
        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": " ",
                                                     "client": "test suite",
                                                     "to": self.example_email("othello")})
        self.assert_json_error(result, "Message must not be empty")

    def test_mirrored_huddle(self):
        # type: () -> None
        """
        Sending a mirrored huddle message works
        """
        self.login(self.mit_email("starnine"))
        result = self.client_post("/json/messages", {"type": "private",
                                                     "sender": self.mit_email("sipbtest"),
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": ujson.dumps([self.mit_email("starnine"),
                                                                        self.mit_email("espuser")])},
                                  subdomain="zephyr")
        self.assert_json_success(result)

    def test_mirrored_personal(self):
        # type: () -> None
        """
        Sending a mirrored personal message works
        """
        self.login(self.mit_email("starnine"))
        result = self.client_post("/json/messages", {"type": "private",
                                                     "sender": self.mit_email("sipbtest"),
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": self.mit_email("starnine")},
                                  subdomain="zephyr")
        self.assert_json_success(result)

    def test_mirrored_personal_to_someone_else(self):
        # type: () -> None
        """
        Sending a mirrored personal message to someone else is not allowed.
        """
        self.login(self.mit_email("starnine"))
        result = self.client_post("/json/messages", {"type": "private",
                                                     "sender": self.mit_email("sipbtest"),
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": self.mit_email("espuser")},
                                  subdomain="zephyr")
        self.assert_json_error(result, "User not authorized for this query")

    def test_duplicated_mirrored_huddle(self):
        # type: () -> None
        """
        Sending two mirrored huddles in the row return the same ID
        """
        msg = {"type": "private",
               "sender": self.mit_email("sipbtest"),
               "content": "Test message",
               "client": "zephyr_mirror",
               "to": ujson.dumps([self.mit_email("espuser"),
                                  self.mit_email("starnine")])}

        with mock.patch('DNS.dnslookup', return_value=[['starnine:*:84233:101:Athena Consulting Exchange User,,,:/mit/starnine:/bin/bash']]):
            self.login(self.mit_email("starnine"))
            result1 = self.client_post("/json/messages", msg,
                                       subdomain="zephyr")
        with mock.patch('DNS.dnslookup', return_value=[['espuser:*:95494:101:Esp Classroom,,,:/mit/espuser:/bin/athena/bash']]):
            self.login(self.mit_email("espuser"))
            result2 = self.client_post("/json/messages", msg,
                                       subdomain="zephyr")
        self.assertEqual(ujson.loads(result1.content)['id'],
                         ujson.loads(result2.content)['id'])

    def test_strip_message(self):
        # type: () -> None
        """
        Sending a message longer than the maximum message length succeeds but is
        truncated.
        """
        self.login(self.example_email("hamlet"))
        post_data = {"type": "stream", "to": "Verona", "client": "test suite",
                     "content": "  I like whitespace at the end! \n\n \n", "subject": "Test subject"}
        result = self.client_post("/json/messages", post_data)
        self.assert_json_success(result)
        sent_message = self.get_last_message()
        self.assertEqual(sent_message.content, "  I like whitespace at the end!")

    def test_long_message(self):
        # type: () -> None
        """
        Sending a message longer than the maximum message length succeeds but is
        truncated.
        """
        self.login(self.example_email("hamlet"))
        long_message = "A" * (MAX_MESSAGE_LENGTH + 1)
        post_data = {"type": "stream", "to": "Verona", "client": "test suite",
                     "content": long_message, "subject": "Test subject"}
        result = self.client_post("/json/messages", post_data)
        self.assert_json_success(result)

        sent_message = self.get_last_message()
        self.assertEqual(sent_message.content,
                         "A" * (MAX_MESSAGE_LENGTH - 3) + "...")

    def test_long_topic(self):
        # type: () -> None
        """
        Sending a message with a topic longer than the maximum topic length
        succeeds, but the topic is truncated.
        """
        self.login(self.example_email("hamlet"))
        long_topic = "A" * (MAX_SUBJECT_LENGTH + 1)
        post_data = {"type": "stream", "to": "Verona", "client": "test suite",
                     "content": "test content", "subject": long_topic}
        result = self.client_post("/json/messages", post_data)
        self.assert_json_success(result)

        sent_message = self.get_last_message()
        self.assertEqual(sent_message.topic_name(),
                         "A" * (MAX_SUBJECT_LENGTH - 3) + "...")

    def test_send_forged_message_as_not_superuser(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "subject": "Test subject",
                                                     "forged": True})
        self.assert_json_error(result, "User not authorized for this query")

    def test_send_message_as_not_superuser_to_different_domain(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "subject": "Test subject",
                                                     "realm_str": "mit"})
        self.assert_json_error(result, "User not authorized for this query")

    def test_send_message_as_superuser_to_domain_that_dont_exist(self):
        # type: () -> None
        user = get_system_bot(settings.EMAIL_GATEWAY_BOT)
        password = "test_password"
        user.set_password(password)
        user.is_api_super_user = True
        user.save()
        self.login(user.email, password)
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "subject": "Test subject",
                                                     "realm_str": "non-existing"})
        user.is_api_super_user = False
        user.save()
        self.assert_json_error(result, "Unknown realm non-existing")

    def test_send_message_when_sender_is_not_set(self):
        # type: () -> None
        self.login(self.mit_email("starnine"))
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": self.mit_email("starnine")},
                                  subdomain="zephyr")
        self.assert_json_error(result, "Missing sender")

    def test_send_message_as_not_superuser_when_type_is_not_private(self):
        # type: () -> None
        self.login(self.mit_email("starnine"))
        result = self.client_post("/json/messages", {"type": "not-private",
                                                     "sender": self.mit_email("sipbtest"),
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": self.mit_email("starnine")},
                                  subdomain="zephyr")
        self.assert_json_error(result, "User not authorized for this query")

    @mock.patch("zerver.views.messages.create_mirrored_message_users")
    def test_send_message_create_mirrored_message_user_returns_invalid_input(self, create_mirrored_message_users_mock):
        # type: (Any) -> None
        create_mirrored_message_users_mock.return_value = (False, True)
        self.login(self.mit_email("starnine"))
        result = self.client_post("/json/messages", {"type": "private",
                                                     "sender": self.mit_email("sipbtest"),
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": self.mit_email("starnine")},
                                  subdomain="zephyr")
        self.assert_json_error(result, "Invalid mirrored message")

    @mock.patch("zerver.views.messages.create_mirrored_message_users")
    def test_send_message_when_client_is_zephyr_mirror_but_string_id_is_not_zephyr(self, create_mirrored_message_users_mock):
        # type: (Any) -> None
        create_mirrored_message_users_mock.return_value = (True, True)
        user = self.mit_user("starnine")
        email = user.email
        user.realm.string_id = 'notzephyr'
        user.realm.save()
        self.login(email)
        result = self.client_post("/json/messages", {"type": "private",
                                                     "sender": self.mit_email("sipbtest"),
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": email},
                                  subdomain="notzephyr")
        self.assert_json_error(result, "Invalid mirrored realm")

    @override_settings(REALMS_HAVE_SUBDOMAINS=True)
    def test_send_message_irc_mirror(self):
        # type: () -> None
        self.login(self.example_email('hamlet'))
        bot_info = {
            'full_name': 'IRC bot',
            'short_name': 'irc',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        email = "irc-bot@zulip.testserver"
        user = get_user(email, get_realm('zulip'))
        user.is_api_super_user = True
        user.save()
        user = get_user(email, get_realm('zulip'))
        self.subscribe(user, "#IRCland")
        result = self.client_post("/api/v1/messages",
                                  {"type": "stream",
                                   "forged": "true",
                                   "sender": "irc-user@irc.zulip.com",
                                   "content": "Test message",
                                   "client": "irc_mirror",
                                   "subject": "from irc",
                                   "to": "IRCLand"},
                                  **self.api_auth(email))
        self.assert_json_error(result, "IRC stream names must start with #")
        result = self.client_post("/api/v1/messages",
                                  {"type": "stream",
                                   "forged": "true",
                                   "sender": "irc-user@irc.zulip.com",
                                   "content": "Test message",
                                   "client": "irc_mirror",
                                   "subject": "from irc",
                                   "to": "#IRCLand"},
                                  **self.api_auth(email))
        self.assert_json_success(result)

class EditMessageTest(ZulipTestCase):
    def check_message(self, msg_id, subject=None, content=None):
        # type: (int, Optional[Text], Optional[Text]) -> Message
        msg = Message.objects.get(id=msg_id)
        cached = message_to_dict(msg, False)
        uncached = MessageDict.to_dict_uncached_helper(msg, False)
        self.assertEqual(cached, uncached)
        if subject:
            self.assertEqual(msg.topic_name(), subject)
        if content:
            self.assertEqual(msg.content, content)
        return msg

    def test_save_message(self):
        # type: () -> None
        """This is also tested by a client test, but here we can verify
        the cache against the database"""
        self.login(self.example_email("hamlet"))
        msg_id = self.send_message(self.example_email("hamlet"), "Scotland", Recipient.STREAM,
                                   subject="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': 'after edit'
        })
        self.assert_json_success(result)
        self.check_message(msg_id, content="after edit")

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'subject': 'edited'
        })
        self.assert_json_success(result)
        self.check_message(msg_id, subject="edited")

    def test_fetch_raw_message(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        msg_id = self.send_message(self.example_email("hamlet"), self.example_email("cordelia"), Recipient.PERSONAL,
                                   subject="editing", content="**before** edit")
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_success(result)
        self.assertEqual(result.json()['raw_content'], '**before** edit')

        # Test error cases
        result = self.client_get('/json/messages/999999')
        self.assert_json_error(result, 'Invalid message(s)')

        self.login(self.example_email("cordelia"))
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_success(result)

        self.login(self.example_email("othello"))
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_error(result, 'Invalid message(s)')

    def test_fetch_raw_message_stream_wrong_realm(self):
        # type: () -> None
        user_profile = self.example_user("hamlet")
        self.login(user_profile.email)
        stream = self.make_stream('public_stream')
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_message(user_profile.email, stream.name, Recipient.STREAM,
                                   subject="test", content="test")
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_success(result)

        self.login(self.mit_email("sipbtest"))
        result = self.client_get('/json/messages/' + str(msg_id), subdomain="zephyr")
        self.assert_json_error(result, 'Invalid message(s)')

    def test_fetch_raw_message_private_stream(self):
        # type: () -> None
        user_profile = self.example_user("hamlet")
        self.login(user_profile.email)
        stream = self.make_stream('private_stream', invite_only=True)
        self.subscribe(user_profile, stream.name)
        msg_id = self.send_message(user_profile.email, stream.name, Recipient.STREAM,
                                   subject="test", content="test")
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_success(result)
        self.login(self.example_email("othello"))
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_error(result, 'Invalid message(s)')

    def test_edit_message_no_permission(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        msg_id = self.send_message(self.example_email("iago"), "Scotland", Recipient.STREAM,
                                   subject="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': 'content after edit',
        })
        self.assert_json_error(result, "You don't have permission to edit this message")

    def test_edit_message_no_changes(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        msg_id = self.send_message(self.example_email("hamlet"), "Scotland", Recipient.STREAM,
                                   subject="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
        })
        self.assert_json_error(result, "Nothing to change")

    def test_edit_message_no_topic(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        msg_id = self.send_message(self.example_email("hamlet"), "Scotland", Recipient.STREAM,
                                   subject="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'subject': ' '
        })
        self.assert_json_error(result, "Topic can't be empty")

    def test_edit_message_no_content(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        msg_id = self.send_message(self.example_email("hamlet"), "Scotland", Recipient.STREAM,
                                   subject="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': ' '
        })
        self.assert_json_success(result)
        content = Message.objects.filter(id=msg_id).values_list('content', flat = True)[0]
        self.assertEqual(content, "(deleted)")

    def test_edit_message_history_disabled(self):
        # type: () -> None
        user_profile = self.example_user("hamlet")
        do_set_realm_property(user_profile.realm, "allow_edit_history", False)
        self.login(self.example_email("hamlet"))

        # Single-line edit
        msg_id_1 = self.send_message(self.example_email("hamlet"),
                                     "Denmark",
                                     Recipient.STREAM,
                                     subject="editing",
                                     content="content before edit")

        new_content_1 = 'content after edit'
        result_1 = self.client_patch("/json/messages/" + str(msg_id_1), {
            'message_id': msg_id_1, 'content': new_content_1
        })
        self.assert_json_success(result_1)

        result = self.client_get(
            "/json/messages/" + str(msg_id_1) + "/history")
        self.assert_json_error(result, "Message edit history is disabled in this organization")

        # Now verify that if we fetch the message directly, there's no
        # edit history data attached.
        messages_result = self.client_get("/json/messages",
                                          {"anchor": msg_id_1, "num_before": 0, "num_after": 10})
        self.assert_json_success(messages_result)
        json_messages = ujson.loads(
            messages_result.content.decode('utf-8'))
        for msg in json_messages['messages']:
            self.assertNotIn("edit_history", msg)

    def test_edit_message_history(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))

        # Single-line edit
        msg_id_1 = self.send_message(self.example_email("hamlet"),
                                     "Scotland",
                                     Recipient.STREAM,
                                     subject="editing",
                                     content="content before edit")
        new_content_1 = 'content after edit'
        result_1 = self.client_patch("/json/messages/" + str(msg_id_1), {
            'message_id': msg_id_1, 'content': new_content_1
        })
        self.assert_json_success(result_1)

        message_edit_history_1 = self.client_get(
            "/json/messages/" + str(msg_id_1) + "/history")
        json_response_1 = ujson.loads(
            message_edit_history_1.content.decode('utf-8'))
        message_history_1 = json_response_1['message_history']

        # Check content of message after edit.
        self.assertEqual(message_history_1[0]['rendered_content'],
                         '<p>content before edit</p>')
        self.assertEqual(message_history_1[1]['rendered_content'],
                         '<p>content after edit</p>')
        self.assertEqual(message_history_1[1]['content_html_diff'],
                         ('<p>content '
                          '<span class="highlight_text_deleted">before</span>'
                          '<span class="highlight_text_inserted">after</span>'
                          ' edit</p>'))
        # Check content of message before edit.
        self.assertEqual(message_history_1[1]['prev_rendered_content'],
                         '<p>content before edit</p>')

        # Edits on new lines
        msg_id_2 = self.send_message(self.example_email("hamlet"),
                                     "Scotland",
                                     Recipient.STREAM,
                                     subject="editing",
                                     content=('content before edit, line 1\n'
                                              '\n'
                                              'content before edit, line 3'))
        new_content_2 = ('content before edit, line 1\n'
                         'content after edit, line 2\n'
                         'content before edit, line 3')
        result_2 = self.client_patch("/json/messages/" + str(msg_id_2), {
            'message_id': msg_id_2, 'content': new_content_2
        })
        self.assert_json_success(result_2)

        message_edit_history_2 = self.client_get(
            "/json/messages/" + str(msg_id_2) + "/history")
        json_response_2 = ujson.loads(
            message_edit_history_2.content.decode('utf-8'))
        message_history_2 = json_response_2['message_history']

        self.assertEqual(message_history_2[0]['rendered_content'],
                         ('<p>content before edit, line 1</p>\n'
                          '<p>content before edit, line 3</p>'))
        self.assertEqual(message_history_2[1]['rendered_content'],
                         ('<p>content before edit, line 1<br>\n'
                          'content after edit, line 2<br>\n'
                          'content before edit, line 3</p>'))
        self.assertEqual(message_history_2[1]['content_html_diff'],
                         ('<p>content before edit, line 1</p>'
                          '<span class="highlight_text_deleted">\n'
                          '</span><p><span class="highlight_text_inserted">\n'
                          'content after edit, line 2</span><br>'
                          '<span class="highlight_text_inserted">\n'
                          '</span>content before edit, line 3</p>'))
        self.assertEqual(message_history_2[1]['prev_rendered_content'],
                         ('<p>content before edit, line 1</p>\n'
                          '<p>content before edit, line 3</p>'))

    def test_edit_cases(self):
        # type: () -> None
        """This test verifies the accuracy of construction of Zulip's edit
        history data structures."""
        self.login(self.example_email("hamlet"))
        hamlet = self.example_user('hamlet')
        msg_id = self.send_message(self.example_email("hamlet"), "Scotland", Recipient.STREAM,
                                   subject="subject 1", content="content 1")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': 'content 2',
        })
        self.assert_json_success(result)
        history = ujson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0]['prev_content'], 'content 1')
        self.assertEqual(history[0]['user_id'], hamlet.id)
        self.assertEqual(set(history[0].keys()),
                         {u'timestamp', u'prev_content', u'user_id',
                          u'prev_rendered_content', u'prev_rendered_content_version'})

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'subject': 'subject 2',
        })
        self.assert_json_success(result)
        history = ujson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0]['prev_subject'], 'subject 1')
        self.assertEqual(history[0]['user_id'], hamlet.id)
        self.assertEqual(set(history[0].keys()), {u'timestamp', u'prev_subject', u'user_id'})

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': 'content 3',
            'subject': 'subject 3',
        })
        self.assert_json_success(result)
        history = ujson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0]['prev_content'], 'content 2')
        self.assertEqual(history[0]['prev_subject'], 'subject 2')
        self.assertEqual(history[0]['user_id'], hamlet.id)
        self.assertEqual(set(history[0].keys()),
                         {u'timestamp', u'prev_subject', u'prev_content', u'user_id',
                          u'prev_rendered_content', u'prev_rendered_content_version'})

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': 'content 4',
        })
        self.assert_json_success(result)
        history = ujson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0]['prev_content'], 'content 3')
        self.assertEqual(history[0]['user_id'], hamlet.id)

        self.login(self.example_email("iago"))
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'subject': 'subject 4',
        })
        self.assert_json_success(result)
        history = ujson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0]['prev_subject'], 'subject 3')
        self.assertEqual(history[0]['user_id'], self.example_user('iago').id)

        history = ujson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0]['prev_subject'], 'subject 3')
        self.assertEqual(history[2]['prev_subject'], 'subject 2')
        self.assertEqual(history[3]['prev_subject'], 'subject 1')
        self.assertEqual(history[1]['prev_content'], 'content 3')
        self.assertEqual(history[2]['prev_content'], 'content 2')
        self.assertEqual(history[4]['prev_content'], 'content 1')

        # Now, we verify that the edit history data sent back has the
        # correct filled-out fields
        message_edit_history = self.client_get("/json/messages/" + str(msg_id) + "/history")

        json_response = ujson.loads(message_edit_history.content.decode('utf-8'))

        # We reverse the message history view output so that the IDs line up with the above.
        message_history = list(reversed(json_response['message_history']))
        i = 0
        for entry in message_history:
            expected_entries = {u'content', u'rendered_content', u'topic', u'timestamp', u'user_id'}
            if i in {0, 2, 3}:
                expected_entries.add('prev_topic')
            if i in {1, 2, 4}:
                expected_entries.add('prev_content')
                expected_entries.add('prev_rendered_content')
                expected_entries.add('content_html_diff')
            i += 1
            self.assertEqual(expected_entries, set(entry.keys()))
        self.assertEqual(len(message_history), 6)
        self.assertEqual(message_history[0]['prev_topic'], 'subject 3')
        self.assertEqual(message_history[0]['topic'], 'subject 4')
        self.assertEqual(message_history[1]['topic'], 'subject 3')
        self.assertEqual(message_history[2]['topic'], 'subject 3')
        self.assertEqual(message_history[2]['prev_topic'], 'subject 2')
        self.assertEqual(message_history[3]['topic'], 'subject 2')
        self.assertEqual(message_history[3]['prev_topic'], 'subject 1')
        self.assertEqual(message_history[4]['topic'], 'subject 1')

        self.assertEqual(message_history[0]['content'], 'content 4')
        self.assertEqual(message_history[1]['content'], 'content 4')
        self.assertEqual(message_history[1]['prev_content'], 'content 3')
        self.assertEqual(message_history[2]['content'], 'content 3')
        self.assertEqual(message_history[2]['prev_content'], 'content 2')
        self.assertEqual(message_history[3]['content'], 'content 2')
        self.assertEqual(message_history[4]['content'], 'content 2')
        self.assertEqual(message_history[4]['prev_content'], 'content 1')

        self.assertEqual(message_history[5]['content'], 'content 1')
        self.assertEqual(message_history[5]['topic'], 'subject 1')

    def test_edit_message_content_limit(self):
        # type: () -> None
        def set_message_editing_params(allow_message_editing,
                                       message_content_edit_limit_seconds):
            # type: (bool, int) -> None
            result = self.client_patch("/json/realm", {
                'allow_message_editing': ujson.dumps(allow_message_editing),
                'message_content_edit_limit_seconds': message_content_edit_limit_seconds
            })
            self.assert_json_success(result)

        def do_edit_message_assert_success(id_, unique_str, topic_only = False):
            # type: (int, Text, bool) -> None
            new_subject = 'subject' + unique_str
            new_content = 'content' + unique_str
            params_dict = {'message_id': id_, 'subject': new_subject}
            if not topic_only:
                params_dict['content'] = new_content
            result = self.client_patch("/json/messages/" + str(id_), params_dict)
            self.assert_json_success(result)
            if topic_only:
                self.check_message(id_, subject=new_subject)
            else:
                self.check_message(id_, subject=new_subject, content=new_content)

        def do_edit_message_assert_error(id_, unique_str, error, topic_only = False):
            # type: (int, Text, Text, bool) -> None
            message = Message.objects.get(id=id_)
            old_subject = message.topic_name()
            old_content = message.content
            new_subject = 'subject' + unique_str
            new_content = 'content' + unique_str
            params_dict = {'message_id': id_, 'subject': new_subject}
            if not topic_only:
                params_dict['content'] = new_content
            result = self.client_patch("/json/messages/" + str(id_), params_dict)
            message = Message.objects.get(id=id_)
            self.assert_json_error(result, error)
            self.check_message(id_, subject=old_subject, content=old_content)

        self.login(self.example_email("iago"))
        # send a message in the past
        id_ = self.send_message(self.example_email("iago"), "Scotland", Recipient.STREAM,
                                content="content", subject="subject")
        message = Message.objects.get(id=id_)
        message.pub_date = message.pub_date - datetime.timedelta(seconds=180)
        message.save()

        # test the various possible message editing settings
        # high enough time limit, all edits allowed
        set_message_editing_params(True, 240)
        do_edit_message_assert_success(id_, 'A')

        # out of time, only topic editing allowed
        set_message_editing_params(True, 120)
        do_edit_message_assert_success(id_, 'B', True)
        do_edit_message_assert_error(id_, 'C', "The time limit for editing this message has past")

        # infinite time, all edits allowed
        set_message_editing_params(True, 0)
        do_edit_message_assert_success(id_, 'D')

        # without allow_message_editing, nothing is allowed
        set_message_editing_params(False, 240)
        do_edit_message_assert_error(id_, 'E', "Your organization has turned off message editing", True)
        set_message_editing_params(False, 120)
        do_edit_message_assert_error(id_, 'F', "Your organization has turned off message editing", True)
        set_message_editing_params(False, 0)
        do_edit_message_assert_error(id_, 'G', "Your organization has turned off message editing", True)

    def test_propagate_topic_forward(self):
        # type: () -> None
        self.login(self.example_email("hamlet"))
        id1 = self.send_message(self.example_email("hamlet"), "Scotland", Recipient.STREAM,
                                subject="topic1")
        id2 = self.send_message(self.example_email("iago"), "Scotland", Recipient.STREAM,
                                subject="topic1")
        id3 = self.send_message(self.example_email("iago"), "Rome", Recipient.STREAM,
                                subject="topic1")
        id4 = self.send_message(self.example_email("hamlet"), "Scotland", Recipient.STREAM,
                                subject="topic2")
        id5 = self.send_message(self.example_email("iago"), "Scotland", Recipient.STREAM,
                                subject="topic1")

        result = self.client_patch("/json/messages/" + str(id1), {
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
        # type: () -> None
        self.login(self.example_email("hamlet"))
        id1 = self.send_message(self.example_email("hamlet"), "Scotland", Recipient.STREAM,
                                subject="topic1")
        id2 = self.send_message(self.example_email("hamlet"), "Scotland", Recipient.STREAM,
                                subject="topic1")
        id3 = self.send_message(self.example_email("iago"), "Rome", Recipient.STREAM,
                                subject="topic1")
        id4 = self.send_message(self.example_email("hamlet"), "Scotland", Recipient.STREAM,
                                subject="topic2")
        id5 = self.send_message(self.example_email("iago"), "Scotland", Recipient.STREAM,
                                subject="topic1")
        id6 = self.send_message(self.example_email("iago"), "Scotland", Recipient.STREAM,
                                subject="topic3")

        result = self.client_patch("/json/messages/" + str(id2), {
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

class MirroredMessageUsersTest(ZulipTestCase):
    def test_invalid_sender(self):
        # type: () -> None
        user = self.example_user('hamlet')
        recipients = []  # type: List[Text]

        Request = namedtuple('Request', ['POST'])
        request = Request(POST=dict())  # no sender

        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user, recipients)

        self.assertEqual(valid_input, False)
        self.assertEqual(mirror_sender, None)

    def test_invalid_client(self):
        # type: () -> None
        client = get_client(name='banned_mirror')  # Invalid!!!

        user = self.example_user('hamlet')
        sender = user

        recipients = []  # type: List[Text]

        Request = namedtuple('Request', ['POST', 'client'])
        request = Request(POST = dict(sender=sender.email, type='private'),
                          client = client)

        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user, recipients)

        self.assertEqual(valid_input, False)
        self.assertEqual(mirror_sender, None)

    def test_invalid_email(self):
        # type: () -> None
        invalid_email = 'alice AT example.com'
        recipients = [invalid_email]

        # We use an MIT user here to maximize code coverage
        user = self.mit_user('starnine')
        sender = user

        Request = namedtuple('Request', ['POST', 'client'])

        for client_name in ['zephyr_mirror', 'irc_mirror', 'jabber_mirror']:
            client = get_client(name=client_name)

            request = Request(POST = dict(sender=sender.email, type='private'),
                              client = client)

            (valid_input, mirror_sender) = \
                create_mirrored_message_users(request, user, recipients)

            self.assertEqual(valid_input, False)
            self.assertEqual(mirror_sender, None)

    @mock.patch('DNS.dnslookup', return_value=[['sipbtest:*:20922:101:Fred Sipb,,,:/mit/sipbtest:/bin/athena/tcsh']])
    def test_zephyr_mirror_new_recipient(self, ignored):
        # type: (Any) -> None
        """Test mirror dummy user creation for PM recipients"""
        client = get_client(name='zephyr_mirror')

        user = self.mit_user('starnine')
        sender = self.mit_user('sipbtest')
        new_user_email = 'bob_the_new_user@mit.edu'
        new_user_realm = get_realm("zephyr")

        recipients = [user.email, new_user_email]

        # Now make the request.
        Request = namedtuple('Request', ['POST', 'client'])
        request = Request(POST = dict(sender=sender.email, type='private'),
                          client = client)

        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user, recipients)

        self.assertTrue(valid_input)
        self.assertEqual(mirror_sender, sender)

        realm_users = UserProfile.objects.filter(realm=sender.realm)
        realm_emails = {user.email for user in realm_users}
        self.assertIn(user.email, realm_emails)
        self.assertIn(new_user_email, realm_emails)

        bob = get_user(new_user_email, new_user_realm)
        self.assertTrue(bob.is_mirror_dummy)

    @mock.patch('DNS.dnslookup', return_value=[['sipbtest:*:20922:101:Fred Sipb,,,:/mit/sipbtest:/bin/athena/tcsh']])
    def test_zephyr_mirror_new_sender(self, ignored):
        # type: (Any) -> None
        """Test mirror dummy user creation for sender when sending to stream"""
        client = get_client(name='zephyr_mirror')

        user = self.mit_user('starnine')
        sender_email = 'new_sender@mit.edu'

        recipients = ['stream_name']

        # Now make the request.
        Request = namedtuple('Request', ['POST', 'client'])
        request = Request(POST = dict(sender=sender_email, type='stream'),
                          client = client)

        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user, recipients)

        assert(mirror_sender is not None)
        self.assertTrue(valid_input)
        self.assertEqual(mirror_sender.email, sender_email)
        self.assertTrue(mirror_sender.is_mirror_dummy)

    def test_irc_mirror(self):
        # type: () -> None
        client = get_client(name='irc_mirror')

        sender = self.example_user('hamlet')
        user = sender

        recipients = [self.nonreg_email('alice'), 'bob@irc.zulip.com', self.nonreg_email('cordelia')]

        # Now make the request.
        Request = namedtuple('Request', ['POST', 'client'])
        request = Request(POST = dict(sender=sender.email, type='private'),
                          client = client)

        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user, recipients)

        self.assertEqual(valid_input, True)
        self.assertEqual(mirror_sender, sender)

        realm_users = UserProfile.objects.filter(realm=sender.realm)
        realm_emails = {user.email for user in realm_users}
        self.assertIn(self.nonreg_email('alice'), realm_emails)
        self.assertIn('bob@irc.zulip.com', realm_emails)

        bob = get_user('bob@irc.zulip.com', sender.realm)
        self.assertTrue(bob.is_mirror_dummy)

    def test_jabber_mirror(self):
        # type: () -> None
        client = get_client(name='jabber_mirror')

        sender = self.example_user('hamlet')
        user = sender

        recipients = [self.nonreg_email('alice'), self.nonreg_email('bob'), self.nonreg_email('cordelia')]

        # Now make the request.
        Request = namedtuple('Request', ['POST', 'client'])
        request = Request(POST = dict(sender=sender.email, type='private'),
                          client = client)

        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user, recipients)

        self.assertEqual(valid_input, True)
        self.assertEqual(mirror_sender, sender)

        realm_users = UserProfile.objects.filter(realm=sender.realm)
        realm_emails = {user.email for user in realm_users}
        self.assertIn(self.nonreg_email('alice'), realm_emails)
        self.assertIn(self.nonreg_email('bob'), realm_emails)

        bob = get_user(self.nonreg_email('bob'), sender.realm)
        self.assertTrue(bob.is_mirror_dummy)

class StarTests(ZulipTestCase):

    def change_star(self, messages, add=True, **kwargs):
        # type: (List[int], bool, **Any) -> HttpResponse
        return self.client_post("/json/messages/flags",
                                {"messages": ujson.dumps(messages),
                                 "op": "add" if add else "remove",
                                 "flag": "starred"},
                                **kwargs)

    def test_change_star(self):
        # type: () -> None
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        self.login(self.example_email("hamlet"))
        message_ids = [self.send_message(self.example_email("hamlet"), self.example_email("hamlet"),
                                         Recipient.PERSONAL, "test")]

        # Star a message.
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        for msg in self.get_messages():
            if msg['id'] in message_ids:
                self.assertEqual(msg['flags'], ['starred'])
            else:
                self.assertEqual(msg['flags'], ['read'])

        result = self.change_star(message_ids, False)
        self.assert_json_success(result)

        # Remove the stars.
        for msg in self.get_messages():
            if msg['id'] in message_ids:
                self.assertEqual(msg['flags'], [])

    def test_change_star_public_stream_historical(self):
        # type: () -> None
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        stream_name = "new_stream"
        self.subscribe(self.example_user("hamlet"), stream_name)
        self.login(self.example_email("hamlet"))
        message_ids = [self.send_message(self.example_email("hamlet"), stream_name,
                                         Recipient.STREAM, "test")]
        # Send a second message so we can verify it isn't modified
        other_message_ids = [self.send_message(self.example_email("hamlet"), stream_name,
                                               Recipient.STREAM, "test_unused")]
        received_message_ids = [self.send_message(self.example_email("hamlet"), [self.example_email("cordelia")],
                                                  Recipient.PERSONAL, "test_received")]

        # Now login as another user who wasn't on that stream
        self.login(self.example_email("cordelia"))
        # Send a message to yourself to make sure we have at least one with the read flag
        sent_message_ids = [self.send_message(self.example_email("cordelia"), [self.example_email("cordelia")],
                                              Recipient.PERSONAL, "test_read_message")]
        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps(sent_message_ids),
                                   "op": "add",
                                   "flag": "read"})

        # We can't change flags other than "starred" on historical messages:
        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps(message_ids),
                                   "op": "add",
                                   "flag": "read"})
        self.assert_json_error(result, 'Invalid message(s)')

        # Trying to change a list of more than one historical message fails
        result = self.change_star(message_ids * 2)
        self.assert_json_error(result, 'Invalid message(s)')

        # Confirm that one can change the historical flag now
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        for msg in self.get_messages():
            if msg['id'] in message_ids:
                self.assertEqual(set(msg['flags']), {'starred', 'historical', 'read'})
            elif msg['id'] in received_message_ids:
                self.assertEqual(msg['flags'], [])
            else:
                self.assertEqual(msg['flags'], ['read'])
            self.assertNotIn(msg['id'], other_message_ids)

        result = self.change_star(message_ids, False)
        self.assert_json_success(result)

        # But it still doesn't work if you're in another realm
        self.login(self.mit_email("sipbtest"))
        result = self.change_star(message_ids, subdomain="zephyr")
        self.assert_json_error(result, 'Invalid message(s)')

    def test_change_star_private_message_security(self):
        # type: () -> None
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        self.login(self.example_email("hamlet"))
        message_ids = [self.send_message(self.example_email("hamlet"), self.example_email("hamlet"),
                                         Recipient.PERSONAL, "test")]

        # Starring private messages you didn't receive fails.
        self.login(self.example_email("cordelia"))
        result = self.change_star(message_ids)
        self.assert_json_error(result, 'Invalid message(s)')

    def test_change_star_private_stream_security(self):
        # type: () -> None
        stream_name = "private_stream"
        self.make_stream(stream_name, invite_only=True)
        self.subscribe(self.example_user("hamlet"), stream_name)
        self.login(self.example_email("hamlet"))
        message_ids = [self.send_message(self.example_email("hamlet"), stream_name,
                                         Recipient.STREAM, "test")]

        # Starring private stream messages you received works
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        # Starring private stream messages you didn't receive fails.
        self.login(self.example_email("cordelia"))
        result = self.change_star(message_ids)
        self.assert_json_error(result, 'Invalid message(s)')

    def test_new_message(self):
        # type: () -> None
        """
        New messages aren't starred.
        """
        test_email = self.example_email('hamlet')
        self.login(test_email)
        content = "Test message for star"
        self.send_message(test_email, "Verona", Recipient.STREAM,
                          content=content)

        sent_message = UserMessage.objects.filter(
            user_profile=self.example_user('hamlet')
        ).order_by("id").reverse()[0]
        self.assertEqual(sent_message.message.content, content)
        self.assertFalse(sent_message.flags.starred)

class AttachmentTest(ZulipTestCase):
    def test_basics(self):
        # type: () -> None
        self.assertFalse(Message.content_has_attachment('whatever'))
        self.assertFalse(Message.content_has_attachment('yo http://foo.com'))
        self.assertTrue(Message.content_has_attachment('yo\n https://staging.zulip.com/user_uploads/'))
        self.assertTrue(Message.content_has_attachment('yo\n /user_uploads/1/wEAnI-PEmVmCjo15xxNaQbnj/photo-10.jpg foo'))

        self.assertFalse(Message.content_has_image('whatever'))
        self.assertFalse(Message.content_has_image('yo http://foo.com'))
        self.assertFalse(Message.content_has_image('yo\n /user_uploads/1/wEAnI-PEmVmCjo15xxNaQbnj/photo-10.pdf foo'))
        for ext in [".bmp", ".gif", ".jpg", "jpeg", ".png", ".webp", ".JPG"]:
            content = 'yo\n /user_uploads/1/wEAnI-PEmVmCjo15xxNaQbnj/photo-10.%s foo' % (ext,)
            self.assertTrue(Message.content_has_image(content))

        self.assertFalse(Message.content_has_link('whatever'))
        self.assertTrue(Message.content_has_link('yo\n http://foo.com'))
        self.assertTrue(Message.content_has_link('yo\n https://example.com?spam=1&eggs=2'))
        self.assertTrue(Message.content_has_link('yo /user_uploads/1/wEAnI-PEmVmCjo15xxNaQbnj/photo-10.pdf foo'))

    def test_claim_attachment(self):
        # type: () -> None

        # Create dummy DB entry
        user_profile = self.example_user('hamlet')
        sample_size = 10
        dummy_files = [
            ('zulip.txt', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt', sample_size),
            ('temp_file.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py', sample_size),
            ('abc.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py', sample_size)
        ]

        for file_name, path_id, size in dummy_files:
            create_attachment(file_name, path_id, user_profile, size)

        # Send message referring the attachment
        self.subscribe(user_profile, "Denmark")

        body = "Some files here ...[zulip.txt](http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)" +  \
               "http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py.... Some more...." + \
               "http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py"

        self.send_message(user_profile.email, "Denmark", Recipient.STREAM, body, "test")

        for file_name, path_id, size in dummy_files:
            attachment = Attachment.objects.get(path_id=path_id)
            self.assertTrue(attachment.is_claimed())

class MissedMessageTest(ZulipTestCase):
    def test_missed_message_userids(self):
        # type: () -> None
        UserPresence.objects.all().delete()

        sender = self.example_user('cordelia')
        realm = sender.realm
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        recipient_ids = {hamlet.id, othello.id}
        message_type = 'stream'
        user_flags = {}  # type: Dict[int, List[str]]

        def assert_missing(user_ids):
            # type: (List[int]) -> None
            missed_message_userids = get_userids_for_missed_messages(
                realm=realm,
                sender_id=sender.id,
                message_type=message_type,
                active_user_ids=recipient_ids,
                user_flags=user_flags,
            )
            self.assertEqual(sorted(user_ids), sorted(missed_message_userids))

        def set_presence(user_id, client_name, ago):
            # type: (int, Text, int) -> None
            when = timezone_now() - datetime.timedelta(seconds=ago)
            UserPresence.objects.create(
                user_profile_id=user_id,
                client=get_client(client_name),
                timestamp=when,
            )

        message_type = 'private'
        assert_missing([hamlet.id, othello.id])

        message_type = 'stream'
        user_flags[hamlet.id] = ['mentioned']
        assert_missing([hamlet.id])

        set_presence(hamlet.id, 'iPhone', ago=5000)
        assert_missing([hamlet.id])

        set_presence(hamlet.id, 'webapp', ago=15)
        assert_missing([])

        message_type = 'private'
        assert_missing([othello.id])

class LogDictTest(ZulipTestCase):
    def test_to_log_dict(self):
        # type: () -> None
        email = self.example_email('hamlet')
        stream_name = 'Denmark'
        topic_name = 'Copenhagen'
        content = 'find me some good coffee shops'
        # self.login(self.example_email("hamlet"))
        message_id = self.send_message(email, stream_name,
                                       message_type=Recipient.STREAM,
                                       subject=topic_name,
                                       content=content)
        message = Message.objects.get(id=message_id)
        dct = message.to_log_dict()

        self.assertTrue('timestamp' in dct)

        self.assertEqual(dct['content'], 'find me some good coffee shops')
        self.assertEqual(dct['id'], message.id)
        self.assertEqual(dct['recipient'], 'Denmark')
        self.assertEqual(dct['sender_realm_str'], 'zulip')
        self.assertEqual(dct['sender_email'], self.example_email("hamlet"))
        self.assertEqual(dct['sender_full_name'], 'King Hamlet')
        self.assertEqual(dct['sender_id'], self.example_user('hamlet').id)
        self.assertEqual(dct['sender_short_name'], 'hamlet')
        self.assertEqual(dct['sending_client'], 'test suite')
        self.assertEqual(dct['subject'], 'Copenhagen')
        self.assertEqual(dct['type'], 'stream')

class CheckMessageTest(ZulipTestCase):
    def test_basic_check_message_call(self):
        # type: () -> None
        sender = self.example_user('othello')
        client = make_client(name="test suite")
        stream_name = u'España y Francia'
        self.make_stream(stream_name)
        subject_name = 'issue'
        message_content = 'whatever'
        addressee = Addressee.for_stream(stream_name, subject_name)
        ret = check_message(sender, client, addressee, message_content)
        self.assertEqual(ret['message'].sender.email, self.example_email("othello"))

    def test_bot_pm_feature(self):
        # type: () -> None
        """We send a PM to a bot's owner if their bot sends a message to
        an unsubscribed stream"""
        parent = self.example_user('othello')
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
        client = make_client(name="test suite")
        stream_name = u'Россия'
        subject_name = 'issue'
        addressee = Addressee.for_stream(stream_name, subject_name)
        message_content = 'whatever'
        old_count = message_stream_count(parent)

        # Try sending to stream that doesn't exist sends a reminder to
        # the sender
        with self.assertRaises(JsonableError):
            check_message(sender, client, addressee, message_content)

        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 1)
        self.assertIn("that stream does not yet exist.", most_recent_message(parent).content)

        # Try sending to stream that exists with no subscribers soon
        # after; due to rate-limiting, this should send nothing.
        self.make_stream(stream_name)
        ret = check_message(sender, client, addressee, message_content)
        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 1)

        # Try sending to stream that exists with no subscribers longer
        # after; this should send an error to the bot owner that the
        # stream doesn't exist
        assert(sender.last_reminder is not None)
        sender.last_reminder = sender.last_reminder - datetime.timedelta(hours=1)
        sender.save(update_fields=["last_reminder"])
        ret = check_message(sender, client, addressee, message_content)

        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 2)
        self.assertEqual(ret['message'].sender.email, 'othello-bot@zulip.com')
        self.assertIn("there are no subscribers to that stream", most_recent_message(parent).content)


class DeleteMessageTest(ZulipTestCase):

    def test_delete_message_by_owner(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        msg_id = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM)
        result = self.client_delete('/json/messages/{msg_id}'.format(msg_id=msg_id))
        self.assert_json_error(result, "You don't have permission to edit this message")

    def test_delete_message_by_realm_admin(self):
        # type: () -> None
        self.login("iago@zulip.com")
        msg_id = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM)
        result = self.client_delete('/json/messages/{msg_id}'.format(msg_id=msg_id))
        self.assert_json_success(result)

    def test_delete_message_second_time(self):
        # type: () -> None
        self.login("iago@zulip.com")
        msg_id = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
                                   subject="editing", content="before edit")
        self.client_delete('/json/messages/{msg_id}'.format(msg_id=msg_id))
        result = self.client_delete('/json/messages/{msg_id}'.format(msg_id=msg_id))
        self.assert_json_error(result, "Invalid message(s)")

class SoftDeactivationMessageTest(ZulipTestCase):

    def test_maybe_catch_up_soft_deactivated_user(self):
        # type: () -> None
        recipient_list  = [self.example_user("hamlet"), self.example_user("iago")]
        for user_profile in recipient_list:
            self.subscribe(user_profile, "Denmark")

        sender = self.example_email('iago')
        stream_name = 'Denmark'
        subject = 'foo'

        def last_realm_audit_log_entry(event_type):
            # type: (str) -> RealmAuditLog
            return RealmAuditLog.objects.filter(
                event_type=event_type
            ).order_by('-event_time')[0]

        long_term_idle_user = self.example_user('hamlet')
        # We are sending this message to ensure that long_term_idle_user has
        # at least one UserMessage row.
        self.send_message(long_term_idle_user.email, stream_name,
                          Recipient.STREAM)
        do_soft_deactivate_users([long_term_idle_user])

        message = 'Test Message 1'
        self.send_message(sender, stream_name, Recipient.STREAM,
                          message, subject)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        self.assertNotEqual(idle_user_msg_list[-1].content, message)
        with queries_captured() as queries:
            maybe_catch_up_soft_deactivated_user(long_term_idle_user)
        self.assert_length(queries, 8)
        self.assertFalse(long_term_idle_user.long_term_idle)
        self.assertEqual(last_realm_audit_log_entry(
            'user_soft_activated').modified_user, long_term_idle_user)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 1)
        self.assertEqual(idle_user_msg_list[-1].content, message)

    def test_add_missing_messages(self):
        # type: () -> None
        recipient_list  = [self.example_user("hamlet"), self.example_user("iago")]
        for user_profile in recipient_list:
            self.subscribe(user_profile, "Denmark")

        sender = self.example_user('iago')
        realm = sender.realm
        sending_client = make_client(name="test suite")
        stream_name = 'Denmark'
        stream = get_stream(stream_name, realm)
        subject = 'foo'

        def send_fake_message(message_content, stream):
            # type: (str, Stream) -> Message
            recipient = get_recipient(Recipient.STREAM, stream.id)
            return Message.objects.create(sender = sender,
                                          recipient = recipient,
                                          subject = subject,
                                          content = message_content,
                                          pub_date = timezone_now(),
                                          sending_client = sending_client)

        long_term_idle_user = self.example_user('hamlet')
        self.send_message(long_term_idle_user.email, stream_name,
                          Recipient.STREAM)
        do_soft_deactivate_users([long_term_idle_user])

        # Test that add_missing_messages() in simplest case of adding a
        # message for which UserMessage row doesn't exist for this user.
        sent_message = send_fake_message('Test Message 1', stream)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        self.assertNotEqual(idle_user_msg_list[-1], sent_message)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 5)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 1)
        self.assertEqual(idle_user_msg_list[-1], sent_message)

        # Test that add_missing_messages() only adds messages that aren't
        # already present in the UserMessage table. This test works on the
        # fact that previous test just above this added a message but didn't
        # updated the last_active_message_id field for the user.
        sent_message = send_fake_message('Test Message 2', stream)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        self.assertNotEqual(idle_user_msg_list[-1], sent_message)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 5)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 1)
        self.assertEqual(idle_user_msg_list[-1], sent_message)

        # Test UserMessage rows are created correctly in case of stream
        # Subscription was altered by admin while user was away.

        # Test for a public stream.
        sent_message_list = []
        sent_message_list.append(send_fake_message('Test Message 3', stream))
        # Alter subscription to stream.
        self.unsubscribe(long_term_idle_user, stream_name)
        send_fake_message('Test Message 4', stream)
        self.subscribe(long_term_idle_user, stream_name)
        sent_message_list.append(send_fake_message('Test Message 5', stream))
        sent_message_list.reverse()
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        for sent_message in sent_message_list:
            self.assertNotEqual(idle_user_msg_list.pop(), sent_message)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 5)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 2)
        for sent_message in sent_message_list:
            self.assertEqual(idle_user_msg_list.pop(), sent_message)

        # Test consecutive subscribe/unsubscribe in a public stream
        sent_message_list = []

        sent_message_list.append(send_fake_message('Test Message 6', stream))
        # Unsubscribe from stream and then immediately subscribe back again.
        self.unsubscribe(long_term_idle_user, stream_name)
        self.subscribe(long_term_idle_user, stream_name)
        sent_message_list.append(send_fake_message('Test Message 7', stream))
        # Again unsubscribe from stream and send a message.
        # This will make sure that if initially in a unsubscribed state
        # a consecutive subscribe/unsubscribe doesn't misbehave.
        self.unsubscribe(long_term_idle_user, stream_name)
        send_fake_message('Test Message 8', stream)
        # Do a subscribe and unsubscribe immediately.
        self.subscribe(long_term_idle_user, stream_name)
        self.unsubscribe(long_term_idle_user, stream_name)

        sent_message_list.reverse()
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        for sent_message in sent_message_list:
            self.assertNotEqual(idle_user_msg_list.pop(), sent_message)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 5)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 2)
        for sent_message in sent_message_list:
            self.assertEqual(idle_user_msg_list.pop(), sent_message)
        # Note: At this point in this test we have long_term_idle_user
        # unsubscribed from the 'Denmark' stream.

        # Test for a Private Stream.
        stream_name = "Core"
        private_stream = self.make_stream('Core', invite_only=True)
        self.subscribe(self.example_user("iago"), stream_name)
        sent_message_list = []
        send_fake_message('Test Message 9', private_stream)
        self.subscribe(self.example_user("hamlet"), stream_name)
        sent_message_list.append(send_fake_message('Test Message 10', private_stream))
        self.unsubscribe(long_term_idle_user, stream_name)
        send_fake_message('Test Message 11', private_stream)
        self.subscribe(long_term_idle_user, stream_name)
        sent_message_list.append(send_fake_message('Test Message 12', private_stream))
        sent_message_list.reverse()
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        for sent_message in sent_message_list:
            self.assertNotEqual(idle_user_msg_list.pop(), sent_message)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 5)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 2)
        for sent_message in sent_message_list:
            self.assertEqual(idle_user_msg_list.pop(), sent_message)

    def test_user_message_filter(self):
        # type: () -> None
        # In this test we are basically testing out the logic used out in
        # do_send_messages() in action.py for filtering the messages for which
        # UserMessage rows should be created for a soft-deactivated user.
        recipient_list  = [
            self.example_user("hamlet"),
            self.example_user("iago"),
            self.example_user('cordelia')
        ]
        for user_profile in recipient_list:
            self.subscribe(user_profile, "Denmark")

        cordelia = self.example_user('cordelia')
        sender = self.example_email('iago')
        stream_name = 'Denmark'
        subject = 'foo'

        def send_stream_message(content):
            # type: (str) -> None
            self.send_message(sender, stream_name, Recipient.STREAM,
                              content, subject)

        def send_personal_message(content):
            # type: (str) -> None
            self.send_message(sender, self.example_email("hamlet"),
                              Recipient.PERSONAL, content)

        long_term_idle_user = self.example_user('hamlet')
        self.send_message(long_term_idle_user.email, stream_name,
                          Recipient.STREAM)
        do_soft_deactivate_users([long_term_idle_user])

        def assert_um_count(user, count):
            # type: (UserProfile, int) -> None
            user_messages = get_user_messages(user)
            self.assertEqual(len(user_messages), count)

        def assert_last_um_content(user, content, negate=False):
            # type: (UserProfile, Text, bool) -> None
            user_messages = get_user_messages(user)
            if negate:
                self.assertNotEqual(user_messages[-1].content, content)
            else:
                self.assertEqual(user_messages[-1].content, content)

        # Test that sending a message to a stream with soft deactivated user
        # doesn't end up creating UserMessage row for deactivated user.
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test Message 1'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, force_text(message), negate=True)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, force_text(message))

        # Test sending a private message to soft deactivated user creates
        # UserMessage row.
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test PM'
        send_personal_message(message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_last_um_content(long_term_idle_user, force_text(message))

        # Test UserMessage row is created while user is deactivated if
        # user itself is mentioned.
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**King Hamlet** mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, force_text(message))
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, force_text(message))

        # Test UserMessage row is not created while user is deactivated if
        # anyone is mentioned but the user.
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**Cordelia Lear**  mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, force_text(message), negate=True)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, force_text(message))

        # Test UserMessage row is created while user is deactivated if
        # there is a wildcard mention such as @all or @everyone
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**all** mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, force_text(message))
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, force_text(message))

        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**everyone** mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, force_text(message))
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, force_text(message))

        # Test UserMessage row is not created while user is deactivated if there
        # is a alert word in message.
        do_add_alert_words(long_term_idle_user, ['test_alert_word'])
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Testing test_alert_word'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, force_text(message))
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, force_text(message))

        # Test UserMessage row is created while user is deactivated if
        # message is a me message.
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = '/me says test'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, force_text(message), negate=True)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, force_text(message))
