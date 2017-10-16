# -*- coding: utf-8 -*-

import mock
from typing import Any, Union, Mapping, Callable

from zerver.lib.actions import (
    do_create_user,
    get_service_bot_events,
)
from zerver.lib.bot_lib import StateHandler, StateHandlerError
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    get_realm,
    BotUserStateData,
    UserProfile,
    Recipient,
)

BOT_TYPE_TO_QUEUE_NAME = {
    UserProfile.OUTGOING_WEBHOOK_BOT: 'outgoing_webhooks',
    UserProfile.EMBEDDED_BOT: 'embedded_bots',
}

class TestServiceBotBasics(ZulipTestCase):
    def _get_outgoing_bot(self):
        # type: () -> UserProfile
        outgoing_bot = do_create_user(
            email="bar-bot@zulip.com",
            password="test",
            realm=get_realm("zulip"),
            full_name="BarBot",
            short_name='bb',
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            bot_owner=self.example_user('cordelia'),
        )

        return outgoing_bot

    def test_service_events_for_pms(self):
        # type: () -> None
        sender = self.example_user('hamlet')
        assert(not sender.is_bot)

        outgoing_bot = self._get_outgoing_bot()

        event_dict = get_service_bot_events(
            sender=sender,
            service_bot_tuples=[
                (outgoing_bot.id, outgoing_bot.bot_type),
            ],
            mentioned_user_ids=set(),
            recipient_type=Recipient.PERSONAL,
        )

        expected = dict(
            outgoing_webhooks=[
                dict(trigger='private_message', user_profile_id=outgoing_bot.id),
            ],
        )

        self.assertEqual(event_dict, expected)

    def test_service_events_for_stream_mentions(self):
        # type: () -> None
        sender = self.example_user('hamlet')
        assert(not sender.is_bot)

        outgoing_bot = self._get_outgoing_bot()

        event_dict = get_service_bot_events(
            sender=sender,
            service_bot_tuples=[
                (outgoing_bot.id, outgoing_bot.bot_type),
            ],
            mentioned_user_ids={outgoing_bot.id},
            recipient_type=Recipient.STREAM,
        )

        expected = dict(
            outgoing_webhooks=[
                dict(trigger='mention', user_profile_id=outgoing_bot.id),
            ],
        )

        self.assertEqual(event_dict, expected)

    def test_service_events_for_unsubscribed_stream_mentions(self):
        # type: () -> None
        sender = self.example_user('hamlet')
        assert(not sender.is_bot)

        outgoing_bot = self._get_outgoing_bot()

        '''
        If an outgoing bot is mentioned on a stream message, we will
        create an event for it even if it is not subscribed to the
        stream and not part of our original `service_bot_tuples`.

        Note that we add Cordelia as a red herring value that the
        code should ignore, since she is not a bot.
        '''

        cordelia = self.example_user('cordelia')

        event_dict = get_service_bot_events(
            sender=sender,
            service_bot_tuples=[],
            mentioned_user_ids={
                outgoing_bot.id,
                cordelia.id,  # should be excluded, not a service bot
            },
            recipient_type=Recipient.STREAM,
        )

        expected = dict(
            outgoing_webhooks=[
                dict(trigger='mention', user_profile_id=outgoing_bot.id),
            ],
        )

        self.assertEqual(event_dict, expected)

class TestServiceBotStateHandler(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.user_profile = self.example_user("othello")
        self.bot_profile = do_create_user(email="embedded-bot-1@zulip.com",
                                          password="test",
                                          realm=get_realm("zulip"),
                                          full_name="EmbeddedBo1",
                                          short_name="embedded-bot-1",
                                          bot_type=UserProfile.EMBEDDED_BOT,
                                          bot_owner=self.user_profile)
        self.second_bot_profile = do_create_user(email="embedded-bot-2@zulip.com",
                                                 password="test",
                                                 realm=get_realm("zulip"),
                                                 full_name="EmbeddedBot2",
                                                 short_name="embedded-bot-2",
                                                 bot_type=UserProfile.EMBEDDED_BOT,
                                                 bot_owner=self.user_profile)

    def test_basic_storage_and_retrieval(self):
        # type: () -> None
        state_handler = StateHandler(self.bot_profile)
        state_handler['some key'] = 'some value'
        state_handler['some other key'] = 'some other value'
        self.assertEqual(state_handler['some key'], 'some value')
        self.assertEqual(state_handler['some other key'], 'some other value')
        self.assertFalse('nonexistent key' in state_handler)
        self.assertRaises(BotUserStateData.DoesNotExist, lambda: state_handler['nonexistent key'])

        second_state_handler = StateHandler(self.second_bot_profile)
        self.assertRaises(BotUserStateData.DoesNotExist, lambda: second_state_handler['some key'])
        second_state_handler['some key'] = 'yet another value'
        self.assertEqual(state_handler['some key'], 'some value')
        self.assertEqual(second_state_handler['some key'], 'yet another value')

    def test_storage_limit(self):
        # type: () -> None
        # Reduce maximal state size for faster test string construction.
        StateHandler.state_size_limit = 100
        state_handler = StateHandler(self.bot_profile)
        key = 'capacity-filling entry'
        state_handler[key] = 'x' * (state_handler.state_size_limit - len(key))

        with self.assertRaisesMessage(StateHandlerError, "Cannot set state. Request would require 132 bytes storage. "
                                                         "The current storage limit is 100."):
            state_handler['too much data'] = 'a few bits too long'

        second_state_handler = StateHandler(self.second_bot_profile)
        second_state_handler['another big entry'] = 'x' * (state_handler.state_size_limit - 40)
        second_state_handler['normal entry'] = 'abcd'

class TestServiceBotEventTriggers(ZulipTestCase):

    def setUp(self):
        # type: () -> None
        self.user_profile = self.example_user("othello")
        self.bot_profile = do_create_user(email="foo-bot@zulip.com",
                                          password="test",
                                          realm=get_realm("zulip"),
                                          full_name="FooBot",
                                          short_name="foo-bot",
                                          bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                          bot_owner=self.user_profile)
        self.second_bot_profile = do_create_user(email="bar-bot@zulip.com",
                                                 password="test",
                                                 realm=get_realm("zulip"),
                                                 full_name="BarBot",
                                                 short_name="bar-bot",
                                                 bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                                 bot_owner=self.user_profile)

        # TODO: In future versions this won't be required
        self.subscribe(self.bot_profile, 'Denmark')

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_trigger_on_stream_mention_from_user(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        for bot_type, expected_queue_name in BOT_TYPE_TO_QUEUE_NAME.items():
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()

            content = u'@**FooBot** foo bar!!!'
            recipient = 'Denmark'
            trigger = 'mention'
            message_type = Recipient._type_names[Recipient.STREAM]

            def check_values_passed(queue_name, trigger_event, x):
                # type: (Any, Union[Mapping[Any, Any], Any], Callable[[Any], None]) -> None
                self.assertEqual(queue_name, expected_queue_name)
                self.assertEqual(trigger_event["failed_tries"], 0)
                self.assertEqual(trigger_event["message"]["content"], content)
                self.assertEqual(trigger_event["message"]["display_recipient"], recipient)
                self.assertEqual(trigger_event["message"]["sender_email"], self.user_profile.email)
                self.assertEqual(trigger_event["message"]["type"], message_type)
                self.assertEqual(trigger_event['trigger'], trigger)
                self.assertEqual(trigger_event['user_profile_id'], self.bot_profile.id)
            mock_queue_json_publish.side_effect = check_values_passed

            self.send_message(
                self.user_profile.email,
                'Denmark',
                Recipient.STREAM,
                content)
            self.assertTrue(mock_queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_no_trigger_on_stream_message_without_mention(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        sender_email = self.user_profile.email
        recipients = "Denmark"
        message_type = Recipient.STREAM
        self.send_message(sender_email, recipients, message_type)
        self.assertFalse(mock_queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_no_trigger_on_stream_mention_from_bot(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        for bot_type in BOT_TYPE_TO_QUEUE_NAME:
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()

            self.send_message(
                self.second_bot_profile.email,
                'Denmark',
                Recipient.STREAM,
                u'@**FooBot** foo bar!!!')
            self.assertFalse(mock_queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_trigger_on_personal_message_from_user(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        for bot_type, expected_queue_name in BOT_TYPE_TO_QUEUE_NAME.items():
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()

            sender_email = self.user_profile.email
            recipient_email = self.bot_profile.email
            message_type = Recipient.PERSONAL

            def check_values_passed(queue_name, trigger_event, x):
                # type: (Any, Union[Mapping[Any, Any], Any], Callable[[Any], None]) -> None
                self.assertEqual(queue_name, expected_queue_name)
                self.assertEqual(trigger_event["user_profile_id"], self.bot_profile.id)
                self.assertEqual(trigger_event["trigger"], "private_message")
                self.assertEqual(trigger_event["failed_tries"], 0)
                self.assertEqual(trigger_event["message"]["sender_email"], sender_email)
                display_recipients = [
                    trigger_event["message"]["display_recipient"][0]["email"],
                    trigger_event["message"]["display_recipient"][1]["email"],
                ]
                self.assertTrue(sender_email in display_recipients)
                self.assertTrue(recipient_email in display_recipients)
            mock_queue_json_publish.side_effect = check_values_passed

            self.send_message(sender_email, recipient_email, message_type, subject='', content='test')
            self.assertTrue(mock_queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_no_trigger_on_personal_message_from_bot(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        for bot_type in BOT_TYPE_TO_QUEUE_NAME:
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()

            sender_email = self.second_bot_profile.email
            recipient_email = self.bot_profile.email
            message_type = Recipient.PERSONAL
            self.send_message(sender_email, recipient_email, message_type)
            self.assertFalse(mock_queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_trigger_on_huddle_message_from_user(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        for bot_type, expected_queue_name in BOT_TYPE_TO_QUEUE_NAME.items():
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()

            self.second_bot_profile.bot_type = bot_type
            self.second_bot_profile.save()

            sender_email = self.user_profile.email
            recipient_emails = [self.bot_profile.email, self.second_bot_profile.email]
            message_type = Recipient.HUDDLE
            profile_ids = [self.bot_profile.id, self.second_bot_profile.id]

            def check_values_passed(queue_name, trigger_event, x):
                # type: (Any, Union[Mapping[Any, Any], Any], Callable[[Any], None]) -> None
                self.assertEqual(queue_name, expected_queue_name)
                self.assertIn(trigger_event["user_profile_id"], profile_ids)
                profile_ids.remove(trigger_event["user_profile_id"])
                self.assertEqual(trigger_event["trigger"], "private_message")
                self.assertEqual(trigger_event["failed_tries"], 0)
                self.assertEqual(trigger_event["message"]["sender_email"], sender_email)
                self.assertEqual(trigger_event["message"]["type"], u'private')
            mock_queue_json_publish.side_effect = check_values_passed

            self.send_message(sender_email, recipient_emails, message_type, subject='', content='test')
            self.assertEqual(mock_queue_json_publish.call_count, 2)
            mock_queue_json_publish.reset_mock()

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_no_trigger_on_huddle_message_from_bot(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        for bot_type in BOT_TYPE_TO_QUEUE_NAME:
            self.bot_profile.bot_type = bot_type
            self.bot_profile.save()

            sender_email = self.second_bot_profile.email
            recipient_emails = [self.user_profile.email, self.bot_profile.email]
            message_type = Recipient.HUDDLE
            self.send_message(sender_email, recipient_emails, message_type)
            self.assertFalse(mock_queue_json_publish.called)
