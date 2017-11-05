# -*- coding: utf-8 -*-

from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import message_stream_count, most_recent_message
from zerver.models import get_realm, get_user, Recipient, UserProfile

from typing import Any, Dict
import ujson

class TutorialTests(ZulipTestCase):
    def setUp(self) -> None:
        # This emulates the welcome message sent by the welcome bot to hamlet@zulip.com
        # This is only a quick fix - ideally, we would have this message sent by the initialization
        # code in populate_db.py
        user_email = 'hamlet@zulip.com'
        bot_email = 'welcome-bot@zulip.com'
        content = 'Shortened welcome message.'
        self.send_personal_message(bot_email, user_email, content)

    def test_tutorial_status(self) -> None:
        email = self.example_email('hamlet')
        self.login(email)

        cases = [
            ('started', UserProfile.TUTORIAL_STARTED),
            ('finished', UserProfile.TUTORIAL_FINISHED),
        ]
        for incoming_status, expected_db_status in cases:
            params = dict(status=ujson.dumps(incoming_status))
            result = self.client_post('/json/users/me/tutorial_status', params)
            self.assert_json_success(result)
            user = self.example_user('hamlet')
            self.assertEqual(user.tutorial_status, expected_db_status)

    def test_single_response_to_pm(self) -> None:
        realm = get_realm('zulip')
        user_email = 'hamlet@zulip.com'
        bot_email = 'welcome-bot@zulip.com'
        content = 'whatever'
        self.login(user_email)
        self.send_personal_message(user_email, bot_email, content)
        user = get_user(user_email, realm)
        user_messages = message_stream_count(user)
        expected_response = ("Congratulations on your first reply! :tada:\n\n"
                             "Feel free to continue using this space to practice your new messaging "
                             "skills. Or, try clicking on some of the stream names to your left!")
        self.assertEqual(most_recent_message(user).content, expected_response)
        # Welcome bot shouldn't respond to further PMs.
        self.send_personal_message(user_email, bot_email, content)
        self.assertEqual(message_stream_count(user), user_messages+1)

    def test_no_response_to_group_pm(self) -> None:
        realm = get_realm('zulip')  # Assume realm is always 'zulip'
        user1_email = self.example_email('hamlet')
        user2_email = self.example_email('cordelia')
        bot_email = self.example_email('welcome_bot')
        content = "whatever"
        self.login(user1_email)
        self.send_huddle_message(user1_email, [bot_email, user2_email], content)
        user1 = get_user(user1_email, realm)
        user1_messages = message_stream_count(user1)
        self.assertEqual(most_recent_message(user1).content, content)
        # Welcome bot should still respond to initial PM after group PM.
        self.send_personal_message(user1_email, bot_email, content)
        self.assertEqual(message_stream_count(user1), user1_messages+2)
