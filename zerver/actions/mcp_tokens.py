from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.models import RealmAuditLog, UserProfile
from zerver.models.mcp import UserMCPApiToken, generate_mcp_api_token, hash_mcp_api_token
from zerver.models.realm_audit_logs import AuditLogEventType


@transaction.atomic(durable=True)
def do_create_mcp_api_token(
    user_profile: UserProfile, label: str, *, acting_user: UserProfile | None
) -> tuple[UserMCPApiToken, str]:
    """Creates a personal MCP token, returning the row and the raw token.

    The raw token is returned to the caller exactly once here; only its
    digest is persisted.  acting_user is the actor for the audit log (the user
    themselves for the API, None for the management command).
    """
    raw_token = generate_mcp_api_token()
    token = UserMCPApiToken.objects.create(
        user_profile=user_profile,
        token_digest=hash_mcp_api_token(raw_token),
        label=label,
    )
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=acting_user,
        modified_user=user_profile,
        event_type=AuditLogEventType.USER_MCP_API_TOKEN_CREATED,
        event_time=timezone_now(),
        extra_data={"mcp_token_id": token.id, "label": label},
    )
    return token, raw_token


@transaction.atomic(durable=True)
def do_revoke_mcp_api_token(user_profile: UserProfile, token: UserMCPApiToken) -> None:
    token_id = token.id
    label = token.label
    token.delete()
    RealmAuditLog.objects.create(
        realm=user_profile.realm,
        acting_user=user_profile,
        modified_user=user_profile,
        event_type=AuditLogEventType.USER_MCP_API_TOKEN_REVOKED,
        event_time=timezone_now(),
        extra_data={"mcp_token_id": token_id, "label": label},
    )
