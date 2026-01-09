from typing import Any
from unittest.mock import MagicMock, patch

import orjson
import requests
import responses

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, SubMessage, UserPresence, UserProfile
from zerver.models.bots import Service
from zerver.tests.test_queue_worker import FakeClient, simulated_queue_client
from zerver.worker.bot_interactions import BotInteractionWorker
from zerver.worker.deferred_work import DeferredWorker


class BotInteractionsTestCase(ZulipTestCase):
    def send_bot_message_with_widget(
        self, bot: UserProfile, widget_type: str, extra_data: dict[str, Any]
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
                "data": orjson.dumps(
                    {"fields": {"name": "John", "email": "john@example.com"}}
                ).decode(),
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
                        "components": [{"type": "button", "label": "Click", "custom_id": "btn1"}],
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


class BotInteractionWorkerTests(ZulipTestCase):
    """Tests for the BotInteractionWorker queue processing."""

    def make_interaction_event(
        self, bot: UserProfile, user: UserProfile, message_id: int
    ) -> dict[str, Any]:
        """Helper to create a standard interaction event."""
        return {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-interaction-id",
            "message": {
                "id": message_id,
                "stream_id": 1,
                "topic": "test",
            },
            "user": {
                "id": user.id,
                "email": user.delivery_email,
                "full_name": user.full_name,
            },
        }

    @responses.activate
    def test_worker_routes_to_outgoing_webhook_bot(self) -> None:
        """Verify worker routes events to outgoing webhook bots via HTTP POST."""
        owner = self.example_user("hamlet")
        bot = self.create_test_bot(
            "webhook-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            service_name="test-service",
            payload_url='"https://bot.example.com/"',
        )

        # Mock the bot's webhook URL
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json={},
            status=200,
        )

        event = self.make_interaction_event(bot, owner, message_id=123)

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with simulated_queue_client(fake_client):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        # Verify the HTTP POST was made
        self.assert_length(responses.calls, 1)
        request_body = responses.calls[0].request.body
        assert request_body is not None
        payload = orjson.loads(request_body)
        self.assertEqual(payload["type"], "interaction")
        self.assertEqual(payload["interaction_type"], "button_click")
        self.assertEqual(payload["custom_id"], "btn1")

    def test_worker_routes_to_embedded_bot(self) -> None:
        """Verify worker routes events to embedded bots via handler method."""
        owner = self.example_user("hamlet")
        bot = self.create_test_bot(
            "embedded-bot",
            owner,
            bot_type=UserProfile.EMBEDDED_BOT,
            service_name="helloworld",  # Required for embedded bots
        )

        event = self.make_interaction_event(bot, owner, message_id=123)

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        # Mock the embedded bot handler
        with (
            simulated_queue_client(fake_client),
            patch("zerver.lib.bot_lib.get_bot_handler") as mock_get_handler,
        ):
            mock_handler = MagicMock()
            mock_handler.handle_interaction = MagicMock()
            mock_get_handler.return_value = mock_handler

            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

            # Verify handle_interaction was called
            mock_handler.handle_interaction.assert_called_once()
            call_args = mock_handler.handle_interaction.call_args
            interaction = call_args.kwargs["interaction"]
            self.assertEqual(interaction["type"], "button_click")
            self.assertEqual(interaction["custom_id"], "btn1")

    def test_worker_logs_warning_for_unsupported_bot_type(self) -> None:
        """Verify worker logs warning for unsupported bot types."""
        owner = self.example_user("hamlet")
        bot = self.create_test_bot(
            "default-bot",
            owner,
            bot_type=UserProfile.DEFAULT_BOT,
        )

        event = self.make_interaction_event(bot, owner, message_id=123)

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with (
            simulated_queue_client(fake_client),
            self.assertLogs("zerver.worker.bot_interactions", level="WARNING") as logs,
        ):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        self.assertTrue(
            any("unsupported bot type" in log for log in logs.output),
            f"Expected warning about unsupported bot type, got: {logs.output}",
        )


class OutgoingWebhookInteractionTests(ZulipTestCase):
    """Tests for HTTP delivery of interactions to webhook bots."""

    def create_webhook_bot_with_service(
        self, owner: UserProfile, url: str = "https://bot.example.com/"
    ) -> UserProfile:
        """Helper to create a webhook bot with a configured service."""
        bot = self.create_test_bot(
            "webhook-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            service_name="test-service",
            payload_url=f'"{url}"',  # URL must be JSON-encoded
        )
        return bot

    def make_interaction_event(
        self,
        bot: UserProfile,
        user: UserProfile,
        message_id: int,
        interaction_type: str = "button_click",
        custom_id: str = "btn1",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Helper to create an interaction event."""
        return {
            "bot_user_id": bot.id,
            "interaction_type": interaction_type,
            "custom_id": custom_id,
            "data": data or {},
            "interaction_id": "test-interaction-id",
            "message": {
                "id": message_id,
                "stream_id": 1,
                "topic": "test topic",
            },
            "user": {
                "id": user.id,
                "email": user.delivery_email,
                "full_name": user.full_name,
            },
        }

    @responses.activate
    def test_interaction_payload_contains_required_fields(self) -> None:
        """Verify the POST payload contains all required fields."""
        owner = self.example_user("hamlet")
        bot = self.create_webhook_bot_with_service(owner)

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json={},
            status=200,
        )

        event = self.make_interaction_event(
            bot, owner, message_id=456, custom_id="my_button", data={"key": "value"}
        )

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with simulated_queue_client(fake_client):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        self.assert_length(responses.calls, 1)
        request_body = responses.calls[0].request.body
        assert request_body is not None
        payload = orjson.loads(request_body)

        # Verify required fields
        self.assertEqual(payload["type"], "interaction")
        self.assertEqual(payload["interaction_type"], "button_click")
        self.assertEqual(payload["custom_id"], "my_button")
        self.assertEqual(payload["data"], {"key": "value"})
        self.assertEqual(payload["interaction_id"], "test-interaction-id")

        # Verify bot info
        self.assertEqual(payload["bot_email"], bot.email)
        self.assertEqual(payload["bot_full_name"], bot.full_name)

        # Verify message context
        self.assertEqual(payload["message"]["id"], 456)
        self.assertEqual(payload["message"]["topic"], "test topic")

        # Verify user context
        self.assertEqual(payload["user"]["id"], owner.id)
        self.assertEqual(payload["user"]["email"], owner.delivery_email)

    @responses.activate
    def test_interaction_includes_service_token(self) -> None:
        """Verify the service token is included for bot authentication."""
        owner = self.example_user("hamlet")
        bot = self.create_webhook_bot_with_service(owner)

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json={},
            status=200,
        )

        event = self.make_interaction_event(bot, owner, message_id=123)

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with simulated_queue_client(fake_client):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        request_body = responses.calls[0].request.body
        assert request_body is not None
        payload = orjson.loads(request_body)
        # Token should be present (generated by create_test_bot)
        self.assertIn("token", payload)
        self.assertIsInstance(payload["token"], str)
        self.assertGreater(len(payload["token"]), 0)

    @responses.activate
    def test_timeout_logs_warning(self) -> None:
        """Verify timeout errors are logged properly."""
        owner = self.example_user("hamlet")
        bot = self.create_webhook_bot_with_service(owner)

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            body=requests.exceptions.Timeout("Connection timed out"),
        )

        event = self.make_interaction_event(bot, owner, message_id=123)

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with (
            simulated_queue_client(fake_client),
            self.assertLogs("zerver.worker.bot_interactions", level="WARNING") as logs,
        ):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        self.assertTrue(
            any("Timeout" in log for log in logs.output),
            f"Expected timeout warning, got: {logs.output}",
        )

    @responses.activate
    def test_connection_error_logs_warning(self) -> None:
        """Verify connection errors are logged properly."""
        owner = self.example_user("hamlet")
        bot = self.create_webhook_bot_with_service(owner)

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            body=requests.exceptions.ConnectionError("Connection refused"),
        )

        event = self.make_interaction_event(bot, owner, message_id=123)

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with (
            simulated_queue_client(fake_client),
            self.assertLogs("zerver.worker.bot_interactions", level="WARNING") as logs,
        ):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        self.assertTrue(
            any("Error delivering interaction" in log for log in logs.output),
            f"Expected connection error warning, got: {logs.output}",
        )

    @responses.activate
    def test_non_2xx_status_logs_warning(self) -> None:
        """Verify non-2xx responses are logged as warnings."""
        owner = self.example_user("hamlet")
        bot = self.create_webhook_bot_with_service(owner)

        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json={"error": "Internal server error"},
            status=500,
        )

        event = self.make_interaction_event(bot, owner, message_id=123)

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with (
            simulated_queue_client(fake_client),
            self.assertLogs("zerver.worker.bot_interactions", level="WARNING") as logs,
        ):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        self.assertTrue(
            any("status 500" in log for log in logs.output),
            f"Expected 500 status warning, got: {logs.output}",
        )

    def test_bot_without_services_logs_warning(self) -> None:
        """Verify bots without configured services log a warning."""
        owner = self.example_user("hamlet")
        # Create bot without a service
        bot = self.create_test_bot(
            "no-service-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
        )
        # Remove any auto-created services
        Service.objects.filter(user_profile=bot).delete()

        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "message": {"id": 123, "stream_id": 1, "topic": "test"},
            "user": {"id": owner.id, "email": owner.delivery_email, "full_name": owner.full_name},
        }

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with (
            simulated_queue_client(fake_client),
            self.assertLogs("zerver.worker.bot_interactions", level="WARNING") as logs,
        ):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        self.assertTrue(
            any("no services configured" in log for log in logs.output),
            f"Expected 'no services' warning, got: {logs.output}",
        )


class BotInteractionResponseTests(ZulipTestCase):
    """Tests for processing bot responses to interactions."""

    def send_bot_message_with_widget(
        self, bot: UserProfile, widget_type: str, extra_data: dict[str, Any]
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

    def create_webhook_bot_with_service(
        self, owner: UserProfile, url: str = "https://bot.example.com/"
    ) -> UserProfile:
        """Helper to create a webhook bot with a configured service."""
        return self.create_test_bot(
            "webhook-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            service_name="test-service",
            payload_url=f'"{url}"',  # URL must be JSON-encoded
        )

    @responses.activate
    def test_bot_public_message_response(self) -> None:
        """Verify bot can respond with a public message."""
        owner = self.example_user("hamlet")
        bot = self.create_webhook_bot_with_service(owner)
        message_id = self.send_bot_message_with_widget(bot, "interactive", {"components": []})

        # Bot responds with content -> creates new message
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json={"content": "Button clicked! Here's your response."},
            status=200,
        )

        message = Message.objects.get(id=message_id)
        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-id",
            "message": {
                "id": message_id,
                "stream_id": message.recipient.type_id,
                "topic": message.topic_name(),
            },
            "user": {
                "id": owner.id,
                "email": owner.delivery_email,
                "full_name": owner.full_name,
            },
        }

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with simulated_queue_client(fake_client):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        # Verify a new message was created by the bot
        last_message = Message.objects.order_by("-id").first()
        assert last_message is not None
        self.assertEqual(last_message.sender_id, bot.id)
        self.assertEqual(last_message.content, "Button clicked! Here's your response.")

    @responses.activate
    def test_bot_ephemeral_response(self) -> None:
        """Verify bot can respond with ephemeral message (visible only to user)."""
        owner = self.example_user("hamlet")
        bot = self.create_webhook_bot_with_service(owner)
        message_id = self.send_bot_message_with_widget(bot, "interactive", {"components": []})

        # Bot responds with ephemeral content
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json={"content": "Only you can see this!", "ephemeral": True},
            status=200,
        )

        message = Message.objects.get(id=message_id)
        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-id",
            "message": {
                "id": message_id,
                "stream_id": message.recipient.type_id,
                "topic": message.topic_name(),
            },
            "user": {
                "id": owner.id,
                "email": owner.delivery_email,
                "full_name": owner.full_name,
            },
        }

        initial_message_count = Message.objects.count()

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with simulated_queue_client(fake_client):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        # Ephemeral responses create submessages, not new messages
        self.assertEqual(Message.objects.count(), initial_message_count)

        # Verify submessage was created
        submessage = SubMessage.objects.filter(message_id=message_id).order_by("-id").first()
        assert submessage is not None
        self.assertEqual(submessage.sender_id, bot.id)

        content = orjson.loads(submessage.content)
        self.assertEqual(content["type"], "bot_response")
        self.assertEqual(content["content"], "Only you can see this!")

    @responses.activate
    def test_bot_empty_response_is_ignored(self) -> None:
        """Verify empty responses don't cause errors."""
        owner = self.example_user("hamlet")
        bot = self.create_webhook_bot_with_service(owner)
        message_id = self.send_bot_message_with_widget(bot, "interactive", {"components": []})

        # Bot responds with empty body
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            body="",
            status=200,
        )

        message = Message.objects.get(id=message_id)
        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-id",
            "message": {
                "id": message_id,
                "stream_id": message.recipient.type_id,
                "topic": message.topic_name(),
            },
            "user": {
                "id": owner.id,
                "email": owner.delivery_email,
                "full_name": owner.full_name,
            },
        }

        initial_message_count = Message.objects.count()
        initial_submessage_count = SubMessage.objects.count()

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        # Should not raise any errors
        with simulated_queue_client(fake_client):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        # No new messages or submessages should be created
        self.assertEqual(Message.objects.count(), initial_message_count)
        self.assertEqual(SubMessage.objects.count(), initial_submessage_count)

    @responses.activate
    def test_bot_invalid_json_response_is_ignored(self) -> None:
        """Verify invalid JSON responses are handled gracefully."""
        owner = self.example_user("hamlet")
        bot = self.create_webhook_bot_with_service(owner)
        message_id = self.send_bot_message_with_widget(bot, "interactive", {"components": []})

        # Bot responds with invalid JSON
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            body="not valid json {{{",
            status=200,
        )

        message = Message.objects.get(id=message_id)
        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-id",
            "message": {
                "id": message_id,
                "stream_id": message.recipient.type_id,
                "topic": message.topic_name(),
            },
            "user": {
                "id": owner.id,
                "email": owner.delivery_email,
                "full_name": owner.full_name,
            },
        }

        initial_message_count = Message.objects.count()

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        # Should not raise any errors
        with simulated_queue_client(fake_client):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        # No new messages should be created
        self.assertEqual(Message.objects.count(), initial_message_count)

    @responses.activate
    def test_bot_response_with_widget_content(self) -> None:
        """Verify bot can respond with widget content (as object or JSON string)."""
        owner = self.example_user("hamlet")
        bot = self.create_webhook_bot_with_service(owner)
        message_id = self.send_bot_message_with_widget(bot, "interactive", {"components": []})

        # Bot responds with widget content as an object (the natural format from docs)
        # The worker should handle encoding it to JSON for check_send_message
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json={
                "content": "Here's a widget update",
                "widget_content": {
                    "widget_type": "interactive",
                    "extra_data": {
                        "components": [
                            {
                                "type": "action_row",
                                "components": [
                                    {"type": "button", "label": "Updated!", "custom_id": "new_btn"}
                                ],
                            }
                        ]
                    },
                },
            },
            status=200,
        )

        message = Message.objects.get(id=message_id)
        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-id",
            "message": {
                "id": message_id,
                "stream_id": message.recipient.type_id,
                "topic": message.topic_name(),
            },
            "user": {
                "id": owner.id,
                "email": owner.delivery_email,
                "full_name": owner.full_name,
            },
        }

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with simulated_queue_client(fake_client):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        # Verify a new message was created
        last_message = Message.objects.order_by("-id").first()
        assert last_message is not None
        self.assertEqual(last_message.sender_id, bot.id)
        self.assertEqual(last_message.content, "Here's a widget update")
        # Widget content is stored as a submessage
        submessages = SubMessage.objects.filter(message_id=last_message.id)
        self.assertTrue(submessages.exists())


class EmbeddedBotInteractionTests(ZulipTestCase):
    """Tests for embedded bot interaction handling."""

    def test_embedded_bot_without_handle_interaction(self) -> None:
        """Verify bots without handle_interaction method don't cause errors."""
        owner = self.example_user("hamlet")
        bot = self.create_test_bot(
            "embedded-bot",
            owner,
            bot_type=UserProfile.EMBEDDED_BOT,
            service_name="helloworld",  # Required for embedded bots
        )

        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-id",
            "message": {"id": 123, "stream_id": 1, "topic": "test"},
            "user": {"id": owner.id, "email": owner.delivery_email, "full_name": owner.full_name},
        }

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        # Mock a handler without handle_interaction method
        with (
            simulated_queue_client(fake_client),
            patch("zerver.lib.bot_lib.get_bot_handler") as mock_get_handler,
        ):
            mock_handler = MagicMock(spec=[])  # No handle_interaction attr
            mock_get_handler.return_value = mock_handler

            # Should not raise any errors
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

    def test_embedded_bot_handler_exception_logged(self) -> None:
        """Verify exceptions in bot handlers are logged and don't crash worker."""
        owner = self.example_user("hamlet")
        bot = self.create_test_bot(
            "embedded-bot",
            owner,
            bot_type=UserProfile.EMBEDDED_BOT,
            service_name="helloworld",  # Required for embedded bots
        )

        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-id",
            "message": {"id": 123, "stream_id": 1, "topic": "test"},
            "user": {"id": owner.id, "email": owner.delivery_email, "full_name": owner.full_name},
        }

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with (
            simulated_queue_client(fake_client),
            patch("zerver.lib.bot_lib.get_bot_handler") as mock_get_handler,
            self.assertLogs("zerver.worker.bot_interactions", level="ERROR") as logs,
        ):
            mock_handler = MagicMock()
            mock_handler.handle_interaction.side_effect = ValueError("Bot crashed!")
            mock_get_handler.return_value = mock_handler

            # Should not raise, but should log
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        self.assertTrue(
            any("Error delivering interaction" in log for log in logs.output),
            f"Expected error log, got: {logs.output}",
        )


class BotInteractionIntegrationTests(ZulipTestCase):
    """Full integration tests for the bot interaction flow."""

    def send_bot_message_with_widget(
        self, bot: UserProfile, widget_type: str, extra_data: dict[str, Any]
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

    @responses.activate
    def test_full_button_click_flow(self) -> None:
        """Test complete flow: user clicks button -> bot receives -> bot responds."""
        owner = self.example_user("hamlet")
        bot = self.create_test_bot(
            "webhook-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            service_name="test-service",
            payload_url='"https://bot.example.com/"',
        )

        # 1. Bot sends a message with a button widget
        message_id = self.send_bot_message_with_widget(
            bot,
            "interactive",
            {
                "components": [
                    {
                        "type": "action_row",
                        "components": [
                            {"type": "button", "label": "Click me!", "custom_id": "test_btn"}
                        ],
                    }
                ]
            },
        )

        # 2. Mock the bot's webhook response
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json={"content": "Thanks for clicking! Your request is being processed."},
            status=200,
        )

        # 3. User clicks the button
        self.login_user(owner)
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "button_click",
                "custom_id": "test_btn",
                "data": "{}",
            },
        )
        self.assert_json_success(result)
        interaction_response = orjson.loads(result.content)
        self.assertIn("interaction_id", interaction_response)

        # 4. Get the queued event and process it through the worker
        # In production, this happens automatically via RabbitMQ
        message = Message.objects.get(id=message_id)

        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "test_btn",
            "data": {},
            "interaction_id": interaction_response["interaction_id"],
            "message": {
                "id": message_id,
                "stream_id": message.recipient.type_id,
                "topic": message.topic_name(),
            },
            "user": {
                "id": owner.id,
                "email": owner.delivery_email,
                "full_name": owner.full_name,
            },
        }

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with simulated_queue_client(fake_client):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        # 5. Verify the HTTP POST was made to the bot
        self.assert_length(responses.calls, 1)
        request_body = responses.calls[0].request.body
        assert request_body is not None
        payload = orjson.loads(request_body)
        self.assertEqual(payload["type"], "interaction")
        self.assertEqual(payload["interaction_type"], "button_click")
        self.assertEqual(payload["custom_id"], "test_btn")
        self.assertEqual(payload["user"]["id"], owner.id)

        # 6. Verify the bot's response created a new message
        last_message = Message.objects.order_by("-id").first()
        assert last_message is not None
        self.assertEqual(last_message.sender_id, bot.id)
        self.assertEqual(
            last_message.content, "Thanks for clicking! Your request is being processed."
        )


class BotPresenceQueueIntegrationTests(ZulipTestCase):
    """Tests for integration between bot presence and the queue system."""

    def test_bot_presence_update_via_deferred_work_connect(self) -> None:
        """Test that bot_presence_update events are processed by DeferredWorker."""
        bot = self.example_user("default_bot")
        UserPresence.objects.filter(user_profile=bot).delete()

        event = {
            "type": "bot_presence_update",
            "user_profile_id": bot.id,
            "is_connected": True,
        }

        fake_client = FakeClient()
        fake_client.enqueue("deferred_work", event)

        with simulated_queue_client(fake_client):
            worker = DeferredWorker()
            worker.setup()
            worker.start()

        # Verify presence was updated
        presence = UserPresence.objects.get(user_profile=bot)
        self.assertIsNotNone(presence.last_active_time)

    def test_bot_presence_update_via_deferred_work_disconnect(self) -> None:
        """Test that disconnect events are processed correctly."""
        bot = self.example_user("default_bot")
        UserPresence.objects.filter(user_profile=bot).delete()

        # First connect the bot
        from zerver.actions.bot_presence import do_update_bot_presence

        do_update_bot_presence(bot, is_connected=True)

        # Verify it's connected
        presence = UserPresence.objects.get(user_profile=bot)
        self.assertIsNotNone(presence.last_active_time)

        # Now queue a disconnect event
        event = {
            "type": "bot_presence_update",
            "user_profile_id": bot.id,
            "is_connected": False,
        }

        fake_client = FakeClient()
        fake_client.enqueue("deferred_work", event)

        with simulated_queue_client(fake_client):
            worker = DeferredWorker()
            worker.setup()
            worker.start()

        # Verify presence was updated to disconnected
        presence.refresh_from_db()
        self.assertIsNone(presence.last_active_time)

    def test_bot_presence_connect_hook_queues_event(self) -> None:
        """Test that the bot_presence_connect_hook queues the correct event."""
        from zerver.tornado.bot_presence import bot_presence_connect_hook

        bot = self.example_user("default_bot")

        with patch("zerver.tornado.bot_presence.queue_json_publish_rollback_unsafe") as mock_queue:
            bot_presence_connect_hook(bot.id, is_bot=True)

            mock_queue.assert_called_once()
            call_args = mock_queue.call_args
            self.assertEqual(call_args[0][0], "deferred_work")
            event = call_args[0][1]
            self.assertEqual(event["type"], "bot_presence_update")
            self.assertEqual(event["user_profile_id"], bot.id)
            self.assertTrue(event["is_connected"])

    def test_bot_presence_connect_hook_skips_non_bots(self) -> None:
        """Test that the connect hook doesn't queue events for non-bots."""
        from zerver.tornado.bot_presence import bot_presence_connect_hook

        user = self.example_user("hamlet")

        with patch("zerver.tornado.bot_presence.queue_json_publish_rollback_unsafe") as mock_queue:
            bot_presence_connect_hook(user.id, is_bot=False)
            mock_queue.assert_not_called()

    def test_bot_presence_gc_hook_queues_disconnect(self) -> None:
        """Test that the GC hook queues disconnect when last queue is collected."""
        from zerver.tornado.bot_presence import bot_presence_gc_hook

        bot = self.example_user("default_bot")

        # Create a mock client descriptor
        mock_client = MagicMock()
        mock_client.is_bot = True

        with patch("zerver.tornado.bot_presence.queue_json_publish_rollback_unsafe") as mock_queue:
            bot_presence_gc_hook(bot.id, mock_client, last_for_user=True)

            mock_queue.assert_called_once()
            call_args = mock_queue.call_args
            self.assertEqual(call_args[0][0], "deferred_work")
            event = call_args[0][1]
            self.assertEqual(event["type"], "bot_presence_update")
            self.assertEqual(event["user_profile_id"], bot.id)
            self.assertFalse(event["is_connected"])

    def test_bot_presence_gc_hook_skips_if_not_last_queue(self) -> None:
        """Test that the GC hook doesn't queue disconnect if bot has other queues."""
        from zerver.tornado.bot_presence import bot_presence_gc_hook

        bot = self.example_user("default_bot")

        mock_client = MagicMock()
        mock_client.is_bot = True

        with patch("zerver.tornado.bot_presence.queue_json_publish_rollback_unsafe") as mock_queue:
            bot_presence_gc_hook(bot.id, mock_client, last_for_user=False)
            mock_queue.assert_not_called()

    def test_bot_presence_gc_hook_skips_non_bots(self) -> None:
        """Test that the GC hook doesn't queue disconnect for non-bots."""
        from zerver.tornado.bot_presence import bot_presence_gc_hook

        user = self.example_user("hamlet")

        mock_client = MagicMock()
        mock_client.is_bot = False

        with patch("zerver.tornado.bot_presence.queue_json_publish_rollback_unsafe") as mock_queue:
            bot_presence_gc_hook(user.id, mock_client, last_for_user=True)
            mock_queue.assert_not_called()

    def test_deferred_worker_skips_non_bot_presence_update(self) -> None:
        """Test that presence updates for non-bots are ignored gracefully."""
        user = self.example_user("hamlet")
        self.assertFalse(user.is_bot)

        event = {
            "type": "bot_presence_update",
            "user_profile_id": user.id,
            "is_connected": True,
        }

        fake_client = FakeClient()
        fake_client.enqueue("deferred_work", event)

        # Should not raise any errors
        with simulated_queue_client(fake_client):
            worker = DeferredWorker()
            worker.setup()
            worker.start()

        # No UserPresence should be created for non-bots via bot presence update
        self.assertFalse(UserPresence.objects.filter(user_profile=user).exists())


class BotInteractionWithPresenceTests(ZulipTestCase):
    """Tests verifying bot interactions work correctly with bot presence state."""

    def send_bot_message_with_widget(
        self, bot: UserProfile, widget_type: str, extra_data: dict[str, Any]
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

    @responses.activate
    def test_interaction_works_with_connected_bot(self) -> None:
        """Test that interactions work when bot is marked as connected."""
        from zerver.actions.bot_presence import do_update_bot_presence

        owner = self.example_user("hamlet")
        bot = self.create_test_bot(
            "connected-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            service_name="test-service",
            payload_url='"https://bot.example.com/"',
        )

        # Mark bot as connected
        do_update_bot_presence(bot, is_connected=True)

        # Bot sends a message
        message_id = self.send_bot_message_with_widget(
            bot,
            "interactive",
            {
                "components": [
                    {
                        "type": "action_row",
                        "components": [{"type": "button", "label": "Click", "custom_id": "btn1"}],
                    }
                ]
            },
        )

        # Mock the webhook response
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json={"content": "Response from connected bot"},
            status=200,
        )

        # User interacts
        self.login_user(owner)
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

        # Process the interaction via worker
        message = Message.objects.get(id=message_id)
        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-id",
            "message": {
                "id": message_id,
                "stream_id": message.recipient.type_id,
                "topic": message.topic_name(),
            },
            "user": {
                "id": owner.id,
                "email": owner.delivery_email,
                "full_name": owner.full_name,
            },
        }

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with simulated_queue_client(fake_client):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        # Verify the interaction was delivered
        self.assert_length(responses.calls, 1)

        # Verify bot is still connected
        presence = UserPresence.objects.get(user_profile=bot)
        self.assertIsNotNone(presence.last_active_time)

    @responses.activate
    def test_interaction_works_with_disconnected_bot(self) -> None:
        """Test that interactions are still delivered even when bot is marked disconnected.

        This tests the case where a bot may have temporarily disconnected but
        its webhook is still responsive. The interaction should still be delivered.
        """
        from zerver.actions.bot_presence import do_update_bot_presence

        owner = self.example_user("hamlet")
        bot = self.create_test_bot(
            "disconnected-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            service_name="test-service",
            payload_url='"https://bot.example.com/"',
        )

        # Mark bot as connected then disconnected
        do_update_bot_presence(bot, is_connected=True)
        do_update_bot_presence(bot, is_connected=False)

        presence = UserPresence.objects.get(user_profile=bot)
        self.assertIsNone(presence.last_active_time)

        # Bot's webhook is still responsive
        responses.add(
            responses.POST,
            "https://bot.example.com/",
            json={"content": "Response from bot webhook"},
            status=200,
        )

        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-id",
            "message": {"id": 123, "stream_id": 1, "topic": "test"},
            "user": {
                "id": owner.id,
                "email": owner.delivery_email,
                "full_name": owner.full_name,
            },
        }

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with simulated_queue_client(fake_client):
            worker = BotInteractionWorker()
            worker.setup()
            worker.start()

        # Interaction should still be delivered
        self.assert_length(responses.calls, 1)


class BotInteractionErrorScenarioTests(ZulipTestCase):
    """Tests for error scenarios in bot interaction processing."""

    def test_bot_deleted_after_interaction_queued(self) -> None:
        """Test graceful handling when bot is deleted after interaction is queued."""
        owner = self.example_user("hamlet")
        bot = self.create_test_bot(
            "temp-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
        )
        bot_id = bot.id

        event = {
            "bot_user_id": bot_id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-id",
            "message": {"id": 123, "stream_id": 1, "topic": "test"},
            "user": {"id": owner.id, "email": owner.delivery_email, "full_name": owner.full_name},
        }

        # Delete the bot before processing
        bot.delete()

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        # Should not raise - worker should handle missing bot gracefully
        with self.assertLogs("zerver.worker.bot_interactions", level="WARNING"):
            with simulated_queue_client(fake_client):
                worker = BotInteractionWorker()
                worker.setup()
                worker.start()

    def test_bot_type_changed_to_unsupported(self) -> None:
        """Test handling when bot type is changed to unsupported type after message sent."""
        owner = self.example_user("hamlet")
        bot = self.create_test_bot(
            "changing-bot",
            owner,
            bot_type=UserProfile.DEFAULT_BOT,  # Unsupported type
        )

        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-id",
            "message": {"id": 123, "stream_id": 1, "topic": "test"},
            "user": {"id": owner.id, "email": owner.delivery_email, "full_name": owner.full_name},
        }

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        # Should log warning about unsupported bot type
        with self.assertLogs("zerver.worker.bot_interactions", level="WARNING") as logs:
            with simulated_queue_client(fake_client):
                worker = BotInteractionWorker()
                worker.setup()
                worker.start()

        self.assertTrue(any("unsupported bot type" in log for log in logs.output))

    @responses.activate
    def test_bot_service_url_dns_failure(self) -> None:
        """Test handling of DNS/connection failures to bot service URL."""
        owner = self.example_user("hamlet")
        bot = self.create_test_bot(
            "dns-fail-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            service_name="test-service",
            payload_url='"https://nonexistent.invalid/"',
        )

        responses.add(
            responses.POST,
            "https://nonexistent.invalid/",
            body=requests.exceptions.ConnectionError("Name resolution failed"),
        )

        event = {
            "bot_user_id": bot.id,
            "interaction_type": "button_click",
            "custom_id": "btn1",
            "data": {},
            "interaction_id": "test-id",
            "message": {"id": 123, "stream_id": 1, "topic": "test"},
            "user": {"id": owner.id, "email": owner.delivery_email, "full_name": owner.full_name},
        }

        fake_client = FakeClient()
        fake_client.enqueue("bot_interactions", event)

        with self.assertLogs("zerver.worker.bot_interactions", level="WARNING") as logs:
            with simulated_queue_client(fake_client):
                worker = BotInteractionWorker()
                worker.setup()
                worker.start()

        self.assertTrue(any("Error delivering interaction" in log for log in logs.output))

    def test_interaction_with_missing_message_id(self) -> None:
        """Test handling of interaction with non-existent message."""
        owner = self.example_user("hamlet")
        bot = self.create_test_bot(
            "test-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
        )

        # Use a message ID that definitely doesn't exist
        result = self.api_post(
            owner,
            "/api/v1/bot_interactions",
            {
                "message_id": orjson.dumps(999999999).decode(),
                "interaction_type": "button_click",
                "custom_id": "btn1",
                "data": "{}",
            },
        )
        self.assert_json_error(result, "Invalid message(s)")


class BotInteractionPermissionTests(ZulipTestCase):
    """Tests for permission and authorization in bot interactions."""

    def send_bot_message_with_widget(
        self, bot: UserProfile, widget_type: str, extra_data: dict[str, Any]
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

    def test_user_must_be_authenticated(self) -> None:
        """Test that unauthenticated requests are rejected."""
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": "123",
                "interaction_type": "button_click",
                "custom_id": "btn1",
                "data": "{}",
            },
        )
        # Should be rejected as unauthorized
        self.assertEqual(result.status_code, 401)

    def test_user_can_only_interact_with_accessible_messages(self) -> None:
        """Test that users can only interact with messages they can access."""
        owner = self.example_user("hamlet")
        other_user = self.example_user("othello")
        bot = self.create_test_bot(
            "test-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
        )

        # Create a private message to owner only
        result = self.api_post(
            bot,
            "/api/v1/messages",
            {
                "type": "direct",
                "to": orjson.dumps([owner.email]).decode(),
                "content": "private widget message",
                "widget_content": orjson.dumps(
                    {
                        "widget_type": "interactive",
                        "extra_data": {
                            "components": [
                                {
                                    "type": "action_row",
                                    "components": [
                                        {"type": "button", "label": "Click", "custom_id": "btn1"}
                                    ],
                                }
                            ]
                        },
                    }
                ).decode(),
            },
        )
        self.assert_json_success(result)
        message_id = orjson.loads(result.content)["id"]

        # Other user tries to interact - should fail
        self.login_user(other_user)
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "button_click",
                "custom_id": "btn1",
                "data": "{}",
            },
        )
        self.assert_json_error(result, "Invalid message(s)")

    def test_can_only_interact_with_bot_messages(self) -> None:
        """Test that interactions are only allowed on bot messages."""
        user = self.example_user("hamlet")

        # Send a regular (non-bot) message
        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": orjson.dumps("Verona").decode(),
                "topic": "test",
                "content": "regular user message",
            },
        )
        self.assert_json_success(result)
        message_id = orjson.loads(result.content)["id"]

        # Try to interact with it
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
        self.assert_json_error(result, "Can only interact with bot messages")


class BotInteractionDataValidationTests(ZulipTestCase):
    """Tests for edge cases in interaction data validation."""

    def send_bot_message_with_widget(
        self, bot: UserProfile, widget_type: str, extra_data: dict[str, Any]
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

    def test_empty_interaction_type_rejected(self) -> None:
        """Test that empty interaction_type is rejected."""
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test-bot", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)
        message_id = self.send_bot_message_with_widget(
            bot, "interactive", {"components": []}
        )

        self.login_user(user)
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "",
                "custom_id": "btn1",
                "data": "{}",
            },
        )
        self.assert_json_error(result, "Invalid interaction type")

    def test_empty_custom_id_allowed(self) -> None:
        """Test that empty custom_id is allowed (some widgets may not need it)."""
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test-bot", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)
        message_id = self.send_bot_message_with_widget(
            bot, "interactive", {"components": []}
        )

        self.login_user(user)
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "button_click",
                "custom_id": "",
                "data": "{}",
            },
        )
        # Empty custom_id should be allowed
        self.assert_json_success(result)

    def test_invalid_data_json_rejected(self) -> None:
        """Test that invalid JSON in data field is rejected."""
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test-bot", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)
        message_id = self.send_bot_message_with_widget(
            bot, "interactive", {"components": []}
        )

        self.login_user(user)
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "button_click",
                "custom_id": "btn1",
                "data": "not valid json {{{",
            },
        )
        self.assert_json_error_contains(result, "")  # Should return some error

    def test_long_custom_id_handled(self) -> None:
        """Test that very long custom_id values are handled gracefully."""
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test-bot", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)
        message_id = self.send_bot_message_with_widget(
            bot, "interactive", {"components": []}
        )

        # Create a very long custom_id
        long_custom_id = "btn_" + "x" * 10000

        self.login_user(user)
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "button_click",
                "custom_id": long_custom_id,
                "data": "{}",
            },
        )
        # Should either succeed or return a clear error about length
        # The important thing is it shouldn't crash
        self.assertTrue(result.status_code in [200, 400])

    def test_nested_data_payload(self) -> None:
        """Test that complex nested data payloads work correctly."""
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test-bot", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)
        message_id = self.send_bot_message_with_widget(
            bot, "interactive", {"components": []}
        )

        complex_data = {
            "fields": {
                "name": {"value": "John", "valid": True},
                "email": {"value": "john@example.com", "valid": True},
            },
            "metadata": {
                "timestamp": 1234567890,
                "source": "form_submit",
            },
        }

        self.login_user(user)
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "modal_submit",
                "custom_id": "form1",
                "data": orjson.dumps(complex_data).decode(),
            },
        )
        self.assert_json_success(result)

    def test_unicode_in_data_and_custom_id(self) -> None:
        """Test that unicode characters in data and custom_id work correctly."""
        user = self.example_user("hamlet")
        bot = self.create_test_bot("test-bot", user, bot_type=UserProfile.OUTGOING_WEBHOOK_BOT)
        message_id = self.send_bot_message_with_widget(
            bot, "interactive", {"components": []}
        )

        self.login_user(user)
        result = self.client_post(
            "/json/bot_interactions",
            {
                "message_id": orjson.dumps(message_id).decode(),
                "interaction_type": "button_click",
                "custom_id": "btn_日本語_emoji_🎉",
                "data": orjson.dumps({"message": "こんにちは世界 🌍"}).decode(),
            },
        )
        self.assert_json_success(result)
