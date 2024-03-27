from django.http import HttpRequest
from typing_extensions import override

from zerver.lib.onboarding import send_initial_direct_message
from zerver.lib.test_classes import ZulipTestCase
from zerver.views.custom_welcome_message import preview_custom_welcome_test_message


class CustomWelcomeMessageTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("iago")

    def test_preview_custom_welcome_test_message(self) -> None:
        self.login("iago")
        request = HttpRequest()
        request.user = self.user_profile
        custom_welcome_test_message = "Welcome to Zulip!"

        result = self.client_post(
            "/json/realm/preview_custom_welcome_message",
            {"custom_welcome_test_message": custom_welcome_test_message},
        )
        self.assert_json_success(result)

        response = preview_custom_welcome_test_message(
            request, self.user_profile, custom_welcome_test_message=custom_welcome_test_message
        )
        self.assert_json_success(response)

    def test_not_realm_admin(self) -> None:
        self.login("hamlet")
        request = HttpRequest()
        request.user = self.user_profile
        custom_welcome_test_message = "Welcome to Zulip!"

        result = self.client_post(
            "/json/realm/preview_custom_welcome_message",
            {"custom_welcome_test_message": custom_welcome_test_message},
        )
        self.assert_json_error(result, "Must be an organization administrator")

    def test_custom_welcome_message_enabled_with_text(self) -> None:
        # Set up the realm with custom_welcome_message_enabled and custom_welcome_message_text
        realm = self.user_profile.realm
        realm.custom_welcome_message_enabled = True
        realm.custom_welcome_message_text = "Custom welcome message text"
        realm.save(update_fields=["custom_welcome_message_enabled", "custom_welcome_message_text"])

        # Call the send_initial_direct_message function
        send_initial_direct_message(self.user_profile)

        # Fetch the last message sent to the user profile
        last_message = self.get_last_message()

        # Verify that the custom welcome message is included in the message content
        self.assertIn("Custom welcome message text", last_message.content)
