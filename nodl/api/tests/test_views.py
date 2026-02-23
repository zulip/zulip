"""Unit tests for nodl API views.

Tests cover:
- Service key authentication (AC: 7)
- Request validation
- Sync endpoint functionality
"""

import json
import uuid
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase

from nodl.api.views import require_service_auth, sync_user
from nodl.sync.user_sync import UserSyncResult


class TestRequireServiceAuth(TestCase):
    """Test cases for require_service_auth decorator."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_unauthenticated_request_returns_401(self) -> None:
        """Test requests without service auth return 401."""

        @require_service_auth
        def dummy_view(request):
            return {"status": "ok"}

        request = self.factory.get("/test/")
        request.is_service_request = False

        response = dummy_view(request)

        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "UNAUTHORIZED")

    def test_authenticated_request_passes_through(self) -> None:
        """Test requests with service auth pass through."""

        @require_service_auth
        def dummy_view(request):
            from django.http import JsonResponse

            return JsonResponse({"status": "ok"})

        request = self.factory.get("/test/")
        request.is_service_request = True

        response = dummy_view(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["status"], "ok")


class TestSyncUserEndpoint(TestCase):
    """Test cases for sync_user API endpoint."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.valid_payload = {
            "supabase_user_id": str(uuid.uuid4()),
            "email": "test@example.com",
            "full_name": "Test User",
            "avatar_url": None,
            "workspace_id": "test-workspace",
            "role": "editor",
        }

    def _make_authenticated_request(self, method: str, data: dict | None = None):
        """Create a request with service authentication."""
        if method == "POST":
            request = self.factory.post(
                "/api/v1/internal/users/sync",
                data=json.dumps(data) if data else "",
                content_type="application/json",
            )
        else:
            request = self.factory.get("/api/v1/internal/users/sync")

        request.is_service_request = True
        return request

    def test_method_not_allowed_for_get(self) -> None:
        """Test GET requests return 405."""
        request = self._make_authenticated_request("GET")
        response = sync_user(request)

        self.assertEqual(response.status_code, 405)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "METHOD_NOT_ALLOWED")

    def test_invalid_json_returns_400(self) -> None:
        """Test invalid JSON body returns 400."""
        request = self.factory.post(
            "/api/v1/internal/users/sync",
            data="not valid json",
            content_type="application/json",
        )
        request.is_service_request = True

        response = sync_user(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "INVALID_JSON")

    def test_validation_error_returns_400(self) -> None:
        """Test missing required fields returns 400."""
        request = self._make_authenticated_request(
            "POST",
            {"email": "test@example.com"},  # Missing required fields
        )

        response = sync_user(request)

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertEqual(data["code"], "VALIDATION_ERROR")

    @patch("nodl.api.views.UserSyncService")
    def test_successful_sync(self, mock_service_class: MagicMock) -> None:
        """Test successful sync returns 200 with zulip_user_id."""
        mock_service = MagicMock()
        mock_service.sync_user.return_value = UserSyncResult(
            success=True,
            zulip_user_id=123,
            error=None,
        )
        mock_service_class.return_value = mock_service

        request = self._make_authenticated_request("POST", self.valid_payload)
        response = sync_user(request)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["zulip_user_id"], 123)

    @patch("nodl.api.views.UserSyncService")
    def test_failed_sync(self, mock_service_class: MagicMock) -> None:
        """Test failed sync returns 500 with error message."""
        mock_service = MagicMock()
        mock_service.sync_user.return_value = UserSyncResult(
            success=False,
            zulip_user_id=None,
            error="Realm not found",
        )
        mock_service_class.return_value = mock_service

        request = self._make_authenticated_request("POST", self.valid_payload)
        response = sync_user(request)

        self.assertEqual(response.status_code, 500)
        data = json.loads(response.content)
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["code"], "SYNC_FAILED")
        self.assertEqual(data["msg"], "Realm not found")


class TestUserSyncPayload(TestCase):
    """Test cases for UserSyncPayload validation."""

    def test_valid_payload(self) -> None:
        """Test valid payload passes validation."""
        from nodl.api.views import UserSyncPayload

        payload = UserSyncPayload(
            supabase_user_id=str(uuid.uuid4()),
            email="test@example.com",
            full_name="Test User",
            avatar_url="https://example.com/avatar.png",
            workspace_id="workspace-uuid",
            role="editor",
        )

        self.assertIsNotNone(payload.supabase_user_id)
        self.assertEqual(payload.email, "test@example.com")

    def test_avatar_url_optional(self) -> None:
        """Test avatar_url can be None."""
        from nodl.api.views import UserSyncPayload

        payload = UserSyncPayload(
            supabase_user_id=str(uuid.uuid4()),
            email="test@example.com",
            full_name="Test User",
            avatar_url=None,
            workspace_id="workspace-uuid",
            role="viewer",
        )

        self.assertIsNone(payload.avatar_url)
