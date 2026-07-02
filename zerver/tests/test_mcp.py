from typing import Any

import orjson
from django.conf import settings
from django.db import connection
from django.test import override_settings
from typing_extensions import override

from zerver.actions.mcp_tokens import do_create_mcp_api_token, do_revoke_mcp_api_token
from zerver.actions.users import do_deactivate_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, Reaction, UserMessage


class MCPServerTestCase(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")
        _row, self.raw_token = do_create_mcp_api_token(
            self.user, "test client", acting_user=self.user
        )

    def mcp_request(self, body: object, token: str | None = None) -> Any:
        return self.client_post(
            "/api/v1/mcp",
            orjson.dumps(body).decode(),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token if token is not None else self.raw_token}",
        )

    def mcp_json(self, body: object, token: str | None = None) -> dict[str, Any]:
        result = self.mcp_request(body, token)
        self.assertEqual(result.status_code, 200)
        return orjson.loads(result.content)

    def tools_call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        response = self.mcp_json(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            }
        )
        return response["result"]

    def update_search_index(self) -> None:
        # Search is indexed asynchronously in production; in tests we index
        # message content by brute force, for whichever backend is in use.
        with connection.cursor() as cursor:
            if settings.USING_PGROONGA:
                cursor.execute("UPDATE zerver_message SET search_pgroonga = rendered_content")
            else:
                cursor.execute(
                    "UPDATE zerver_message SET search_tsvector = "
                    "to_tsvector('zulip.english_us_search', rendered_content)"
                )

    # === Protocol ===

    def test_initialize_reports_our_version(self) -> None:
        result = self.mcp_json(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25"},
            }
        )["result"]
        self.assertEqual(result["serverInfo"]["name"], "Zulip")
        self.assertEqual(result["protocolVersion"], "2025-11-25")
        self.assertIn("tools", result["capabilities"])

    def test_initialize_with_unsupported_version_returns_our_version(self) -> None:
        result = self.mcp_json(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "1999-01-01"},
            }
        )["result"]
        self.assertEqual(result["protocolVersion"], "2025-11-25")

    def test_notifications_get_an_empty_202(self) -> None:
        # Any id-less message is a JSON-RPC notification and gets no response.
        for method in ["notifications/initialized", "notifications/cancelled"]:
            result = self.mcp_request({"jsonrpc": "2.0", "method": method})
            self.assertEqual(result.status_code, 202)
            self.assertEqual(result.content, b"")

    def test_ping(self) -> None:
        response = self.mcp_json({"jsonrpc": "2.0", "id": 7, "method": "ping"})
        self.assertEqual(response["id"], 7)
        self.assertEqual(response["result"], {})

    def test_tools_list(self) -> None:
        tools = self.mcp_json({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"][
            "tools"
        ]
        self.assertEqual(
            {tool["name"] for tool in tools},
            {
                "search_messages",
                "get_messages",
                "list_channels",
                "list_topics",
                "get_users",
                "send_message",
                "add_reaction",
                "mark_read",
            },
        )
        for tool in tools:
            self.assertIn("description", tool)
            self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_unknown_method_is_a_protocol_error(self) -> None:
        response = self.mcp_json({"jsonrpc": "2.0", "id": 1, "method": "bogus/method"})
        self.assertEqual(response["error"]["code"], -32601)

    def test_unknown_tool_is_a_protocol_error(self) -> None:
        response = self.mcp_json(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "no_such_tool", "arguments": {}},
            }
        )
        self.assertEqual(response["error"]["code"], -32602)

    def test_invalid_arguments_are_tool_errors(self) -> None:
        # Omitting get_messages's required channel is a recoverable tool error.
        self.assertTrue(self.tools_call("get_messages", {})["isError"])

    def test_invalid_jsonrpc_request(self) -> None:
        response = self.mcp_json({"jsonrpc": "2.0", "id": 1})
        self.assertEqual(response["error"]["code"], -32600)

    def test_non_dict_params_does_not_crash(self) -> None:
        response = self.mcp_json(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": [1, 2, 3]}
        )
        self.assertEqual(response["error"]["code"], -32602)

    def test_malformed_json_body(self) -> None:
        result = self.client_post(
            "/api/v1/mcp",
            "not valid json{",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.raw_token}",
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(orjson.loads(result.content)["error"]["code"], -32700)

    def test_non_object_payload(self) -> None:
        # JSON-RPC batching (a top-level array) is not supported.
        self.assertEqual(self.mcp_json([1, 2, 3])["error"]["code"], -32600)

    # === Authentication ===

    def test_missing_authorization_header(self) -> None:
        result = self.client_post(
            "/api/v1/mcp",
            orjson.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).decode(),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 401)

    def test_malformed_token(self) -> None:
        result = self.mcp_request({"jsonrpc": "2.0", "id": 1, "method": "ping"}, token="garbage")
        self.assertEqual(result.status_code, 401)

    def test_unknown_token(self) -> None:
        result = self.mcp_request({"jsonrpc": "2.0", "id": 1, "method": "ping"}, token="zmcp_nope")
        self.assertEqual(result.status_code, 401)

    def test_revoked_token_is_rejected(self) -> None:
        token_row, raw = do_create_mcp_api_token(self.user, "temp", acting_user=self.user)
        do_revoke_mcp_api_token(self.user, token_row)
        result = self.mcp_request({"jsonrpc": "2.0", "id": 1, "method": "ping"}, token=raw)
        self.assertEqual(result.status_code, 401)

    def test_deactivated_user_is_rejected(self) -> None:
        do_deactivate_user(self.user, acting_user=None)
        result = self.mcp_request({"jsonrpc": "2.0", "id": 1, "method": "ping"})
        self.assertEqual(result.status_code, 401)

    def test_cross_realm_token_is_rejected(self) -> None:
        mit_user = self.mit_user("sipbtest")
        _row, raw = do_create_mcp_api_token(mit_user, "mit", acting_user=mit_user)
        # A zephyr-realm token used against the (default) zulip subdomain is rejected.
        result = self.mcp_request({"jsonrpc": "2.0", "id": 1, "method": "ping"}, token=raw)
        self.assertEqual(result.status_code, 401)

    def test_get_method_not_allowed(self) -> None:
        self.assertEqual(self.client_get("/api/v1/mcp").status_code, 405)

    def test_last_used_is_recorded(self) -> None:
        token_row, raw = do_create_mcp_api_token(self.user, "fresh", acting_user=self.user)
        self.assertIsNone(token_row.last_used)
        self.mcp_json({"jsonrpc": "2.0", "id": 1, "method": "ping"}, token=raw)
        token_row.refresh_from_db()
        self.assertIsNotNone(token_row.last_used)

    # === Read tools ===

    def test_get_messages(self) -> None:
        self.subscribe(self.user, "Denmark")
        self.send_stream_message(self.user, "Denmark", "hello world", topic_name="greet")
        result = self.tools_call("get_messages", {"channel": "Denmark", "topic": "greet"})
        messages = result["structuredContent"]["messages"]
        self.assertTrue(any(message["content"] == "hello world" for message in messages))

    @override_settings(USING_PGROONGA=False)
    def test_search_messages_tsearch(self) -> None:
        self.subscribe(self.user, "Denmark")
        self.send_stream_message(self.user, "Denmark", "needle in a haystack", topic_name="search")
        self.update_search_index()
        # A channel-scoped search exercises the channel + search narrow.
        result = self.tools_call("search_messages", {"query": "needle", "channel": "Denmark"})
        messages = result["structuredContent"]["messages"]
        self.assertTrue(any("needle" in message["content"] for message in messages))

    @override_settings(USING_PGROONGA=True)
    def test_search_messages_pgroonga_finds_direct_message(self) -> None:
        cordelia = self.example_user("cordelia")
        self.send_personal_message(self.user, cordelia, "secret needle direct message")
        self.update_search_index()
        result = self.tools_call("search_messages", {"query": "needle"})
        matches = [
            message
            for message in result["structuredContent"]["messages"]
            if "needle" in message["content"]
        ]
        self.assertTrue(matches)
        # A direct message renders with recipients rather than a channel/topic.
        self.assertIn("direct_message_recipients", matches[0])

    def test_list_channels(self) -> None:
        self.subscribe(self.user, "Denmark")
        result = self.tools_call("list_channels", {})
        names = {channel["name"] for channel in result["structuredContent"]["channels"]}
        self.assertIn("Denmark", names)

    def test_list_topics(self) -> None:
        self.subscribe(self.user, "Denmark")
        self.send_stream_message(self.user, "Denmark", "x", topic_name="alpha topic")
        result = self.tools_call("list_topics", {"channel": "Denmark"})
        names = {topic["name"] for topic in result["structuredContent"]["topics"]}
        self.assertIn("alpha topic", names)

    def test_get_users(self) -> None:
        result = self.tools_call("get_users", {"query": "hamlet"})
        users = result["structuredContent"]["users"]
        self.assertTrue(any("hamlet" in user["full_name"].lower() for user in users))

    def test_get_users_respects_limit(self) -> None:
        result = self.tools_call("get_users", {"limit": 1})
        self.assert_length(result["structuredContent"]["users"], 1)

    def test_cannot_read_inaccessible_private_channel(self) -> None:
        othello = self.example_user("othello")
        self.make_stream("secret", invite_only=True)
        self.subscribe(othello, "secret")
        self.send_stream_message(othello, "secret", "classified", topic_name="t")
        # Hamlet isn't subscribed, so the private message must not leak.
        result = self.tools_call("get_messages", {"channel": "secret"})
        self.assertFalse(result["isError"])
        self.assertEqual(result["structuredContent"]["messages"], [])

    # === Write tools ===

    def test_send_channel_message(self) -> None:
        self.subscribe(self.user, "Denmark")
        result = self.tools_call(
            "send_message", {"channel": "Denmark", "topic": "mcp", "content": "Hello from MCP"}
        )
        message = Message.objects.get(id=result["structuredContent"]["message_id"])
        self.assertEqual(message.content, "Hello from MCP")
        self.assertEqual(message.topic_name(), "mcp")

    def test_send_direct_message_by_user_id(self) -> None:
        cordelia = self.example_user("cordelia")
        result = self.tools_call(
            "send_message", {"direct_message_recipients": [cordelia.id], "content": "hi via mcp"}
        )
        message = Message.objects.get(id=result["structuredContent"]["message_id"])
        self.assertEqual(message.content, "hi via mcp")

    def test_send_channel_message_requires_topic(self) -> None:
        self.subscribe(self.user, "Denmark")
        result = self.tools_call("send_message", {"channel": "Denmark", "content": "no topic"})
        self.assertTrue(result["isError"])

    def test_send_message_requires_a_target(self) -> None:
        self.assertTrue(self.tools_call("send_message", {"content": "orphan"})["isError"])

    def test_send_message_rejects_channel_and_dm_together(self) -> None:
        cordelia = self.example_user("cordelia")
        result = self.tools_call(
            "send_message",
            {
                "channel": "Denmark",
                "topic": "x",
                "direct_message_recipients": [cordelia.id],
                "content": "?",
            },
        )
        self.assertTrue(result["isError"])

    def test_add_reaction(self) -> None:
        self.subscribe(self.user, "Denmark")
        message_id = self.send_stream_message(self.user, "Denmark", "react to me", topic_name="r")
        result = self.tools_call(
            "add_reaction", {"message_id": message_id, "emoji_name": "thumbs_up"}
        )
        self.assertFalse(result["isError"])
        self.assertTrue(
            Reaction.objects.filter(message_id=message_id, user_profile=self.user).exists()
        )

    def test_add_reaction_on_inaccessible_message(self) -> None:
        othello = self.example_user("othello")
        self.make_stream("secret", invite_only=True)
        self.subscribe(othello, "secret")
        message_id = self.send_stream_message(othello, "secret", "x", topic_name="t")
        result = self.tools_call(
            "add_reaction", {"message_id": message_id, "emoji_name": "thumbs_up"}
        )
        self.assertTrue(result["isError"])

    def test_mark_read_by_message_ids(self) -> None:
        othello = self.example_user("othello")
        self.subscribe(self.user, "Denmark")
        self.subscribe(othello, "Denmark")
        message_id = self.send_stream_message(othello, "Denmark", "unread", topic_name="u")
        self.assertFalse(self.tools_call("mark_read", {"message_ids": [message_id]})["isError"])
        user_message = UserMessage.objects.get(user_profile=self.user, message_id=message_id)
        self.assertIn("read", user_message.flags_list())

    def test_mark_read_by_channel(self) -> None:
        othello = self.example_user("othello")
        self.subscribe(self.user, "Denmark")
        self.subscribe(othello, "Denmark")
        message_id = self.send_stream_message(othello, "Denmark", "unread", topic_name="u")
        self.assertFalse(self.tools_call("mark_read", {"channel": "Denmark"})["isError"])
        user_message = UserMessage.objects.get(user_profile=self.user, message_id=message_id)
        self.assertIn("read", user_message.flags_list())

    def test_mark_read_requires_a_target(self) -> None:
        self.assertTrue(self.tools_call("mark_read", {})["isError"])

    def test_mark_read_rejects_ids_and_channel_together(self) -> None:
        result = self.tools_call("mark_read", {"message_ids": [1], "channel": "Denmark"})
        self.assertTrue(result["isError"])

    # === Access control ===

    def test_cannot_send_to_inaccessible_private_channel(self) -> None:
        self.make_stream("secret-plans", invite_only=True)
        result = self.tools_call(
            "send_message", {"channel": "secret-plans", "topic": "x", "content": "should fail"}
        )
        self.assertTrue(result["isError"])
        self.assertFalse(
            Message.objects.filter(realm=self.user.realm, content="should fail").exists()
        )

    def test_tools_act_as_the_authenticating_user(self) -> None:
        self.subscribe(self.user, "Denmark")
        result = self.tools_call(
            "send_message", {"channel": "Denmark", "topic": "who", "content": "whoami"}
        )
        message = Message.objects.get(id=result["structuredContent"]["message_id"])
        self.assertEqual(message.sender_id, self.user.id)
