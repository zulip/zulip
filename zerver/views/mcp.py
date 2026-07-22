from typing import Any

import orjson
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt

from zerver.decorator import require_post, validate_api_key
from zerver.lib.exceptions import JsonableError, ResourceNotFoundError, UnauthorizedError
from zerver.lib.mcp.protocol import (
    JSON_RPC_INVALID_REQUEST,
    JSON_RPC_PARSE_ERROR,
    handle_mcp_message,
    make_json_rpc_error,
)
from zerver.lib.mcp.tools import MCP_CLIENT_NAME
from zerver.lib.rate_limiter import rate_limit_request_by_ip, rate_limit_user
from zerver.models import UserProfile


def authenticate_mcp_request(request: HttpRequest) -> UserProfile:
    # Rate limit by IP before looking at credentials, so that guessing
    # API keys is throttled even without a valid account.
    rate_limit_request_by_ip(request, domain="api_by_ip")

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise UnauthorizedError(
            _("MCP requests must include an API key as a bearer token."),
            www_authenticate="bearer",
        )
    user_profile = validate_api_key(
        request, None, auth_header.removeprefix("Bearer "), client_name=MCP_CLIENT_NAME
    )
    rate_limit_user(request, user_profile, domain="api_by_user")
    return user_profile


def json_rpc_response(response: dict[str, Any], status: int = 200) -> HttpResponse:
    return HttpResponse(orjson.dumps(response), status=status, content_type="application/json")


@csrf_exempt
@require_post
def mcp_endpoint(request: HttpRequest) -> HttpResponse:
    if not settings.MCP_SERVER_ENABLED:
        raise ResourceNotFoundError(_("MCP is disabled on this server."))

    user_profile = authenticate_mcp_request(request)
    if not user_profile.realm.enable_mcp_access:
        raise JsonableError(_("MCP access is not enabled for this organization."))

    try:
        message = orjson.loads(request.body)
    except orjson.JSONDecodeError:
        return json_rpc_response(
            make_json_rpc_error(None, JSON_RPC_PARSE_ERROR, "Request body is not valid JSON."),
            status=400,
        )
    # JSON-RPC batching was removed from the MCP specification in 2025;
    # a conforming client sends one message per POST.
    if not isinstance(message, dict):
        return json_rpc_response(
            make_json_rpc_error(
                None, JSON_RPC_INVALID_REQUEST, "Expected a single JSON-RPC message."
            ),
            status=400,
        )

    response = handle_mcp_message(user_profile, message)
    if response is None:
        # 202 acknowledges a notification, which has no reply.
        return HttpResponse(status=202)
    return json_rpc_response(response)
