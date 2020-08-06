import orjson
from django.conf import settings

from zerver.lib.actions import internal_send_private_message
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import message_stream_count, most_recent_message
from zerver.models import UserProfile, get_system_bot


class TutorialTests(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        # This emulates the welcome message sent by the welcome bot to hamlet@zulip.com
        # This is only a quick fix - ideally, we would have this message sent by the initialization
        # code in populate_db.py
        user = self.example_user('hamlet')
        welcome_bot = get_system_bot(settings.WELCOME_BOT)
        content = 'Shortened welcome message.'
        internal_send_private_message(welcome_bot.realm, welcome_bot, user, content)

    def test_tutorial_status(self) -> None:
        user = self.example_user('hamlet')
        self.login_user(user)

        cases = [
            ('started', UserProfile.TUTORIAL_STARTED),
            ('finished', UserProfile.TUTORIAL_FINISHED),
        ]
        for incoming_status, expected_db_status in cases:
            params = dict(status=orjson.dumps(incoming_status).decode())
            result = self.client_post('/json/users/me/tutorial_status', params)
            self.assert_json_success(result)
            user = self.example_user('hamlet')
            self.assertEqual(user.tutorial_status, expected_db_status)

    def test_single_response_to_pm(self) -> None:
        user = self.example_user('hamlet')
        bot = get_system_bot(settings.WELCOME_BOT)
        content = 'whatever'
        self.login_user(user)
        self.send_personal_message(user, bot, content)
        user_messages = message_stream_count(user)
        expected_response = ("Congratulations on your first reply! :tada:\n\n"
                             "Feel free to continue using this space to practice your new messaging "
                             "skills. Or, try clicking on some of the stream names to your left!")
        self.assertEqual(most_recent_message(user).content, expected_response)
        # Welcome bot shouldn't respond to further PMs.
        self.send_personal_message(user, bot, content)
        self.assertEqual(message_stream_count(user), user_messages+1)

    def test_no_response_to_group_pm(self) -> None:
        user1 = self.example_user('hamlet')
        user2 = self.example_user('cordelia')
        bot = get_system_bot(settings.WELCOME_BOT)
        content = "whatever"
        self.login_user(user1)
        self.send_huddle_message(user1, [bot, user2], content)
        user1_messages = message_stream_count(user1)
        self.assertEqual(most_recent_message(user1).content, content)
        # Welcome bot should still respond to initial PM after group PM.
        self.send_personal_message(user1, bot, content)
        self.assertEqual(message_stream_count(user1), user1_messages+2)
