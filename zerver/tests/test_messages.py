# -*- coding: utf-8 -*-
from __future__ import absolute_import
from django.db.models import Q
from django.conf import settings
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.utils import timezone
from zerver.lib import bugdown
from zerver.decorator import JsonableError
from zerver.lib.test_runner import slow
from zilencer.models import Deployment

from zerver.lib.message import (
    MessageDict,
    message_to_dict,
)

from zerver.lib.test_helpers import (
    get_user_messages,
    make_client,
    message_ids, message_stream_count,
    most_recent_message,
    most_recent_usermessage,
    queries_captured,
)

from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zerver.models import (
    MAX_MESSAGE_LENGTH, MAX_SUBJECT_LENGTH,
    Message, Realm, Recipient, Stream, UserMessage, UserProfile, Attachment, RealmAlias,
    get_realm, get_stream, get_user_profile_by_email,
    Reaction, sew_messages_and_reactions
)

from zerver.lib.actions import (
    check_message,
    check_send_message,
    extract_recipients,
    do_create_user,
    get_client,
    get_recipient,
)

from zerver.lib.upload import create_attachment

from zerver.views.messages import create_mirrored_message_users

import datetime
import DNS
import mock
import time
import ujson
from six.moves import range
from typing import Any, List, Optional, Text

class TopicHistoryTest(ZulipTestCase):
    def test_topics_history(self):
        # type: () -> None
        # verified: int(UserMessage.flags.read) == 1
        email = 'iago@zulip.com'
        stream_name = 'Verona'
        self.login(email)

        user_profile = get_user_profile_by_email(email)
        stream = get_stream(stream_name, user_profile.realm)
        recipient = get_recipient(Recipient.STREAM, stream.id)

        def create_test_message(topic, read, starred=False):
            # type: (str, bool, bool) -> None

            hamlet = get_user_profile_by_email('hamlet@zulip.com')
            message = Message.objects.create(
                sender=hamlet,
                recipient=recipient,
                subject=topic,
                content='whatever',
                pub_date=timezone.now(),
                sending_client=get_client('whatever'),
            )
            flags = 0
            if read:
                flags |= UserMessage.flags.read

            # use this to make sure our query isn't confused
            # by other flags
            if starred:
                flags |= UserMessage.flags.starred

            UserMessage.objects.create(
                user_profile=user_profile,
                message=message,
                flags=flags,
            )

        create_test_message('topic2', read=False)
        create_test_message('toPIc1', read=False, starred=True)
        create_test_message('topic2', read=False)
        create_test_message('topic2', read=True)
        create_test_message('topic2', read=False, starred=True)
        create_test_message('Topic2', read=False)
        create_test_message('already_read', read=True)

        endpoint = '/json/users/me/%d/topics' % (stream.id,)
        result = self.client_get(endpoint, dict())
        self.assert_json_success(result)
        history = ujson.loads(result.content)['topics']

        # We only look at the most recent three topics, because
        # the prior fixture data may be unreliable.
        self.assertEqual(history[:3], [
            [u'already_read', 0],
            [u'Topic2', 4],
            [u'toPIc1', 1],
        ])

    def test_bad_stream_id(self):
        # type: () -> None
        email = 'iago@zulip.com'
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
        realm = Realm.objects.create(string_id=domain, domain=domain, invite_required=False)
        RealmAlias.objects.create(realm=realm, domain=domain)
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
        self.register(email, 'test')
        return get_user_profile_by_email(email)

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

        def assert_disallowed():
            # type: () -> Any
            return self.assertRaisesRegex(
                JsonableError,
                'You can\'t send private messages outside of your organization.')

        random_zulip_email = 'random@zulip.com'
        user1_email = 'user1@1.example.com'
        user1a_email = 'user1a@1.example.com'
        user2_email = 'user2@2.example.com'
        user3_email = 'user3@3.example.com'
        feedback_email = 'feedback@zulip.com'
        support_email = 'support@3.example.com' # note: not zulip.com

        self.create_user(random_zulip_email)
        user1 = self.create_user(user1_email)
        user1a = self.create_user(user1a_email)
        user2 = self.create_user(user2_email)
        self.create_user(user3_email)
        feedback_bot = get_user_profile_by_email(feedback_email)
        support_bot = self.create_user(support_email)

        # Users can PM themselves
        self.send_message(user1_email, user1_email, Recipient.PERSONAL)
        assert_message_received(user1, user1)

        # Users on the same realm can PM each other
        self.send_message(user1_email, user1a_email, Recipient.PERSONAL)
        assert_message_received(user1a, user1)

        # Cross-realm bots in the zulip.com realm can PM any realm
        self.send_message(feedback_email, user2_email, Recipient.PERSONAL)
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
        with assert_disallowed():
            self.send_message(user1_email, [user3_email, support_email], Recipient.PERSONAL)

        # Users on three different realms can't PM each other,
        # even if one of the users is a cross-realm bot.
        with assert_disallowed():
            self.send_message(user1_email, [user2_email, feedback_email],
                              Recipient.PERSONAL)

        with assert_disallowed():
            self.send_message(feedback_email, [user1_email, user2_email],
                              Recipient.PERSONAL)

        # Users on the different realms can not PM each other
        with assert_disallowed():
            self.send_message(user1_email, user2_email, Recipient.PERSONAL)

        # Users on non-zulip realms can't PM "ordinary" Zulip users
        with assert_disallowed():
            self.send_message(user1_email, random_zulip_email, Recipient.PERSONAL)

        # Users on three different realms can not PM each other
        with assert_disallowed():
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
        self.register("test@zulip.com", "test")
        user_profile = get_user_profile_by_email('test@zulip.com')
        old_messages_count = message_stream_count(user_profile)
        self.send_message("test@zulip.com", "test@zulip.com", Recipient.PERSONAL)
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
        self.register("test1@zulip.com", "test1")

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
        # type: (Text, Text, Text) -> None
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

    @slow("assert_personal checks several profiles")
    def test_personal(self):
        # type: () -> None
        """
        If you send a personal, only you and the recipient see it.
        """
        self.login("hamlet@zulip.com")
        self.assert_personal("hamlet@zulip.com", "othello@zulip.com")

    @slow("assert_personal checks several profiles")
    def test_non_ascii_personal(self):
        # type: () -> None
        """
        Sending a PM containing non-ASCII characters succeeds.
        """
        self.login("hamlet@zulip.com")
        self.assert_personal("hamlet@zulip.com", "othello@zulip.com", u"hümbüǵ")

class StreamMessagesTest(ZulipTestCase):

    def assert_stream_message(self, stream_name, subject="test subject",
                              content="test content"):
        # type: (Text, Text, Text) -> None
        """
        Check that messages sent to a stream reach all subscribers to that stream.
        """
        realm = get_realm('zulip')
        subscribers = self.users_subscribed_to_stream(stream_name, realm)
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

    def test_not_too_many_queries(self):
        # type: () -> None
        recipient_list  = ['hamlet@zulip.com', 'iago@zulip.com', 'cordelia@zulip.com', 'othello@zulip.com']
        for email in recipient_list:
            self.subscribe_to_stream(email, "Denmark")

        sender_email = 'hamlet@zulip.com'
        sender = get_user_profile_by_email(sender_email)
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

        send_message() # prime the caches
        with queries_captured() as queries:
            send_message()

        self.assert_max_length(queries, 14)

    def test_stream_message_dict(self):
        # type: () -> None
        user_profile = get_user_profile_by_email("iago@zulip.com")
        self.subscribe_to_stream(user_profile.email, "Denmark")
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM,
                          content="whatever", subject="my topic")
        message = most_recent_message(user_profile)
        row = Message.get_raw_db_rows([message.id])[0]
        dct = MessageDict.build_dict_from_raw_db_row(row, apply_markdown=True)
        self.assertEqual(dct['display_recipient'], 'Denmark')

        stream = get_stream('Denmark', user_profile.realm)
        self.assertEqual(dct['stream_id'], stream.id)

    def test_stream_message_unicode(self):
        # type: () -> None
        user_profile = get_user_profile_by_email("iago@zulip.com")
        self.subscribe_to_stream(user_profile.email, "Denmark")
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM,
                          content="whatever", subject="my topic")
        message = most_recent_message(user_profile)
        self.assertEqual(str(message),
                         u'<Message: Denmark / my topic / '
                         '<UserProfile: hamlet@zulip.com <Realm: zulip 1>>>')

    def test_message_mentions(self):
        # type: () -> None
        user_profile = get_user_profile_by_email("iago@zulip.com")
        self.subscribe_to_stream(user_profile.email, "Denmark")
        self.send_message("hamlet@zulip.com", "Denmark", Recipient.STREAM,
                          content="test @**Iago** rules")
        message = most_recent_message(user_profile)
        assert(UserMessage.objects.get(user_profile=user_profile, message=message).flags.mentioned.is_set)

    def test_stream_message_mirroring(self):
        # type: () -> None
        from zerver.lib.actions import do_change_is_admin
        email = "iago@zulip.com"
        user_profile = get_user_profile_by_email(email)

        do_change_is_admin(user_profile, True, 'api_super_user')
        result = self.client_post("/api/v1/messages", {"type": "stream",
                                                       "to": "Verona",
                                                       "sender": "cordelia@zulip.com",
                                                       "client": "test suite",
                                                       "subject": "announcement",
                                                       "content": "Everyone knows Iago rules",
                                                       "forged": "true"},
                                  **self.api_auth(email))
        self.assert_json_success(result)
        do_change_is_admin(user_profile, False, 'api_super_user')
        result = self.client_post("/api/v1/messages", {"type": "stream",
                                                       "to": "Verona",
                                                       "sender": "cordelia@zulip.com",
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
        self.login("hamlet@zulip.com")

        # Subscribe everyone to a stream with non-ASCII characters.
        non_ascii_stream_name = u"hümbüǵ"
        realm = get_realm("zulip")
        stream = self.make_stream(non_ascii_stream_name)
        for user_profile in UserProfile.objects.filter(realm=realm):
            self.subscribe_to_stream(user_profile.email, stream.name)

        self.assert_stream_message(non_ascii_stream_name, subject=u"hümbüǵ",
                                   content=u"hümbüǵ")

class MessageDictTest(ZulipTestCase):
    @slow('builds lots of messages')
    def test_bulk_message_fetching(self):
        # type: () -> None
        sender = get_user_profile_by_email('othello@zulip.com')
        receiver = get_user_profile_by_email('hamlet@zulip.com')
        pm_recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        stream_name = u'Çiğdem'
        stream = self.make_stream(stream_name)
        stream_recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        sending_client = make_client(name="test suite")

        for i in range(300):
            for recipient in [pm_recipient, stream_recipient]:
                message = Message(
                    sender=sender,
                    recipient=recipient,
                    subject='whatever',
                    content='whatever %d' % i,
                    pub_date=timezone.now(),
                    sending_client=sending_client,
                    last_edit_time=timezone.now(),
                    edit_history='[]'
                )
                message.save()

                Reaction.objects.create(user_profile=sender, message=message,
                                        emoji_name='simple_smile')

        ids = [row['id'] for row in Message.objects.all().values('id')]
        num_ids = len(ids)
        self.assertTrue(num_ids >= 600)

        t = time.time()
        with queries_captured() as queries:
            rows = list(Message.get_raw_db_rows(ids))

            for row in rows:
                MessageDict.build_dict_from_raw_db_row(row, False)

        delay = time.time() - t
        # Make sure we don't take longer than 1ms per message to extract messages.
        self.assertTrue(delay < 0.001 * num_ids)
        self.assert_max_length(queries, 11)
        self.assertEqual(len(rows), num_ids)

    def test_applying_markdown(self):
        # type: () -> None
        sender = get_user_profile_by_email('othello@zulip.com')
        receiver = get_user_profile_by_email('hamlet@zulip.com')
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        sending_client = make_client(name="test suite")
        message = Message(
            sender=sender,
            recipient=recipient,
            subject='whatever',
            content='hello **world**',
            pub_date=timezone.now(),
            sending_client=sending_client,
            last_edit_time=timezone.now(),
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

    def test_reaction(self):
        # type: () -> None
        sender = get_user_profile_by_email('othello@zulip.com')
        receiver = get_user_profile_by_email('hamlet@zulip.com')
        recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        sending_client = make_client(name="test suite")
        message = Message(
            sender=sender,
            recipient=recipient,
            subject='whatever',
            content='hello **world**',
            pub_date=timezone.now(),
            sending_client=sending_client,
            last_edit_time=timezone.now(),
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
        sender = get_user_profile_by_email('othello@zulip.com')
        receiver = get_user_profile_by_email('hamlet@zulip.com')
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
                    pub_date=timezone.now(),
                    sending_client=sending_client,
                    last_edit_time=timezone.now(),
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
        self.login("hamlet@zulip.com")
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
        email = "hamlet@zulip.com"
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
        email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(email)
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
        self.login("hamlet@zulip.com")
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
        self.login("hamlet@zulip.com")
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
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": "othello@zulip.com"})
        self.assert_json_success(result)

    def test_personal_message_to_nonexistent_user(self):
        # type: () -> None
        """
        Sending a personal message to an invalid email returns error JSON.
        """
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": "nonexistent"})
        self.assert_json_error(result, "Invalid email 'nonexistent'")

    def test_invalid_type(self):
        # type: () -> None
        """
        Sending a message of unknown type returns error JSON.
        """
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/messages", {"type": "invalid type",
                                                     "content": "Test message",
                                                     "client": "test suite",
                                                     "to": "othello@zulip.com"})
        self.assert_json_error(result, "Invalid message type")

    def test_empty_message(self):
        # type: () -> None
        """
        Sending a message that is empty or only whitespace should fail
        """
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": " ",
                                                     "client": "test suite",
                                                     "to": "othello@zulip.com"})
        self.assert_json_error(result, "Message must not be empty")

    def test_mirrored_huddle(self):
        # type: () -> None
        """
        Sending a mirrored huddle message works
        """
        self.login("starnine@mit.edu")
        result = self.client_post("/json/messages", {"type": "private",
                                                     "sender": "sipbtest@mit.edu",
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": ujson.dumps(["starnine@mit.edu",
                                                                        "espuser@mit.edu"])})
        self.assert_json_success(result)

    def test_mirrored_personal(self):
        # type: () -> None
        """
        Sending a mirrored personal message works
        """
        self.login("starnine@mit.edu")
        result = self.client_post("/json/messages", {"type": "private",
                                                     "sender": "sipbtest@mit.edu",
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": "starnine@mit.edu"})
        self.assert_json_success(result)

    def test_duplicated_mirrored_huddle(self):
        # type: () -> None
        """
        Sending two mirrored huddles in the row return the same ID
        """
        msg = {"type": "private",
               "sender": "sipbtest@mit.edu",
               "content": "Test message",
               "client": "zephyr_mirror",
               "to": ujson.dumps(["espuser@mit.edu",
                                  "starnine@mit.edu"])}

        with mock.patch('DNS.dnslookup', return_value=[['starnine:*:84233:101:Athena Consulting Exchange User,,,:/mit/starnine:/bin/bash']]):
            self.login("starnine@mit.edu")
            result1 = self.client_post("/json/messages", msg)
        with mock.patch('DNS.dnslookup', return_value=[['espuser:*:95494:101:Esp Classroom,,,:/mit/espuser:/bin/athena/bash']]):
            self.login("espuser@mit.edu")
            result2 = self.client_post("/json/messages", msg)
        self.assertEqual(ujson.loads(result1.content)['id'],
                         ujson.loads(result2.content)['id'])

    def test_strip_message(self):
        # type: () -> None
        """
        Sending a message longer than the maximum message length succeeds but is
        truncated.
        """
        self.login("hamlet@zulip.com")
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
        self.login("hamlet@zulip.com")
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
        self.login("hamlet@zulip.com")
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
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "subject": "Test subject",
                                                     "forged": True})
        self.assert_json_error(result, "User not authorized for this query")

    def test_send_message_as_not_superuser_to_different_domain(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        result = self.client_post("/json/messages", {"type": "stream",
                                                     "to": "Verona",
                                                     "client": "test suite",
                                                     "content": "Test message",
                                                     "subject": "Test subject",
                                                     "realm_str": "mit"})
        self.assert_json_error(result, "User not authorized for this query")

    def test_send_message_as_superuser_to_domain_that_dont_exist(self):
        # type: () -> None
        email = "emailgateway@zulip.com"
        user = get_user_profile_by_email(email)
        password = "test_password"
        user.set_password(password)
        user.is_api_super_user = True
        user.save()
        self.login(email, password)
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
        self.login("starnine@mit.edu")
        result = self.client_post("/json/messages", {"type": "private",
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": "starnine@mit.edu"})
        self.assert_json_error(result, "Missing sender")

    def test_send_message_as_not_superuser_when_type_is_not_private(self):
        # type: () -> None
        self.login("starnine@mit.edu")
        result = self.client_post("/json/messages", {"type": "not-private",
                                                     "sender": "sipbtest@mit.edu",
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": "starnine@mit.edu"})
        self.assert_json_error(result, "User not authorized for this query")

    @mock.patch("zerver.views.messages.create_mirrored_message_users")
    def test_send_message_create_mirrored_message_user_returns_invalid_input(self, create_mirrored_message_users_mock):
        # type: (Any) -> None
        create_mirrored_message_users_mock.return_value = (False, True)
        self.login("starnine@mit.edu")
        result = self.client_post("/json/messages", {"type": "private",
                                                     "sender": "sipbtest@mit.edu",
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": "starnine@mit.edu"})
        self.assert_json_error(result, "Invalid mirrored message")

    @mock.patch("zerver.views.messages.create_mirrored_message_users")
    def test_send_message_when_client_is_zephyr_mirror_but_string_id_is_not_zephyr(self, create_mirrored_message_users_mock):
        # type: (Any) -> None
        create_mirrored_message_users_mock.return_value = (True, True)
        email = "starnine@mit.edu"
        user = get_user_profile_by_email(email)
        user.realm.string_id = 'not_zephyr'
        user.realm.save()
        self.login("starnine@mit.edu")
        result = self.client_post("/json/messages", {"type": "private",
                                                     "sender": "sipbtest@mit.edu",
                                                     "content": "Test message",
                                                     "client": "zephyr_mirror",
                                                     "to": "starnine@mit.edu"}, name='gownooo')
        self.assert_json_error(result, "Invalid mirrored realm")

    def test_send_message_irc_mirror(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        bot_info = {
            'full_name': 'IRC bot',
            'short_name': 'irc',
        }
        result = self.client_post("/json/bots", bot_info)
        self.assert_json_success(result)

        email = "irc-bot@zulip.testserver"
        user = get_user_profile_by_email(email)
        user.is_api_super_user = True
        user.save()
        user = get_user_profile_by_email(email)
        self.subscribe_to_stream(email, "#IRCland", realm=user.realm)
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
        self.login("hamlet@zulip.com")
        msg_id = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
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
        self.login("hamlet@zulip.com")
        msg_id = self.send_message("hamlet@zulip.com", "cordelia@zulip.com", Recipient.PERSONAL,
                                   subject="editing", content="**before** edit")
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_success(result)
        data = ujson.loads(result.content)
        self.assertEqual(data['raw_content'], '**before** edit')

        # Test error cases
        result = self.client_get('/json/messages/999999')
        self.assert_json_error(result, 'Invalid message(s)')

        self.login("cordelia@zulip.com")
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_success(result)

        self.login("othello@zulip.com")
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_error(result, 'Invalid message(s)')

    def test_fetch_raw_message_stream_wrong_realm(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        self.login(email)
        stream = self.make_stream('public_stream')
        self.subscribe_to_stream(email, stream.name)
        msg_id = self.send_message(email, stream.name, Recipient.STREAM,
                                   subject="test", content="test")
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_success(result)

        self.login("sipbtest@mit.edu")
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_error(result, 'Invalid message(s)')

    def test_fetch_raw_message_private_stream(self):
        # type: () -> None
        email = "hamlet@zulip.com"
        self.login(email)
        stream = self.make_stream('private_stream', invite_only=True)
        self.subscribe_to_stream(email, stream.name)
        msg_id = self.send_message(email, stream.name, Recipient.STREAM,
                                   subject="test", content="test")
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_success(result)
        self.login("othello@zulip.com")
        result = self.client_get('/json/messages/' + str(msg_id))
        self.assert_json_error(result, 'Invalid message(s)')

    def test_edit_message_no_permission(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        msg_id = self.send_message("iago@zulip.com", "Scotland", Recipient.STREAM,
                                   subject="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': 'content after edit',
        })
        self.assert_json_error(result, "You don't have permission to edit this message")

    def test_edit_message_no_changes(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        msg_id = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
                                   subject="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
        })
        self.assert_json_error(result, "Nothing to change")

    def test_edit_message_no_topic(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        msg_id = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
                                   subject="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'subject': ' '
        })
        self.assert_json_error(result, "Topic can't be empty")

    def test_edit_message_no_content(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        msg_id = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
                                   subject="editing", content="before edit")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'content': ' '
        })
        self.assert_json_success(result)
        content = Message.objects.filter(id=msg_id).values_list('content', flat = True)[0]
        self.assertEqual(content, "(deleted)")

    def test_edit_message_history(self):
        # type: () -> None
        self.login("hamlet@zulip.com")
        msg_id = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
                                   subject="editing", content="content before edit")
        new_content = 'content after edit'

        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id, 'content': new_content
        })
        self.assert_json_success(result)

        message_edit_history = self.client_get("/json/messages/" + str(msg_id) + "/history")
        json_response = ujson.loads(message_edit_history.content.decode('utf-8'))
        message_history = json_response['message_history']

        # Check content of message after edit.
        self.assertEqual(message_history[0]['rendered_content'],
                         '<p>content before edit</p>')
        self.assertEqual(message_history[1]['rendered_content'],
                         '<p>content after edit</p>')
        self.assertEqual(message_history[1]['content_html_diff'],
                         '<p>content <span class="highlight_text_replaced">after</span> edit</p>')

        # Check content of message before edit.
        self.assertEqual(message_history[1]['prev_rendered_content'],
                         '<p>content before edit</p>')

    def test_edit_cases(self):
        # type: () -> None
        """This test verifies the accuracy of construction of Zulip's edit
        history data structures."""
        self.login("hamlet@zulip.com")
        hamlet = get_user_profile_by_email("hamlet@zulip.com")
        msg_id = self.send_message("hamlet@zulip.com", "Scotland", Recipient.STREAM,
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

        self.login("iago@zulip.com")
        result = self.client_patch("/json/messages/" + str(msg_id), {
            'message_id': msg_id,
            'subject': 'subject 4',
        })
        self.assert_json_success(result)
        history = ujson.loads(Message.objects.get(id=msg_id).edit_history)
        self.assertEqual(history[0]['prev_subject'], 'subject 3')
        self.assertEqual(history[0]['user_id'], get_user_profile_by_email("iago@zulip.com").id)

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

        self.login("iago@zulip.com")
        # send a message in the past
        id_ = self.send_message("iago@zulip.com", "Scotland", Recipient.STREAM,
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
        do_edit_message_assert_error(id_, 'E', "Your organization has turned off message editing.", True)
        set_message_editing_params(False, 120)
        do_edit_message_assert_error(id_, 'F', "Your organization has turned off message editing.", True)
        set_message_editing_params(False, 0)
        do_edit_message_assert_error(id_, 'G', "Your organization has turned off message editing.", True)

    def test_propagate_topic_forward(self):
        # type: () -> None
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

class MirroredMessageUsersTest(TestCase):
    class Request(object):
        pass

    def test_invalid_sender(self):
        # type: () -> None
        user = get_user_profile_by_email('hamlet@zulip.com')
        recipients = [] # type: List[Text]
        request = self.Request()
        request.POST = dict() # no sender

        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user, recipients)

        self.assertEqual(valid_input, False)
        self.assertEqual(mirror_sender, None)

    def test_invalid_client(self):
        # type: () -> None
        client = get_client(name='banned_mirror') # Invalid!!!

        user = get_user_profile_by_email('hamlet@zulip.com')
        sender = user

        recipients = [] # type: List[Text]
        request = self.Request()
        request.POST = dict(
            sender=sender.email,
            type='private')
        request.client = client

        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user, recipients)

        self.assertEqual(valid_input, False)
        self.assertEqual(mirror_sender, None)

    def test_invalid_email(self):
        # type: () -> None
        invalid_email = 'alice AT example.com'
        recipients = [invalid_email]

        # We use an MIT user here to maximize code coverage
        user = get_user_profile_by_email('starnine@mit.edu')
        sender = user

        for client_name in ['zephyr_mirror', 'irc_mirror', 'jabber_mirror']:
            client = get_client(name=client_name)

            request = self.Request()
            request.POST = dict(
                sender=sender.email,
                type='private')
            request.client = client

            (valid_input, mirror_sender) = \
                create_mirrored_message_users(request, user, recipients)

            self.assertEqual(valid_input, False)
            self.assertEqual(mirror_sender, None)

    @mock.patch('DNS.dnslookup', return_value=[['sipbtest:*:20922:101:Fred Sipb,,,:/mit/sipbtest:/bin/athena/tcsh']])
    def test_zephyr_mirror_new_recipient(self, ignored):
        # type: (Any) -> None
        """Test mirror dummy user creation for PM recipients"""
        client = get_client(name='zephyr_mirror')

        user = get_user_profile_by_email('starnine@mit.edu')
        sender = get_user_profile_by_email('sipbtest@mit.edu')
        new_user_email = 'bob_the_new_user@mit.edu'

        recipients = [user.email, new_user_email]

        # Now make the request.
        request = self.Request()
        request.POST = dict(
            sender=sender.email,
            type='private')
        request.client = client

        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user, recipients)

        self.assertTrue(valid_input)
        self.assertEqual(mirror_sender, sender)

        realm_users = UserProfile.objects.filter(realm=sender.realm)
        realm_emails = {user.email for user in realm_users}
        self.assertIn(user.email, realm_emails)
        self.assertIn(new_user_email, realm_emails)

        bob = get_user_profile_by_email(new_user_email)
        self.assertTrue(bob.is_mirror_dummy)

    @mock.patch('DNS.dnslookup', return_value=[['sipbtest:*:20922:101:Fred Sipb,,,:/mit/sipbtest:/bin/athena/tcsh']])
    def test_zephyr_mirror_new_sender(self, ignored):
        # type: (Any) -> None
        """Test mirror dummy user creation for sender when sending to stream"""
        client = get_client(name='zephyr_mirror')

        user = get_user_profile_by_email('starnine@mit.edu')
        sender_email = 'new_sender@mit.edu'

        recipients = ['stream_name']

        # Now make the request.
        request = self.Request()
        request.POST = dict(
            sender=sender_email,
            type='stream')
        request.client = client

        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user, recipients)

        self.assertTrue(valid_input)
        self.assertEqual(mirror_sender.email, sender_email)
        self.assertTrue(mirror_sender.is_mirror_dummy)

    def test_irc_mirror(self):
        # type: () -> None
        client = get_client(name='irc_mirror')

        sender = get_user_profile_by_email('hamlet@zulip.com')
        user = sender

        recipients = ['alice@zulip.com', 'bob@irc.zulip.com', 'cordelia@zulip.com']

        # Now make the request.
        request = self.Request()
        request.POST = dict(
            sender=sender.email,
            type='private')
        request.client = client

        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user, recipients)

        self.assertEqual(valid_input, True)
        self.assertEqual(mirror_sender, sender)

        realm_users = UserProfile.objects.filter(realm=sender.realm)
        realm_emails = {user.email for user in realm_users}
        self.assertIn('alice@zulip.com', realm_emails)
        self.assertIn('bob@irc.zulip.com', realm_emails)

        bob = get_user_profile_by_email('bob@irc.zulip.com')
        self.assertTrue(bob.is_mirror_dummy)

    def test_jabber_mirror(self):
        # type: () -> None
        client = get_client(name='jabber_mirror')

        sender = get_user_profile_by_email('hamlet@zulip.com')
        user = sender

        recipients = ['alice@zulip.com', 'bob@zulip.com', 'cordelia@zulip.com']

        # Now make the request.
        request = self.Request()
        request.POST = dict(
            sender=sender.email,
            type='private')
        request.client = client

        (valid_input, mirror_sender) = \
            create_mirrored_message_users(request, user, recipients)

        self.assertEqual(valid_input, True)
        self.assertEqual(mirror_sender, sender)

        realm_users = UserProfile.objects.filter(realm=sender.realm)
        realm_emails = {user.email for user in realm_users}
        self.assertIn('alice@zulip.com', realm_emails)
        self.assertIn('bob@zulip.com', realm_emails)

        bob = get_user_profile_by_email('bob@zulip.com')
        self.assertTrue(bob.is_mirror_dummy)

class StarTests(ZulipTestCase):

    def change_star(self, messages, add=True):
        # type: (List[int], bool) -> HttpResponse
        return self.client_post("/json/messages/flags",
                                {"messages": ujson.dumps(messages),
                                 "op": "add" if add else "remove",
                                 "flag": "starred"})

    def test_change_star(self):
        # type: () -> None
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

    def test_change_star_public_stream_historical(self):
        # type: () -> None
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        stream_name = "new_stream"
        self.subscribe_to_stream("hamlet@zulip.com", stream_name)
        self.login("hamlet@zulip.com")
        message_ids = [self.send_message("hamlet@zulip.com", stream_name,
                                         Recipient.STREAM, "test")]
        # Send a second message so we can verify it isn't modified
        other_message_ids = [self.send_message("hamlet@zulip.com", stream_name,
                                               Recipient.STREAM, "test_unused")]

        # Now login as another user who wasn't on that stream
        self.login("cordelia@zulip.com")

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

        for msg in self.get_old_messages():
            if msg['id'] in message_ids + other_message_ids:
                self.assertEqual(set(msg['flags']), {'starred', 'historical', 'read'})
            else:
                self.assertEqual(msg['flags'], ['read'])

        result = self.change_star(message_ids, False)
        self.assert_json_success(result)

        # But it still doesn't work if you're in another realm
        self.login("sipbtest@mit.edu")
        result = self.change_star(message_ids)
        self.assert_json_error(result, 'Invalid message(s)')

    def test_change_star_private_message_security(self):
        # type: () -> None
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        self.login("hamlet@zulip.com")
        message_ids = [self.send_message("hamlet@zulip.com", "hamlet@zulip.com",
                                         Recipient.PERSONAL, "test")]

        # Starring private messages you didn't receive fails.
        self.login("cordelia@zulip.com")
        result = self.change_star(message_ids)
        self.assert_json_error(result, 'Invalid message(s)')

    def test_change_star_private_stream_security(self):
        # type: () -> None
        stream_name = "private_stream"
        self.make_stream(stream_name, invite_only=True)
        self.subscribe_to_stream("hamlet@zulip.com", stream_name)
        self.login("hamlet@zulip.com")
        message_ids = [self.send_message("hamlet@zulip.com", stream_name,
                                         Recipient.STREAM, "test")]

        # Starring private stream messages you received works
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        # Starring private stream messages you didn't receive fails.
        self.login("cordelia@zulip.com")
        result = self.change_star(message_ids)
        self.assert_json_error(result, 'Invalid message(s)')

    def test_new_message(self):
        # type: () -> None
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
        sender_email = "hamlet@zulip.com"
        user_profile = get_user_profile_by_email(sender_email)
        sample_size = 10
        dummy_files = [
            ('zulip.txt', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt', sample_size),
            ('temp_file.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py', sample_size),
            ('abc.py', '1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py', sample_size)
        ]

        for file_name, path_id, size in dummy_files:
            create_attachment(file_name, path_id, user_profile, size)

        # Send message referring the attachment
        self.subscribe_to_stream(sender_email, "Denmark")

        body = "Some files here ...[zulip.txt](http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt)" +  \
               "http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py.... Some more...." + \
               "http://localhost:9991/user_uploads/1/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py"

        self.send_message(sender_email, "Denmark", Recipient.STREAM, body, "test")

        for file_name, path_id, size in dummy_files:
            attachment = Attachment.objects.get(path_id=path_id)
            self.assertTrue(attachment.is_claimed())

class LogDictTest(ZulipTestCase):
    def test_to_log_dict(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        stream_name = 'Denmark'
        topic_name = 'Copenhagen'
        content = 'find me some good coffee shops'
        # self.login("hamlet@zulip.com")
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
        self.assertEqual(dct['sender_domain'], 'zulip.com')
        self.assertEqual(dct['sender_email'], 'hamlet@zulip.com')
        self.assertEqual(dct['sender_full_name'], 'King Hamlet')
        self.assertEqual(dct['sender_id'], get_user_profile_by_email(email).id)
        self.assertEqual(dct['sender_short_name'], 'hamlet')
        self.assertEqual(dct['sending_client'], 'test suite')
        self.assertEqual(dct['subject'], 'Copenhagen')
        self.assertEqual(dct['type'], 'stream')

class CheckMessageTest(ZulipTestCase):
    def test_basic_check_message_call(self):
        # type: () -> None
        sender = get_user_profile_by_email('othello@zulip.com')
        client = make_client(name="test suite")
        stream_name = u'España y Francia'
        self.make_stream(stream_name)
        message_type_name = 'stream'
        message_to = None
        message_to = [stream_name]
        subject_name = 'issue'
        message_content = 'whatever'
        ret = check_message(sender, client, message_type_name, message_to,
                            subject_name, message_content)
        self.assertEqual(ret['message'].sender.email, 'othello@zulip.com')

    def test_bot_pm_feature(self):
        # type: () -> None
        """We send a PM to a bot's owner if their bot sends a message to
        an unsubscribed stream"""
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
        client = make_client(name="test suite")
        stream_name = u'Россия'
        message_type_name = 'stream'
        message_to = None
        message_to = [stream_name]
        subject_name = 'issue'
        message_content = 'whatever'
        old_count = message_stream_count(parent)

        # Try sending to stream that doesn't exist sends a reminder to
        # the sender
        with self.assertRaises(JsonableError):
            check_message(sender, client, message_type_name, message_to,
                          subject_name, message_content)
        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 1)
        self.assertIn("that stream does not yet exist.", most_recent_message(parent).content)

        # Try sending to stream that exists with no subscribers soon
        # after; due to rate-limiting, this should send nothing.
        self.make_stream(stream_name)
        ret = check_message(sender, client, message_type_name, message_to,
                            subject_name, message_content)
        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 1)

        # Try sending to stream that exists with no subscribers longer
        # after; this should send an error to the bot owner that the
        # stream doesn't exist
        sender.last_reminder = sender.last_reminder - datetime.timedelta(hours=1)
        sender.save(update_fields=["last_reminder"])
        ret = check_message(sender, client, message_type_name, message_to,
                            subject_name, message_content)
        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 2)
        self.assertEqual(ret['message'].sender.email, 'othello-bot@zulip.com')
        self.assertIn("there are no subscribers to that stream", most_recent_message(parent).content)
