# -*- coding: utf-8 -*-

from unittest import mock
from mock import patch
from typing import Any, Dict, Tuple, Text, Optional

from zerver.lib.bot_lib import EmbeddedBotQuitException, EmbeddedBotHandler
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import (
    UserProfile, Recipient, get_display_recipient,
    get_service_profile, get_user, get_realm
)

import ujson

class TestEmbeddedBotMessaging(ZulipTestCase):
    def setUp(self) -> None:
        self.user_profile = self.example_user("othello")
        self.bot_profile = self.create_test_bot('embedded', self.user_profile,
                                                full_name='Embedded bot',
                                                bot_type=UserProfile.EMBEDDED_BOT,
                                                service_name='helloworld',
                                                config_data=ujson.dumps({'foo': 'bar'}))

    def test_pm_to_embedded_bot(self) -> None:
        self.send_personal_message(self.user_profile.email, self.bot_profile.email,
                                   content="help")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "beep boop")
        self.assertEqual(last_message.sender_id, self.bot_profile.id)
        display_recipient = get_display_recipient(last_message.recipient)
        # The next two lines error on mypy because the display_recipient is of type Union[Text, List[Dict[str, Any]]].
        # In this case, we know that display_recipient will be of type List[Dict[str, Any]].
        # Otherwise this test will error, which is wanted behavior anyway.
        self.assert_length(display_recipient, 1)  # type: ignore
        self.assertEqual(display_recipient[0]['email'], self.user_profile.email)   # type: ignore

    def test_stream_message_to_embedded_bot(self) -> None:
        self.send_stream_message(self.user_profile.email, "Denmark",
                                 content="@**{}** foo".format(self.bot_profile.full_name),
                                 topic_name="bar")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "beep boop")
        self.assertEqual(last_message.sender_id, self.bot_profile.id)
        self.assertEqual(last_message.subject, "bar")
        display_recipient = get_display_recipient(last_message.recipient)
        self.assertEqual(display_recipient, "Denmark")

    def test_stream_message_not_to_embedded_bot(self) -> None:
        self.send_stream_message(self.user_profile.email, "Denmark",
                                 content="foo", topic_name="bar")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "foo")

    def test_message_to_embedded_bot_with_initialize(self) -> None:
        with patch('zulip_bots.bots.helloworld.helloworld.HelloWorldHandler.initialize',
                   create=True) as mock_initialize:
            self.send_stream_message(self.user_profile.email, "Denmark",
                                     content="@**{}** foo".format(self.bot_profile.full_name),
                                     topic_name="bar")
            mock_initialize.assert_called_once()

    def test_embedded_bot_quit_exception(self) -> None:
        with patch('zulip_bots.bots.helloworld.helloworld.HelloWorldHandler.handle_message',
                   side_effect=EmbeddedBotQuitException("I'm quitting!")):
            with patch('logging.warning') as mock_logging:
                self.send_stream_message(self.user_profile.email, "Denmark",
                                         content="@**{}** foo".format(self.bot_profile.full_name),
                                         topic_name="bar")
                mock_logging.assert_called_once_with("I'm quitting!")

class TestEmbeddedBotFailures(ZulipTestCase):
    def test_message_embedded_bot_with_invalid_service(self) -> None:
        user_profile = self.example_user("othello")
        self.create_test_bot(short_name='embedded', user_profile=user_profile,
                             bot_type=UserProfile.EMBEDDED_BOT,
                             service_name='helloworld')
        bot_profile = get_user("embedded-bot@zulip.testserver",
                               get_realm('zulip'))
        service_profile = get_service_profile(bot_profile.id, 'helloworld')
        service_profile.name = 'invalid'
        service_profile.save()
        with patch('logging.error') as logging_error_mock:
            self.send_stream_message(user_profile.email, "Denmark",
                                     content="@**{}** foo".format(bot_profile.full_name),
                                     topic_name="bar")
            logging_error_mock.assert_called_once_with(
                "Error: User {} has bot with invalid embedded bot service invalid".format(bot_profile.id))
