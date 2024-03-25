from django.http import HttpRequest
from typing_extensions import override

from zerver.lib.onboarding import send_initial_direct_message
from zerver.lib.test_classes import ZulipTestCase
from zerver.views.welcome_bot_custom_message import send_test_custom_welcome_bot_message


class CustomWelcomeBotMessageTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("iago")

    def test_custom_welcome_bot_message(self) -> None:
        self.login("iago")
        request = HttpRequest()
        request.user = self.user_profile
        custom_welcome_bot_message = "Welcome to Zulip!"

        result = self.client_post(
            "/json/realm/test_custom_welcome_bot_message",
            {"custom_welcome_bot_message": custom_welcome_bot_message},
        )
        self.assert_json_success(result)

        response = send_test_custom_welcome_bot_message(
            request, self.user_profile, custom_welcome_bot_message=custom_welcome_bot_message
        )
        self.assert_json_success(response)

    def test_not_realm_admin(self) -> None:
        self.login("hamlet")
        request = HttpRequest()
        request.user = self.user_profile
        custom_welcome_bot_message = "Welcome to Zulip!"

        result = self.client_post(
            "/json/realm/test_custom_welcome_bot_message",
            {"custom_welcome_bot_message": custom_welcome_bot_message},
        )
        self.assert_json_error(result, "Must be an organization administrator")

    def test_custom_welcome_bot_message_enabled_with_text(self) -> None:
        # Set up the realm with custom_welcome_bot_message_enabled and custom_welcome_bot_message
        realm = self.user_profile.realm
        realm.custom_welcome_bot_message_enabled = True
        realm.custom_welcome_bot_message = "Custom welcome bot message"
        realm.save(
            update_fields=["custom_welcome_bot_message_enabled", "custom_welcome_bot_message"]
        )

        send_initial_direct_message(self.user_profile)

        last_message = self.get_last_message()

        self.assertIn("Custom welcome bot message", last_message.content)
