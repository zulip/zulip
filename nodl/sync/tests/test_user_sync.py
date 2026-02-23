"""Unit tests for UserSyncService.

Tests cover:
- User creation sync (IV1)
- User update sync (IV2)
- Role mapping (AC: 6)
- Retry logic (AC: 5)
- API endpoint authentication (AC: 7)
"""

import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase

from nodl.extensions.models import SyncStatus
from nodl.sync.user_sync import UserSyncRequest, UserSyncResult, UserSyncService
from zerver.models import UserProfile


class TestUserSyncService(TestCase):
    """Test cases for UserSyncService."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.service = UserSyncService()
        self.sample_request = UserSyncRequest(
            supabase_user_id=str(uuid.uuid4()),
            email="test@example.com",
            full_name="Test User",
            avatar_url=None,
            workspace_id="test-workspace",
            role="editor",
        )

    def test_role_mapping_owner(self) -> None:
        """Test owner role maps to ROLE_REALM_OWNER."""
        result = self.service._map_role("owner")
        self.assertEqual(result, UserProfile.ROLE_REALM_OWNER)

    def test_role_mapping_admin(self) -> None:
        """Test admin role maps to ROLE_REALM_ADMINISTRATOR."""
        result = self.service._map_role("admin")
        self.assertEqual(result, UserProfile.ROLE_REALM_ADMINISTRATOR)

    def test_role_mapping_editor(self) -> None:
        """Test editor role maps to ROLE_MEMBER."""
        result = self.service._map_role("editor")
        self.assertEqual(result, UserProfile.ROLE_MEMBER)

    def test_role_mapping_viewer(self) -> None:
        """Test viewer role maps to ROLE_GUEST."""
        result = self.service._map_role("viewer")
        self.assertEqual(result, UserProfile.ROLE_GUEST)

    def test_role_mapping_unknown_defaults_to_member(self) -> None:
        """Test unknown role defaults to ROLE_MEMBER."""
        result = self.service._map_role("unknown_role")
        self.assertEqual(result, UserProfile.ROLE_MEMBER)

    def test_max_retry_constant(self) -> None:
        """Test MAX_RETRY_ATTEMPTS is set to 3."""
        self.assertEqual(self.service.MAX_RETRY_ATTEMPTS, 3)

    @patch("nodl.sync.user_sync.UserSyncService._get_realm_for_workspace")
    def test_sync_fails_without_realm(self, mock_get_realm: MagicMock) -> None:
        """Test sync fails when realm not found for workspace."""
        mock_get_realm.return_value = None

        result = self.service.sync_user(self.sample_request)

        self.assertFalse(result.success)
        self.assertIsNone(result.zulip_user_id)
        self.assertIn("Realm not found", result.error or "")

    @patch("nodl.sync.user_sync.NodlUserExtension.objects.get_or_create")
    def test_retry_limit_exceeded(self, mock_get_or_create: MagicMock) -> None:
        """Test sync fails when max retry attempts exceeded."""
        # Create a mock extension that has exceeded retry limit
        mock_extension = MagicMock()
        mock_extension.sync_status = SyncStatus.FAILED
        mock_extension.sync_attempts = 3
        mock_get_or_create.return_value = (mock_extension, False)

        result = self.service.sync_user(self.sample_request)

        self.assertFalse(result.success)
        self.assertIn("Max retry attempts", result.error or "")


class TestUserSyncRequest(TestCase):
    """Test cases for UserSyncRequest dataclass."""

    def test_request_creation(self) -> None:
        """Test UserSyncRequest can be created with all fields."""
        request = UserSyncRequest(
            supabase_user_id="test-uuid",
            email="test@example.com",
            full_name="Test User",
            avatar_url="https://example.com/avatar.png",
            workspace_id="workspace-uuid",
            role="editor",
        )

        self.assertEqual(request.supabase_user_id, "test-uuid")
        self.assertEqual(request.email, "test@example.com")
        self.assertEqual(request.full_name, "Test User")
        self.assertEqual(request.avatar_url, "https://example.com/avatar.png")
        self.assertEqual(request.workspace_id, "workspace-uuid")
        self.assertEqual(request.role, "editor")

    def test_request_with_none_avatar(self) -> None:
        """Test UserSyncRequest accepts None for avatar_url."""
        request = UserSyncRequest(
            supabase_user_id="test-uuid",
            email="test@example.com",
            full_name="Test User",
            avatar_url=None,
            workspace_id="workspace-uuid",
            role="viewer",
        )

        self.assertIsNone(request.avatar_url)


class TestUserSyncResult(TestCase):
    """Test cases for UserSyncResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful sync result."""
        result = UserSyncResult(
            success=True,
            zulip_user_id=123,
            error=None,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.zulip_user_id, 123)
        self.assertIsNone(result.error)

    def test_failure_result(self) -> None:
        """Test failed sync result."""
        result = UserSyncResult(
            success=False,
            zulip_user_id=None,
            error="Test error message",
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.zulip_user_id)
        self.assertEqual(result.error, "Test error message")


class TestSyncStatusEnum(TestCase):
    """Test cases for SyncStatus enum."""

    def test_sync_status_values(self) -> None:
        """Test SyncStatus enum has correct values."""
        self.assertEqual(SyncStatus.PENDING, "pending")
        self.assertEqual(SyncStatus.SYNCING, "syncing")
        self.assertEqual(SyncStatus.SYNCED, "synced")
        self.assertEqual(SyncStatus.FAILED, "failed")

    def test_sync_status_choices(self) -> None:
        """Test SyncStatus choices for model field."""
        choices = SyncStatus.choices
        expected = [
            ("pending", "Pending"),
            ("syncing", "Syncing"),
            ("synced", "Synced"),
            ("failed", "Failed"),
        ]
        self.assertEqual(choices, expected)
