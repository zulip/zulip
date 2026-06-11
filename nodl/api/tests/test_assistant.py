"""Unit tests for the internal assistant endpoints (Epic 2, Story 2.1)."""

import base64
import json
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase
from pydantic import ValidationError

from nodl.api.views.assistant import (
    get_task_stream_messages,
    send_assistant_message,
)
from nodl.api.views.card_schemas import (
    NODL_CARD_PREFIX,
    UnknownCardTypeError,
    build_card_message_content,
    encode_card,
    validate_card_payload,
)


class TestCardEncoding(TestCase):
    def test_encode_round_trip(self) -> None:
        payload = {
            "task_id": str(uuid.uuid4()),
            "mode": "assessment",
            "answer": "On track overall.",
            "risks": ["Tile delivery is late"],
        }

        encoded = encode_card("ask_ai_answer", payload)

        self.assertTrue(encoded.startswith(NODL_CARD_PREFIX))
        self.assertTrue(encoded.endswith(" -->"))
        b64 = encoded[len(NODL_CARD_PREFIX) : -len(" -->")]
        envelope = json.loads(base64.urlsafe_b64decode(b64.encode("ascii")))
        self.assertEqual(envelope["card_type"], "ask_ai_answer")
        self.assertEqual(envelope["payload"]["answer"], "On track overall.")
        self.assertEqual(envelope["payload"]["risks"], ["Tile delivery is late"])

    def test_unknown_card_type_rejected(self) -> None:
        with self.assertRaises(UnknownCardTypeError):
            validate_card_payload("not_a_card", {})

    def test_invalid_payload_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            validate_card_payload("checkin", {"checkin_id": "x"})  # missing fields

    def test_message_content_keeps_markdown_fallback(self) -> None:
        content = build_card_message_content(
            "checkin",
            {
                "checkin_id": str(uuid.uuid4()),
                "task_id": str(uuid.uuid4()),
                "workspace_id": str(uuid.uuid4()),
                "rule": "deadline_approaching",
                "question": "Is this task on track?",
            },
            "**Check-in**: Is this task on track?",
        )

        self.assertTrue(content.startswith(NODL_CARD_PREFIX))
        self.assertIn("**Check-in**: Is this task on track?", content)


class TestAssistantAuth(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()

    def test_read_requires_service_auth(self) -> None:
        request = self.factory.get(f"/api/v1/internal/task-streams/{uuid.uuid4()}/messages")
        request.is_service_request = False

        response = get_task_stream_messages(request, uuid.uuid4())

        self.assertEqual(response.status_code, 401)

    def test_send_requires_service_auth(self) -> None:
        request = self.factory.post("/api/v1/internal/messages/send")
        request.is_service_request = False

        response = send_assistant_message(request)

        self.assertEqual(response.status_code, 401)


class TestReadTaskStreamMessages(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.task_id = uuid.uuid4()
        self.workspace_id = str(uuid.uuid4())

    def _request(self, query: str):
        request = self.factory.get(f"/api/v1/internal/task-streams/{self.task_id}/messages?{query}")
        request.is_service_request = True
        return request

    def test_workspace_id_required(self) -> None:
        response = get_task_stream_messages(self._request(""), self.task_id)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)["code"], "VALIDATION_ERROR")

    @patch("nodl.api.views.assistant._get_task_stream_extension", return_value=None)
    def test_unknown_task_is_404(self, _mock_ext: MagicMock) -> None:
        response = get_task_stream_messages(
            self._request(f"workspace_id={self.workspace_id}"), self.task_id
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(json.loads(response.content)["code"], "TASK_STREAM_NOT_FOUND")

    @patch("nodl.api.views.assistant.NodlRealmUserExtension.objects")
    @patch("nodl.api.views.assistant.Message.objects")
    @patch("nodl.api.views.assistant._get_task_stream_extension")
    def test_returns_messages_with_human_anchor_metadata(
        self,
        mock_get_extension: MagicMock,
        mock_message_objects: MagicMock,
        mock_realm_user_objects: MagicMock,
    ) -> None:
        extension = MagicMock(zulip_realm_id=1)
        extension.zulip_stream = MagicMock(recipient_id=7, deactivated=True)
        mock_get_extension.return_value = extension

        supabase_id = uuid.uuid4()
        human = MagicMock(
            id=10,
            sender_id=11,
            date_sent=datetime(2026, 6, 11, 12, 0, tzinfo=UTC),
            content="tiles arrived",
        )
        human.sender.full_name = "Person"
        human.sender.is_bot = False
        human.topic_name.return_value = "task"
        bot = MagicMock(
            id=12,
            sender_id=99,
            date_sent=datetime(2026, 6, 11, 12, 5, tzinfo=UTC),
            content="<!-- nodl-card:v1:abc -->\n\nAssessment",
        )
        bot.sender.full_name = "nodl Assistant"
        bot.sender.is_bot = True
        bot.topic_name.return_value = "task"

        stream_messages = mock_message_objects.filter.return_value
        page_query = (
            stream_messages.filter.return_value.select_related.return_value.order_by.return_value
        )
        page_query.__getitem__.return_value = [human, bot]
        # AD-10: bot message id 12 is newest, but the human anchor stays at 10.
        stream_messages.exclude.return_value.aggregate.return_value = {"id__max": 10}
        stream_messages.aggregate.return_value = {"last_edit_time__max": None}
        mock_realm_user_objects.filter.return_value.values_list.return_value = [(11, supabase_id)]

        response = get_task_stream_messages(
            self._request(f"workspace_id={self.workspace_id}&anchor=0"), self.task_id
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data["messages"]), 2)
        self.assertEqual(data["messages"][0]["sender"]["supabase_user_id"], str(supabase_id))
        self.assertFalse(data["messages"][0]["sender"]["is_bot"])
        self.assertTrue(data["messages"][1]["sender"]["is_bot"])
        self.assertEqual(data["latest_human_anchor"], 10)
        self.assertIsNone(data["last_edit_time"])
        self.assertTrue(data["found_newest"])
        self.assertTrue(data["stream_archived"])


class TestSendAssistantMessage(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.payload = {
            "workspace_id": str(uuid.uuid4()),
            "task_id": str(uuid.uuid4()),
            "topic": "task",
            "content": "Assessment: on track.",
        }

    def _request(self, payload: dict):
        request = self.factory.post(
            "/api/v1/internal/messages/send",
            data=json.dumps(payload),
            content_type="application/json",
        )
        request.is_service_request = True
        return request

    @patch("nodl.api.views.assistant._get_task_stream_extension", return_value=None)
    def test_unknown_task_is_404(self, _mock_ext: MagicMock) -> None:
        response = send_assistant_message(self._request(self.payload))

        self.assertEqual(response.status_code, 404)

    @patch("nodl.api.views.assistant._get_task_stream_extension")
    def test_archived_stream_is_409(self, mock_get_extension: MagicMock) -> None:
        extension = MagicMock()
        extension.zulip_stream.deactivated = True
        mock_get_extension.return_value = extension

        response = send_assistant_message(self._request(self.payload))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(json.loads(response.content)["code"], "STREAM_ARCHIVED")

    @patch("nodl.api.views.assistant._get_task_stream_extension")
    def test_invalid_card_payload_is_400(self, mock_get_extension: MagicMock) -> None:
        extension = MagicMock()
        extension.zulip_stream.deactivated = False
        mock_get_extension.return_value = extension

        payload = {**self.payload, "card_type": "checkin", "card_payload": {"bad": True}}
        response = send_assistant_message(self._request(payload))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)["code"], "INVALID_CARD")

    @patch("nodl.api.views.assistant.get_client")
    @patch("nodl.api.views.assistant.check_send_message")
    @patch("nodl.api.views.assistant.bulk_add_subscriptions")
    @patch("nodl.api.views.assistant.Subscription.objects")
    @patch("nodl.api.views.assistant.ensure_assistant_bot")
    @patch("nodl.api.views.assistant.NodlRealmExtension.objects")
    @patch("nodl.api.views.assistant._get_task_stream_extension")
    def test_sends_card_as_bot_and_subscribes_if_needed(
        self,
        mock_get_extension: MagicMock,
        mock_realm_ext_objects: MagicMock,
        mock_ensure_bot: MagicMock,
        mock_subscription_objects: MagicMock,
        mock_subscribe: MagicMock,
        mock_send: MagicMock,
        _mock_get_client: MagicMock,
    ) -> None:
        extension = MagicMock()
        extension.zulip_stream = MagicMock(id=42, deactivated=False)
        mock_get_extension.return_value = extension
        bot = MagicMock(id=99)
        mock_ensure_bot.return_value = bot
        mock_subscription_objects.filter.return_value.exists.return_value = False
        mock_send.return_value = MagicMock(message_id=123)

        payload = {
            **self.payload,
            "card_type": "ask_ai_answer",
            "card_payload": {
                "task_id": self.payload["task_id"],
                "mode": "assessment",
                "answer": "On track.",
            },
        }
        response = send_assistant_message(self._request(payload))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)["message_id"], 123)
        mock_subscribe.assert_called_once()
        sent_content = mock_send.call_args.kwargs["message_content"]
        self.assertTrue(sent_content.startswith("<!-- nodl-card:v1:"))
        self.assertIn("Assessment: on track.", sent_content)
        self.assertEqual(mock_send.call_args.kwargs["sender"], bot)
        self.assertEqual(mock_send.call_args.kwargs["message_to"], [42])


class TestUpdateAssistantCard(TestCase):
    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.payload = {
            "workspace_id": str(uuid.uuid4()),
            "task_id": str(uuid.uuid4()),
            "content": "**Check-in**: answered",
            "card_type": "checkin",
            "card_payload": {
                "checkin_id": str(uuid.uuid4()),
                "task_id": str(uuid.uuid4()),
                "workspace_id": str(uuid.uuid4()),
                "rule": "deadline_approaching",
                "question": "Is this task on track?",
                "status": "responded",
                "response": "blocked",
            },
        }

    def _request(self, payload: dict, message_id: int = 77):
        request = self.factory.post(
            f"/api/v1/internal/messages/{message_id}/update-card",
            data=json.dumps(payload),
            content_type="application/json",
        )
        request.is_service_request = True
        return request

    def test_requires_service_auth(self) -> None:
        from nodl.api.views.assistant import update_assistant_card

        request = self.factory.post("/api/v1/internal/messages/77/update-card")
        request.is_service_request = False

        self.assertEqual(update_assistant_card(request, 77).status_code, 401)

    @patch("nodl.api.views.assistant._get_task_stream_extension", return_value=None)
    def test_unknown_task_is_404(self, _mock_ext: MagicMock) -> None:
        from nodl.api.views.assistant import update_assistant_card

        response = update_assistant_card(self._request(self.payload), 77)

        self.assertEqual(response.status_code, 404)

    @patch("nodl.api.views.assistant.do_update_message")
    @patch("nodl.api.views.assistant.MentionData")
    @patch("nodl.api.views.assistant.MentionBackend")
    @patch("nodl.api.views.assistant.render_message_markdown")
    @patch("nodl.api.views.assistant.Message.objects")
    @patch("nodl.api.views.assistant.ensure_assistant_bot")
    @patch("nodl.api.views.assistant.NodlRealmExtension.objects")
    @patch("nodl.api.views.assistant.transaction.atomic")
    @patch("nodl.api.views.assistant._get_task_stream_extension")
    def test_rewrites_card_as_bot(
        self,
        mock_get_extension: MagicMock,
        mock_atomic: MagicMock,
        mock_realm_ext_objects: MagicMock,
        mock_ensure_bot: MagicMock,
        mock_message_objects: MagicMock,
        mock_render: MagicMock,
        _mock_backend: MagicMock,
        _mock_mention: MagicMock,
        mock_update: MagicMock,
    ) -> None:
        from nodl.api.views.assistant import update_assistant_card

        mock_atomic.return_value.__enter__ = MagicMock()
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
        extension = MagicMock()
        extension.zulip_stream = MagicMock(recipient_id=7)
        mock_get_extension.return_value = extension
        bot = MagicMock(id=99)
        mock_ensure_bot.return_value = bot
        message = MagicMock(sender_id=99, content="old")
        message.topic_name.return_value = "task"
        lookup = mock_message_objects.select_for_update.return_value.select_related.return_value.filter.return_value
        lookup.first.return_value = message

        response = update_assistant_card(self._request(self.payload), 77)

        self.assertEqual(response.status_code, 200, response.content)
        sent_content = mock_update.call_args.kwargs["message_edit_request"].content
        self.assertTrue(sent_content.startswith("<!-- nodl-card:v1:"))
        self.assertIn("**Check-in**: answered", sent_content)
        self.assertEqual(mock_update.call_args.kwargs["user_profile"], bot)

    @patch("nodl.api.views.assistant.transaction.atomic")
    @patch("nodl.api.views.assistant.NodlRealmExtension.objects")
    @patch("nodl.api.views.assistant.ensure_assistant_bot")
    @patch("nodl.api.views.assistant.Message.objects")
    @patch("nodl.api.views.assistant._get_task_stream_extension")
    def test_rejects_non_bot_messages(
        self,
        mock_get_extension: MagicMock,
        mock_message_objects: MagicMock,
        mock_ensure_bot: MagicMock,
        _mock_realm_ext: MagicMock,
        mock_atomic: MagicMock,
    ) -> None:
        from nodl.api.views.assistant import update_assistant_card

        mock_atomic.return_value.__enter__ = MagicMock()
        mock_atomic.return_value.__exit__ = MagicMock(return_value=False)
        extension = MagicMock()
        extension.zulip_stream = MagicMock(recipient_id=7)
        mock_get_extension.return_value = extension
        mock_ensure_bot.return_value = MagicMock(id=99)
        human_message = MagicMock(sender_id=11)
        lookup = mock_message_objects.select_for_update.return_value.select_related.return_value.filter.return_value
        lookup.first.return_value = human_message

        response = update_assistant_card(self._request(self.payload), 77)

        self.assertEqual(response.status_code, 403)
