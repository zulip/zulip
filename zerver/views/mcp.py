import orjson
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt

from zerver.lib.mcp.auth import authenticate_mcp_request
from zerver.lib.mcp.protocol import (
    JSON_RPC_INVALID_REQUEST,
    JSON_RPC_PARSE_ERROR,
    handle_mcp_message,
    make_json_rpc_error,
)


@csrf_exempt
def mcp_server_view(request: HttpRequest) -> HttpResponse:
    """The native MCP server endpoint (Streamable HTTP transport, stateless).

    Each POST carries one JSON-RPC 2.0 message, authenticated by a personal
    MCP token, and runs as the owning user.  We do not support the GET SSE
    stream, since v1 has no server-initiated messages.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    user_profile = authenticate_mcp_request(request)

    try:
        payload = orjson.loads(request.body)
    except orjson.JSONDecodeError:
        return _json_response(make_json_rpc_error(None, JSON_RPC_PARSE_ERROR, "Parse error."))

    if not isinstance(payload, dict):
        # JSON-RPC batching was removed in MCP 2025-06-18.
        return _json_response(
            make_json_rpc_error(
                None, JSON_RPC_INVALID_REQUEST, "Expected a single JSON-RPC request object."
            )
        )

    response = handle_mcp_message(user_profile, payload)
    if response is None:
        # Notifications get an empty HTTP 202, per the MCP spec.
        return HttpResponse(status=202)
    return _json_response(response)


def _json_response(data: dict[str, object]) -> HttpResponse:
    return HttpResponse(orjson.dumps(data), content_type="application/json")
