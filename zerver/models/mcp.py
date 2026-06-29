import hashlib
import secrets

from django.db import models
from django.db.models import CASCADE
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.models.users import UserProfile

# MCP tokens are dedicated credentials for the native MCP server endpoint
# (POST /api/v1/mcp).  Unlike UserProfile.api_key -- a single all-powerful
# credential stored in plaintext -- these are per-client, individually
# revocable, and persisted only as a SHA-256 digest, so a database leak does
# not expose working credentials.
MCP_API_TOKEN_PREFIX = "zmcp_"


def generate_mcp_api_token() -> str:
    # 32 bytes of entropy, URL-safe base64 encoded, behind a recognizable
    # prefix so leaked tokens are easy to identify in logs and secret scanners.
    return MCP_API_TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_mcp_api_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def has_mcp_api_token_format(token: str) -> bool:
    # A cheap structural check to avoid hashing and a database lookup for
    # tokens that obviously aren't ours.
    return token.startswith(MCP_API_TOKEN_PREFIX) and len(token) <= 200


class UserMCPApiToken(models.Model):
    """A revocable, per-user credential for authenticating to the native MCP
    server endpoint.  The agent acts as the owning user, with that user's
    permissions; revoking a token does not disturb the user's api_key or
    other integrations.
    """

    MAX_LABEL_LENGTH = 100
    MAX_TOKENS_PER_USER = 25

    user_profile = models.ForeignKey(UserProfile, on_delete=CASCADE)
    # SHA-256 hex digest of the token; the raw token is shown to the user
    # exactly once, at creation, and never stored.
    token_digest = models.CharField(max_length=64, unique=True)
    # A user-supplied name identifying where the token is used,
    # e.g. "Claude Desktop (laptop)".
    label = models.CharField(max_length=MAX_LABEL_LENGTH)
    date_created = models.DateTimeField(default=timezone_now)
    last_used = models.DateTimeField(null=True, default=None)

    @override
    def __str__(self) -> str:
        return f"{self.user_profile.delivery_email} / {self.label}"
