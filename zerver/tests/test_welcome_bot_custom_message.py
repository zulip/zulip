from django.http import HttpRequest
from typing_extensions import override

from zerver.lib.onboarding import send_initial_direct_message
from zerver.lib.test_classes import ZulipTestCase
from zerver.views.welcome_bot_custom_message import send_test_welcome_bot_custom_message


class WelcomeBotCustomMessageTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("iago")

    def test_welcome_bot_custom_message(self) -> None:
        self.login("iago")
        request = HttpRequest()
        request.user = self.user_profile
        welcome_bot_custom_message = "Welcome to Zulip!"

        result = self.client_post(
            "/json/realm/test_welcome_bot_custom_message",
            {"welcome_bot_custom_message": welcome_bot_custom_message},
        )
        self.assert_json_success(result)

        response = send_test_welcome_bot_custom_message(
            request, self.user_profile, welcome_bot_custom_message=welcome_bot_custom_message
        )
        self.assert_json_success(response)

    def test_not_realm_admin(self) -> None:
        self.login("hamlet")
        request = HttpRequest()
        request.user = self.user_profile
        welcome_bot_custom_message = "Welcome to Zulip!"

        result = self.client_post(
            "/json/realm/test_welcome_bot_custom_message",
            {"welcome_bot_custom_message": welcome_bot_custom_message},
        )
        self.assert_json_error(result, "Must be an organization administrator")

    def test_welcome_bot_custom_message_enabled_with_text(self) -> None:
        # Set up the realm with welcome_bot_custom_message_enabled and welcome_bot_custom_message
        realm = self.user_profile.realm
        realm.welcome_bot_custom_message_enabled = True
        realm.welcome_bot_custom_message = "Welcome bot custom message"
        realm.save(
            update_fields=["welcome_bot_custom_message_enabled", "welcome_bot_custom_message"]
        )

        send_initial_direct_message(self.user_profile)

        last_message = self.get_last_message()

        self.assertIn("Welcome bot custom message", last_message.content)
