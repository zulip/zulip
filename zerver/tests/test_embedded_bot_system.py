# -*- coding: utf-8 -*-

from typing import Any, Dict, Tuple, Text, Optional

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile, Recipient, get_display_recipient

class TestEmbeddedBotMessaging(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.user_profile = self.example_user("othello")
        self.bot_profile = self.create_test_bot('embedded-bot@zulip.testserver', self.user_profile, 'Embedded bot',
                                                'embedded', UserProfile.EMBEDDED_BOT, service_name='helloworld')

    def test_pm_to_embedded_bot(self):
        # type: () -> None
        self.send_message(self.user_profile.email, self.bot_profile.email,
                          message_type=Recipient.PERSONAL, content="help")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "beep boop")
        self.assertEqual(last_message.sender_id, self.bot_profile.id)
        display_recipient = get_display_recipient(last_message.recipient)
        # The next two lines error on mypy because the display_recipient is of type Union[Text, List[Dict[str, Any]]].
        # In this case, we know that display_recipient will be of type List[Dict[str, Any]].
        # Otherwise this test will error, which is wanted behavior anyway.
        self.assert_length(display_recipient, 1)  # type: ignore
        self.assertEqual(display_recipient[0]['email'], self.user_profile.email)   # type: ignore

    def test_stream_message_to_embedded_bot(self):
        # type: () -> None
        self.send_message(self.user_profile.email, "Denmark", Recipient.STREAM,
                          content="@**{}** foo".format(self.bot_profile.full_name), subject="bar")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "beep boop")
        self.assertEqual(last_message.sender_id, self.bot_profile.id)
        self.assertEqual(last_message.subject, "bar")
        display_recipient = get_display_recipient(last_message.recipient)
        self.assertEqual(display_recipient, "Denmark")

    def test_stream_message_not_to_embedded_bot(self):
        # type: () -> None
        self.send_message(self.user_profile.email, "Denmark", Recipient.STREAM,
                          content="foo", subject="bar")
        last_message = self.get_last_message()
        self.assertEqual(last_message.content, "foo")
