from datetime import timedelta

from django.http import HttpRequest
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _

from zerver.decorator import process_client, validate_account_and_subdomain
from zerver.lib.exceptions import JsonableError, UnauthorizedError
from zerver.lib.rate_limiter import rate_limit_request_by_ip, rate_limit_user
from zerver.models import UserProfile
from zerver.models.mcp import UserMCPApiToken, has_mcp_api_token_format, hash_mcp_api_token

MCP_CLIENT_NAME = "ZulipMCP"
# Throttle last_used DB writes: skip the update if it happened within this
# window, to avoid write amplification from agents calling the endpoint often.
MCP_TOKEN_LAST_USED_RESOLUTION = timedelta(minutes=5)


def authenticate_mcp_request(request: HttpRequest) -> UserProfile:
    """Authenticates an MCP request via its `Authorization: Bearer <token>`
    header, returning the owning user.  Mirrors the api_key path in
    zerver.decorator: it validates the realm/subdomain, records the client,
    and applies per-user rate limiting.  Raises an HTTP-level error (handled
    by the JSON error middleware) on any failure.
    """
    # Rate limit by IP up front, so unauthenticated callers can't cheaply
    # probe tokens; each attempt otherwise costs a hash and an indexed query.
    rate_limit_request_by_ip(request, domain="api_by_ip")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError(_("Missing or malformed MCP bearer token."))

    token = auth_header[len("Bearer ") :].strip()
    if not has_mcp_api_token_format(token):
        raise UnauthorizedError(_("Invalid MCP token."))

    try:
        token_row = UserMCPApiToken.objects.select_related(
            "user_profile", "user_profile__realm"
        ).get(token_digest=hash_mcp_api_token(token))
    except UserMCPApiToken.DoesNotExist:
        raise UnauthorizedError(_("Invalid MCP token."))

    user_profile = token_row.user_profile
    try:
        validate_account_and_subdomain(request, user_profile)
    except JsonableError as e:
        raise UnauthorizedError(e.msg)

    request.user = user_profile
    process_client(request, user_profile, client_name=MCP_CLIENT_NAME, query="mcp_endpoint")
    rate_limit_user(request, user_profile, domain="api_by_user")

    # Record last use for the token listing, throttled to limit write volume.
    now = timezone_now()
    if token_row.last_used is None or now - token_row.last_used > MCP_TOKEN_LAST_USED_RESOLUTION:
        token_row.last_used = now
        token_row.save(update_fields=["last_used"])

    return user_profile
