"""Unit tests for WorkspaceSyncService.

Tests cover:
- Workspace sync creates realm (IV1)
- Member sync (IV2)
- Workspace deletion deactivates realm (IV3)
"""

import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase

from nodl.extensions.models import NodlRealmExtension, SyncStatus
from nodl.sync.workspace_sync import (
    WorkspaceSyncRequest,
    WorkspaceSyncResult,
    WorkspaceSyncService,
)


class TestWorkspaceSyncService(TestCase):
    """Test cases for WorkspaceSyncService."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.service = WorkspaceSyncService()
        self.sample_request = WorkspaceSyncRequest(
            nodl_workspace_id=str(uuid.uuid4()),
            name="Test Workspace",
            description="A test workspace",
            members=[],
        )

    @patch("nodl.sync.workspace_sync.do_create_realm")
    @patch("nodl.sync.workspace_sync.ensure_stream")
    def test_sync_creates_realm_with_default_stream(
        self, mock_ensure_stream: MagicMock, mock_create_realm: MagicMock
    ) -> None:
        """Test sync creates realm with default #general stream (IV1)."""
        mock_realm = MagicMock()
        mock_realm.id = 1
        mock_create_realm.return_value = mock_realm

        result = self.service.sync_workspace(self.sample_request)

        self.assertTrue(result.success)
        self.assertEqual(result.zulip_realm_id, 1)

        # Verify realm created with correct params
        mock_create_realm.assert_called_once()
        call_kwargs = mock_create_realm.call_args.kwargs
        self.assertEqual(call_kwargs["name"], "Test Workspace")
        self.assertEqual(call_kwargs["description"], "A test workspace")

        # Verify default stream created
        mock_ensure_stream.assert_called_once()
        stream_kwargs = mock_ensure_stream.call_args.kwargs
        self.assertEqual(stream_kwargs["stream_name"], "general")
        self.assertFalse(stream_kwargs["invite_only"])

    @patch("nodl.sync.workspace_sync.do_create_realm")
    @patch("nodl.sync.workspace_sync.ensure_stream")
    def test_sync_creates_extension_record(
        self, mock_ensure_stream: MagicMock, mock_create_realm: MagicMock
    ) -> None:
        """Test sync creates NodlRealmExtension record."""
        mock_realm = MagicMock()
        mock_realm.id = 1
        mock_create_realm.return_value = mock_realm

        workspace_id = str(uuid.uuid4())
        request = WorkspaceSyncRequest(
            nodl_workspace_id=workspace_id,
            name="Test Workspace",
            description=None,
            members=[],
        )

        result = self.service.sync_workspace(request)

        self.assertTrue(result.success)

        # Verify extension record created
        extension = NodlRealmExtension.objects.get(nodl_workspace_id=uuid.UUID(workspace_id))
        self.assertEqual(extension.sync_status, SyncStatus.SYNCED)
        self.assertIsNotNone(extension.last_synced_at)

    @patch("nodl.sync.workspace_sync.NodlRealmExtension.objects.select_related")
    def test_sync_updates_existing_realm(self, mock_select_related: MagicMock) -> None:
        """Test sync updates existing realm instead of creating new one."""
        mock_realm = MagicMock()
        mock_realm.id = 1
        mock_realm.name = "Old Name"
        mock_realm.description = "Old description"

        mock_extension = MagicMock()
        mock_extension.zulip_realm = mock_realm
        mock_extension.nodl_workspace_id = uuid.UUID(self.sample_request.nodl_workspace_id)

        mock_queryset = MagicMock()
        mock_queryset.get_or_create.return_value = (mock_extension, False)
        mock_select_related.return_value = mock_queryset

        result = self.service.sync_workspace(self.sample_request)

        self.assertTrue(result.success)
        self.assertEqual(result.zulip_realm_id, 1)

        # Verify realm was updated, not created
        self.assertEqual(mock_realm.name, "Test Workspace")

    @patch("nodl.sync.workspace_sync.do_create_realm")
    @patch("nodl.sync.workspace_sync.ensure_stream")
    def test_sync_fails_on_exception(
        self, mock_ensure_stream: MagicMock, mock_create_realm: MagicMock
    ) -> None:
        """Test sync handles exceptions and sets failed status."""
        mock_create_realm.side_effect = Exception("Realm creation failed")

        result = self.service.sync_workspace(self.sample_request)

        self.assertFalse(result.success)
        self.assertIsNone(result.zulip_realm_id)
        self.assertIn("Realm creation failed", result.error or "")

        # Verify extension status set to failed
        extension = NodlRealmExtension.objects.get(
            nodl_workspace_id=uuid.UUID(self.sample_request.nodl_workspace_id)
        )
        self.assertEqual(extension.sync_status, SyncStatus.FAILED)


class TestMemberSync(TestCase):
    """Test cases for member synchronization (IV2)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.service = WorkspaceSyncService()

    @patch("nodl.sync.workspace_sync.UserSyncService")
    def test_sync_workspace_members(self, mock_user_sync_service: MagicMock) -> None:
        """Test member sync calls UserSyncService for each member."""
        mock_instance = MagicMock()
        mock_instance.sync_user.return_value = MagicMock(success=True, zulip_user_id=1)
        mock_user_sync_service.return_value = mock_instance

        mock_realm = MagicMock()
        mock_realm.string_id = "test-workspace"
        mock_realm.id = 1

        members = [
            {
                "supabase_user_id": str(uuid.uuid4()),
                "email": "user1@example.com",
                "full_name": "User One",
                "role": "editor",
            },
            {
                "supabase_user_id": str(uuid.uuid4()),
                "email": "user2@example.com",
                "full_name": "User Two",
                "role": "viewer",
            },
        ]

        self.service.sync_workspace_members(mock_realm, members)

        # Verify UserSyncService called for each member
        self.assertEqual(mock_instance.sync_user.call_count, 2)

    @patch("nodl.sync.workspace_sync.UserSyncService")
    def test_member_sync_continues_on_failure(self, mock_user_sync_service: MagicMock) -> None:
        """Test member sync continues even if one member fails."""
        mock_instance = MagicMock()
        # First member fails, second succeeds
        mock_instance.sync_user.side_effect = [
            MagicMock(success=False, error="User sync failed"),
            MagicMock(success=True, zulip_user_id=2),
        ]
        mock_user_sync_service.return_value = mock_instance

        mock_realm = MagicMock()
        mock_realm.string_id = "test-workspace"
        mock_realm.id = 1

        members = [
            {"supabase_user_id": str(uuid.uuid4()), "email": "fail@example.com", "role": "editor"},
            {
                "supabase_user_id": str(uuid.uuid4()),
                "email": "success@example.com",
                "role": "viewer",
            },
        ]

        # Should not raise exception
        self.service.sync_workspace_members(mock_realm, members)

        # Both members were attempted
        self.assertEqual(mock_instance.sync_user.call_count, 2)


class TestRealmDeactivation(TestCase):
    """Test cases for realm deactivation (IV3)."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.service = WorkspaceSyncService()

    def test_deactivate_realm_not_found(self) -> None:
        """Test deactivate fails when workspace not found."""
        result = self.service.deactivate_realm(str(uuid.uuid4()))

        self.assertFalse(result.success)
        self.assertIn("No realm found", result.error or "")

    @patch("nodl.sync.workspace_sync.do_deactivate_realm")
    @patch("nodl.sync.workspace_sync.NodlRealmExtension.objects.select_related")
    def test_deactivate_realm_success(
        self, mock_select_related: MagicMock, mock_deactivate: MagicMock
    ) -> None:
        """Test realm deactivation (soft delete) success (IV3)."""
        mock_realm = MagicMock()
        mock_realm.id = 1

        mock_extension = MagicMock()
        mock_extension.zulip_realm = mock_realm

        mock_queryset = MagicMock()
        mock_queryset.get.return_value = mock_extension
        mock_select_related.return_value = mock_queryset

        workspace_id = str(uuid.uuid4())
        result = self.service.deactivate_realm(workspace_id)

        self.assertTrue(result.success)
        self.assertEqual(result.zulip_realm_id, 1)

        # Verify soft delete called (not hard delete)
        mock_deactivate.assert_called_once()
        call_kwargs = mock_deactivate.call_args.kwargs
        self.assertEqual(call_kwargs["deactivation_reason"], "workspace_deleted")
        self.assertFalse(call_kwargs["email_owners"])

    @patch("nodl.sync.workspace_sync.do_deactivate_realm")
    @patch("nodl.sync.workspace_sync.NodlRealmExtension.objects.select_related")
    def test_deactivate_realm_handles_exception(
        self, mock_select_related: MagicMock, mock_deactivate: MagicMock
    ) -> None:
        """Test deactivate handles exceptions gracefully."""
        mock_realm = MagicMock()
        mock_realm.id = 1

        mock_extension = MagicMock()
        mock_extension.zulip_realm = mock_realm

        mock_queryset = MagicMock()
        mock_queryset.get.return_value = mock_extension
        mock_select_related.return_value = mock_queryset

        mock_deactivate.side_effect = Exception("Deactivation failed")

        result = self.service.deactivate_realm(str(uuid.uuid4()))

        self.assertFalse(result.success)
        self.assertIn("Deactivation failed", result.error or "")


class TestWorkspaceSyncRequest(TestCase):
    """Test cases for WorkspaceSyncRequest dataclass."""

    def test_request_creation(self) -> None:
        """Test WorkspaceSyncRequest can be created with all fields."""
        request = WorkspaceSyncRequest(
            nodl_workspace_id="workspace-uuid",
            name="Test Workspace",
            description="A test workspace",
            members=[
                {"supabase_user_id": "user-uuid", "email": "test@example.com", "role": "editor"}
            ],
        )

        self.assertEqual(request.nodl_workspace_id, "workspace-uuid")
        self.assertEqual(request.name, "Test Workspace")
        self.assertEqual(request.description, "A test workspace")
        self.assertEqual(len(request.members), 1)

    def test_request_with_empty_members(self) -> None:
        """Test WorkspaceSyncRequest accepts empty members list."""
        request = WorkspaceSyncRequest(
            nodl_workspace_id="workspace-uuid",
            name="Test Workspace",
            description=None,
            members=[],
        )

        self.assertEqual(len(request.members), 0)
        self.assertIsNone(request.description)


class TestWorkspaceSyncResult(TestCase):
    """Test cases for WorkspaceSyncResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful sync result."""
        result = WorkspaceSyncResult(
            success=True,
            zulip_realm_id=123,
            error=None,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.zulip_realm_id, 123)
        self.assertIsNone(result.error)

    def test_failure_result(self) -> None:
        """Test failed sync result."""
        result = WorkspaceSyncResult(
            success=False,
            zulip_realm_id=None,
            error="Test error message",
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.zulip_realm_id)
        self.assertEqual(result.error, "Test error message")
