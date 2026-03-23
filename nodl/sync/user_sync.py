"""User synchronization service for nodl-to-Zulip user sync."""

import logging
import uuid
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from nodl.extensions.models import NodlUserExtension, SyncStatus
from zerver.actions.create_user import do_create_user
from zerver.actions.user_settings import do_change_full_name
from zerver.actions.users import do_change_user_role
from zerver.models import Realm, UserProfile

logger = logging.getLogger(__name__)


@dataclass
class UserSyncRequest:
    """Request payload for user synchronization."""

    supabase_user_id: str
    email: str
    full_name: str
    avatar_url: str | None
    workspace_id: str
    role: str  # 'owner', 'admin', 'editor', 'viewer'


@dataclass
class UserSyncResult:
    """Result of a user sync operation."""

    success: bool
    zulip_user_id: int | None
    error: str | None


class UserSyncService:
    """Service for synchronizing users between nodl (Supabase) and Zulip.

    Handles user creation, updates, and role mapping with retry logic.
    """

    MAX_RETRY_ATTEMPTS = 3

    # Role mapping: nodl role -> Zulip role constant
    ROLE_MAPPING = {
        "owner": UserProfile.ROLE_REALM_OWNER,
        "admin": UserProfile.ROLE_REALM_ADMINISTRATOR,
        "editor": UserProfile.ROLE_MEMBER,
        "viewer": UserProfile.ROLE_GUEST,
    }

    def sync_user(self, request: UserSyncRequest) -> UserSyncResult:
        """Synchronize a user from nodl to Zulip.

        Creates a new Zulip user or updates an existing one based on the
        Supabase user data.

        Args:
            request: User sync request with Supabase user data.

        Returns:
            UserSyncResult with success status and Zulip user ID if successful.
        """
        supabase_uuid = uuid.UUID(request.supabase_user_id)

        # Get or create extension record
        extension, created = NodlUserExtension.objects.get_or_create(
            supabase_user_id=supabase_uuid,
            defaults={"sync_status": SyncStatus.PENDING},
        )

        # Check retry limit for failed syncs - but only if we don't have
        # a linked user AND can't find an existing one to link
        # This prevents blocking updates when the extension was created
        # but never successfully linked (e.g., due to previous duplicate key errors)
        if extension.sync_status == SyncStatus.FAILED:  # noqa: SIM102
            if extension.sync_attempts >= self.MAX_RETRY_ATTEMPTS:
                # Before giving up, check if user exists and can be linked
                realm = self._get_realm_for_workspace(request.workspace_id)
                if realm:
                    existing_user = UserProfile.objects.filter(
                        realm=realm,
                        delivery_email__iexact=request.email,
                        is_active=True,
                    ).first()
                    if existing_user:
                        # User exists! Reset attempts and continue with sync
                        logger.info(
                            "Resetting sync attempts for user %s - found existing Zulip user %d",
                            request.supabase_user_id,
                            existing_user.id,
                        )
                        extension.sync_attempts = 0
                    else:
                        logger.warning(
                            "Max retry attempts exceeded for user %s",
                            request.supabase_user_id,
                        )
                        return UserSyncResult(
                            success=False,
                            zulip_user_id=None,
                            error=f"Max retry attempts ({self.MAX_RETRY_ATTEMPTS}) exceeded",
                        )

        # Mark as syncing
        extension.sync_status = SyncStatus.SYNCING
        extension.sync_attempts += 1
        extension.save(update_fields=["sync_status", "sync_attempts"])

        try:
            with transaction.atomic():
                realm = self._get_realm_for_workspace(request.workspace_id)
                if not realm:
                    raise ValueError(f"Realm not found for workspace {request.workspace_id}")

                if extension.zulip_user and extension.zulip_user.realm_id == realm.id:
                    user = self._update_user(extension.zulip_user, request, realm)
                else:
                    # Check if user already exists in this realm (created via workspace sync)
                    # This prevents duplicate key errors when extension wasn't linked
                    existing_user = UserProfile.objects.filter(
                        realm=realm,
                        delivery_email__iexact=request.email,
                        is_active=True,
                    ).first()

                    if existing_user:
                        # Check if this user is already linked to another extension
                        # (OneToOne constraint on zulip_user)
                        existing_extension = NodlUserExtension.objects.filter(
                            zulip_user=existing_user
                        ).first()

                        if existing_extension and existing_extension.id != extension.id:
                            # User already linked to different extension
                            # Delete the orphan extension (current one) and use existing
                            logger.info(
                                "Zulip user %d already linked to extension %d "
                                "(supabase_user_id=%s), deleting orphan "
                                "extension %d (supabase_user_id=%s)",
                                existing_user.id,
                                existing_extension.id,
                                existing_extension.supabase_user_id,
                                extension.id,
                                supabase_uuid,
                            )
                            # Delete orphan extension (releases supabase_user_id constraint)
                            extension.delete()
                            # Use the existing extension going forward
                            extension = existing_extension
                            extension.sync_status = SyncStatus.SYNCING
                            extension.save(update_fields=["sync_status"])
                            user = self._update_user(existing_user, request, realm)
                        else:
                            # Link existing user to extension and update
                            logger.info(
                                "Found existing Zulip user %d for email %s, linking to extension",
                                existing_user.id,
                                request.email,
                            )
                            extension.zulip_user = existing_user
                            user = self._update_user(existing_user, request, realm)
                    else:
                        user = self._create_user(request, realm)
                        extension.zulip_user = user

                extension.sync_status = SyncStatus.SYNCED
                extension.sync_error = None
                extension.last_synced_at = timezone.now()
                extension.save()

                logger.info(
                    "Successfully synced user %s to Zulip user %d",
                    request.supabase_user_id,
                    user.id,
                )

                return UserSyncResult(
                    success=True,
                    zulip_user_id=user.id,
                    error=None,
                )

        except Exception as e:
            logger.exception(
                "Failed to sync user %s: %s",
                request.supabase_user_id,
                str(e),
            )
            extension.sync_status = SyncStatus.FAILED
            extension.sync_error = str(e)
            extension.save(update_fields=["sync_status", "sync_error"])

            return UserSyncResult(
                success=False,
                zulip_user_id=None,
                error=str(e),
            )

    def _map_role(self, nodl_role: str) -> int:
        """Map nodl role to Zulip role constant.

        Args:
            nodl_role: Role from nodl ('owner', 'admin', 'editor', 'viewer').

        Returns:
            Zulip role constant (ROLE_REALM_OWNER, etc.).
        """
        return self.ROLE_MAPPING.get(nodl_role, UserProfile.ROLE_MEMBER)

    def _create_user(self, request: UserSyncRequest, realm: Realm) -> UserProfile:
        """Create a new Zulip user.

        Args:
            request: User sync request with user data.
            realm: Zulip realm to create user in.

        Returns:
            Created UserProfile.
        """
        role = self._map_role(request.role)

        user = do_create_user(
            email=request.email,
            password=None,  # No password - auth via Supabase
            realm=realm,
            full_name=request.full_name,
            role=role,
            acting_user=None,
        )

        logger.info(
            "Created Zulip user %d for Supabase user %s",
            user.id,
            request.supabase_user_id,
        )

        return user

    def _update_user(
        self, user: UserProfile, request: UserSyncRequest, realm: Realm
    ) -> UserProfile:
        """Update an existing Zulip user.

        Args:
            user: Existing Zulip UserProfile.
            request: User sync request with updated data.
            realm: Zulip realm.

        Returns:
            Updated UserProfile.
        """
        # Update full name if changed
        if user.full_name != request.full_name:
            do_change_full_name(user, request.full_name, acting_user=None)

        # Update role if changed
        new_role = self._map_role(request.role)
        if user.role != new_role:
            do_change_user_role(user, new_role, acting_user=None)

        logger.info(
            "Updated Zulip user %d for Supabase user %s",
            user.id,
            request.supabase_user_id,
        )

        return user

    def _get_realm_for_workspace(self, workspace_id: str) -> Realm | None:
        """Get the Zulip realm for a nodl workspace.

        Uses the workspace_id as the realm's string_id (subdomain).

        Args:
            workspace_id: nodl workspace UUID.

        Returns:
            Realm if found, None otherwise.
        """
        try:
            return Realm.objects.get(string_id=workspace_id)
        except Realm.DoesNotExist:
            return None
