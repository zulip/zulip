"""Unit tests for streams API endpoints.

Tests cover:
- AC1: List streams with unread counts
- AC2: Create stream
- AC3: Get stream details
- AC4: Update stream (admin only)
- AC5: Archive stream (admin only)
- AC6: Get topics in stream
- AC7: Subscribe to stream
- AC8: Unsubscribe from stream
- AC9: Rate limiting
- IV1: Realm scoping
- IV2: Private stream visibility
- IV3: Permission enforcement
"""

import json
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from nodl.api.views.streams import (
    archive_stream,
    create_stream,
    get_stream,
    get_stream_topics,
    list_streams,
    subscribe_to_stream,
    unsubscribe_from_stream,
    update_stream,
)


class MockUserProfile:
    """Mock user profile for testing."""

    def __init__(
        self,
        id: int = 1,
        realm_id: int = 1,
        role: int = 400,  # Regular user
        is_authenticated: bool = True,
    ):
        self.id = id
        self.realm_id = realm_id
        self.realm = MockRealm(realm_id)
        self.role = role
        self.is_authenticated = is_authenticated


class MockRealm:
    """Mock realm for testing."""

    def __init__(self, id: int = 1):
        self.id = id


class MockStream:
    """Mock stream for testing."""

    def __init__(
        self,
        id: int = 1,
        name: str = "general",
        description: str = "General discussion",
        realm_id: int = 1,
        invite_only: bool = False,
        history_public_to_subscribers: bool = True,
        first_message_id: int = 100,
        recipient_id: int = 1,
        stream_post_policy: int = 1,
        deactivated: bool = False,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.realm_id = realm_id
        self.realm = MockRealm(realm_id)
        self.invite_only = invite_only
        self.history_public_to_subscribers = history_public_to_subscribers
        self.first_message_id = first_message_id
        self.recipient_id = recipient_id
        self.recipient = MagicMock(id=recipient_id)
        self.stream_post_policy = stream_post_policy
        self.deactivated = deactivated
        self.STREAM_POST_POLICY_ADMINS = 2

    def is_history_realm_public(self) -> bool:
        return not self.invite_only

    def refresh_from_db(self) -> None:
        pass


def mock_task_extension(
    stream_id: int,
    task_id: str,
    task_title: str = "",
    archived_at=None,
) -> MagicMock:
    extension = MagicMock()
    extension.zulip_stream_id = stream_id
    extension.nodl_task_id = task_id
    extension.task_title = task_title
    extension.archived_at = archived_at
    return extension


class TestRequireJwtAuth(TestCase):
    """Test cases for JWT authentication decorator."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_unauthenticated_request_returns_401(self) -> None:
        """Test requests without auth return 401."""
        request = self.factory.get("/api/v1/streams")
        request.user_profile = None

        response = list_streams(request)

        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "UNAUTHORIZED")

    @patch("nodl.api.views.streams.Subscription.objects.filter")
    @patch("nodl.api.views.streams.NodlTaskStreamExtension.objects")
    @patch("nodl.api.views.streams._get_unread_counts_for_streams")
    @patch("nodl.api.views.streams.get_streams_for_user")
    def test_authenticated_request_passes_through(
        self,
        mock_get_streams: MagicMock,
        mock_unread_counts: MagicMock,
        mock_task_stream_objects: MagicMock,
        mock_subscription_filter: MagicMock,
    ) -> None:
        """Test requests with auth pass through."""
        mock_get_streams.return_value = []
        mock_unread_counts.return_value = {}
        mock_task_stream_objects.filter.return_value = []
        mock_subscription_filter.return_value.values.return_value = []

        request = self.factory.get("/api/v1/streams")
        request.user_profile = MockUserProfile()

        response = list_streams(request)

        self.assertEqual(response.status_code, 200)


class TestListStreams(TestCase):
    """Test cases for list streams endpoint (AC: 1)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile()

    @patch("nodl.api.views.streams.Subscription.objects.filter")
    @patch("nodl.api.views.streams.NodlTaskStreamExtension.objects")
    @patch("nodl.api.views.streams._get_unread_counts_for_streams")
    @patch("nodl.api.views.streams.get_streams_for_user")
    def test_list_streams_returns_unread_counts(
        self,
        mock_get_streams: MagicMock,
        mock_unread_counts: MagicMock,
        mock_task_stream_objects: MagicMock,
        mock_subscription_filter: MagicMock,
    ) -> None:
        """Test AC1: List streams with unread counts."""
        stream = MockStream()
        mock_get_streams.return_value = [stream]
        mock_unread_counts.return_value = {stream.recipient_id: 5}
        mock_task_stream_objects.filter.return_value = []
        mock_subscription_filter.return_value.values.return_value = []

        request = self.factory.get("/api/v1/streams")
        request.user_profile = self.user

        response = list_streams(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")
        self.assertEqual(len(data["streams"]), 1)
        self.assertEqual(data["streams"][0]["unread_count"], 5)

    @patch("nodl.api.views.streams.Subscription.objects.filter")
    @patch("nodl.api.views.streams.NodlTaskStreamExtension.objects")
    @patch("nodl.api.views.streams._get_unread_counts_for_streams")
    @patch("nodl.api.views.streams.get_streams_for_user")
    def test_streams_scoped_to_user_realm_iv1(
        self,
        mock_get_streams: MagicMock,
        mock_unread_counts: MagicMock,
        mock_task_stream_objects: MagicMock,
        mock_subscription_filter: MagicMock,
    ) -> None:
        """Test IV1: Streams scoped to user's realm only."""
        # Stream in user's realm
        user_realm_stream = MockStream(id=1, realm_id=1)
        # Stream in different realm
        other_realm_stream = MockStream(id=2, realm_id=2)

        mock_get_streams.return_value = [user_realm_stream, other_realm_stream]
        mock_unread_counts.return_value = {}
        mock_task_stream_objects.filter.return_value = []
        mock_subscription_filter.return_value.values.return_value = []

        request = self.factory.get("/api/v1/streams")
        request.user_profile = self.user

        response = list_streams(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        stream_ids = [s["id"] for s in data["streams"]]
        self.assertIn(1, stream_ids)
        self.assertNotIn(2, stream_ids)

    @patch("nodl.api.views.streams.Subscription.objects.filter")
    @patch("nodl.api.views.streams.NodlTaskStreamExtension.objects")
    @patch("nodl.api.views.streams._get_unread_counts_for_streams")
    @patch("nodl.api.views.streams.get_streams_for_user")
    def test_task_streams_hidden_from_list_response(
        self,
        mock_get_streams: MagicMock,
        mock_unread_counts: MagicMock,
        mock_task_stream_objects: MagicMock,
        mock_subscription_filter: MagicMock,
    ) -> None:
        normal_stream = MockStream(id=1, name="general", realm_id=1)
        task_stream = MockStream(id=2, name="task-abc", realm_id=1)
        mock_get_streams.return_value = [normal_stream, task_stream]
        mock_unread_counts.return_value = {}
        mock_task_stream_objects.filter.return_value = [
            mock_task_extension(2, "47d74c7c-ccc7-4a32-b95c-54c8f84aee1b")
        ]
        mock_subscription_filter.return_value.values.return_value = []

        request = self.factory.get("/api/v1/streams")
        request.user_profile = self.user

        response = list_streams(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual([stream["id"] for stream in data["streams"]], [1])
        self.assertEqual(data["task_streams"], [])

    @patch("nodl.api.views.streams.Subscription.objects.filter")
    @patch("nodl.api.views.streams.NodlTaskStreamExtension.objects")
    @patch("nodl.api.views.streams._get_unread_counts_for_streams")
    @patch("nodl.api.views.streams.get_streams_for_user")
    def test_task_streams_returned_when_requested(
        self,
        mock_get_streams: MagicMock,
        mock_unread_counts: MagicMock,
        mock_task_stream_objects: MagicMock,
        mock_subscription_filter: MagicMock,
    ) -> None:
        normal_stream = MockStream(id=1, name="general", realm_id=1)
        task_stream = MockStream(id=2, name="task-abc", realm_id=1)
        task_id = "47d74c7c-ccc7-4a32-b95c-54c8f84aee1b"
        mock_get_streams.return_value = [normal_stream, task_stream]
        mock_unread_counts.return_value = {}
        mock_task_stream_objects.filter.return_value = [
            mock_task_extension(2, task_id, "Install cabinets")
        ]
        mock_subscription_filter.return_value.values.return_value = []

        request = self.factory.get("/api/v1/streams?include_task_streams=true")
        request.user_profile = self.user

        response = list_streams(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual([stream["id"] for stream in data["streams"]], [1])
        self.assertEqual([stream["id"] for stream in data["task_streams"]], [2])
        self.assertEqual(data["task_streams"][0]["task_id"], task_id)
        self.assertEqual(data["task_streams"][0]["display_name"], "Install cabinets")
        self.assertTrue(data["task_streams"][0]["is_task_stream"])
        self.assertFalse(data["task_streams"][0]["is_archived"])

    @patch("nodl.api.views.streams.Subscription.objects.filter")
    @patch("nodl.api.views.streams.NodlTaskStreamExtension.objects")
    @patch("nodl.api.views.streams._get_unread_counts_for_streams")
    @patch("nodl.api.views.streams.get_streams_for_user")
    def test_archived_task_streams_returned_when_requested(
        self,
        mock_get_streams: MagicMock,
        mock_unread_counts: MagicMock,
        mock_task_stream_objects: MagicMock,
        mock_subscription_filter: MagicMock,
    ) -> None:
        task_stream = MockStream(id=2, name="task-done", realm_id=1, deactivated=True)
        task_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        mock_get_streams.return_value = [task_stream]
        mock_unread_counts.return_value = {}
        mock_task_stream_objects.filter.return_value = [
            mock_task_extension(2, task_id, "Paint kitchen", archived_at=object())
        ]
        mock_subscription_filter.return_value.values.return_value = []

        request = self.factory.get("/api/v1/streams?include_task_streams=true")
        request.user_profile = self.user

        response = list_streams(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["streams"], [])
        self.assertEqual([stream["id"] for stream in data["task_streams"]], [2])
        self.assertEqual(data["task_streams"][0]["display_name"], "Paint kitchen")
        self.assertTrue(data["task_streams"][0]["is_archived"])

    def test_method_not_allowed_for_post(self) -> None:
        """Test POST requests return 405."""
        request = self.factory.post("/api/v1/streams")
        request.user_profile = self.user

        response = list_streams(request)

        self.assertEqual(response.status_code, 405)


class TestCreateStream(TestCase):
    """Test cases for create stream endpoint (AC: 2)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile()
        self.user.realm = MockRealm()

    @patch("nodl.api.views.streams.bulk_add_subscriptions")
    @patch("nodl.api.views.streams.create_stream_if_needed")
    @patch("nodl.api.views.streams.check_stream_name_available")
    def test_create_stream(
        self,
        mock_check_name: MagicMock,
        mock_create: MagicMock,
        mock_subscribe: MagicMock,
    ) -> None:
        """Test AC2: Create new stream."""
        new_stream = MockStream(id=42, name="new-stream")
        mock_create.return_value = (new_stream, True)

        request = self.factory.post(
            "/api/v1/streams/create",
            data=json.dumps(
                {
                    "name": "new-stream",
                    "description": "A new stream",
                    "is_private": False,
                }
            ),
            content_type="application/json",
        )
        request.user_profile = self.user

        response = create_stream(request)

        self.assertEqual(response.status_code, 201)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["stream"]["name"], "new-stream")

    @patch("nodl.api.views.streams.check_stream_name_available")
    def test_create_stream_duplicate_name(
        self,
        mock_check_name: MagicMock,
    ) -> None:
        """Test stream creation fails for duplicate name."""
        mock_check_name.side_effect = Exception("Stream exists")

        request = self.factory.post(
            "/api/v1/streams/create",
            data=json.dumps(
                {
                    "name": "existing-stream",
                    "description": "Duplicate",
                }
            ),
            content_type="application/json",
        )
        request.user_profile = self.user

        response = create_stream(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "STREAM_EXISTS")

    def test_create_stream_invalid_json(self) -> None:
        """Test invalid JSON returns 400."""
        request = self.factory.post(
            "/api/v1/streams/create",
            data="not valid json",
            content_type="application/json",
        )
        request.user_profile = self.user

        response = create_stream(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "INVALID_JSON")

    def test_create_stream_validation_error(self) -> None:
        """Test missing required fields returns 400."""
        request = self.factory.post(
            "/api/v1/streams/create",
            data=json.dumps({}),  # Missing required 'name' field
            content_type="application/json",
        )
        request.user_profile = self.user

        response = create_stream(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "VALIDATION_ERROR")


class TestGetStream(TestCase):
    """Test cases for get stream endpoint (AC: 3)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile()

    @patch("nodl.api.views.streams._get_subscribers_for_stream")
    @patch("nodl.api.views.streams.access_stream_by_id")
    def test_get_stream_details(
        self,
        mock_access: MagicMock,
        mock_subscribers: MagicMock,
    ) -> None:
        """Test AC3: Get stream details including subscribers."""
        stream = MockStream(id=42)
        mock_access.return_value = (stream, None)
        mock_subscribers.return_value = [1, 2, 3]

        request = self.factory.get("/api/v1/streams/42")
        request.user_profile = self.user

        response = get_stream(request, stream_id=42)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["stream"]["id"], 42)
        self.assertEqual(data["stream"]["subscribers"], [1, 2, 3])

    @patch("nodl.api.views.streams.access_stream_by_id")
    def test_get_stream_not_found(
        self,
        mock_access: MagicMock,
    ) -> None:
        """Test stream not found returns 404."""
        mock_access.side_effect = Exception("Not found")

        request = self.factory.get("/api/v1/streams/999")
        request.user_profile = self.user

        response = get_stream(request, stream_id=999)

        self.assertEqual(response.status_code, 404)


class TestUpdateStream(TestCase):
    """Test cases for update stream endpoint (AC: 4)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.admin_user = MockUserProfile(role=200)  # Admin role

    @patch("nodl.api.views.streams._get_subscribers_for_stream")
    @patch("nodl.api.views.streams.do_rename_stream")
    @patch("nodl.api.views.streams.access_stream_for_delete_or_update_requiring_metadata_access")
    def test_update_stream_requires_admin_iv3(
        self,
        mock_access: MagicMock,
        mock_rename: MagicMock,
        mock_subscribers: MagicMock,
    ) -> None:
        """Test IV3: Update stream requires admin permission."""
        stream = MockStream(id=42, name="old-name")
        mock_access.return_value = (stream, None)
        mock_subscribers.return_value = []

        request = self.factory.patch(
            "/api/v1/streams/42/update",
            data=json.dumps({"name": "new-name"}),
            content_type="application/json",
        )
        request.user_profile = self.admin_user

        response = update_stream(request, stream_id=42)

        self.assertEqual(response.status_code, 200)

    @patch("nodl.api.views.streams.access_stream_for_delete_or_update_requiring_metadata_access")
    def test_update_stream_forbidden_for_non_admin(
        self,
        mock_access: MagicMock,
    ) -> None:
        """Test non-admin cannot update stream."""
        mock_access.side_effect = Exception("Permission denied")

        non_admin = MockUserProfile(role=400)  # Regular user
        request = self.factory.patch(
            "/api/v1/streams/42/update",
            data=json.dumps({"name": "new-name"}),
            content_type="application/json",
        )
        request.user_profile = non_admin

        response = update_stream(request, stream_id=42)

        self.assertEqual(response.status_code, 403)


class TestArchiveStream(TestCase):
    """Test cases for archive stream endpoint (AC: 5)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.admin_user = MockUserProfile(role=200)  # Admin role

    @patch("nodl.api.views.streams.do_deactivate_stream")
    @patch("nodl.api.views.streams.access_stream_for_delete_or_update_requiring_metadata_access")
    def test_archive_stream(
        self,
        mock_access: MagicMock,
        mock_deactivate: MagicMock,
    ) -> None:
        """Test AC5: Archive stream (soft delete)."""
        stream = MockStream(id=42)
        mock_access.return_value = (stream, None)

        request = self.factory.delete("/api/v1/streams/42/archive")
        request.user_profile = self.admin_user

        response = archive_stream(request, stream_id=42)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")
        mock_deactivate.assert_called_once()

    @patch("nodl.api.views.streams.access_stream_for_delete_or_update_requiring_metadata_access")
    def test_archive_stream_forbidden_for_non_admin(
        self,
        mock_access: MagicMock,
    ) -> None:
        """Test IV3: Non-admin cannot archive stream."""
        mock_access.side_effect = Exception("Permission denied")

        non_admin = MockUserProfile(role=400)  # Regular user
        request = self.factory.delete("/api/v1/streams/42/archive")
        request.user_profile = non_admin

        response = archive_stream(request, stream_id=42)

        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "FORBIDDEN")


class TestGetStreamTopics(TestCase):
    """Test cases for get stream topics endpoint (AC: 6)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile()

    @patch("nodl.api.views.streams.get_topic_history_for_stream")
    @patch("nodl.api.views.streams.access_stream_by_id")
    def test_get_topics(
        self,
        mock_access: MagicMock,
        mock_topics: MagicMock,
    ) -> None:
        """Test AC6: Get topics with message counts."""
        stream = MockStream(id=42)
        mock_access.return_value = (stream, None)
        mock_topics.return_value = [
            {"name": "Welcome", "max_id": 12345},
            {"name": "General", "max_id": 12346},
        ]

        request = self.factory.get("/api/v1/streams/42/topics")
        request.user_profile = self.user

        response = get_stream_topics(request, stream_id=42)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")
        self.assertEqual(len(data["topics"]), 2)


class TestSubscribe(TestCase):
    """Test cases for subscribe endpoint (AC: 7)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile()
        self.user.realm = MockRealm()

    @patch("nodl.api.views.streams.bulk_add_subscriptions")
    @patch("nodl.api.views.streams.access_stream_by_id")
    def test_subscribe_to_stream(
        self,
        mock_access: MagicMock,
        mock_subscribe: MagicMock,
    ) -> None:
        """Test AC7: Subscribe to stream."""
        stream = MockStream(id=42)
        mock_access.return_value = (stream, None)
        mock_subscribe.return_value = ([], [])  # (new_subs, already_subscribed)

        request = self.factory.post("/api/v1/streams/42/subscribe")
        request.user_profile = self.user

        response = subscribe_to_stream(request, stream_id=42)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")


class TestUnsubscribe(TestCase):
    """Test cases for unsubscribe endpoint (AC: 8)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile()
        self.user.realm = MockRealm()

    @patch("nodl.api.views.streams.bulk_remove_subscriptions")
    @patch("nodl.api.views.streams.access_stream_by_id")
    def test_unsubscribe_from_stream(
        self,
        mock_access: MagicMock,
        mock_unsubscribe: MagicMock,
    ) -> None:
        """Test AC8: Unsubscribe from stream."""
        stream = MockStream(id=42)
        mock_access.return_value = (stream, None)
        mock_unsubscribe.return_value = ([], [])  # (removed, not_subscribed)

        request = self.factory.delete("/api/v1/streams/42/unsubscribe")
        request.user_profile = self.user

        response = unsubscribe_from_stream(request, stream_id=42)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")


class TestPrivateStreamVisibility(TestCase):
    """Test cases for private stream visibility (IV2)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile()

    @patch("nodl.api.views.streams._get_unread_count_for_stream")
    @patch("nodl.api.views.streams.get_streams_for_user")
    def test_private_stream_not_visible_to_non_subscriber_iv2(
        self,
        mock_get_streams: MagicMock,
        mock_unread: MagicMock,
    ) -> None:
        """Test IV2: Private streams not visible to non-subscribers."""
        # get_streams_for_user already filters private streams for non-subscribers
        # so we simulate it returning only public streams
        public_stream = MockStream(id=1, invite_only=False)
        mock_get_streams.return_value = [public_stream]
        mock_unread.return_value = 0

        request = self.factory.get("/api/v1/streams")
        request.user_profile = self.user

        response = list_streams(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        # Only public stream should be visible
        self.assertEqual(len(data["streams"]), 1)
        self.assertEqual(data["streams"][0]["is_private"], False)


class TestRateLimiting(TestCase):
    """Test cases for rate limiting (AC: 9)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = MockUserProfile()

    @patch("nodl.api.views.streams.Subscription.objects.filter")
    @patch("nodl.api.views.streams.NodlTaskStreamExtension.objects")
    @patch("nodl.api.views.streams._get_unread_counts_for_streams")
    @patch("nodl.api.views.streams.StreamsRateLimitedObject.rate_limit_request")
    @patch("nodl.api.views.streams.get_streams_for_user")
    def test_rate_limiting_decorator_applied(
        self,
        mock_get_streams: MagicMock,
        mock_rate_limit: MagicMock,
        mock_unread_counts: MagicMock,
        mock_task_stream_objects: MagicMock,
        mock_subscription_filter: MagicMock,
    ) -> None:
        """Test rate limiting decorator is applied to endpoints."""
        mock_get_streams.return_value = []
        mock_unread_counts.return_value = {}
        mock_task_stream_objects.filter.return_value = []
        mock_subscription_filter.return_value.values.return_value = []

        request = self.factory.get("/api/v1/streams")
        request.user_profile = self.user

        list_streams(request)

        # Rate limiter should be called
        mock_rate_limit.assert_called_once()


class TestSerializers(TestCase):
    """Test cases for stream serializers."""

    def test_stream_serializer_from_stream(self) -> None:
        """Test StreamSerializer.from_stream method."""
        from nodl.api.serializers.streams import StreamSerializer

        stream = MockStream(
            id=42,
            name="test-stream",
            description="Test description",
            invite_only=True,
        )

        serializer = StreamSerializer.from_stream(stream, subscribers=[1, 2])

        self.assertEqual(serializer.id, 42)
        self.assertEqual(serializer.name, "test-stream")
        self.assertEqual(serializer.is_private, True)
        self.assertEqual(serializer.subscribers, [1, 2])

    def test_stream_list_serializer_with_unread(self) -> None:
        """Test StreamListSerializer with unread counts."""
        from nodl.api.serializers.streams import StreamListSerializer

        stream = MockStream(id=42)

        serializer = StreamListSerializer.from_stream_with_unread(
            stream,
            unread_count=10,
        )

        self.assertEqual(serializer.unread_count, 10)

    def test_topic_serializer(self) -> None:
        """Test TopicSerializer."""
        from nodl.api.serializers.streams import TopicSerializer

        topic = TopicSerializer(
            name="Welcome",
            max_id=12345,
            unread_count=5,
        )

        self.assertEqual(topic.name, "Welcome")
        self.assertEqual(topic.max_id, 12345)
        self.assertEqual(topic.unread_count, 5)

    def test_stream_create_payload_validation(self) -> None:
        """Test StreamCreatePayload validation."""
        from nodl.api.serializers.streams import StreamCreatePayload

        # Valid payload
        payload = StreamCreatePayload(
            name="new-stream",
            description="A new stream",
            is_private=False,
        )
        self.assertEqual(payload.name, "new-stream")

        # Invalid payload - empty name
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            StreamCreatePayload(name="")  # min_length=1

    def test_stream_update_payload_optional_fields(self) -> None:
        """Test StreamUpdatePayload with optional fields."""
        from nodl.api.serializers.streams import StreamUpdatePayload

        # All fields optional
        payload = StreamUpdatePayload()
        self.assertIsNone(payload.name)
        self.assertIsNone(payload.description)

        # Partial update
        payload = StreamUpdatePayload(name="updated-name")
        self.assertEqual(payload.name, "updated-name")
        self.assertIsNone(payload.description)
