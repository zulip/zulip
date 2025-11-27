"""nodl extension models for user and workspace synchronization."""

from django.db import models

from zerver.models import Realm, UserProfile


class SyncStatus(models.TextChoices):
    """Sync status state machine values."""

    PENDING = "pending", "Pending"
    SYNCING = "syncing", "Syncing"
    SYNCED = "synced", "Synced"
    FAILED = "failed", "Failed"


class NodlUserExtension(models.Model):
    """Extension table linking Zulip users to Supabase users.

    Tracks synchronization state between nodl (Supabase) and chat (Zulip)
    user accounts.
    """

    # Reference to Zulip user (one-to-one, nullable for pending syncs)
    zulip_user = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="nodl_extension",
        null=True,
        blank=True,
    )

    # Reference to Supabase user (source of truth)
    supabase_user_id = models.UUIDField(unique=True)

    # Sync state machine
    sync_status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
    )
    sync_error = models.TextField(blank=True, null=True)
    sync_attempts = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)

    # Optimistic locking
    version = models.IntegerField(default=1)

    class Meta:
        db_table = "nodl_user_extension"
        indexes = [
            models.Index(
                fields=["supabase_user_id"],
                name="idx_nodl_user_ext_supabase_id",
            ),
            models.Index(
                fields=["sync_status"],
                name="idx_nodl_user_ext_sync_status",
            ),
        ]

    def __str__(self) -> str:
        return f"NodlUserExtension(supabase={self.supabase_user_id}, status={self.sync_status})"

    @property
    def linked_zulip_user_id(self) -> int | None:
        """Get the Zulip user ID if linked."""
        return self.zulip_user.id if self.zulip_user else None


class NodlRealmExtension(models.Model):
    """Extension table linking Zulip realms to nodl workspaces.

    Tracks synchronization state between nodl workspaces and chat realms,
    plus optional Telegram bot configuration.
    """

    # Reference to Zulip realm (one-to-one)
    zulip_realm = models.OneToOneField(
        Realm,
        on_delete=models.CASCADE,
        related_name="nodl_extension",
    )

    # Reference to nodl workspace (source of truth)
    nodl_workspace_id = models.UUIDField(unique=True)

    # Telegram configuration
    telegram_enabled = models.BooleanField(default=False)
    telegram_bot_token_encrypted = models.TextField(blank=True, null=True)

    # Sync state machine
    sync_status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
    )
    sync_error = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    last_synced_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "nodl_realm_extension"
        indexes = [
            models.Index(
                fields=["nodl_workspace_id"],
                name="idx_nodl_realm_ext_workspace",
            ),
            models.Index(
                fields=["sync_status"],
                name="idx_nodl_realm_ext_status",
            ),
        ]

    def __str__(self) -> str:
        return f"NodlRealmExtension(workspace={self.nodl_workspace_id}, status={self.sync_status})"

    @property
    def linked_zulip_realm_id(self) -> int | None:
        """Get the Zulip realm ID if linked."""
        return self.zulip_realm.id if self.zulip_realm else None
