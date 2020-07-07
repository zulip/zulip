import datetime
from typing import Dict, List
from unittest import mock

from django.utils.timezone import now as timezone_now

from analytics.lib.counts import COUNT_STATS
from analytics.models import RealmCount
from zerver.decorator import JsonableError
from zerver.lib.actions import (
    check_message,
    do_create_user,
    gather_subscriptions_helper,
    get_active_presence_idle_user_ids,
    get_client,
    get_last_message_id,
    send_rate_limited_pm_notification_to_bot_owner,
)
from zerver.lib.addressee import Addressee
from zerver.lib.message import (
    get_first_visible_message_id,
    maybe_update_first_visible_message_id,
    update_first_visible_message_id,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import (
    make_client,
    message_stream_count,
    most_recent_message,
    most_recent_usermessage,
)
from zerver.lib.topic import DB_TOPIC_NAME
from zerver.lib.url_encoding import near_message_url
from zerver.models import (
    Message,
    Recipient,
    Subscription,
    UserPresence,
    UserProfile,
    bulk_get_huddle_user_ids,
    get_huddle_user_ids,
    get_realm,
)


class MiscMessageTest(ZulipTestCase):
    def test_get_last_message_id(self) -> None:
        self.assertEqual(
            get_last_message_id(),
            Message.objects.latest('id').id,
        )

        Message.objects.all().delete()

        self.assertEqual(get_last_message_id(), -1)

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
