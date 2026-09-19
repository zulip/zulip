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
from zerver.lib.mcp.tools import MCP_CLIENT_NAME, MCP_TOOLS_BY_NAME
from zerver.lib.rate_limiter import rate_limit_request_by_ip, rate_limit_user
from zerver.lib.request import RequestNotes
from zerver.models import UserProfile


def authenticate_mcp_request(request: HttpRequest) -> UserProfile:
    # Rate limit by IP before looking at credentials, so that guessing
    # API keys is throttled even without a valid account.
    rate_limit_request_by_ip(request, domain="api_by_ip")

    # The scheme is case-insensitive, as get_basic_credentials also has
    # it; this header gets typed by hand into agent configurations.
    scheme, _separator, api_key = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not api_key:
        raise UnauthorizedError(
            _("MCP requests must include an API key as a bearer token."),
            www_authenticate="bearer",
        )
    user_profile = validate_api_key(request, None, api_key, client_name=MCP_CLIENT_NAME)
    rate_limit_user(request, user_profile, domain="api_by_user")
    return user_profile


def json_rpc_response(response: dict[str, Any], status: int = 200) -> HttpResponse:
    return HttpResponse(orjson.dumps(response), status=status, content_type="application/json")


def log_mcp_tool_call(request: HttpRequest, message: dict[str, Any]) -> None:
    """Names the tool in the request log, so that which tools agents reach
    for is visible while the tool set is still taking shape. Only names the
    server knows are logged, keeping request data out of the log.
    """
    if message.get("method") != "tools/call":
        return
    params = message.get("params")
    name = params.get("name") if isinstance(params, dict) else None
    log_data = RequestNotes.get_notes(request).log_data
    assert log_data is not None
    known_tool = isinstance(name, str) and name in MCP_TOOLS_BY_NAME
    log_data["extra"] = f"[{name}]" if known_tool else "[unknown tool]"


@csrf_exempt
@require_post
def mcp_endpoint(request: HttpRequest) -> HttpResponse:
    if not settings.MCP_SERVER_ENABLED:
        raise ResourceNotFoundError(_("MCP is disabled on this server."))

    user_profile = authenticate_mcp_request(request)
    if not user_profile.realm.enable_mcp_read_access:
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

    log_mcp_tool_call(request, message)
    response = handle_mcp_message(user_profile, message)
    if response is None:
        # 202 acknowledges a notification, which has no reply.
        return HttpResponse(status=202)
    return json_rpc_response(response)
