# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function

import mock
from typing import Any, Union, Mapping, Callable

from zerver.lib.actions import do_create_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    get_realm,
    UserProfile,
    Recipient,
)

BOT_TYPE_TO_QUEUE_NAME = {
    UserProfile.OUTGOING_WEBHOOK_BOT: 'outgoing_webhooks',
    UserProfile.EMBEDDED_BOT: 'embedded_bots',
}

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
