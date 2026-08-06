from typing import Any

import orjson
from pydantic import ValidationError

from version import ZULIP_VERSION
from zerver.lib.exceptions import JsonableError
from zerver.lib.mcp.tools import MCP_TOOLS_BY_NAME, get_mcp_tool_definitions
from zerver.models import UserProfile

# The single MCP specification revision this server implements; clients
# adapt to the revision the server reports during initialization.
MCP_PROTOCOL_VERSION = "2025-06-18"
MCP_SERVER_INFO = {"name": "Zulip", "title": "Zulip", "version": ZULIP_VERSION}

# JSON-RPC 2.0 error codes (https://www.jsonrpc.org/specification#error_object).
JSON_RPC_PARSE_ERROR = -32700
JSON_RPC_INVALID_REQUEST = -32600
JSON_RPC_METHOD_NOT_FOUND = -32601
JSON_RPC_INVALID_PARAMS = -32602


def make_json_rpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def make_json_rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool_success_result(payload: dict[str, Any]) -> dict[str, Any]:
    # MCP tool results carry the structured payload in structuredContent,
    # plus an equivalent text block for clients that only read content.
    return {
        "content": [{"type": "text", "text": orjson.dumps(payload).decode()}],
        "structuredContent": payload,
        "isError": False,
    }


def _tool_error_result(message: str) -> dict[str, Any]:
    # Tool execution failures are reported in-band with isError=true, so
    # the model can see the message and recover, unlike protocol errors.
    return {"content": [{"type": "text", "text": message}], "isError": True}


def handle_mcp_message(user_profile: UserProfile, message: dict[str, Any]) -> dict[str, Any] | None:
    """Dispatches a single JSON-RPC message for the authenticated user,
    returning the JSON-RPC response, or None for notifications.
    """
    if message.get("jsonrpc") != "2.0" or "method" not in message:
        return make_json_rpc_error(
            message.get("id"), JSON_RPC_INVALID_REQUEST, "Invalid JSON-RPC request."
        )

    # A JSON-RPC message without an "id" is a notification, which gets no
    # response (notifications/initialized, notifications/cancelled, etc.).
    if "id" not in message:
        return None

    method = message["method"]
    request_id = message["id"]
    params = message.get("params")
    if not isinstance(params, dict):
        params = {}

    if method == "initialize":
        return make_json_rpc_result(
            request_id,
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": MCP_SERVER_INFO,
            },
        )

    if method == "ping":
        return make_json_rpc_result(request_id, {})

    if method == "tools/list":
        return make_json_rpc_result(request_id, {"tools": get_mcp_tool_definitions()})

    if method == "tools/call":
        return _handle_tools_call(user_profile, request_id, params)

    return make_json_rpc_error(request_id, JSON_RPC_METHOD_NOT_FOUND, f"Unknown method: {method}")


def _handle_tools_call(
    user_profile: UserProfile, request_id: Any, params: dict[str, Any]
) -> dict[str, Any]:
    name = params.get("name")
    arguments = params.get("arguments") or {}

    tool = MCP_TOOLS_BY_NAME.get(name) if isinstance(name, str) else None
    if tool is None:
        return make_json_rpc_error(request_id, JSON_RPC_INVALID_PARAMS, f"Unknown tool: {name}")

    try:
        payload = tool.handler(user_profile, arguments)
    except ValidationError as e:
        return make_json_rpc_result(request_id, _tool_error_result(f"Invalid arguments: {e}"))
    except JsonableError as e:
        # Access control and other Zulip errors surface with their
        # user-facing message, never leaking internals.
        return make_json_rpc_result(request_id, _tool_error_result(e.msg))

    return make_json_rpc_result(request_id, _tool_success_result(payload))
