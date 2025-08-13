from typing_extensions import override

from zerver.lib.test_classes import ZulipTestCase


class WelcomeBotCustomMessageTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("iago")

    def test_empty_welcome_bot_custom_message(self) -> None:
        user = self.example_user("desdemona")
        self.login_user(user)

        result = self.client_post(
            "/json/realm/test_welcome_bot_custom_message",
            {"welcome_message_custom_text": ""},
        )
        self.assert_json_error(result, "Message must not be empty")

    def test_welcome_bot_custom_message(self) -> None:
        user = self.example_user("desdemona")
        self.login_user(user)
        welcome_message_custom_text = "Welcome Bot custom message for testing"

        result = self.client_post(
            "/json/realm/test_welcome_bot_custom_message",
            {"welcome_message_custom_text": welcome_message_custom_text},
        )
        response_dict = self.assert_json_success(result)
        welcome_bot_custom_message_id = response_dict["message_id"]

        # Make sure that only message with custom text is sent.
        previous_message = self.get_second_to_last_message()
        self.assertNotEqual(previous_message.sender.email, "welcome-bot@zulip.com")

        received_welcome_bot_custom_message = self.get_last_message()

        self.assertEqual(received_welcome_bot_custom_message.sender.email, "welcome-bot@zulip.com")
        self.assertIn(welcome_message_custom_text, received_welcome_bot_custom_message.content)
        self.assertEqual(welcome_bot_custom_message_id, received_welcome_bot_custom_message.id)
