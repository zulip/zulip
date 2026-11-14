from typing import Any

import orjson
from pydantic import ValidationError

from version import ZULIP_VERSION
from zerver.lib.exceptions import JsonableError
from zerver.lib.mcp.tools import MCP_TOOLS_BY_NAME, get_mcp_tool_definitions
from zerver.models import UserProfile

# The one MCP specification revision this server implements; clients
# adapt to whichever revision the server reports at initialization.
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
    # The text block duplicates structuredContent, for clients that only
    # read content.
    return {
        "content": [{"type": "text", "text": orjson.dumps(payload).decode()}],
        "structuredContent": payload,
        "isError": False,
    }


def _tool_error_result(message: str) -> dict[str, Any]:
    # In-band tool errors, unlike protocol errors, reach the model, which
    # can then explain the failure or retry.
    return {"content": [{"type": "text", "text": message}], "isError": True}


def handle_mcp_message(user_profile: UserProfile, message: dict[str, Any]) -> dict[str, Any] | None:
    """Dispatches a single JSON-RPC message for the authenticated user,
    returning the JSON-RPC response, or None for notifications.
    """
    if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return make_json_rpc_error(
            message.get("id"), JSON_RPC_INVALID_REQUEST, "Invalid JSON-RPC request."
        )

    # A message without an "id" is a JSON-RPC notification, such as
    # notifications/initialized, and gets no response.
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

    if not isinstance(name, str):
        return make_json_rpc_error(
            request_id, JSON_RPC_INVALID_PARAMS, "Tool name is missing or not a string."
        )
    tool = MCP_TOOLS_BY_NAME.get(name)
    if tool is None:
        return make_json_rpc_error(request_id, JSON_RPC_INVALID_PARAMS, f"Unknown tool: {name}")

    try:
        payload = tool.handler(user_profile, arguments)
    except ValidationError as e:
        return make_json_rpc_result(request_id, _tool_error_result(f"Invalid arguments: {e}"))
    except JsonableError as e:
        # Zulip's user-facing error messages, access control failures
        # included, are safe to hand to the model.
        return make_json_rpc_result(request_id, _tool_error_result(e.msg))

    return make_json_rpc_result(request_id, _tool_success_result(payload))
