"""Unit tests for messages API endpoints.

Tests cover:
- AC1: GET /messages with anchor-based pagination
- AC2: POST /messages sends message
- AC3: GET /messages/{id} returns single message with reactions
- AC4: PATCH /messages/{id} edits message (owner only)
- AC5: DELETE /messages/{id} deletes message (owner or admin)
- AC6: Messages include rendered_content
- AC7: Filter by stream_id and topic query parameters
- AC8: Rate limiting (60 messages/minute)
- IV1: Messages persist to database correctly
- IV2: Markdown rendering matches expected output
- IV3: Edit history tracked for edited messages
"""

import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from nodl.api.views.messages import (
    delete_message,
    edit_message,
    get_message,
    list_messages,
    send_message,
)


class MockUserProfile:
    """Mock user profile for testing."""

    ROLE_REALM_OWNER = 100
    ROLE_REALM_ADMINISTRATOR = 200
    ROLE_MODERATOR = 300
    ROLE_MEMBER = 400
    ROLE_GUEST = 600

    def __init__(
        self,
        id: int = 1,
        realm_id: int = 1,
        role: int = 400,  # Regular user
        is_authenticated: bool = True,
        full_name: str = "Test User",
        delivery_email: str = "test@example.com",
        avatar_source: str = "G",
    ):
        self.id = id
        self.realm_id = realm_id
        self.role = role
        self.is_authenticated = is_authenticated
        self.full_name = full_name
        self.delivery_email = delivery_email
        self.avatar_source = avatar_source
        self.realm = MockRealm(realm_id)


class MockRealm:
    """Mock realm for testing."""

    def __init__(self, id: int = 1):
        self.id = id


class MockRecipient:
    """Mock recipient for testing."""

    def __init__(self, id: int = 1, type_id: int = 1):
        self.id = id
        self.type_id = type_id


class MockStream:
    """Mock stream for testing."""

    def __init__(
        self,
        id: int = 1,
        name: str = "general",
        realm_id: int = 1,
        recipient_id: int = 1,
    ):
        self.id = id
        self.name = name
        self.realm_id = realm_id
        self.recipient_id = recipient_id
        self.recipient = MockRecipient(id=recipient_id, type_id=id)


class MockMessage:
    """Mock message for testing."""

    def __init__(
        self,
        id: int = 1,
        sender_id: int = 1,
        recipient_id: int = 1,
        realm_id: int = 1,
        content: str = "Test message",
        rendered_content: str = "<p>Test message</p>",
        subject: str = "Test Topic",
        is_channel_message: bool = True,
        date_sent: MagicMock = None,
        last_edit_time: MagicMock = None,
        edit_history: str = None,
    ):
        self.id = id
        self.sender_id = sender_id
        self.sender = MockUserProfile(id=sender_id)
        self.recipient_id = recipient_id
        self.recipient = MockRecipient(id=recipient_id, type_id=1)
        self.realm_id = realm_id
        self.content = content
        self.rendered_content = rendered_content
        self.subject = subject
        self.is_channel_message = is_channel_message
        self.date_sent = date_sent or MagicMock(timestamp=lambda: 1701100800)
        self.last_edit_time = last_edit_time
        self.edit_history = edit_history

    def topic_name(self) -> str:
        return self.subject

    def refresh_from_db(self) -> None:
        pass


class TestRequireJwtAuth(TestCase):
    """Test cases for JWT authentication decorator."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_unauthenticated_request_returns_401(self) -> None:
        """Test requests without auth return 401."""
        request = self.factory.get("/api/v1/messages")
        request.user_profile = None

        response = list_messages(request)

        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "UNAUTHORIZED")


class TestListMessages(TestCase):
    """Test cases for list messages endpoint (AC: 1, 7)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile()

    def test_stream_id_required(self) -> None:
        """Test stream_id is required."""
        request = self.factory.get("/api/v1/messages")
        request.user_profile = self.user

        response = list_messages(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "INVALID_PARAMS")
        self.assertIn("stream_id", data["msg"])

    @patch("nodl.api.views.messages.access_stream_by_id")
    def test_stream_not_found_returns_404(
        self,
        mock_access: MagicMock,
    ) -> None:
        """Test stream not found returns 404."""
        mock_access.side_effect = Exception("Not found")

        request = self.factory.get("/api/v1/messages?stream_id=999")
        request.user_profile = self.user

        response = list_messages(request)

        self.assertEqual(response.status_code, 404)

    @patch("nodl.api.views.messages.Message")
    @patch("nodl.api.views.messages.access_stream_by_id")
    def test_list_messages_with_anchor_newest(
        self,
        mock_access: MagicMock,
        mock_message_model: MagicMock,
    ) -> None:
        """Test AC1: List messages with anchor=newest."""
        stream = MockStream(id=42)
        mock_access.return_value = (stream, None)

        # Mock the queryset chain
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.select_related.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_qs.first.return_value = None
        mock_message_model.objects = mock_qs

        request = self.factory.get("/api/v1/messages?stream_id=42&anchor=newest&num_before=10")
        request.user_profile = self.user

        response = list_messages(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")
        self.assertIn("messages", data)

    @patch("nodl.api.views.messages.Message")
    @patch("nodl.api.views.messages.access_stream_by_id")
    def test_filter_by_topic_ac7(
        self,
        mock_access: MagicMock,
        mock_message_model: MagicMock,
    ) -> None:
        """Test AC7: Filter by topic query parameter."""
        stream = MockStream(id=42)
        mock_access.return_value = (stream, None)

        # Mock the queryset chain
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.select_related.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_qs.first.return_value = None
        mock_message_model.objects = mock_qs

        request = self.factory.get("/api/v1/messages?stream_id=42&topic=TestTopic")
        request.user_profile = self.user

        response = list_messages(request)

        self.assertEqual(response.status_code, 200)
        # Verify topic filter was applied
        mock_qs.filter.assert_called()

    def test_method_not_allowed_for_post(self) -> None:
        """Test POST requests return 405."""
        request = self.factory.post("/api/v1/messages")
        request.user_profile = self.user

        response = list_messages(request)

        self.assertEqual(response.status_code, 405)


class TestSendMessage(TestCase):
    """Test cases for send message endpoint (AC: 2, 6)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile()

    @patch("nodl.api.views.messages.Message")
    @patch("nodl.api.views.messages.check_send_message")
    @patch("nodl.api.views.messages.get_client")
    @patch("nodl.api.views.messages.access_stream_by_id")
    def test_send_message_ac2(
        self,
        mock_access: MagicMock,
        mock_get_client: MagicMock,
        mock_send: MagicMock,
        mock_message_model: MagicMock,
    ) -> None:
        """Test AC2: Send message to stream."""
        stream = MockStream(id=42)
        mock_access.return_value = (stream, None)
        mock_get_client.return_value = MagicMock()

        # Mock send result
        send_result = MagicMock()
        send_result.message_id = 12345
        mock_send.return_value = send_result

        # Mock message retrieval
        message = MockMessage(id=12345, content="Hello **world**!")
        mock_message_model.objects.select_related.return_value.get.return_value = message

        request = self.factory.post(
            "/api/v1/messages/send",
            data=json.dumps(
                {
                    "stream_id": 42,
                    "topic": "Test Topic",
                    "content": "Hello **world**!",
                }
            ),
            content_type="application/json",
        )
        request.user_profile = self.user

        response = send_message(request)

        self.assertEqual(response.status_code, 201)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["id"], 12345)

    @patch("nodl.api.views.messages.access_stream_by_id")
    def test_send_to_invalid_stream_returns_404(
        self,
        mock_access: MagicMock,
    ) -> None:
        """Test send to invalid stream returns 404."""
        mock_access.side_effect = Exception("Not found")

        request = self.factory.post(
            "/api/v1/messages/send",
            data=json.dumps(
                {
                    "stream_id": 999,
                    "topic": "Test",
                    "content": "Hello",
                }
            ),
            content_type="application/json",
        )
        request.user_profile = self.user

        response = send_message(request)

        self.assertEqual(response.status_code, 404)

    def test_send_invalid_json_returns_400(self) -> None:
        """Test invalid JSON returns 400."""
        request = self.factory.post(
            "/api/v1/messages/send",
            data="not valid json",
            content_type="application/json",
        )
        request.user_profile = self.user

        response = send_message(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "INVALID_JSON")

    def test_send_validation_error_returns_400(self) -> None:
        """Test validation error returns 400."""
        request = self.factory.post(
            "/api/v1/messages/send",
            data=json.dumps(
                {
                    "stream_id": 42,
                    # Missing required fields
                }
            ),
            content_type="application/json",
        )
        request.user_profile = self.user

        response = send_message(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "VALIDATION_ERROR")


class TestGetMessage(TestCase):
    """Test cases for get message endpoint (AC: 3)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile()

    @patch("nodl.api.views.messages._get_message_flags")
    @patch("nodl.api.views.messages._get_reactions_for_message")
    @patch("nodl.api.views.messages.access_message")
    def test_get_message_with_reactions_ac3(
        self,
        mock_access: MagicMock,
        mock_reactions: MagicMock,
        mock_flags: MagicMock,
    ) -> None:
        """Test AC3: Get message with reactions."""
        message = MockMessage(id=12345)
        mock_access.return_value = message
        mock_reactions.return_value = [
            MagicMock(
                model_dump=lambda: {
                    "emoji_name": "thumbs_up",
                    "emoji_code": "1f44d",
                    "user_ids": [1, 2],
                }
            )
        ]
        mock_flags.return_value = ["read"]

        request = self.factory.get("/api/v1/messages/12345")
        request.user_profile = self.user

        response = get_message(request, message_id=12345)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")
        self.assertIn("message", data)

    @patch("nodl.api.views.messages.access_message")
    def test_get_nonexistent_message_returns_404(
        self,
        mock_access: MagicMock,
    ) -> None:
        """Test nonexistent message returns 404."""
        from zerver.lib.exceptions import JsonableError

        mock_access.side_effect = JsonableError("Not found")

        request = self.factory.get("/api/v1/messages/999")
        request.user_profile = self.user

        response = get_message(request, message_id=999)

        self.assertEqual(response.status_code, 404)


class TestEditMessage(TestCase):
    """Test cases for edit message endpoint (AC: 4)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile(id=1)

    @patch("nodl.api.views.messages._get_message_flags")
    @patch("nodl.api.views.messages._get_reactions_for_message")
    @patch("nodl.api.views.messages.do_update_message")
    @patch("nodl.api.views.messages.render_message_markdown")
    @patch("nodl.api.views.messages.access_message")
    def test_owner_can_edit_ac4(
        self,
        mock_access: MagicMock,
        mock_render: MagicMock,
        mock_update: MagicMock,
        mock_reactions: MagicMock,
        mock_flags: MagicMock,
    ) -> None:
        """Test AC4: Owner can edit message."""
        message = MockMessage(id=12345, sender_id=1)  # Same as user.id
        mock_access.return_value = message
        mock_render.return_value = MagicMock(rendered_content="<p>Updated</p>")
        mock_reactions.return_value = []
        mock_flags.return_value = []

        request = self.factory.patch(
            "/api/v1/messages/12345/edit",
            data=json.dumps({"content": "Updated content"}),
            content_type="application/json",
        )
        request.user_profile = self.user

        response = edit_message(request, message_id=12345)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")

    @patch("nodl.api.views.messages.access_message")
    def test_non_owner_cannot_edit_ac4(
        self,
        mock_access: MagicMock,
    ) -> None:
        """Test AC4: Non-owner cannot edit message."""
        message = MockMessage(id=12345, sender_id=999)  # Different from user.id
        mock_access.return_value = message

        request = self.factory.patch(
            "/api/v1/messages/12345/edit",
            data=json.dumps({"content": "Hacked!"}),
            content_type="application/json",
        )
        request.user_profile = self.user

        response = edit_message(request, message_id=12345)

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "FORBIDDEN")

    @patch("nodl.api.views.messages._get_message_flags")
    @patch("nodl.api.views.messages._get_reactions_for_message")
    @patch("nodl.api.views.messages.do_update_message")
    @patch("nodl.api.views.messages.render_message_markdown")
    @patch("nodl.api.views.messages.access_message")
    def test_edit_tracks_history_iv3(
        self,
        mock_access: MagicMock,
        mock_render: MagicMock,
        mock_update: MagicMock,
        mock_reactions: MagicMock,
        mock_flags: MagicMock,
    ) -> None:
        """Test IV3: Edit history is tracked when message is edited.

        Verifies that do_update_message is called with proper parameters
        which ensures Zulip's edit history tracking is triggered.
        """
        original_content = "Original message content"
        updated_content = "Updated message content"

        # Create message with original content and edit_history tracking
        message = MockMessage(
            id=12345,
            sender_id=1,
            content=original_content,
            rendered_content=f"<p>{original_content}</p>",
            edit_history=None,  # No prior edits
        )
        mock_access.return_value = message

        # Mock rendering result
        mock_render.return_value = MagicMock(
            rendered_content=f"<p>{updated_content}</p>",
        )
        mock_reactions.return_value = []
        mock_flags.return_value = []

        request = self.factory.patch(
            "/api/v1/messages/12345/edit",
            data=json.dumps({"content": updated_content}),
            content_type="application/json",
        )
        request.user_profile = self.user

        response = edit_message(request, message_id=12345)

        self.assertEqual(response.status_code, 200)

        # Verify do_update_message was called - this is what triggers edit history
        mock_update.assert_called_once()

        # Verify the call includes message_edit_request with new content
        call_kwargs = mock_update.call_args.kwargs
        self.assertEqual(call_kwargs["user_profile"], self.user)
        self.assertEqual(call_kwargs["target_message"], message)

        # Verify the edit request contains the new content
        edit_request = call_kwargs["message_edit_request"]
        self.assertEqual(edit_request.content, updated_content)

        # Verify rendering result is passed (required for history tracking)
        self.assertIsNotNone(call_kwargs["rendering_result"])


class TestDeleteMessage(TestCase):
    """Test cases for delete message endpoint (AC: 5)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile(id=1)

    @patch("nodl.api.views.messages.do_delete_messages")
    @patch("nodl.api.views.messages.access_message")
    def test_owner_can_delete_ac5(
        self,
        mock_access: MagicMock,
        mock_delete: MagicMock,
    ) -> None:
        """Test AC5: Owner can delete message."""
        message = MockMessage(id=12345, sender_id=1)  # Same as user.id
        mock_access.return_value = message

        request = self.factory.delete("/api/v1/messages/12345/delete")
        request.user_profile = self.user

        response = delete_message(request, message_id=12345)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")
        mock_delete.assert_called_once()

    @patch("nodl.api.views.messages.do_delete_messages")
    @patch("nodl.api.views.messages.access_message")
    def test_admin_can_delete_ac5(
        self,
        mock_access: MagicMock,
        mock_delete: MagicMock,
    ) -> None:
        """Test AC5: Admin can delete any message."""
        admin_user = MockUserProfile(id=1, role=MockUserProfile.ROLE_REALM_ADMINISTRATOR)
        message = MockMessage(id=12345, sender_id=999)  # Different sender
        mock_access.return_value = message

        request = self.factory.delete("/api/v1/messages/12345/delete")
        request.user_profile = admin_user

        response = delete_message(request, message_id=12345)

        self.assertEqual(response.status_code, 200)
        mock_delete.assert_called_once()

    @patch("nodl.api.views.messages.access_message")
    def test_non_owner_non_admin_cannot_delete_ac5(
        self,
        mock_access: MagicMock,
    ) -> None:
        """Test AC5: Non-owner non-admin cannot delete message."""
        message = MockMessage(id=12345, sender_id=999)  # Different from user.id
        mock_access.return_value = message

        request = self.factory.delete("/api/v1/messages/12345/delete")
        request.user_profile = self.user  # Regular user

        response = delete_message(request, message_id=12345)

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "FORBIDDEN")


class TestRenderedContent(TestCase):
    """Test cases for Markdown rendering (AC: 6, IV2)."""

    def test_message_serializer_includes_rendered_content_ac6(self) -> None:
        """Test AC6: Messages include rendered_content."""
        from nodl.api.serializers.messages import MessageSerializer

        message = MockMessage(
            id=1,
            content="**bold** and _italic_",
            rendered_content="<p><strong>bold</strong> and <em>italic</em></p>",
        )

        serializer = MessageSerializer.from_message(message)

        self.assertIn("rendered_content", serializer.model_dump())
        self.assertEqual(
            serializer.rendered_content,
            "<p><strong>bold</strong> and <em>italic</em></p>",
        )


class TestRateLimiting(TestCase):
    """Test cases for rate limiting (AC: 8)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile()

    @patch("nodl.api.views.messages.MessagesRateLimitedObject.rate_limit_request")
    @patch("nodl.api.views.messages.Message")
    @patch("nodl.api.views.messages.access_stream_by_id")
    def test_rate_limiting_applied_to_list(
        self,
        mock_access: MagicMock,
        mock_message_model: MagicMock,
        mock_rate_limit: MagicMock,
    ) -> None:
        """Test rate limiting is applied to list endpoint."""
        stream = MockStream(id=42)
        mock_access.return_value = (stream, None)

        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.select_related.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.__getitem__ = MagicMock(return_value=[])
        mock_qs.first.return_value = None
        mock_message_model.objects = mock_qs

        request = self.factory.get("/api/v1/messages?stream_id=42")
        request.user_profile = self.user

        list_messages(request)

        mock_rate_limit.assert_called_once()

    @patch("nodl.api.views.messages.MessagesRateLimitedObject.rate_limit_request")
    def test_rate_limit_exceeded_returns_429(
        self,
        mock_rate_limit: MagicMock,
    ) -> None:
        """Test AC8: Rate limit exceeded returns 429."""
        mock_rate_limit.side_effect = Exception("Rate limited")

        request = self.factory.get("/api/v1/messages?stream_id=42")
        request.user_profile = self.user

        response = list_messages(request)

        self.assertEqual(response.status_code, 429)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "RATE_LIMITED")
        self.assertIn("retry_after", data)


class TestMessagePersistence(TestCase):
    """Test cases for message persistence (IV1)."""

    @patch("nodl.api.views.messages.Message")
    @patch("nodl.api.views.messages.check_send_message")
    @patch("nodl.api.views.messages.get_client")
    @patch("nodl.api.views.messages.access_stream_by_id")
    def test_sent_message_persists_iv1(
        self,
        mock_access: MagicMock,
        mock_get_client: MagicMock,
        mock_send: MagicMock,
        mock_message_model: MagicMock,
    ) -> None:
        """Test IV1: Sent message persists to database."""
        factory = RequestFactory()
        user = MockUserProfile()

        stream = MockStream(id=42)
        mock_access.return_value = (stream, None)
        mock_get_client.return_value = MagicMock()

        send_result = MagicMock()
        send_result.message_id = 12345
        mock_send.return_value = send_result

        message = MockMessage(id=12345, content="Test content")
        mock_message_model.objects.select_related.return_value.get.return_value = message

        request = factory.post(
            "/api/v1/messages/send",
            data=json.dumps(
                {
                    "stream_id": 42,
                    "topic": "Test",
                    "content": "Test content",
                }
            ),
            content_type="application/json",
        )
        request.user_profile = user

        response = send_message(request)

        self.assertEqual(response.status_code, 201)
        # Verify check_send_message was called (which creates the message)
        mock_send.assert_called_once()


class TestSerializers(TestCase):
    """Test cases for message serializers."""

    def test_message_serializer_from_message(self) -> None:
        """Test MessageSerializer.from_message method."""
        from nodl.api.serializers.messages import MessageSerializer

        message = MockMessage(
            id=12345,
            sender_id=1,
            content="Hello **world**!",
            rendered_content="<p>Hello <strong>world</strong>!</p>",
            subject="Test Topic",
        )

        serializer = MessageSerializer.from_message(message)

        self.assertEqual(serializer.id, 12345)
        self.assertEqual(serializer.content, "Hello **world**!")
        self.assertIn("<strong>world</strong>", serializer.rendered_content)

    def test_message_list_serializer_from_message(self) -> None:
        """Test MessageListSerializer.from_message method."""
        from nodl.api.serializers.messages import MessageListSerializer

        message = MockMessage(id=12345)

        serializer = MessageListSerializer.from_message(message)

        self.assertEqual(serializer.id, 12345)

    def test_reaction_serializer(self) -> None:
        """Test ReactionSerializer."""
        from nodl.api.serializers.messages import ReactionSerializer

        reaction = ReactionSerializer(
            emoji_name="thumbs_up",
            emoji_code="1f44d",
            user_ids=[1, 2, 3],
        )

        self.assertEqual(reaction.emoji_name, "thumbs_up")
        self.assertEqual(reaction.user_ids, [1, 2, 3])

    def test_message_create_payload_validation(self) -> None:
        """Test MessageCreatePayload validation."""
        from nodl.api.serializers.messages import MessageCreatePayload

        # Valid payload
        payload = MessageCreatePayload(
            stream_id=42,
            topic="Test Topic",
            content="Hello world!",
        )
        self.assertEqual(payload.stream_id, 42)
        self.assertEqual(payload.topic, "Test Topic")

        # Invalid payload - empty content
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            MessageCreatePayload(
                stream_id=42,
                topic="Test",
                content="",  # min_length=1
            )

    def test_message_update_payload_validation(self) -> None:
        """Test MessageUpdatePayload validation."""
        from nodl.api.serializers.messages import MessageUpdatePayload

        # Valid payload
        payload = MessageUpdatePayload(content="Updated content")
        self.assertEqual(payload.content, "Updated content")

        # Invalid payload - empty content
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            MessageUpdatePayload(content="")  # min_length=1
