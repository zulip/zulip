from typing import TYPE_CHECKING

import orjson

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse


class BotInteractionsTestCase(ZulipTestCase):
    def send_bot_message_with_widget(
        self, bot: UserProfile, widget_type: str, extra_data: dict
    ) -> int:
        """Helper to send a message with a widget from a bot."""
        widget_content = orjson.dumps(
            {"widget_type": widget_type, "extra_data": extra_data}
        ).decode()

        result = self.api_post(
            bot,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": orjson.dumps("Verona").decode(),
                "topic": "test",
                "content": "test widget",
                "widget_content": widget_content,
            },
        )
        self.assert_json_success(result)
        return orjson.loads(result.content)["id"]

    def test_handle_bot_interaction_button_click(self) -> None:
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        # Send a message with an interactive widget
        message_id = self.send_bot_message_with_widget(
            bot,
            "interactive",
            {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {"type": "button", "label": "Click me", "custom_id": "btn1"}
                        ],
                    }
                ]
            },
        )

        # User interacts with the button
        self.login_user(user)
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "button_click",
                "custom_id": "btn1",
                "data": "{}",
            },
        )
        self.assert_json_success(result)

    def test_handle_bot_interaction_select_menu(self) -> None:
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        # Send a message with an interactive widget with select menu
        message_id = self.send_bot_message_with_widget(
            bot,
            "interactive",
            {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {
                                "type": "select_menu",
                                "custom_id": "select1",
                                "options": [
                                    {"label": "Option 1", "value": "opt1"},
                                    {"label": "Option 2", "value": "opt2"},
                                ],
                            }
                        ],
                    }
                ]
            },
        )

        # User interacts with the select menu
        self.login_user(user)
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "select_menu",
                "custom_id": "select1",
                "data": orjson.dumps({"values": ["opt1"]}).decode(),
            },
        )
        self.assert_json_success(result)

    def test_handle_bot_interaction_modal_submit(self) -> None:
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        # Send a message with an interactive widget
        message_id = self.send_bot_message_with_widget(
            bot,
            "interactive",
            {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {"type": "button", "label": "Open Form", "custom_id": "form_btn"}
                        ],
                    }
                ]
            },
        )

        # User submits a modal
        self.login_user(user)
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "modal_submit",
                "custom_id": "my_modal",
                "data": orjson.dumps({"fields": {"name": "John", "email": "john@example.com"}}).decode(),
            },
        )
        self.assert_json_success(result)

    def test_handle_bot_interaction_non_bot_message(self) -> None:
        user = self.example_user("hamlet")

        # Send a regular message (not from a bot)
        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": orjson.dumps("Verona").decode(),
                "topic": "test",
                "content": "regular message",
            },
        )
        self.assert_json_success(result)
        message_id = orjson.loads(result.content)["id"]

        # Try to interact with it
        result = self.api_post(
            user,
            "/api/v1/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "button_click",
                "custom_id": "btn1",
                "data": "{}",
            },
        )
        self.assert_json_error(result, "Can only interact with bot messages")

    def test_handle_bot_interaction_invalid_type(self) -> None:
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        # Send a message with an interactive widget
        message_id = self.send_bot_message_with_widget(
            bot,
            "interactive",
            {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {"type": "button", "label": "Click", "custom_id": "btn1"}
                        ],
                    }
                ]
            },
        )

        # Try invalid interaction type
        self.login_user(user)
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "invalid_type",
                "custom_id": "btn1",
                "data": "{}",
            },
        )
        self.assert_json_error(result, "Invalid interaction type")


class FreeformWidgetSecurityTestCase(ZulipTestCase):
    def test_freeform_widget_requires_trusted_bot(self) -> None:
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        # Bot is not trusted by default
        self.assertFalse(bot.is_trusted_bot)

        # Try to send a freeform widget
        widget_content = orjson.dumps(
            {"widget_type": "freeform", "extra_data": {"html": "<div>test</div>"}}
        ).decode()

        result = self.api_post(
            bot,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": orjson.dumps("Verona").decode(),
                "topic": "test",
                "content": "test widget",
                "widget_content": widget_content,
            },
        )
        self.assert_json_error(result, "Freeform widgets require a trusted bot")

    def test_freeform_widget_trusted_bot_allowed(self) -> None:
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)

        # Mark bot as trusted
        bot.is_trusted_bot = True
        bot.save()

        # Now freeform widget should be allowed
        widget_content = orjson.dumps(
            {"widget_type": "freeform", "extra_data": {"html": "<div>test</div>"}}
        ).decode()

        result = self.api_post(
            bot,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": orjson.dumps("Verona").decode(),
                "topic": "test",
                "content": "test widget",
                "widget_content": widget_content,
            },
        )
        self.assert_json_success(result)

    def test_freeform_widget_non_bot_rejected(self) -> None:
        user = self.example_user("hamlet")

        # Regular user tries to send freeform widget
        widget_content = orjson.dumps(
            {"widget_type": "freeform", "extra_data": {"html": "<div>test</div>"}}
        ).decode()

        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": orjson.dumps("Verona").decode(),
                "topic": "test",
                "content": "test widget",
                "widget_content": widget_content,
            },
        )
        self.assert_json_error(result, "Freeform widgets require a trusted bot")
