"""Workspace synchronization service for nodl-to-Zulip realm sync."""

import logging
import uuid
from dataclasses import dataclass

from django.utils import timezone

from nodl.extensions.models import NodlRealmExtension, SyncStatus
from zerver.actions.create_realm import do_create_realm
from zerver.actions.realm_settings import do_deactivate_realm
from zerver.lib.streams import ensure_stream
from zerver.models import Realm

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceSyncRequest:
    """Request payload for workspace synchronization."""

    nodl_workspace_id: str
    name: str
    description: str | None
    members: list[dict]  # [{supabase_user_id, email, role}, ...]


@dataclass
class WorkspaceSyncResult:
    """Result of a workspace sync operation."""

    success: bool
    zulip_realm_id: int | None
    error: str | None


class WorkspaceSyncService:
    """Service for synchronizing workspaces between nodl and Zulip.

    Handles realm creation, updates, member sync, and deactivation.
    """

    def sync_workspace(self, request: WorkspaceSyncRequest) -> WorkspaceSyncResult:
        """Synchronize a workspace from nodl to Zulip.

        Creates a new Zulip realm or updates an existing one based on the
        nodl workspace data.

        Args:
            request: Workspace sync request with nodl workspace data.

        Returns:
            WorkspaceSyncResult with success status and Zulip realm ID if successful.
        """
        workspace_uuid = uuid.UUID(request.nodl_workspace_id)

        try:
            # Check if extension exists (read-only, no transaction needed)
            try:
                extension = NodlRealmExtension.objects.select_related("zulip_realm").get(
                    nodl_workspace_id=workspace_uuid
                )
                # Extension exists - update the realm
                extension.sync_status = SyncStatus.SYNCING
                extension.save(update_fields=["sync_status"])
                realm = self._update_realm(extension.zulip_realm, request)
                is_new_realm = False
            except NodlRealmExtension.DoesNotExist:
                # New workspace - create realm FIRST (has its own durable transaction)
                realm = self._create_realm(request)
                # Then create extension linking to the new realm
                extension = NodlRealmExtension.objects.create(
                    nodl_workspace_id=workspace_uuid,
                    zulip_realm=realm,
                    sync_status=SyncStatus.SYNCING,
                )
                is_new_realm = True

            # Create default stream for new realms
            if is_new_realm:
                self._create_default_stream(realm)

            # Sync members if provided
            if request.members:
                self.sync_workspace_members(realm, request.members)

            # Mark as synced
            extension.sync_status = SyncStatus.SYNCED
            extension.sync_error = None
            extension.last_synced_at = timezone.now()
            extension.save()

            logger.info(
                "Successfully synced workspace %s to Zulip realm %d",
                request.nodl_workspace_id,
                realm.id,
            )

            return WorkspaceSyncResult(
                success=True,
                zulip_realm_id=realm.id,
                error=None,
            )

        except Exception as e:
            logger.exception(
                "Failed to sync workspace %s: %s",
                request.nodl_workspace_id,
                str(e),
            )
            # Try to update extension status if it exists
            try:
                extension = NodlRealmExtension.objects.get(nodl_workspace_id=workspace_uuid)
                extension.sync_status = SyncStatus.FAILED
                extension.sync_error = str(e)
                extension.save(update_fields=["sync_status", "sync_error"])
            except NodlRealmExtension.DoesNotExist:
                pass  # Extension was never created, nothing to update

            return WorkspaceSyncResult(
                success=False,
                zulip_realm_id=None,
                error=str(e),
            )

    def _create_realm(self, request: WorkspaceSyncRequest) -> Realm:
        """Create a new Zulip realm for a workspace.

        Args:
            request: Workspace sync request with workspace data.

        Returns:
            Created Realm.
        """
        # Use first 20 chars of workspace ID as subdomain (Zulip constraint)
        string_id = request.nodl_workspace_id[:20].lower()

        realm = do_create_realm(
            string_id=string_id,
            name=request.name,
            description=request.description,
            org_type=Realm.ORG_TYPES["business"]["id"],
            create_zulip_discussion_channel=False,
        )

        logger.info(
            "Created Zulip realm %d for workspace %s",
            realm.id,
            request.nodl_workspace_id,
        )

        return realm

    def _update_realm(self, realm: Realm, request: WorkspaceSyncRequest) -> Realm:
        """Update an existing Zulip realm.

        Args:
            realm: Existing Zulip Realm.
            request: Workspace sync request with updated data.

        Returns:
            Updated Realm.
        """
        updated = False

        if realm.name != request.name:
            realm.name = request.name
            updated = True

        if request.description and realm.description != request.description:
            realm.description = request.description
            updated = True

        if updated:
            realm.save(update_fields=["name", "description"])
            logger.info(
                "Updated Zulip realm %d for workspace %s",
                realm.id,
                request.nodl_workspace_id,
            )

        return realm

    def _create_default_stream(self, realm: Realm) -> None:
        """Create #general stream for new realm.

        Args:
            realm: Zulip realm to create stream in.
        """
        ensure_stream(
            realm=realm,
            stream_name="general",
            invite_only=False,
            stream_description="General discussion",
            acting_user=None,
        )

        logger.info(
            "Created default #general stream for realm %d",
            realm.id,
        )

    def sync_workspace_members(self, realm: Realm, members: list[dict]) -> None:
        """Sync workspace members to realm.

        This method handles adding new members, removing old members,
        and updating roles for existing members.

        Args:
            realm: Zulip realm to sync members to.
            members: List of member dicts with supabase_user_id, email, role.
        """
        from nodl.sync.user_sync import UserSyncRequest, UserSyncService

        user_sync_service = UserSyncService()

        for member in members:
            sync_request = UserSyncRequest(
                supabase_user_id=member["supabase_user_id"],
                email=member["email"],
                full_name=member.get("full_name", member["email"]),
                avatar_url=member.get("avatar_url"),
                workspace_id=realm.string_id,
                role=member["role"],
            )

            result = user_sync_service.sync_user(sync_request)

            if not result.success:
                logger.warning(
                    "Failed to sync member %s to realm %d: %s",
                    member["supabase_user_id"],
                    realm.id,
                    result.error,
                )

    def deactivate_realm(self, nodl_workspace_id: str) -> WorkspaceSyncResult:
        """Deactivate (soft delete) a realm for a deleted workspace.

        Does not hard delete - preserves message history.

        Args:
            nodl_workspace_id: nodl workspace UUID.

        Returns:
            WorkspaceSyncResult with success status.
        """
        workspace_uuid = uuid.UUID(nodl_workspace_id)

        try:
            extension = NodlRealmExtension.objects.select_related("zulip_realm").get(
                nodl_workspace_id=workspace_uuid
            )
        except NodlRealmExtension.DoesNotExist:
            return WorkspaceSyncResult(
                success=False,
                zulip_realm_id=None,
                error=f"No realm found for workspace {nodl_workspace_id}",
            )

        if not extension.zulip_realm:
            return WorkspaceSyncResult(
                success=False,
                zulip_realm_id=None,
                error=f"Realm not linked for workspace {nodl_workspace_id}",
            )

        try:
            do_deactivate_realm(
                extension.zulip_realm,
                acting_user=None,
                deactivation_reason="workspace_deleted",
                email_owners=False,
            )

            logger.info(
                "Deactivated Zulip realm %d for deleted workspace %s",
                extension.zulip_realm.id,
                nodl_workspace_id,
            )

            return WorkspaceSyncResult(
                success=True,
                zulip_realm_id=extension.zulip_realm.id,
                error=None,
            )

        except Exception as e:
            logger.exception(
                "Failed to deactivate realm for workspace %s: %s",
                nodl_workspace_id,
                str(e),
            )
            return WorkspaceSyncResult(
                success=False,
                zulip_realm_id=None,
                error=str(e),
            )
