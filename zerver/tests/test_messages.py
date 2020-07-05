import datetime
from typing import Any, Dict, List, Union
from unittest import mock

import ujson
from django.http import HttpResponse
from django.test import override_settings
from django.utils.timezone import now as timezone_now

from analytics.lib.counts import COUNT_STATS
from analytics.models import RealmCount
from zerver.decorator import JsonableError
from zerver.lib.actions import (
    check_message,
    do_add_alert_words,
    do_change_stream_invite_only,
    do_claim_attachments,
    do_create_user,
    do_update_message,
    extract_private_recipients,
    extract_stream_indicator,
    gather_subscriptions_helper,
    get_active_presence_idle_user_ids,
    get_client,
    get_last_message_id,
    internal_prep_private_message,
    internal_prep_stream_message_by_name,
    internal_send_huddle_message,
    internal_send_private_message,
    internal_send_stream_message,
    internal_send_stream_message_by_name,
    send_rate_limited_pm_notification_to_bot_owner,
)
from zerver.lib.addressee import Addressee
from zerver.lib.markdown import MentionData
from zerver.lib.message import (
    MessageDict,
    bulk_access_messages,
    get_first_visible_message_id,
    maybe_update_first_visible_message_id,
    messages_for_ids,
    render_markdown,
    sew_messages_and_reactions,
    update_first_visible_message_id,
)
from zerver.lib.soft_deactivation import (
    add_missing_messages,
    do_soft_activate_users,
    do_soft_deactivate_users,
    reactivate_user_if_soft_deactivated,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    get_subscription,
    get_user_messages,
    make_client,
    message_stream_count,
    most_recent_message,
    most_recent_usermessage,
    queries_captured,
)
from zerver.lib.topic import DB_TOPIC_NAME
from zerver.lib.types import DisplayRecipientT, UserDisplayRecipient
from zerver.lib.upload import create_attachment
from zerver.lib.url_encoding import near_message_url
from zerver.models import (
    Attachment,
    Message,
    Reaction,
    Realm,
    RealmAuditLog,
    RealmDomain,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserPresence,
    UserProfile,
    bulk_get_huddle_user_ids,
    flush_per_request_caches,
    get_display_recipient,
    get_huddle_user_ids,
    get_realm,
    get_stream,
    get_system_bot,
    get_user,
)


class MiscMessageTest(ZulipTestCase):
    def test_get_last_message_id(self) -> None:
        self.assertEqual(
            get_last_message_id(),
            Message.objects.latest('id').id,
        )

        Message.objects.all().delete()

        self.assertEqual(get_last_message_id(), -1)

class TestCrossRealmPMs(ZulipTestCase):
    def make_realm(self, domain: str) -> Realm:
        realm = Realm.objects.create(string_id=domain, invite_required=False)
        RealmDomain.objects.create(realm=realm, domain=domain)
        return realm

    def create_user(self, email: str) -> UserProfile:
        subdomain = email.split("@")[1]
        self.register(email, 'test', subdomain=subdomain)
        return get_user(email, get_realm(subdomain))

    @override_settings(CROSS_REALM_BOT_EMAILS=['notification-bot@zulip.com',
                                               'welcome-bot@zulip.com',
                                               'support@3.example.com'])
    def test_realm_scenarios(self) -> None:
        self.make_realm('1.example.com')
        r2 = self.make_realm('2.example.com')
        self.make_realm('3.example.com')

        def assert_message_received(to_user: UserProfile, from_user: UserProfile) -> None:
            messages = get_user_messages(to_user)
            self.assertEqual(messages[-1].sender.id, from_user.id)

        def assert_invalid_user() -> Any:
            return self.assertRaisesRegex(
                JsonableError,
                'Invalid user ID ')

        user1_email = 'user1@1.example.com'
        user1a_email = 'user1a@1.example.com'
        user2_email = 'user2@2.example.com'
        user3_email = 'user3@3.example.com'
        notification_bot_email = 'notification-bot@zulip.com'
        support_email = 'support@3.example.com'  # note: not zulip.com

        user1 = self.create_user(user1_email)
        user1a = self.create_user(user1a_email)
        user2 = self.create_user(user2_email)
        user3 = self.create_user(user3_email)
        notification_bot = get_system_bot(notification_bot_email)
        with self.settings(CROSS_REALM_BOT_EMAILS=['notification-bot@zulip.com', 'welcome-bot@zulip.com']):
            # HACK: We should probably be creating this "bot" user another
            # way, but since you can't register a user with a
            # cross-realm email, we need to hide this for now.
            support_bot = self.create_user(support_email)

        # Users can PM themselves
        self.send_personal_message(user1, user1)
        assert_message_received(user1, user1)

        # Users on the same realm can PM each other
        self.send_personal_message(user1, user1a)
        assert_message_received(user1a, user1)

        # Cross-realm bots in the zulip.com realm can PM any realm
        # (They need lower level APIs to do this.)
        internal_send_private_message(
            realm=r2,
            sender=get_system_bot(notification_bot_email),
            recipient_user=get_user(user2_email, r2),
            content='bla',
        )
        assert_message_received(user2, notification_bot)

        # All users can PM cross-realm bots in the zulip.com realm
        self.send_personal_message(user1, notification_bot)
        assert_message_received(notification_bot, user1)

        # Users can PM cross-realm bots on non-zulip realms.
        # (The support bot represents some theoretical bot that we may
        # create in the future that does not have zulip.com as its realm.)
        self.send_personal_message(user1,  support_bot)
        assert_message_received(support_bot, user1)

        # Allow sending PMs to two different cross-realm bots simultaneously.
        # (We don't particularly need this feature, but since users can
        # already individually send PMs to cross-realm bots, we shouldn't
        # prevent them from sending multiple bots at once.  We may revisit
        # this if it's a nuisance for huddles.)
        self.send_huddle_message(user1, [notification_bot, support_bot])
        assert_message_received(notification_bot, user1)
        assert_message_received(support_bot, user1)

        # Prevent old loophole where I could send PMs to other users as long
        # as I copied a cross-realm bot from the same realm.
        with assert_invalid_user():
            self.send_huddle_message(user1, [user3, support_bot])

        # Users on three different realms can't PM each other,
        # even if one of the users is a cross-realm bot.
        with assert_invalid_user():
            self.send_huddle_message(user1, [user2, notification_bot])

        with assert_invalid_user():
            self.send_huddle_message(notification_bot, [user1, user2])

        # Users on the different realms cannot PM each other
        with assert_invalid_user():
            self.send_personal_message(user1, user2)

        # Users on non-zulip realms can't PM "ordinary" Zulip users
        with assert_invalid_user():
            self.send_personal_message(user1, self.example_user('hamlet'))

        # Users on three different realms cannot PM each other
        with assert_invalid_user():
            self.send_huddle_message(user1, [user2, user3])

class TestAddressee(ZulipTestCase):
    def test_addressee_for_user_ids(self) -> None:
        realm = get_realm('zulip')
        user_ids = [self.example_user('cordelia').id,
                    self.example_user('hamlet').id,
                    self.example_user('othello').id]

        result = Addressee.for_user_ids(user_ids=user_ids, realm=realm)
        user_profiles = result.user_profiles()
        result_user_ids = [user_profiles[0].id, user_profiles[1].id,
                           user_profiles[2].id]

        self.assertEqual(set(result_user_ids), set(user_ids))

    def test_addressee_for_user_ids_nonexistent_id(self) -> None:
        def assert_invalid_user_id() -> Any:
            return self.assertRaisesRegex(
                JsonableError,
                'Invalid user ID ')

        with assert_invalid_user_id():
            Addressee.for_user_ids(user_ids=[779], realm=get_realm('zulip'))

    def test_addressee_legacy_build_for_user_ids(self) -> None:
        realm = get_realm('zulip')
        self.login('hamlet')
        user_ids = [self.example_user('cordelia').id,
                    self.example_user('othello').id]

        result = Addressee.legacy_build(
            sender=self.example_user('hamlet'), message_type_name='private',
            message_to=user_ids, topic_name='random_topic',
            realm=realm,
        )
        user_profiles = result.user_profiles()
        result_user_ids = [user_profiles[0].id, user_profiles[1].id]

        self.assertEqual(set(result_user_ids), set(user_ids))

    def test_addressee_legacy_build_for_stream_id(self) -> None:
        realm = get_realm('zulip')
        self.login('iago')
        sender = self.example_user('iago')
        self.subscribe(sender, "Denmark")
        stream = get_stream('Denmark', realm)

        result = Addressee.legacy_build(
            sender=sender, message_type_name='stream',
            message_to=[stream.id], topic_name='random_topic',
            realm=realm,
        )

        stream_id = result.stream_id()
        self.assertEqual(stream.id, stream_id)

class InternalPrepTest(ZulipTestCase):

    def test_returns_for_internal_sends(self) -> None:
        # For our internal_send_* functions we return
        # if the prep stages fail.  This is mostly defensive
        # code, since we are generally creating the messages
        # ourselves, but we want to make sure that the functions
        # won't actually explode if we give them bad content.
        bad_content = ''
        realm = get_realm('zulip')
        cordelia = self.example_user('cordelia')
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        stream = get_stream('Verona', realm)

        with mock.patch('logging.exception') as m:
            internal_send_private_message(
                realm=realm,
                sender=cordelia,
                recipient_user=hamlet,
                content=bad_content,
            )

        m.assert_called_once_with(
            "Error queueing internal message by %s: %s",
            "cordelia@zulip.com",
            "Message must not be empty",
        )

        with mock.patch('logging.exception') as m:
            internal_send_huddle_message(
                realm=realm,
                sender=cordelia,
                emails=[hamlet.email, othello.email],
                content=bad_content,
            )

        m.assert_called_once_with(
            "Error queueing internal message by %s: %s",
            "cordelia@zulip.com",
            "Message must not be empty",
        )

        with mock.patch('logging.exception') as m:
            internal_send_stream_message(
                realm=realm,
                sender=cordelia,
                topic='whatever',
                content=bad_content,
                stream=stream,
            )

        m.assert_called_once_with(
            "Error queueing internal message by %s: %s",
            "cordelia@zulip.com",
            "Message must not be empty",
        )

        with mock.patch('logging.exception') as m:
            internal_send_stream_message_by_name(
                realm=realm,
                sender=cordelia,
                stream_name=stream.name,
                topic='whatever',
                content=bad_content,
            )

        m.assert_called_once_with(
            "Error queueing internal message by %s: %s",
            "cordelia@zulip.com",
            "Message must not be empty",
        )

    def test_error_handling(self) -> None:
        realm = get_realm('zulip')
        sender = self.example_user('cordelia')
        recipient_user = self.example_user('hamlet')
        content = 'x' * 15000

        result = internal_prep_private_message(
            realm=realm,
            sender=sender,
            recipient_user=recipient_user,
            content=content)
        assert result is not None
        message = result['message']
        self.assertIn('message was too long', message.content)

        # Simulate sending a message to somebody not in the
        # realm of the sender.
        recipient_user = self.mit_user('starnine')
        with mock.patch('logging.exception') as logging_mock:
            result = internal_prep_private_message(
                realm=realm,
                sender=sender,
                recipient_user=recipient_user,
                content=content)
        logging_mock.assert_called_once_with(
            "Error queueing internal message by %s: %s",
            "cordelia@zulip.com",
            "You can't send private messages outside of your organization.",
        )

    def test_ensure_stream_gets_called(self) -> None:
        realm = get_realm('zulip')
        sender = self.example_user('cordelia')
        stream_name = 'test_stream'
        topic = 'whatever'
        content = 'hello'

        internal_prep_stream_message_by_name(
            realm=realm,
            sender=sender,
            stream_name=stream_name,
            topic=topic,
            content=content)

        # This would throw an error if the stream
        # wasn't automatically created.
        Stream.objects.get(name=stream_name, realm_id=realm.id)

class ExtractTest(ZulipTestCase):
    def test_extract_stream_indicator(self) -> None:
        self.assertEqual(
            extract_stream_indicator('development'),
            "development",
        )
        self.assertEqual(
            extract_stream_indicator('commas,are,fine'),
            "commas,are,fine",
        )
        self.assertEqual(
            extract_stream_indicator('"Who hasn\'t done this?"'),
            "Who hasn't done this?",
        )
        self.assertEqual(
            extract_stream_indicator("999"),
            999,
        )

        # For legacy reasons it's plausible that users will
        # put a single stream into an array and then encode it
        # as JSON.  We can probably eliminate this support
        # by mid 2020 at the latest.
        self.assertEqual(
            extract_stream_indicator('["social"]'),
            'social',
        )

        self.assertEqual(
            extract_stream_indicator("[123]"),
            123,
        )

        with self.assertRaisesRegex(JsonableError, 'Invalid data type for stream'):
            extract_stream_indicator('{}')

        with self.assertRaisesRegex(JsonableError, 'Invalid data type for stream'):
            extract_stream_indicator('[{}]')

        with self.assertRaisesRegex(JsonableError, 'Expected exactly one stream'):
            extract_stream_indicator('[1,2,"general"]')

    def test_extract_private_recipients_emails(self) -> None:

        # JSON list w/dups, empties, and trailing whitespace
        s = ujson.dumps([' alice@zulip.com ', ' bob@zulip.com ', '   ', 'bob@zulip.com'])
        # sorted() gets confused by extract_private_recipients' return type
        # For testing, ignorance here is better than manual casting
        result = sorted(extract_private_recipients(s))
        self.assertEqual(result, ['alice@zulip.com', 'bob@zulip.com'])

        # simple string with one name
        s = 'alice@zulip.com    '
        self.assertEqual(extract_private_recipients(s), ['alice@zulip.com'])

        # JSON-encoded string
        s = '"alice@zulip.com"'
        self.assertEqual(extract_private_recipients(s), ['alice@zulip.com'])

        # bare comma-delimited string
        s = 'bob@zulip.com, alice@zulip.com'
        result = sorted(extract_private_recipients(s))
        self.assertEqual(result, ['alice@zulip.com', 'bob@zulip.com'])

        # JSON-encoded, comma-delimited string
        s = '"bob@zulip.com,alice@zulip.com"'
        result = sorted(extract_private_recipients(s))
        self.assertEqual(result, ['alice@zulip.com', 'bob@zulip.com'])

        # Invalid data
        s = ujson.dumps(dict(color='red'))
        with self.assertRaisesRegex(JsonableError, 'Invalid data type for recipients'):
            extract_private_recipients(s)

        s = ujson.dumps([{}])
        with self.assertRaisesRegex(JsonableError, 'Invalid data type for recipients'):
            extract_private_recipients(s)

        # Empty list
        self.assertEqual(extract_private_recipients('[]'), [])

        # Heterogeneous lists are not supported
        mixed = ujson.dumps(['eeshan@example.com', 3, 4])
        with self.assertRaisesRegex(JsonableError, 'Recipient lists may contain emails or user IDs, but not both.'):
            extract_private_recipients(mixed)

    def test_extract_recipient_ids(self) -> None:
        # JSON list w/dups
        s = ujson.dumps([3, 3, 12])
        result = sorted(extract_private_recipients(s))
        self.assertEqual(result, [3, 12])

        # Invalid data
        ids = ujson.dumps(dict(recipient=12))
        with self.assertRaisesRegex(JsonableError, 'Invalid data type for recipients'):
            extract_private_recipients(ids)

        # Heterogeneous lists are not supported
        mixed = ujson.dumps([3, 4, 'eeshan@example.com'])
        with self.assertRaisesRegex(JsonableError, 'Recipient lists may contain emails or user IDs, but not both.'):
            extract_private_recipients(mixed)

class PersonalMessagesTest(ZulipTestCase):

    def test_near_pm_message_url(self) -> None:
        realm = get_realm('zulip')
        message = dict(
            type='personal',
            id=555,
            display_recipient=[
                dict(id=77),
                dict(id=80),
            ],
        )
        url = near_message_url(
            realm=realm,
            message=message,
        )
        self.assertEqual(url, 'http://zulip.testserver/#narrow/pm-with/77,80-pm/near/555')

    def test_is_private_flag_not_leaked(self) -> None:
        """
        Make sure `is_private` flag is not leaked to the API.
        """
        self.login('hamlet')
        self.send_personal_message(self.example_user("hamlet"),
                                   self.example_user("cordelia"),
                                   "test")

        for msg in self.get_messages():
            self.assertNotIn('is_private', msg['flags'])

    def test_auto_subbed_to_personals(self) -> None:
        """
        Newly created users are auto-subbed to the ability to receive
        personals.
        """
        test_email = self.nonreg_email('test')
        self.register(test_email, "test")
        user_profile = self.nonreg_user('test')
        old_messages_count = message_stream_count(user_profile)
        self.send_personal_message(user_profile, user_profile)
        new_messages_count = message_stream_count(user_profile)
        self.assertEqual(new_messages_count, old_messages_count + 1)

        recipient = Recipient.objects.get(type_id=user_profile.id,
                                          type=Recipient.PERSONAL)
        message = most_recent_message(user_profile)
        self.assertEqual(message.recipient, recipient)

        with mock.patch('zerver.models.get_display_recipient', return_value='recip'):
            self.assertEqual(
                str(message),
                '<Message: recip /  / '
                '<UserProfile: {} {}>>'.format(user_profile.email, user_profile.realm))

            user_message = most_recent_usermessage(user_profile)
            self.assertEqual(
                str(user_message),
                f'<UserMessage: recip / {user_profile.email} ([])>',
            )

class SewMessageAndReactionTest(ZulipTestCase):
    def test_sew_messages_and_reaction(self) -> None:
        sender = self.example_user('othello')
        receiver = self.example_user('hamlet')
        pm_recipient = Recipient.objects.get(type_id=receiver.id, type=Recipient.PERSONAL)
        stream_name = 'Çiğdem'
        stream = self.make_stream(stream_name)
        stream_recipient = Recipient.objects.get(type_id=stream.id, type=Recipient.STREAM)
        sending_client = make_client(name="test suite")

        needed_ids = []
        for i in range(5):
            for recipient in [pm_recipient, stream_recipient]:
                message = Message(
                    sender=sender,
                    recipient=recipient,
                    content=f'whatever {i}',
                    date_sent=timezone_now(),
                    sending_client=sending_client,
                    last_edit_time=timezone_now(),
                    edit_history='[]',
                )
                message.set_topic_name('whatever')
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

class MessageAccessTests(ZulipTestCase):
    def test_update_invalid_flags(self) -> None:
        message = self.send_personal_message(
            self.example_user("cordelia"),
            self.example_user("hamlet"),
            "hello",
        )

        self.login('hamlet')
        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps([message]),
                                   "op": "add",
                                   "flag": "invalid"})
        self.assert_json_error(result, "Invalid flag: 'invalid'")

        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps([message]),
                                   "op": "add",
                                   "flag": "is_private"})
        self.assert_json_error(result, "Invalid flag: 'is_private'")

        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps([message]),
                                   "op": "add",
                                   "flag": "active_mobile_push_notification"})
        self.assert_json_error(result, "Invalid flag: 'active_mobile_push_notification'")

        result = self.client_post("/json/messages/flags",
                                  {"messages": ujson.dumps([message]),
                                   "op": "add",
                                   "flag": "mentioned"})
        self.assert_json_error(result, "Flag not editable: 'mentioned'")

    def change_star(self, messages: List[int], add: bool=True, **kwargs: Any) -> HttpResponse:
        return self.client_post("/json/messages/flags",
                                {"messages": ujson.dumps(messages),
                                 "op": "add" if add else "remove",
                                 "flag": "starred"},
                                **kwargs)

    def test_change_star(self) -> None:
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        self.login('hamlet')
        message_ids = [self.send_personal_message(self.example_user("hamlet"),
                                                  self.example_user("hamlet"),
                                                  "test")]

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

    def test_change_star_public_stream_historical(self) -> None:
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        stream_name = "new_stream"
        self.subscribe(self.example_user("hamlet"), stream_name)
        self.login('hamlet')
        message_ids = [
            self.send_stream_message(self.example_user("hamlet"), stream_name, "test"),
        ]
        # Send a second message so we can verify it isn't modified
        other_message_ids = [
            self.send_stream_message(self.example_user("hamlet"), stream_name, "test_unused"),
        ]
        received_message_ids = [
            self.send_personal_message(
                self.example_user("hamlet"),
                self.example_user("cordelia"),
                "test_received",
            ),
        ]

        # Now login as another user who wasn't on that stream
        self.login('cordelia')
        # Send a message to yourself to make sure we have at least one with the read flag
        sent_message_ids = [
            self.send_personal_message(
                self.example_user("cordelia"),
                self.example_user("cordelia"),
                "test_read_message",
            ),
        ]
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
        user = self.mit_user('sipbtest')
        self.login_user(user)
        result = self.change_star(message_ids, subdomain="zephyr")
        self.assert_json_error(result, 'Invalid message(s)')

    def test_change_star_private_message_security(self) -> None:
        """
        You can set a message as starred/un-starred through
        POST /json/messages/flags.
        """
        self.login('hamlet')
        message_ids = [
            self.send_personal_message(
                self.example_user("hamlet"),
                self.example_user("hamlet"),
                "test",
            ),
        ]

        # Starring private messages you didn't receive fails.
        self.login('cordelia')
        result = self.change_star(message_ids)
        self.assert_json_error(result, 'Invalid message(s)')

    def test_change_star_private_stream_security(self) -> None:
        stream_name = "private_stream"
        self.make_stream(stream_name, invite_only=True)
        self.subscribe(self.example_user("hamlet"), stream_name)
        self.login('hamlet')
        message_ids = [
            self.send_stream_message(self.example_user("hamlet"), stream_name, "test"),
        ]

        # Starring private stream messages you received works
        result = self.change_star(message_ids)
        self.assert_json_success(result)

        # Starring private stream messages you didn't receive fails.
        self.login('cordelia')
        result = self.change_star(message_ids)
        self.assert_json_error(result, 'Invalid message(s)')

        stream_name = "private_stream_2"
        self.make_stream(stream_name, invite_only=True,
                         history_public_to_subscribers=True)
        self.subscribe(self.example_user("hamlet"), stream_name)
        self.login('hamlet')
        message_ids = [
            self.send_stream_message(self.example_user("hamlet"), stream_name, "test"),
        ]

        # With stream.history_public_to_subscribers = True, you still
        # can't see it if you didn't receive the message and are
        # not subscribed.
        self.login('cordelia')
        result = self.change_star(message_ids)
        self.assert_json_error(result, 'Invalid message(s)')

        # But if you subscribe, then you can star the message
        self.subscribe(self.example_user("cordelia"), stream_name)
        result = self.change_star(message_ids)
        self.assert_json_success(result)

    def test_new_message(self) -> None:
        """
        New messages aren't starred.
        """
        sender = self.example_user('hamlet')
        self.login_user(sender)
        content = "Test message for star"
        self.send_stream_message(sender, "Verona",
                                 content=content)

        sent_message = UserMessage.objects.filter(
            user_profile=self.example_user('hamlet'),
        ).order_by("id").reverse()[0]
        self.assertEqual(sent_message.message.content, content)
        self.assertFalse(sent_message.flags.starred)

    def test_change_star_public_stream_security_for_guest_user(self) -> None:
        # Guest user can't access(star) unsubscribed public stream messages
        normal_user = self.example_user("hamlet")
        stream_name = "public_stream"
        self.make_stream(stream_name)
        self.subscribe(normal_user, stream_name)
        self.login_user(normal_user)

        message_id = [
            self.send_stream_message(normal_user, stream_name, "test 1"),
        ]

        guest_user = self.example_user('polonius')
        self.login_user(guest_user)
        result = self.change_star(message_id)
        self.assert_json_error(result, 'Invalid message(s)')

        # Subscribed guest users can access public stream messages sent before they join
        self.subscribe(guest_user, stream_name)
        result = self.change_star(message_id)
        self.assert_json_success(result)

        # And messages sent after they join
        self.login_user(normal_user)
        message_id = [
            self.send_stream_message(normal_user, stream_name, "test 2"),
        ]
        self.login_user(guest_user)
        result = self.change_star(message_id)
        self.assert_json_success(result)

    def test_change_star_private_stream_security_for_guest_user(self) -> None:
        # Guest users can't access(star) unsubscribed private stream messages
        normal_user = self.example_user("hamlet")
        stream_name = "private_stream"
        stream = self.make_stream(stream_name, invite_only=True)
        self.subscribe(normal_user, stream_name)
        self.login_user(normal_user)

        message_id = [
            self.send_stream_message(normal_user, stream_name, "test 1"),
        ]

        guest_user = self.example_user('polonius')
        self.login_user(guest_user)
        result = self.change_star(message_id)
        self.assert_json_error(result, 'Invalid message(s)')

        # Guest user can't access messages of subscribed private streams if
        # history is not public to subscribers
        self.subscribe(guest_user, stream_name)
        result = self.change_star(message_id)
        self.assert_json_error(result, 'Invalid message(s)')

        # Guest user can access messages of subscribed private streams if
        # history is public to subscribers
        do_change_stream_invite_only(stream, True, history_public_to_subscribers=True)
        result = self.change_star(message_id)
        self.assert_json_success(result)

        # With history not public to subscribers, they can still see new messages
        do_change_stream_invite_only(stream, True, history_public_to_subscribers=False)
        self.login_user(normal_user)
        message_id = [
            self.send_stream_message(normal_user, stream_name, "test 2"),
        ]
        self.login_user(guest_user)
        result = self.change_star(message_id)
        self.assert_json_success(result)

    def test_bulk_access_messages_private_stream(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        stream_name = "private_stream"
        stream = self.make_stream(stream_name, invite_only=True,
                                  history_public_to_subscribers=False)

        self.subscribe(user, stream_name)
        # Send a message before subscribing a new user to stream
        message_one_id = self.send_stream_message(user,
                                                  stream_name, "Message one")

        later_subscribed_user = self.example_user("cordelia")
        # Subscribe a user to private-protected history stream
        self.subscribe(later_subscribed_user, stream_name)

        # Send a message after subscribing a new user to stream
        message_two_id = self.send_stream_message(user,
                                                  stream_name, "Message two")

        message_ids = [message_one_id, message_two_id]
        messages = [Message.objects.select_related().get(id=message_id)
                    for message_id in message_ids]

        filtered_messages = bulk_access_messages(later_subscribed_user, messages)

        # Message sent before subscribing wouldn't be accessible by later
        # subscribed user as stream has protected history
        self.assertEqual(len(filtered_messages), 1)
        self.assertEqual(filtered_messages[0].id, message_two_id)

        do_change_stream_invite_only(stream, True, history_public_to_subscribers=True)

        filtered_messages = bulk_access_messages(later_subscribed_user, messages)

        # Message sent before subscribing are accessible by 8user as stream
        # don't have protected history
        self.assertEqual(len(filtered_messages), 2)

        # Testing messages accessiblity for an unsubscribed user
        unsubscribed_user = self.example_user("ZOE")

        filtered_messages = bulk_access_messages(unsubscribed_user, messages)

        self.assertEqual(len(filtered_messages), 0)

    def test_bulk_access_messages_public_stream(self) -> None:
        user = self.example_user("hamlet")
        self.login_user(user)

        # Testing messages accessiblity including a public stream message
        stream_name = "public_stream"
        self.subscribe(user, stream_name)
        message_one_id = self.send_stream_message(user,
                                                  stream_name, "Message one")

        later_subscribed_user = self.example_user("cordelia")
        self.subscribe(later_subscribed_user, stream_name)

        # Send a message after subscribing a new user to stream
        message_two_id = self.send_stream_message(user,
                                                  stream_name, "Message two")

        message_ids = [message_one_id, message_two_id]
        messages = [Message.objects.select_related().get(id=message_id)
                    for message_id in message_ids]

        # All public stream messages are always accessible
        filtered_messages = bulk_access_messages(later_subscribed_user, messages)
        self.assertEqual(len(filtered_messages), 2)

        unsubscribed_user = self.example_user("ZOE")
        filtered_messages = bulk_access_messages(unsubscribed_user, messages)

        self.assertEqual(len(filtered_messages), 2)

class MessageHasKeywordsTest(ZulipTestCase):
    '''Test for keywords like has_link, has_image, has_attachment.'''

    def setup_dummy_attachments(self, user_profile: UserProfile) -> List[str]:
        sample_size = 10
        realm_id = user_profile.realm_id
        dummy_files = [
            ('zulip.txt', f'{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/zulip.txt', sample_size),
            ('temp_file.py', f'{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/temp_file.py', sample_size),
            ('abc.py', f'{realm_id}/31/4CBjtTLYZhk66pZrF8hnYGwc/abc.py', sample_size),
        ]

        for file_name, path_id, size in dummy_files:
            create_attachment(file_name, path_id, user_profile, size)

        # return path ids
        return [x[1] for x in dummy_files]

    def test_claim_attachment(self) -> None:
        user_profile = self.example_user('hamlet')
        dummy_path_ids = self.setup_dummy_attachments(user_profile)
        dummy_urls = [f"http://zulip.testserver/user_uploads/{x}" for x in dummy_path_ids]

        # Send message referring the attachment
        self.subscribe(user_profile, "Denmark")

        def assert_attachment_claimed(path_id: str, claimed: bool) -> None:
            attachment = Attachment.objects.get(path_id=path_id)
            self.assertEqual(attachment.is_claimed(), claimed)

        # This message should claim attachments 1 only because attachment 2
        # is not being parsed as a link by Markdown.
        body = ("Some files here ...[zulip.txt]({})" +
                "{}.... Some more...." +
                "{}").format(dummy_urls[0], dummy_urls[1], dummy_urls[1])
        self.send_stream_message(user_profile, "Denmark", body, "test")
        assert_attachment_claimed(dummy_path_ids[0], True)
        assert_attachment_claimed(dummy_path_ids[1], False)

        # This message tries to claim the third attachment but fails because
        # Markdown would not set has_attachments = True here.
        body = f"Link in code: `{dummy_urls[2]}`"
        self.send_stream_message(user_profile, "Denmark", body, "test")
        assert_attachment_claimed(dummy_path_ids[2], False)

        # Another scenario where we wouldn't parse the link.
        body = f"Link to not parse: .{dummy_urls[2]}.`"
        self.send_stream_message(user_profile, "Denmark", body, "test")
        assert_attachment_claimed(dummy_path_ids[2], False)

        # Finally, claim attachment 3.
        body = f"Link: {dummy_urls[2]}"
        self.send_stream_message(user_profile, "Denmark", body, "test")
        assert_attachment_claimed(dummy_path_ids[2], True)
        assert_attachment_claimed(dummy_path_ids[1], False)

    def test_finds_all_links(self) -> None:
        msg_ids = []
        msg_contents = ["foo.org", "[bar](baz.gov)", "http://quux.ca"]
        for msg_content in msg_contents:
            msg_ids.append(self.send_stream_message(self.example_user('hamlet'),
                                                    'Denmark', content=msg_content))
        msgs = [Message.objects.get(id=id) for id in msg_ids]
        self.assertTrue(all([msg.has_link for msg in msgs]))

    def test_finds_only_links(self) -> None:
        msg_ids = []
        msg_contents = ["`example.org`", '``example.org```', '$$https://example.org$$', "foo"]
        for msg_content in msg_contents:
            msg_ids.append(self.send_stream_message(self.example_user('hamlet'),
                                                    'Denmark', content=msg_content))
        msgs = [Message.objects.get(id=id) for id in msg_ids]
        self.assertFalse(all([msg.has_link for msg in msgs]))

    def update_message(self, msg: Message, content: str) -> None:
        hamlet = self.example_user('hamlet')
        realm_id = hamlet.realm.id
        rendered_content = render_markdown(msg, content)
        mention_data = MentionData(realm_id, content)
        do_update_message(hamlet, msg, None, None, "change_one", False, False, content,
                          rendered_content, set(), set(), mention_data=mention_data)

    def test_finds_link_after_edit(self) -> None:
        hamlet = self.example_user('hamlet')
        msg_id = self.send_stream_message(hamlet, 'Denmark', content='a')
        msg = Message.objects.get(id=msg_id)

        self.assertFalse(msg.has_link)
        self.update_message(msg, 'a http://foo.com')
        self.assertTrue(msg.has_link)
        self.update_message(msg, 'a')
        self.assertFalse(msg.has_link)
        # Check in blockquotes work
        self.update_message(msg, '> http://bar.com')
        self.assertTrue(msg.has_link)
        self.update_message(msg, 'a `http://foo.com`')
        self.assertFalse(msg.has_link)

    def test_has_image(self) -> None:
        msg_ids = []
        msg_contents = ["Link: foo.org",
                        "Image: https://www.google.com/images/srpr/logo4w.png",
                        "Image: https://www.google.com/images/srpr/logo4w.pdf",
                        "[Google Link](https://www.google.com/images/srpr/logo4w.png)"]
        for msg_content in msg_contents:
            msg_ids.append(self.send_stream_message(self.example_user('hamlet'),
                                                    'Denmark', content=msg_content))
        msgs = [Message.objects.get(id=id) for id in msg_ids]
        self.assertEqual([False, True, False, True], [msg.has_image for msg in msgs])

        self.update_message(msgs[0], 'https://www.google.com/images/srpr/logo4w.png')
        self.assertTrue(msgs[0].has_image)
        self.update_message(msgs[0], 'No Image Again')
        self.assertFalse(msgs[0].has_image)

    def test_has_attachment(self) -> None:
        hamlet = self.example_user('hamlet')
        dummy_path_ids = self.setup_dummy_attachments(hamlet)
        dummy_urls = [f"http://zulip.testserver/user_uploads/{x}" for x in dummy_path_ids]
        self.subscribe(hamlet, "Denmark")

        body = ("Files ...[zulip.txt]({}) {} {}").format(dummy_urls[0], dummy_urls[1], dummy_urls[2])

        msg_id = self.send_stream_message(hamlet, "Denmark", body, "test")
        msg = Message.objects.get(id=msg_id)
        self.assertTrue(msg.has_attachment)
        self.update_message(msg, 'No Attachments')
        self.assertFalse(msg.has_attachment)
        self.update_message(msg, body)
        self.assertTrue(msg.has_attachment)
        self.update_message(msg, f'Link in code: `{dummy_urls[1]}`')
        self.assertFalse(msg.has_attachment)
        # Test blockquotes
        self.update_message(msg, f'> {dummy_urls[1]}')
        self.assertTrue(msg.has_attachment)

        # Additional test to check has_attachment is being set is due to the correct attachment.
        self.update_message(msg, f'Outside: {dummy_urls[0]}. In code: `{dummy_urls[1]}`.')
        self.assertTrue(msg.has_attachment)
        self.assertTrue(msg.attachment_set.filter(path_id=dummy_path_ids[0]))
        self.assertEqual(msg.attachment_set.count(), 1)

        self.update_message(msg, f'Outside: {dummy_urls[1]}. In code: `{dummy_urls[0]}`.')
        self.assertTrue(msg.has_attachment)
        self.assertTrue(msg.attachment_set.filter(path_id=dummy_path_ids[1]))
        self.assertEqual(msg.attachment_set.count(), 1)

        self.update_message(msg, f'Both in code: `{dummy_urls[1]} {dummy_urls[0]}`.')
        self.assertFalse(msg.has_attachment)
        self.assertEqual(msg.attachment_set.count(), 0)

    def test_potential_attachment_path_ids(self) -> None:
        hamlet = self.example_user('hamlet')
        self.subscribe(hamlet, "Denmark")
        dummy_path_ids = self.setup_dummy_attachments(hamlet)

        body = "Hello"
        msg_id = self.send_stream_message(hamlet, "Denmark", body, "test")
        msg = Message.objects.get(id=msg_id)

        with mock.patch("zerver.lib.actions.do_claim_attachments",
                        wraps=do_claim_attachments) as m:
            self.update_message(msg, f'[link](http://{hamlet.realm.host}/user_uploads/{dummy_path_ids[0]})')
            self.assertTrue(m.called)
            m.reset_mock()

            self.update_message(msg, f'[link](/user_uploads/{dummy_path_ids[1]})')
            self.assertTrue(m.called)
            m.reset_mock()

            self.update_message(msg, f'[new text link](/user_uploads/{dummy_path_ids[1]})')
            self.assertFalse(m.called)
            m.reset_mock()

            # It's not clear this is correct behavior
            self.update_message(msg, f'[link](user_uploads/{dummy_path_ids[2]})')
            self.assertFalse(m.called)
            m.reset_mock()

            self.update_message(msg, f'[link](https://github.com/user_uploads/{dummy_path_ids[0]})')
            self.assertFalse(m.called)
            m.reset_mock()

class MissedMessageTest(ZulipTestCase):
    def test_presence_idle_user_ids(self) -> None:
        UserPresence.objects.all().delete()

        sender = self.example_user('cordelia')
        realm = sender.realm
        hamlet = self.example_user('hamlet')
        othello = self.example_user('othello')
        recipient_ids = {hamlet.id, othello.id}
        message_type = 'stream'
        user_flags: Dict[int, List[str]] = {}

        def assert_missing(user_ids: List[int]) -> None:
            presence_idle_user_ids = get_active_presence_idle_user_ids(
                realm=realm,
                sender_id=sender.id,
                message_type=message_type,
                active_user_ids=recipient_ids,
                user_flags=user_flags,
            )
            self.assertEqual(sorted(user_ids), sorted(presence_idle_user_ids))

        def set_presence(user: UserProfile, client_name: str, ago: int) -> None:
            when = timezone_now() - datetime.timedelta(seconds=ago)
            UserPresence.objects.create(
                user_profile_id=user.id,
                realm_id=user.realm_id,
                client=get_client(client_name),
                timestamp=when,
            )

        message_type = 'private'
        assert_missing([hamlet.id, othello.id])

        message_type = 'stream'
        user_flags[hamlet.id] = ['mentioned']
        assert_missing([hamlet.id])

        set_presence(hamlet, 'iPhone', ago=5000)
        assert_missing([hamlet.id])

        set_presence(hamlet, 'webapp', ago=15)
        assert_missing([])

        message_type = 'private'
        assert_missing([othello.id])

class LogDictTest(ZulipTestCase):
    def test_to_log_dict(self) -> None:
        user = self.example_user('hamlet')
        stream_name = 'Denmark'
        topic_name = 'Copenhagen'
        content = 'find me some good coffee shops'
        message_id = self.send_stream_message(user, stream_name,
                                              topic_name=topic_name,
                                              content=content)
        message = Message.objects.get(id=message_id)
        dct = message.to_log_dict()

        self.assertTrue('timestamp' in dct)

        self.assertEqual(dct['content'], 'find me some good coffee shops')
        self.assertEqual(dct['id'], message.id)
        self.assertEqual(dct['recipient'], 'Denmark')
        self.assertEqual(dct['sender_realm_str'], 'zulip')
        self.assertEqual(dct['sender_email'], user.email)
        self.assertEqual(dct['sender_full_name'], 'King Hamlet')
        self.assertEqual(dct['sender_id'], user.id)
        self.assertEqual(dct['sender_short_name'], 'hamlet')
        self.assertEqual(dct['sending_client'], 'test suite')
        self.assertEqual(dct[DB_TOPIC_NAME], 'Copenhagen')
        self.assertEqual(dct['type'], 'stream')

class CheckMessageTest(ZulipTestCase):
    def test_basic_check_message_call(self) -> None:
        sender = self.example_user('othello')
        client = make_client(name="test suite")
        stream_name = 'España y Francia'
        self.make_stream(stream_name)
        topic_name = 'issue'
        message_content = 'whatever'
        addressee = Addressee.for_stream_name(stream_name, topic_name)
        ret = check_message(sender, client, addressee, message_content)
        self.assertEqual(ret['message'].sender.id, sender.id)

    def test_bot_pm_feature(self) -> None:
        """We send a PM to a bot's owner if their bot sends a message to
        an unsubscribed stream"""
        parent = self.example_user('othello')
        bot = do_create_user(
            email='othello-bot@zulip.com',
            password='',
            realm=parent.realm,
            full_name='',
            short_name='',
            bot_type=UserProfile.DEFAULT_BOT,
            bot_owner=parent,
        )
        bot.last_reminder = None

        sender = bot
        client = make_client(name="test suite")
        stream_name = 'Россия'
        topic_name = 'issue'
        addressee = Addressee.for_stream_name(stream_name, topic_name)
        message_content = 'whatever'
        old_count = message_stream_count(parent)

        # Try sending to stream that doesn't exist sends a reminder to
        # the sender
        with self.assertRaises(JsonableError):
            check_message(sender, client, addressee, message_content)

        new_count = message_stream_count(parent)
        self.assertEqual(new_count, old_count + 1)
        self.assertIn("that stream does not exist.", most_recent_message(parent).content)

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
        self.assertIn("does not have any subscribers", most_recent_message(parent).content)

    def test_bot_pm_error_handling(self) -> None:
        # This just test some defensive code.
        cordelia = self.example_user('cordelia')
        test_bot = self.create_test_bot(
            short_name='test',
            user_profile=cordelia,
        )
        content = 'whatever'
        good_realm = test_bot.realm
        wrong_realm = get_realm("zephyr")
        wrong_sender = cordelia

        send_rate_limited_pm_notification_to_bot_owner(test_bot, wrong_realm, content)
        self.assertEqual(test_bot.last_reminder, None)

        send_rate_limited_pm_notification_to_bot_owner(wrong_sender, good_realm, content)
        self.assertEqual(test_bot.last_reminder, None)

        test_bot.realm.deactivated = True
        send_rate_limited_pm_notification_to_bot_owner(test_bot, good_realm, content)
        self.assertEqual(test_bot.last_reminder, None)

class SoftDeactivationMessageTest(ZulipTestCase):

    def test_reactivate_user_if_soft_deactivated(self) -> None:
        recipient_list  = [self.example_user("hamlet"), self.example_user("iago")]
        for user_profile in recipient_list:
            self.subscribe(user_profile, "Denmark")

        sender = self.example_user('iago')
        stream_name = 'Denmark'
        topic_name = 'foo'

        def last_realm_audit_log_entry(event_type: int) -> RealmAuditLog:
            return RealmAuditLog.objects.filter(
                event_type=event_type,
            ).order_by('-event_time')[0]

        long_term_idle_user = self.example_user('hamlet')
        # We are sending this message to ensure that long_term_idle_user has
        # at least one UserMessage row.
        self.send_stream_message(long_term_idle_user, stream_name)
        do_soft_deactivate_users([long_term_idle_user])

        message = 'Test Message 1'
        message_id = self.send_stream_message(sender, stream_name,
                                              message, topic_name)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        self.assertNotEqual(idle_user_msg_list[-1].content, message)
        with queries_captured() as queries:
            reactivate_user_if_soft_deactivated(long_term_idle_user)
        self.assert_length(queries, 8)
        self.assertFalse(long_term_idle_user.long_term_idle)
        self.assertEqual(last_realm_audit_log_entry(
            RealmAuditLog.USER_SOFT_ACTIVATED).modified_user, long_term_idle_user)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 1)
        self.assertEqual(idle_user_msg_list[-1].content, message)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, message_id)

    def test_add_missing_messages(self) -> None:
        recipient_list  = [self.example_user("hamlet"), self.example_user("iago")]
        for user_profile in recipient_list:
            self.subscribe(user_profile, "Denmark")

        sender = self.example_user('iago')
        realm = sender.realm
        sending_client = make_client(name="test suite")
        stream_name = 'Denmark'
        stream = get_stream(stream_name, realm)
        topic_name = 'foo'

        def send_fake_message(message_content: str, stream: Stream) -> Message:
            recipient = stream.recipient
            message = Message(sender = sender,
                              recipient = recipient,
                              content = message_content,
                              date_sent = timezone_now(),
                              sending_client = sending_client)
            message.set_topic_name(topic_name)
            message.save()
            return message

        long_term_idle_user = self.example_user('hamlet')
        self.send_stream_message(long_term_idle_user, stream_name)
        do_soft_deactivate_users([long_term_idle_user])

        # Test that add_missing_messages() in simplest case of adding a
        # message for which UserMessage row doesn't exist for this user.
        sent_message = send_fake_message('Test Message 1', stream)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        self.assertNotEqual(idle_user_msg_list[-1], sent_message)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 6)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 1)
        self.assertEqual(idle_user_msg_list[-1], sent_message)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, sent_message.id)

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
        self.assert_length(queries, 7)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 1)
        self.assertEqual(idle_user_msg_list[-1], sent_message)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, sent_message.id)

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
        self.assert_length(queries, 6)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 2)
        for sent_message in sent_message_list:
            self.assertEqual(idle_user_msg_list.pop(), sent_message)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, sent_message_list[0].id)

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
        self.assert_length(queries, 6)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 2)
        for sent_message in sent_message_list:
            self.assertEqual(idle_user_msg_list.pop(), sent_message)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, sent_message_list[0].id)

        # Test for when user unsubscribes before soft deactivation
        # (must reactivate them in order to do this).

        do_soft_activate_users([long_term_idle_user])
        self.subscribe(long_term_idle_user, stream_name)
        # Send a real message to update last_active_message_id
        sent_message_id = self.send_stream_message(
            sender, stream_name, 'Test Message 9')
        self.unsubscribe(long_term_idle_user, stream_name)
        # Soft deactivate and send another message to the unsubscribed stream.
        do_soft_deactivate_users([long_term_idle_user])
        send_fake_message('Test Message 10', stream)

        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        self.assertEqual(idle_user_msg_list[-1].id, sent_message_id)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        # There are no streams to fetch missing messages from, so
        # the Message.objects query will be avoided.
        self.assert_length(queries, 4)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        # No new UserMessage rows should have been created.
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count)

        # Note: At this point in this test we have long_term_idle_user
        # unsubscribed from the 'Denmark' stream.

        # Test for a Private Stream.
        stream_name = "Core"
        private_stream = self.make_stream('Core', invite_only=True)
        self.subscribe(self.example_user("iago"), stream_name)
        sent_message_list = []
        send_fake_message('Test Message 11', private_stream)
        self.subscribe(self.example_user("hamlet"), stream_name)
        sent_message_list.append(send_fake_message('Test Message 12', private_stream))
        self.unsubscribe(long_term_idle_user, stream_name)
        send_fake_message('Test Message 13', private_stream)
        self.subscribe(long_term_idle_user, stream_name)
        sent_message_list.append(send_fake_message('Test Message 14', private_stream))
        sent_message_list.reverse()
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        for sent_message in sent_message_list:
            self.assertNotEqual(idle_user_msg_list.pop(), sent_message)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 6)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + 2)
        for sent_message in sent_message_list:
            self.assertEqual(idle_user_msg_list.pop(), sent_message)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, sent_message_list[0].id)

    @mock.patch('zerver.lib.soft_deactivation.BULK_CREATE_BATCH_SIZE', 2)
    def test_add_missing_messages_pagination(self) -> None:
        recipient_list  = [self.example_user("hamlet"), self.example_user("iago")]
        stream_name = 'Denmark'
        for user_profile in recipient_list:
            self.subscribe(user_profile, stream_name)

        sender = self.example_user('iago')
        long_term_idle_user = self.example_user('hamlet')
        self.send_stream_message(long_term_idle_user, stream_name)
        do_soft_deactivate_users([long_term_idle_user])

        num_new_messages = 5
        message_ids = []
        for _ in range(num_new_messages):
            message_id = self.send_stream_message(sender, stream_name)
            message_ids.append(message_id)

        idle_user_msg_list = get_user_messages(long_term_idle_user)
        idle_user_msg_count = len(idle_user_msg_list)
        with queries_captured() as queries:
            add_missing_messages(long_term_idle_user)
        self.assert_length(queries, 10)
        idle_user_msg_list = get_user_messages(long_term_idle_user)
        self.assertEqual(len(idle_user_msg_list), idle_user_msg_count + num_new_messages)
        long_term_idle_user.refresh_from_db()
        self.assertEqual(long_term_idle_user.last_active_message_id, message_ids[-1])

    def test_user_message_filter(self) -> None:
        # In this test we are basically testing out the logic used out in
        # do_send_messages() in action.py for filtering the messages for which
        # UserMessage rows should be created for a soft-deactivated user.
        recipient_list  = [
            self.example_user("hamlet"),
            self.example_user("iago"),
            self.example_user('cordelia'),
        ]
        for user_profile in recipient_list:
            self.subscribe(user_profile, "Denmark")

        cordelia = self.example_user('cordelia')
        sender = self.example_user('iago')
        stream_name = 'Denmark'
        topic_name = 'foo'

        def send_stream_message(content: str) -> None:
            self.send_stream_message(sender, stream_name,
                                     content, topic_name)

        def send_personal_message(content: str) -> None:
            self.send_personal_message(sender, self.example_user("hamlet"), content)

        long_term_idle_user = self.example_user('hamlet')
        self.send_stream_message(long_term_idle_user, stream_name)
        do_soft_deactivate_users([long_term_idle_user])

        def assert_um_count(user: UserProfile, count: int) -> None:
            user_messages = get_user_messages(user)
            self.assertEqual(len(user_messages), count)

        def assert_last_um_content(user: UserProfile, content: str, negate: bool=False) -> None:
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
        assert_last_um_content(long_term_idle_user, message, negate=True)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        # Test that sending a message to a stream with soft deactivated user
        # and push/email notifications on creates a UserMessage row for the
        # deactivated user.
        sub = get_subscription(stream_name, long_term_idle_user)
        sub.push_notifications = True
        sub.save()
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test private stream message'
        send_stream_message(message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_last_um_content(long_term_idle_user, message)
        sub.push_notifications = False
        sub.save()

        # Test sending a private message to soft deactivated user creates
        # UserMessage row.
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test PM'
        send_personal_message(message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_last_um_content(long_term_idle_user, message)

        # Test UserMessage row is created while user is deactivated if
        # user itself is mentioned.
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**King Hamlet** mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        # Test UserMessage row is not created while user is deactivated if
        # anyone is mentioned but the user.
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**Cordelia Lear**  mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message, negate=True)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        # Test UserMessage row is created while user is deactivated if
        # there is a wildcard mention such as @all or @everyone
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**all** mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**everyone** mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Test @**stream** mention'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        # Test UserMessage row is not created while user is deactivated if there
        # is a alert word in message.
        do_add_alert_words(long_term_idle_user, ['test_alert_word'])
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = 'Testing test_alert_word'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count + 1)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

        # Test UserMessage row is created while user is deactivated if
        # message is a me message.
        general_user_msg_count = len(get_user_messages(cordelia))
        soft_deactivated_user_msg_count = len(get_user_messages(long_term_idle_user))
        message = '/me says test'
        send_stream_message(message)
        assert_last_um_content(long_term_idle_user, message, negate=True)
        assert_um_count(long_term_idle_user, soft_deactivated_user_msg_count)
        assert_um_count(cordelia, general_user_msg_count + 1)
        assert_last_um_content(cordelia, message)

class MessageHydrationTest(ZulipTestCase):
    def test_hydrate_stream_recipient_info(self) -> None:
        realm = get_realm('zulip')
        cordelia = self.example_user('cordelia')

        stream_id = get_stream('Verona', realm).id

        obj = dict(
            recipient_type=Recipient.STREAM,
            recipient_type_id=stream_id,
            sender_is_mirror_dummy=False,
            sender_email=cordelia.email,
            sender_full_name=cordelia.full_name,
            sender_short_name=cordelia.short_name,
            sender_id=cordelia.id,
        )

        MessageDict.hydrate_recipient_info(obj, 'Verona')

        self.assertEqual(obj['display_recipient'], 'Verona')
        self.assertEqual(obj['type'], 'stream')

    def test_hydrate_pm_recipient_info(self) -> None:
        cordelia = self.example_user('cordelia')
        display_recipient: List[UserDisplayRecipient] = [
            dict(
                email='aaron@example.com',
                full_name='Aaron Smith',
                short_name='Aaron',
                id=999,
                is_mirror_dummy=False,
            ),
        ]

        obj = dict(
            recipient_type=Recipient.PERSONAL,
            recipient_type_id=None,
            sender_is_mirror_dummy=False,
            sender_email=cordelia.email,
            sender_full_name=cordelia.full_name,
            sender_short_name=cordelia.short_name,
            sender_id=cordelia.id,
        )

        MessageDict.hydrate_recipient_info(obj, display_recipient)

        self.assertEqual(
            obj['display_recipient'],
            [
                dict(
                    email='aaron@example.com',
                    full_name='Aaron Smith',
                    short_name='Aaron',
                    id=999,
                    is_mirror_dummy=False,
                ),
                dict(
                    email=cordelia.email,
                    full_name=cordelia.full_name,
                    id=cordelia.id,
                    short_name=cordelia.short_name,
                    is_mirror_dummy=False,
                ),
            ],
        )
        self.assertEqual(obj['type'], 'private')

    def test_messages_for_ids(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')

        stream_name = 'test stream'
        self.subscribe(cordelia, stream_name)

        old_message_id = self.send_stream_message(cordelia, stream_name, content='foo')

        self.subscribe(hamlet, stream_name)

        content = 'hello @**King Hamlet**'
        new_message_id = self.send_stream_message(cordelia, stream_name, content=content)

        user_message_flags = {
            old_message_id: ['read', 'historical'],
            new_message_id: ['mentioned'],
        }

        messages = messages_for_ids(
            message_ids=[old_message_id, new_message_id],
            user_message_flags=user_message_flags,
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )

        self.assertEqual(len(messages), 2)

        for message in messages:
            if message['id'] == old_message_id:
                old_message = message
            elif message['id'] == new_message_id:
                new_message = message

        self.assertEqual(old_message['content'], '<p>foo</p>')
        self.assertEqual(old_message['flags'], ['read', 'historical'])

        self.assertIn('class="user-mention"', new_message['content'])
        self.assertEqual(new_message['flags'], ['mentioned'])

    def test_display_recipient_up_to_date(self) -> None:
        """
        This is a test for a bug where due to caching of message_dicts,
        after updating a user's information, fetching those cached messages
        via messages_for_ids would return message_dicts with display_recipient
        still having the old information. The returned message_dicts should have
        up-to-date display_recipients and we check for that here.
        """

        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        message_id = self.send_personal_message(hamlet, cordelia, 'test')

        cordelia_recipient = cordelia.recipient
        # Cause the display_recipient to get cached:
        get_display_recipient(cordelia_recipient)

        # Change cordelia's email:
        cordelia_new_email = 'new-cordelia@zulip.com'
        cordelia.email = cordelia_new_email
        cordelia.save()

        # Local display_recipient cache needs to be flushed.
        # flush_per_request_caches() is called after every request,
        # so it makes sense to run it here.
        flush_per_request_caches()

        messages = messages_for_ids(
            message_ids=[message_id],
            user_message_flags={message_id: ['read']},
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )
        message = messages[0]

        # Find which display_recipient in the list is cordelia:
        for display_recipient in message['display_recipient']:
            if display_recipient['short_name'] == 'cordelia':
                cordelia_display_recipient = display_recipient

        # Make sure the email is up-to-date.
        self.assertEqual(cordelia_display_recipient['email'], cordelia_new_email)

class TestMessageForIdsDisplayRecipientFetching(ZulipTestCase):
    def _verify_display_recipient(self, display_recipient: DisplayRecipientT,
                                  expected_recipient_objects: Union[Stream, List[UserProfile]]) -> None:
        if isinstance(expected_recipient_objects, Stream):
            self.assertEqual(display_recipient, expected_recipient_objects.name)

        else:
            for user_profile in expected_recipient_objects:
                recipient_dict: UserDisplayRecipient = {
                    'email': user_profile.email,
                    'full_name': user_profile.full_name,
                    'short_name': user_profile.short_name,
                    'id': user_profile.id,
                    'is_mirror_dummy': user_profile.is_mirror_dummy,
                }
                self.assertTrue(recipient_dict in display_recipient)

    def test_display_recipient_personal(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        othello = self.example_user('othello')
        message_ids = [
            self.send_personal_message(hamlet, cordelia, 'test'),
            self.send_personal_message(cordelia, othello, 'test'),
        ]

        messages = messages_for_ids(
            message_ids=message_ids,
            user_message_flags={message_id: ['read'] for message_id in message_ids},
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )

        self._verify_display_recipient(messages[0]['display_recipient'], [hamlet, cordelia])
        self._verify_display_recipient(messages[1]['display_recipient'], [cordelia, othello])

    def test_display_recipient_stream(self) -> None:
        cordelia = self.example_user('cordelia')
        message_ids = [
            self.send_stream_message(cordelia, "Verona", content='test'),
            self.send_stream_message(cordelia, "Denmark", content='test'),
        ]

        messages = messages_for_ids(
            message_ids=message_ids,
            user_message_flags={message_id: ['read'] for message_id in message_ids},
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )

        self._verify_display_recipient(messages[0]['display_recipient'], get_stream("Verona", cordelia.realm))
        self._verify_display_recipient(messages[1]['display_recipient'], get_stream("Denmark", cordelia.realm))

    def test_display_recipient_huddle(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        othello = self.example_user('othello')
        iago = self.example_user('iago')
        message_ids = [
            self.send_huddle_message(hamlet, [cordelia, othello], 'test'),
            self.send_huddle_message(cordelia, [hamlet, othello, iago], 'test'),
        ]

        messages = messages_for_ids(
            message_ids=message_ids,
            user_message_flags={message_id: ['read'] for message_id in message_ids},
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )

        self._verify_display_recipient(messages[0]['display_recipient'], [hamlet, cordelia, othello])
        self._verify_display_recipient(messages[1]['display_recipient'], [hamlet, cordelia, othello, iago])

    def test_display_recipient_various_types(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        othello = self.example_user('othello')
        iago = self.example_user('iago')
        message_ids = [
            self.send_huddle_message(hamlet, [cordelia, othello], 'test'),
            self.send_stream_message(cordelia, "Verona", content='test'),
            self.send_personal_message(hamlet, cordelia, 'test'),
            self.send_stream_message(cordelia, "Denmark", content='test'),
            self.send_huddle_message(cordelia, [hamlet, othello, iago], 'test'),
            self.send_personal_message(cordelia, othello, 'test'),
        ]

        messages = messages_for_ids(
            message_ids=message_ids,
            user_message_flags={message_id: ['read'] for message_id in message_ids},
            search_fields={},
            apply_markdown=True,
            client_gravatar=True,
            allow_edit_history=False,
        )

        self._verify_display_recipient(messages[0]['display_recipient'], [hamlet, cordelia, othello])
        self._verify_display_recipient(messages[1]['display_recipient'], get_stream("Verona", hamlet.realm))
        self._verify_display_recipient(messages[2]['display_recipient'], [hamlet, cordelia])
        self._verify_display_recipient(messages[3]['display_recipient'], get_stream("Denmark", hamlet.realm))
        self._verify_display_recipient(messages[4]['display_recipient'], [hamlet, cordelia, othello, iago])
        self._verify_display_recipient(messages[5]['display_recipient'], [cordelia, othello])

class MessageVisibilityTest(ZulipTestCase):
    def test_update_first_visible_message_id(self) -> None:
        Message.objects.all().delete()
        message_ids = [self.send_stream_message(self.example_user("othello"), "Scotland") for i in range(15)]

        # If message_visibility_limit is None update_first_visible_message_id
        # should set first_visible_message_id to 0
        realm = get_realm("zulip")
        realm.message_visibility_limit = None
        # Setting to a random value other than 0 as the default value of
        # first_visible_message_id is 0
        realm.first_visible_message_id = 5
        realm.save()
        update_first_visible_message_id(realm)
        self.assertEqual(get_first_visible_message_id(realm), 0)

        realm.message_visibility_limit = 10
        realm.save()
        expected_message_id = message_ids[5]
        update_first_visible_message_id(realm)
        self.assertEqual(get_first_visible_message_id(realm), expected_message_id)

        # If the message_visibility_limit is greater than number of messages
        # get_first_visible_message_id should return 0
        realm.message_visibility_limit = 50
        realm.save()
        update_first_visible_message_id(realm)
        self.assertEqual(get_first_visible_message_id(realm), 0)

    def test_maybe_update_first_visible_message_id(self) -> None:
        realm = get_realm("zulip")
        lookback_hours = 30

        realm.message_visibility_limit = None
        realm.save()

        end_time = timezone_now() - datetime.timedelta(hours=lookback_hours - 5)
        stat = COUNT_STATS['messages_sent:is_bot:hour']

        RealmCount.objects.create(realm=realm, property=stat.property,
                                  end_time=end_time, value=5)
        with mock.patch("zerver.lib.message.update_first_visible_message_id") as m:
            maybe_update_first_visible_message_id(realm, lookback_hours)
        m.assert_not_called()

        realm.message_visibility_limit = 10
        realm.save()
        RealmCount.objects.all().delete()
        with mock.patch("zerver.lib.message.update_first_visible_message_id") as m:
            maybe_update_first_visible_message_id(realm, lookback_hours)
        m.assert_not_called()

        RealmCount.objects.create(realm=realm, property=stat.property,
                                  end_time=end_time, value=5)
        with mock.patch("zerver.lib.message.update_first_visible_message_id") as m:
            maybe_update_first_visible_message_id(realm, lookback_hours)
        m.assert_called_once_with(realm)

class TestBulkGetHuddleUserIds(ZulipTestCase):
    def test_bulk_get_huddle_user_ids(self) -> None:
        hamlet = self.example_user('hamlet')
        cordelia = self.example_user('cordelia')
        othello = self.example_user('othello')
        iago = self.example_user('iago')
        message_ids = [
            self.send_huddle_message(hamlet, [cordelia, othello], 'test'),
            self.send_huddle_message(cordelia, [hamlet, othello, iago], 'test'),
        ]

        messages = Message.objects.filter(id__in=message_ids).order_by("id")
        first_huddle_recipient = messages[0].recipient
        first_huddle_user_ids = list(get_huddle_user_ids(first_huddle_recipient))
        second_huddle_recipient = messages[1].recipient
        second_huddle_user_ids = list(get_huddle_user_ids(second_huddle_recipient))

        huddle_user_ids = bulk_get_huddle_user_ids([first_huddle_recipient, second_huddle_recipient])
        self.assertEqual(huddle_user_ids[first_huddle_recipient.id], first_huddle_user_ids)
        self.assertEqual(huddle_user_ids[second_huddle_recipient.id], second_huddle_user_ids)

    def test_bulk_get_huddle_user_ids_empty_list(self) -> None:
        self.assertEqual(bulk_get_huddle_user_ids([]), {})

class NoRecipientIDsTest(ZulipTestCase):
    def test_no_recipient_ids(self) -> None:
        user_profile = self.example_user('cordelia')

        Subscription.objects.filter(user_profile=user_profile, recipient__type=Recipient.STREAM).delete()
        subs = gather_subscriptions_helper(user_profile)

        # Checks that gather_subscriptions_helper will not return anything
        # since there will not be any recipients, without crashing.
        #
        # This covers a rare corner case.
        self.assertEqual(len(subs[0]), 0)
