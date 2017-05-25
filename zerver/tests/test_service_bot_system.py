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

class TestMentionMessageTrigger(ZulipTestCase):

    def check_values_passed(self, queue_name, trigger_event, x):
        # type: (Any, Union[Mapping[Any, Any], Any], Callable[[Any], None]) -> None
        self.assertEqual(queue_name, "outgoing_webhooks")
        self.assertEqual(trigger_event['user_profile_id'], self.bot_profile.id)
        self.assertEqual(trigger_event['trigger'], "mention")
        self.assertEqual(trigger_event["message"]["sender_email"], self.user_profile.email)
        self.assertEqual(trigger_event["message"]["content"], self.content)
        self.assertEqual(trigger_event["message"]["type"], Recipient._type_names[Recipient.STREAM])
        self.assertEqual(trigger_event["message"]["display_recipient"], "Denmark")

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_mention_message_event_flow(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        self.user_profile = self.example_user("othello")
        self.bot_profile = do_create_user(email="foo-bot@zulip.com",
                                          password="test",
                                          realm=get_realm("zulip"),
                                          full_name="FooBot",
                                          short_name="foo-bot",
                                          bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                          bot_owner=self.user_profile)
        self.content = u'@**FooBot** foo bar!!!'
        mock_queue_json_publish.side_effect = self.check_values_passed

        # TODO: In future versions this won't be required
        self.subscribe_to_stream(self.bot_profile.email, "Denmark")
        self.send_message(self.user_profile.email, "Denmark", Recipient.STREAM, self.content)
        self.assertTrue(mock_queue_json_publish.called)

class PersonalMessageTriggersTest(ZulipTestCase):

    def setUp(self):
        # type: () -> None
        user_profile = self.example_user("othello")
        self.bot_user = do_create_user(email="testvabs-bot@zulip.com",
                                       password="test",
                                       realm=get_realm("zulip"),
                                       full_name="The Test Bot",
                                       short_name="bot",
                                       bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                       bot_owner=user_profile)
        self.temp_bot = do_create_user(email="temp-bot@zulip.com",
                                       password="temp",
                                       realm=get_realm("zulip"),
                                       full_name="The Temp test Bot",
                                       short_name="tempbot",
                                       bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
                                       bot_owner=user_profile)

    def test_no_trigger_on_stream_message(self):
        # type: () -> None
        sender_email = self.example_email("othello")
        recipients = "Denmark"
        message_type = Recipient.STREAM
        with mock.patch('zerver.lib.actions.queue_json_publish') as queue_json_publish:
            self.send_message(sender_email, recipients, message_type)
            self.assertFalse(queue_json_publish.called)

    def test_no_trigger_on_message_by_bot(self):
        # type: () -> None
        sender_email = "testvabs-bot@zulip.com"
        recipients = self.example_email("othello")
        message_type = Recipient.PERSONAL

        with mock.patch('zerver.lib.actions.queue_json_publish') as queue_json_publish:
            self.send_message(sender_email, recipients, message_type)
            self.assertFalse(queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_trigger_on_private_message_by_user(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        sender_email = self.example_email("othello")
        recipients = "testvabs-bot@zulip.com"
        message_type = Recipient.PERSONAL
        profile_id = self.bot_user.id

        def check_values_passed(queue_name, trigger_event, x):
            # type: (Any, Union[Mapping[Any, Any], Any], Callable[[Any], None]) -> None
            self.assertEqual(queue_name, "outgoing_webhooks")
            self.assertEqual(trigger_event["user_profile_id"], profile_id)
            self.assertEqual(trigger_event["trigger"], "private_message")
            self.assertEqual(trigger_event["failed_tries"], 0)
            self.assertEqual(trigger_event["message"]["sender_email"], sender_email)
            self.assertEqual(trigger_event["message"]["display_recipient"][0]["email"], sender_email)
            self.assertEqual(trigger_event["message"]["display_recipient"][1]["email"], recipients)
            self.assertEqual(trigger_event["message"]["type"], u'private')

        mock_queue_json_publish.side_effect = check_values_passed
        self.send_message(sender_email, recipients, message_type, subject='', content='test')
        self.assertTrue(mock_queue_json_publish.called)

    @mock.patch('zerver.lib.actions.queue_json_publish')
    def test_trigger_on_huddle_message_by_user(self, mock_queue_json_publish):
        # type: (mock.Mock) -> None
        sender_email = self.example_email("othello")
        recipients = [u"testvabs-bot@zulip.com", u"temp-bot@zulip.com"]
        message_type = Recipient.HUDDLE
        profile_ids = [self.bot_user.id, self.temp_bot.id]

        def check_values_passed(queue_name, trigger_event, x):
            # type: (Any, Union[Mapping[Any, Any], Any], Callable[[Any], None]) -> None
            self.assertEqual(queue_name, "outgoing_webhooks")
            self.assertIn(trigger_event["user_profile_id"], profile_ids)
            profile_ids.remove(trigger_event["user_profile_id"])
            self.assertEqual(trigger_event["trigger"], "private_message")
            self.assertEqual(trigger_event["failed_tries"], 0)
            self.assertEqual(trigger_event["message"]["sender_email"], sender_email)
            self.assertEqual(trigger_event["message"]["type"], u'private')

        mock_queue_json_publish.side_effect = check_values_passed
        self.send_message(sender_email, recipients, message_type, subject='', content='test')
        self.assertEqual(mock_queue_json_publish.call_count, 2)
