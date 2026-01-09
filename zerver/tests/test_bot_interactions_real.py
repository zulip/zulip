"""
Real integration tests for bot interactions.

These tests use an actual HTTP server (no mocking) to verify that:
1. The HTTP payload format is correct
2. Bot responses are processed correctly
3. The full flow works end-to-end

This complements the mocked tests in test_bot_interactions.py which are
faster but don't catch payload format issues or real HTTP behavior.
"""

from typing import Any

import orjson
import responses

from contextlib import contextmanager
from typing import Iterator

from zerver.lib.test_bot_server import TestBotServer, test_bot_server
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, SubMessage, UserProfile
from zerver.tests.test_queue_worker import FakeClient, simulated_queue_client
from zerver.worker.bot_interactions import BotInteractionWorker


@contextmanager
def real_http_test_bot_server() -> Iterator[TestBotServer]:
    """
    Context manager that provides a test bot server with real HTTP enabled.

    This sets up the necessary responses passthru to allow real localhost
    HTTP requests, overriding the default test isolation.
    """
    with test_bot_server() as bot:
        with responses.RequestsMock() as rsps:
            rsps.add_passthru("http://127.0.0.1")
            yield bot


class RealBotInteractionTests(ZulipTestCase):
    """
    Integration tests that use a real HTTP server instead of mocking.

    These tests verify the actual HTTP payload format and response handling
    by running a test bot server that receives real HTTP requests.
    """

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

    def create_webhook_bot_with_url(self, owner: UserProfile, url: str) -> UserProfile:
        """Create a webhook bot pointing to the given URL."""
        return self.create_test_bot(
            "real-test-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            service_name="test-service",
            payload_url=f'"{url}"',  # URL must be JSON-encoded
        )

    def make_interaction_event(
        self,
        bot: UserProfile,
        user: UserProfile,
        message: Message,
        interaction_type: str = "button_click",
        custom_id: str = "btn1",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an interaction event for the worker."""
        return {
            "bot_user_id": bot.id,
            "interaction_type": interaction_type,
            "custom_id": custom_id,
            "data": data or {},
            "interaction_id": "test-interaction-id",
            "message": {
                "id": message.id,
                "stream_id": message.recipient.type_id,
                "topic": message.topic_name(),
            },
            "user": {
                "id": user.id,
                "email": user.delivery_email,
                "full_name": user.full_name,
            },
        }

    def test_real_button_click_payload_format(self) -> None:
        """Verify the HTTP payload format matches the documented API."""
        owner = self.example_user("hamlet")

        with real_http_test_bot_server() as bot_server:
            bot = self.create_webhook_bot_with_url(owner, bot_server.url)

            message_id = self.send_bot_message_with_widget(
                bot,
                "interactive",
                {
                    "components": [
                        {
                            "type": "action_row",
                            "components": [
                                {"type": "button", "label": "Click me", "custom_id": "test_btn"}
                            ],
                        }
                    ]
                },
            )

            message = Message.objects.get(id=message_id)
            event = self.make_interaction_event(
                bot, owner, message, custom_id="test_btn", data={"extra": "data"}
            )

            fake_client = FakeClient()
            fake_client.enqueue("bot_interactions", event)

            with simulated_queue_client(fake_client):
                worker = BotInteractionWorker()
                worker.setup()
                worker.start()

            self.assertTrue(
                bot_server.wait_for_request(timeout=5.0),
                "Bot server did not receive request",
            )

            requests = bot_server.get_requests()
            self.assert_length(requests, 1)

            payload = requests[0]["body"]

            # Verify all required fields are present and correct
            self.assertEqual(payload["type"], "interaction")
            self.assertEqual(payload["interaction_type"], "button_click")
            self.assertEqual(payload["custom_id"], "test_btn")
            self.assertEqual(payload["data"], {"extra": "data"})
            self.assertEqual(payload["interaction_id"], "test-interaction-id")

            # Verify bot info
            self.assertEqual(payload["bot_email"], bot.email)
            self.assertEqual(payload["bot_full_name"], bot.full_name)

            # Verify message context
            self.assertEqual(payload["message"]["id"], message_id)
            self.assertEqual(payload["message"]["topic"], message.topic_name())

            # Verify user context
            self.assertEqual(payload["user"]["id"], owner.id)
            self.assertEqual(payload["user"]["email"], owner.delivery_email)
            self.assertEqual(payload["user"]["full_name"], owner.full_name)

            # Verify token is present (for bot authentication)
            self.assertIn("token", payload)
            self.assertIsInstance(payload["token"], str)
            self.assertGreater(len(payload["token"]), 0)

    def test_real_bot_message_response(self) -> None:
        """Verify bot can respond with a public message via real HTTP."""
        owner = self.example_user("hamlet")

        with real_http_test_bot_server() as bot_server:
            bot = self.create_webhook_bot_with_url(owner, bot_server.url)

            # Configure the bot to respond with a message
            bot_server.set_response({"content": "Hello from real bot!"})

            message_id = self.send_bot_message_with_widget(
                bot, "interactive", {"components": []}
            )

            message = Message.objects.get(id=message_id)
            event = self.make_interaction_event(bot, owner, message)

            initial_message_count = Message.objects.count()

            fake_client = FakeClient()
            fake_client.enqueue("bot_interactions", event)

            with simulated_queue_client(fake_client):
                worker = BotInteractionWorker()
                worker.setup()
                worker.start()

            # Verify bot server received the request
            self.assertTrue(bot_server.wait_for_request(timeout=5.0))

            # Verify a new message was created
            self.assertEqual(Message.objects.count(), initial_message_count + 1)

            last_message = Message.objects.order_by("-id").first()
            assert last_message is not None
            self.assertEqual(last_message.sender_id, bot.id)
            self.assertEqual(last_message.content, "Hello from real bot!")

    def test_real_bot_ephemeral_response(self) -> None:
        """Verify ephemeral responses work via real HTTP."""
        owner = self.example_user("hamlet")

        with real_http_test_bot_server() as bot_server:
            bot = self.create_webhook_bot_with_url(owner, bot_server.url)

            # Configure ephemeral response
            bot_server.set_response({"content": "Secret message!", "ephemeral": True})

            message_id = self.send_bot_message_with_widget(
                bot, "interactive", {"components": []}
            )

            message = Message.objects.get(id=message_id)
            event = self.make_interaction_event(bot, owner, message)

            initial_message_count = Message.objects.count()

            fake_client = FakeClient()
            fake_client.enqueue("bot_interactions", event)

            with simulated_queue_client(fake_client):
                worker = BotInteractionWorker()
                worker.setup()
                worker.start()

            self.assertTrue(bot_server.wait_for_request(timeout=5.0))

            # Ephemeral responses don't create new messages
            self.assertEqual(Message.objects.count(), initial_message_count)

            # But they do create submessages
            submessage = SubMessage.objects.filter(message_id=message_id).order_by("-id").first()
            assert submessage is not None
            self.assertEqual(submessage.sender_id, bot.id)

            content = orjson.loads(submessage.content)
            self.assertEqual(content["type"], "bot_response")
            self.assertEqual(content["content"], "Secret message!")

    def test_real_bot_widget_content_response(self) -> None:
        """Verify bot can respond with widget content as an object."""
        owner = self.example_user("hamlet")

        with real_http_test_bot_server() as bot_server:
            bot = self.create_webhook_bot_with_url(owner, bot_server.url)

            # Bot responds with widget_content as an object (not JSON string)
            # This tests the fix we made to json.dumps the widget_content
            bot_server.set_response(
                {
                    "content": "Updated widget!",
                    "widget_content": {
                        "widget_type": "interactive",
                        "extra_data": {
                            "components": [
                                {
                                    "type": "action_row",
                                    "components": [
                                        {"type": "button", "label": "New button", "custom_id": "new"}
                                    ],
                                }
                            ]
                        },
                    },
                }
            )

            message_id = self.send_bot_message_with_widget(
                bot, "interactive", {"components": []}
            )

            message = Message.objects.get(id=message_id)
            event = self.make_interaction_event(bot, owner, message)

            fake_client = FakeClient()
            fake_client.enqueue("bot_interactions", event)

            with simulated_queue_client(fake_client):
                worker = BotInteractionWorker()
                worker.setup()
                worker.start()

            self.assertTrue(bot_server.wait_for_request(timeout=5.0))

            # Verify message with widget was created
            last_message = Message.objects.order_by("-id").first()
            assert last_message is not None
            self.assertEqual(last_message.sender_id, bot.id)
            self.assertEqual(last_message.content, "Updated widget!")

            # Verify widget content was attached
            submessages = SubMessage.objects.filter(message_id=last_message.id)
            self.assertTrue(submessages.exists())

    def test_real_bot_empty_response(self) -> None:
        """Verify empty responses are handled gracefully."""
        owner = self.example_user("hamlet")

        with real_http_test_bot_server() as bot_server:
            bot = self.create_webhook_bot_with_url(owner, bot_server.url)

            # Bot returns empty response (just acknowledgement)
            bot_server.set_response(None)

            message_id = self.send_bot_message_with_widget(
                bot, "interactive", {"components": []}
            )

            message = Message.objects.get(id=message_id)
            event = self.make_interaction_event(bot, owner, message)

            initial_message_count = Message.objects.count()
            initial_submessage_count = SubMessage.objects.count()

            fake_client = FakeClient()
            fake_client.enqueue("bot_interactions", event)

            # Should not raise any errors
            with simulated_queue_client(fake_client):
                worker = BotInteractionWorker()
                worker.setup()
                worker.start()

            self.assertTrue(bot_server.wait_for_request(timeout=5.0))

            # No new messages or submessages
            self.assertEqual(Message.objects.count(), initial_message_count)
            self.assertEqual(SubMessage.objects.count(), initial_submessage_count)

    def test_real_bot_error_response(self) -> None:
        """Verify 500 errors from bot are handled gracefully."""
        owner = self.example_user("hamlet")

        with real_http_test_bot_server() as bot_server:
            bot = self.create_webhook_bot_with_url(owner, bot_server.url)

            # Bot returns 500 error
            bot_server.set_response({"error": "Internal error"}, status=500)

            message_id = self.send_bot_message_with_widget(
                bot, "interactive", {"components": []}
            )

            message = Message.objects.get(id=message_id)
            event = self.make_interaction_event(bot, owner, message)

            initial_message_count = Message.objects.count()

            fake_client = FakeClient()
            fake_client.enqueue("bot_interactions", event)

            # Should not raise, but should log warning
            with self.assertLogs("zerver.worker.bot_interactions", level="WARNING") as logs:
                with simulated_queue_client(fake_client):
                    worker = BotInteractionWorker()
                    worker.setup()
                    worker.start()

            self.assertTrue(bot_server.wait_for_request(timeout=5.0))

            # Verify warning was logged
            self.assertTrue(
                any("status 500" in log for log in logs.output),
                f"Expected 500 status warning, got: {logs.output}",
            )

            # No messages should be created from error response
            self.assertEqual(Message.objects.count(), initial_message_count)

    def test_real_modal_submit_payload(self) -> None:
        """Verify modal submit payloads are correctly formatted."""
        owner = self.example_user("hamlet")

        with real_http_test_bot_server() as bot_server:
            bot = self.create_webhook_bot_with_url(owner, bot_server.url)

            message_id = self.send_bot_message_with_widget(
                bot,
                "interactive",
                {
                    "components": [
                        {
                            "type": "action_row",
                            "components": [
                                {
                                    "type": "button",
                                    "label": "Open Form",
                                    "custom_id": "open_form",
                                    "modal": {
                                        "custom_id": "feedback_form",
                                        "title": "Feedback",
                                        "components": [],
                                    },
                                }
                            ],
                        }
                    ]
                },
            )

            message = Message.objects.get(id=message_id)

            # Simulate modal submission
            modal_data = {
                "fields": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "feedback": "Great product!",
                }
            }

            event = self.make_interaction_event(
                bot,
                owner,
                message,
                interaction_type="modal_submit",
                custom_id="feedback_form",
                data=modal_data,
            )

            fake_client = FakeClient()
            fake_client.enqueue("bot_interactions", event)

            with simulated_queue_client(fake_client):
                worker = BotInteractionWorker()
                worker.setup()
                worker.start()

            self.assertTrue(bot_server.wait_for_request(timeout=5.0))

            payload = bot_server.get_last_request()
            assert payload is not None

            # Verify modal-specific fields
            self.assertEqual(payload["body"]["interaction_type"], "modal_submit")
            self.assertEqual(payload["body"]["custom_id"], "feedback_form")
            self.assertEqual(payload["body"]["data"], modal_data)

    def test_real_select_menu_payload(self) -> None:
        """Verify select menu payloads contain selected values."""
        owner = self.example_user("hamlet")

        with real_http_test_bot_server() as bot_server:
            bot = self.create_webhook_bot_with_url(owner, bot_server.url)

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
                                    "custom_id": "color_picker",
                                    "options": [
                                        {"label": "Red", "value": "red"},
                                        {"label": "Blue", "value": "blue"},
                                    ],
                                }
                            ],
                        }
                    ]
                },
            )

            message = Message.objects.get(id=message_id)

            event = self.make_interaction_event(
                bot,
                owner,
                message,
                interaction_type="select_menu",
                custom_id="color_picker",
                data={"values": ["blue"]},
            )

            fake_client = FakeClient()
            fake_client.enqueue("bot_interactions", event)

            with simulated_queue_client(fake_client):
                worker = BotInteractionWorker()
                worker.setup()
                worker.start()

            self.assertTrue(bot_server.wait_for_request(timeout=5.0))

            payload = bot_server.get_last_request()
            assert payload is not None

            self.assertEqual(payload["body"]["interaction_type"], "select_menu")
            self.assertEqual(payload["body"]["custom_id"], "color_picker")
            self.assertEqual(payload["body"]["data"], {"values": ["blue"]})


class RealBotInteractionEdgeCaseTests(ZulipTestCase):
    """Edge case tests using real HTTP."""

    def create_webhook_bot_with_url(self, owner: UserProfile, url: str) -> UserProfile:
        """Create a webhook bot pointing to the given URL."""
        return self.create_test_bot(
            "edge-case-bot",
            owner,
            bot_type=UserProfile.OUTGOING_WEBHOOK_BOT,
            service_name="test-service",
            payload_url=f'"{url}"',
        )

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

    def test_unicode_in_payload_and_response(self) -> None:
        """Verify unicode is handled correctly in both directions."""
        owner = self.example_user("hamlet")

        with real_http_test_bot_server() as bot_server:
            bot = self.create_webhook_bot_with_url(owner, bot_server.url)

            # Bot will respond with unicode
            bot_server.set_response({"content": "Hello! Bonjour! Hola!"})

            message_id = self.send_bot_message_with_widget(
                bot, "interactive", {"components": []}
            )

            message = Message.objects.get(id=message_id)

            # Send interaction with unicode data
            event = {
                "bot_user_id": bot.id,
                "interaction_type": "button_click",
                "custom_id": "btn_emoji_",
                "data": {"greeting": "Hello world!"},
                "interaction_id": "test-id",
                "message": {
                    "id": message.id,
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

            self.assertTrue(bot_server.wait_for_request(timeout=5.0))

            # Verify unicode was preserved in request
            payload = bot_server.get_last_request()
            assert payload is not None
            self.assertEqual(payload["body"]["custom_id"], "btn_emoji_")
            self.assertEqual(payload["body"]["data"]["greeting"], "Hello world!")

            # Verify unicode response was processed
            last_message = Message.objects.order_by("-id").first()
            assert last_message is not None
            self.assertEqual(last_message.content, "Hello! Bonjour! Hola!")

    def test_large_payload(self) -> None:
        """Verify large payloads are handled correctly."""
        owner = self.example_user("hamlet")

        with real_http_test_bot_server() as bot_server:
            bot = self.create_webhook_bot_with_url(owner, bot_server.url)

            # Large response
            large_content = "x" * 10000
            bot_server.set_response({"content": large_content})

            message_id = self.send_bot_message_with_widget(
                bot, "interactive", {"components": []}
            )

            message = Message.objects.get(id=message_id)

            # Large data payload
            large_data = {"values": ["item_" + str(i) for i in range(100)]}

            event = {
                "bot_user_id": bot.id,
                "interaction_type": "select_menu",
                "custom_id": "multi_select",
                "data": large_data,
                "interaction_id": "test-id",
                "message": {
                    "id": message.id,
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

            self.assertTrue(bot_server.wait_for_request(timeout=5.0))

            # Verify large data was sent
            payload = bot_server.get_last_request()
            assert payload is not None
            self.assertEqual(len(payload["body"]["data"]["values"]), 100)

            # Verify large response was processed
            last_message = Message.objects.order_by("-id").first()
            assert last_message is not None
            self.assertEqual(last_message.content, large_content)
