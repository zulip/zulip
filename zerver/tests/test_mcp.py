from typing import TYPE_CHECKING, Any

import orjson
from django.conf import settings
from django.db import connection
from django.test import override_settings

from zerver.actions.create_user import do_create_user
from zerver.actions.message_flags import do_update_message_flags
from zerver.actions.realm_linkifiers import do_add_linkifier
from zerver.actions.realm_settings import do_set_realm_property
from zerver.actions.user_settings import do_change_full_name
from zerver.actions.users import do_deactivate_user
from zerver.lib.mcp.protocol import MCP_PROTOCOL_VERSION
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.users import get_accessible_user_ids
from zerver.models import Client, Message, UserProfile
from zerver.models.realms import get_realm
from zerver.views.message_fetch import MAX_MESSAGES_PER_FETCH

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

READ_ONLY_TOOL_NAMES = [
    "get_messages",
    "get_users",
    "list_channels",
    "list_linkifiers",
    "list_topics",
]


class MCPEndpointTestCase(ZulipTestCase):
    def mcp_request(
        self,
        user_profile: UserProfile,
        payload: object,
        *,
        api_key: str | None = None,
        subdomain: str = "zulip",
    ) -> "TestHttpResponse":
        if api_key is None:
            api_key = user_profile.api_key
        return self.client_post(
            "/mcp",
            orjson.dumps(payload).decode(),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {api_key}",
            subdomain=subdomain,
        )

    def call_method(
        self, user_profile: UserProfile, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
        if params is not None:
            payload["params"] = params
        response = self.mcp_request(user_profile, payload)
        self.assertEqual(response.status_code, 200)
        result = orjson.loads(response.content)
        self.assertEqual(result["jsonrpc"], "2.0")
        self.assertEqual(result["id"], 1)
        return result

    def call_tool(
        self, user_profile: UserProfile, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        result = self.call_method(
            user_profile, "tools/call", {"name": name, "arguments": arguments}
        )
        return result["result"]

    def call_tool_expecting_success(
        self, user_profile: UserProfile, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        tool_result = self.call_tool(user_profile, name, arguments)
        self.assertFalse(tool_result["isError"])
        # The text content block carries the same payload as
        # structuredContent, for clients that only read content.
        self.assertEqual(
            orjson.loads(tool_result["content"][0]["text"]), tool_result["structuredContent"]
        )
        payload: dict[str, Any] = tool_result["structuredContent"]
        return payload

    def call_get_messages(
        self, user_profile: UserProfile, narrow: list[dict[str, Any]], **arguments: Any
    ) -> dict[str, Any]:
        return self.call_tool_expecting_success(
            user_profile, "get_messages", {"narrow": narrow, **arguments}
        )

    def call_tool_expecting_error(
        self, user_profile: UserProfile, name: str, arguments: dict[str, Any]
    ) -> str:
        tool_result = self.call_tool(user_profile, name, arguments)
        self.assertTrue(tool_result["isError"])
        error_text: str = tool_result["content"][0]["text"]
        return error_text


class MCPTransportTest(MCPEndpointTestCase):
    def test_get_method_not_allowed(self) -> None:
        with self.assertLogs(level="WARNING") as mock_warning:
            result = self.client_get("/mcp")
        self.assertEqual(result.status_code, 405)
        self.assertEqual(mock_warning.output, ["WARNING:root:Method Not Allowed (GET): /mcp"])

    def test_server_setting_disabled(self) -> None:
        hamlet = self.example_user("hamlet")
        with override_settings(MCP_SERVER_ENABLED=False):
            result = self.mcp_request(hamlet, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        self.assert_json_error(result, "MCP is disabled on this server.", status_code=404)

    def test_realm_setting_disabled(self) -> None:
        hamlet = self.example_user("hamlet")
        do_set_realm_property(hamlet.realm, "enable_mcp_access", False, acting_user=None)
        result = self.mcp_request(hamlet, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        self.assert_json_error(result, "MCP access is not enabled for this organization.")

    def test_missing_authorization_header(self) -> None:
        result = self.client_post(
            "/mcp",
            orjson.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).decode(),
            content_type="application/json",
        )
        self.assert_json_error(
            result,
            "MCP requests must include an API key as a bearer token.",
            status_code=401,
        )
        self.assertEqual(result.headers["WWW-Authenticate"], 'Bearer realm="zulip"')

    def test_basic_authorization_rejected(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.client_post(
            "/mcp",
            orjson.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}).decode(),
            content_type="application/json",
            HTTP_AUTHORIZATION="Basic "
            + self.encode_credentials(hamlet.delivery_email, hamlet.api_key).removeprefix("Basic "),
        )
        self.assertEqual(result.status_code, 401)

    def test_malformed_api_key(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.mcp_request(
            hamlet, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, api_key="x"
        )
        self.assert_json_error(result, "Malformed API key", status_code=401)

    def test_invalid_api_key(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.mcp_request(
            hamlet, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, api_key="A" * 32
        )
        self.assert_json_error(result, "Invalid API key", status_code=401)

    def test_incoming_webhook_bot_rejected(self) -> None:
        webhook_bot = self.example_user("webhook_bot")
        result = self.mcp_request(webhook_bot, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        self.assert_json_error(result, "This API is not available to incoming webhook bots.")

    def test_deactivated_user(self) -> None:
        cordelia = self.example_user("cordelia")
        do_deactivate_user(cordelia, acting_user=None)
        result = self.mcp_request(cordelia, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
        self.assert_json_error(result, "Account is deactivated", status_code=401)

    def test_wrong_subdomain(self) -> None:
        hamlet = self.example_user("hamlet")
        with self.assertLogs(level="WARNING") as mock_warning:
            result = self.mcp_request(
                hamlet, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, subdomain="lear"
            )
        self.assert_json_error(result, "Account is not associated with this subdomain")
        self.assertEqual(
            mock_warning.output,
            [
                "WARNING:root:User {} ({}) attempted to access API on wrong subdomain ({})".format(
                    hamlet.delivery_email, "zulip", "lear"
                )
            ],
        )

    def test_client_recorded(self) -> None:
        hamlet = self.example_user("hamlet")
        self.call_method(hamlet, "ping")
        self.assertTrue(Client.objects.filter(name="ZulipMCP").exists())

    def test_parse_error(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.client_post(
            "/mcp",
            "{invalid json",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {hamlet.api_key}",
        )
        self.assertEqual(result.status_code, 400)
        error = orjson.loads(result.content)["error"]
        self.assertEqual(error["code"], -32700)

    def test_batch_request_rejected(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.mcp_request(hamlet, [{"jsonrpc": "2.0", "id": 1, "method": "ping"}])
        self.assertEqual(result.status_code, 400)
        error = orjson.loads(result.content)["error"]
        self.assertEqual(error["code"], -32600)

    def test_notification_gets_no_response(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.mcp_request(hamlet, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(result.status_code, 202)
        self.assertEqual(result.content, b"")


class MCPProtocolTest(MCPEndpointTestCase):
    def test_invalid_json_rpc_request(self) -> None:
        hamlet = self.example_user("hamlet")
        for payload in [
            {"jsonrpc": "1.0", "id": 5, "method": "ping"},
            {"jsonrpc": "2.0", "id": 5},
        ]:
            response = self.mcp_request(hamlet, payload)
            self.assertEqual(response.status_code, 200)
            result = orjson.loads(response.content)
            self.assertEqual(result["id"], 5)
            self.assertEqual(result["error"]["code"], -32600)

    def test_unknown_method(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.call_method(hamlet, "resources/list")
        self.assertEqual(result["error"]["code"], -32601)
        self.assertEqual(result["error"]["message"], "Unknown method: resources/list")

    def test_ping(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.call_method(hamlet, "ping")
        self.assertEqual(result["result"], {})

    def test_initialize(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.call_method(
            hamlet,
            "initialize",
            {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test"}},
        )
        self.assertEqual(result["result"]["protocolVersion"], MCP_PROTOCOL_VERSION)
        self.assertEqual(result["result"]["capabilities"], {"tools": {"listChanged": False}})
        self.assertEqual(result["result"]["serverInfo"]["name"], "Zulip")

    def test_tools_list(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.call_method(hamlet, "tools/list")
        tools = result["result"]["tools"]
        self.assertEqual(sorted(tool["name"] for tool in tools), READ_ONLY_TOOL_NAMES)
        for tool in tools:
            self.assertNotEqual(tool["description"], "")
            self.assertEqual(tool["inputSchema"]["type"], "object")
            # Unknown arguments are rejected, so that misspelled
            # parameters fail loudly instead of being ignored.
            self.assertFalse(tool["inputSchema"]["additionalProperties"])
            self.assertTrue(tool["annotations"]["readOnlyHint"])

    def test_tools_call_unknown_tool(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.call_method(
            hamlet, "tools/call", {"name": "delete_everything", "arguments": {}}
        )
        self.assertEqual(result["error"]["code"], -32602)
        self.assertEqual(result["error"]["message"], "Unknown tool: delete_everything")

    def test_tools_call_missing_name(self) -> None:
        hamlet = self.example_user("hamlet")
        result = self.call_method(hamlet, "tools/call", {"arguments": {}})
        self.assertEqual(result["error"]["code"], -32602)

    def test_tools_call_invalid_arguments(self) -> None:
        hamlet = self.example_user("hamlet")
        error_text = self.call_tool_expecting_error(
            hamlet, "get_messages", {"narrow": [], "num_before": -1}
        )
        self.assertIn("Invalid arguments", error_text)

    def test_tools_call_unknown_argument(self) -> None:
        hamlet = self.example_user("hamlet")
        error_text = self.call_tool_expecting_error(hamlet, "list_channels", {"bogus": True})
        self.assertIn("Invalid arguments", error_text)


class MCPMessageToolsTest(MCPEndpointTestCase):
    def _update_search_index(self) -> None:
        # In production an async process keeps the full-text search index
        # up to date; tests update it by hand, like test_message_fetch,
        # covering whichever search backend this environment uses.
        with connection.cursor() as cursor:
            if settings.USING_PGROONGA:
                cursor.execute(
                    """
                UPDATE zerver_message SET
                search_pgroonga = escape_html(subject) || ' ' || rendered_content
                """
                )
            else:
                cursor.execute(
                    """
                UPDATE zerver_message SET
                search_tsvector = to_tsvector('zulip.english_us_search',
                subject || rendered_content)
                """
                )

    @override_settings(USING_PGROONGA=False)
    def test_narrow_search(self) -> None:
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "mcp-search")
        message_id = self.send_stream_message(
            hamlet, "mcp-search", content="the whale spouts **loudly**", topic_name="sightings"
        )
        self._update_search_index()
        payload = self.call_get_messages(hamlet, [{"operator": "search", "operand": "whale"}])
        message = payload["messages"][-1]
        self.assertEqual(
            message,
            {
                "id": message_id,
                "sender": {"user_id": hamlet.id, "full_name": hamlet.full_name},
                "timestamp": datetime_to_timestamp(Message.objects.get(id=message_id).date_sent),
                "channel": "mcp-search",
                "topic": "sightings",
                # Content is Zulip Markdown, not rendered HTML.
                "content": "the whale spouts **loudly**",
            },
        )

    def test_narrow_search_restricted_to_channel(self) -> None:
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "mcp-search-a")
        self.subscribe(hamlet, "mcp-search-b")
        self.send_stream_message(hamlet, "mcp-search-a", content="narwhal in channel a")
        self.send_stream_message(hamlet, "mcp-search-b", content="narwhal in channel b")
        self._update_search_index()
        payload = self.call_get_messages(
            hamlet,
            [
                {"operator": "search", "operand": "narwhal"},
                {"operator": "channel", "operand": "mcp-search-a"},
            ],
        )
        self.assertEqual(
            [message["content"] for message in payload["messages"]], ["narwhal in channel a"]
        )

    def test_narrow_search_in_direct_messages(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        othello = self.example_user("othello")
        self.send_personal_message(hamlet, cordelia, content="the xylophone arrives tomorrow")
        self._update_search_index()

        payload = self.call_get_messages(hamlet, [{"operator": "search", "operand": "xylophone"}])
        message = payload["messages"][-1]
        self.assertEqual(
            message["direct_message_with"],
            sorted(
                [
                    {"user_id": hamlet.id, "full_name": hamlet.full_name},
                    {"user_id": cordelia.id, "full_name": cordelia.full_name},
                ],
                key=lambda user: user["user_id"],
            ),
        )

        # Users not in the conversation cannot find it.
        payload = self.call_get_messages(othello, [{"operator": "search", "operand": "xylophone"}])
        self.assertEqual(payload["messages"], [])

    def test_senders_sharing_a_full_name_are_distinguishable(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        do_change_full_name(cordelia, hamlet.full_name, acting_user=None, notify=False)
        self.subscribe(hamlet, "mcp-names")
        self.subscribe(cordelia, "mcp-names")
        self.send_stream_message(hamlet, "mcp-names", content="from the first")
        self.send_stream_message(cordelia, "mcp-names", content="from the second")

        payload = self.call_get_messages(hamlet, [{"operator": "channel", "operand": "mcp-names"}])
        senders = [message["sender"] for message in payload["messages"]]
        self.assertEqual(
            [sender["full_name"] for sender in senders], [hamlet.full_name, hamlet.full_name]
        )
        self.assertEqual([sender["user_id"] for sender in senders], [hamlet.id, cordelia.id])

    def test_narrow_search_excludes_private_channels(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.make_stream("mcp-private", invite_only=True)
        self.subscribe(cordelia, "mcp-private")
        self.send_stream_message(cordelia, "mcp-private", content="the sekrit launch date")
        self._update_search_index()

        # The subscriber finds it; hamlet must not.
        payload = self.call_get_messages(cordelia, [{"operator": "search", "operand": "sekrit"}])
        self.assert_length(payload["messages"], 1)
        payload = self.call_get_messages(hamlet, [{"operator": "search", "operand": "sekrit"}])
        self.assertEqual(payload["messages"], [])

    def test_get_messages_by_channel_and_topic(self) -> None:
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "mcp-reading")
        self.send_stream_message(hamlet, "mcp-reading", content="first", topic_name="alpha")
        self.send_stream_message(hamlet, "mcp-reading", content="second", topic_name="beta")
        third_id = self.send_stream_message(
            hamlet, "mcp-reading", content="third", topic_name="alpha"
        )

        channel_narrow = {"operator": "channel", "operand": "mcp-reading"}
        payload = self.call_get_messages(hamlet, [channel_narrow])
        self.assertEqual(
            [message["content"] for message in payload["messages"]], ["first", "second", "third"]
        )
        self.assertTrue(payload["found_oldest"])

        payload = self.call_get_messages(
            hamlet, [channel_narrow, {"operator": "topic", "operand": "alpha"}]
        )
        self.assertEqual(
            [message["content"] for message in payload["messages"]], ["first", "third"]
        )

        # Negated terms work like in any other narrow.
        payload = self.call_get_messages(
            hamlet, [channel_narrow, {"operator": "topic", "operand": "alpha", "negated": True}]
        )
        self.assertEqual([message["content"] for message in payload["messages"]], ["second"])

        payload = self.call_get_messages(hamlet, [channel_narrow], num_before=1)
        self.assertEqual([message["id"] for message in payload["messages"]], [third_id])
        self.assertFalse(payload["found_oldest"])

    def test_get_messages_narrow_by_sender(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(hamlet, "mcp-senders")
        self.subscribe(cordelia, "mcp-senders")
        self.send_stream_message(hamlet, "mcp-senders", content="from hamlet")
        self.send_stream_message(cordelia, "mcp-senders", content="from cordelia")

        payload = self.call_get_messages(
            hamlet,
            [
                {"operator": "channel", "operand": "mcp-senders"},
                {"operator": "sender", "operand": cordelia.id},
            ],
        )
        self.assertEqual([message["content"] for message in payload["messages"]], ["from cordelia"])

    def test_get_messages_empty_narrow(self) -> None:
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "mcp-feed")
        message_id = self.send_stream_message(hamlet, "mcp-feed", content="newest in the feed")
        payload = self.call_get_messages(hamlet, [])
        self.assertEqual(payload["messages"][-1]["id"], message_id)

    def test_get_messages_public_channel_history(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.make_stream("mcp-public-history")
        self.subscribe(cordelia, "mcp-public-history")
        message_id = self.send_stream_message(
            cordelia, "mcp-public-history", content="sent before hamlet subscribed"
        )

        # Hamlet never received this message, but a public channel's history
        # is readable, as with GET /messages.
        payload = self.call_get_messages(
            hamlet, [{"operator": "channel", "operand": "mcp-public-history"}]
        )
        self.assertEqual([message["id"] for message in payload["messages"]], [message_id])

    def test_get_messages_unsubscribed_private_channel(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.make_stream("mcp-private-2", invite_only=True)
        self.subscribe(cordelia, "mcp-private-2")
        self.send_stream_message(cordelia, "mcp-private-2", content="hidden")

        # Like GET /messages, a narrow to an existing channel the user
        # cannot access returns no messages rather than an error.
        private_narrow = [{"operator": "channel", "operand": "mcp-private-2"}]
        payload = self.call_get_messages(hamlet, private_narrow)
        self.assertEqual(payload["messages"], [])

        payload = self.call_get_messages(cordelia, private_narrow)
        self.assertEqual([message["content"] for message in payload["messages"]], ["hidden"])

    def test_get_messages_unknown_channel(self) -> None:
        hamlet = self.example_user("hamlet")
        error_text = self.call_tool_expecting_error(
            hamlet,
            "get_messages",
            {"narrow": [{"operator": "channel", "operand": "no-such-channel"}]},
        )
        self.assertIn("channel", error_text)

    def test_get_messages_invalid_narrow(self) -> None:
        hamlet = self.example_user("hamlet")
        # An unknown operator is rejected when building the query.
        error_text = self.call_tool_expecting_error(
            hamlet,
            "get_messages",
            {"narrow": [{"operator": "bogus_operator", "operand": "x"}]},
        )
        self.assertIn("Invalid narrow operator", error_text)

        # A term missing its operand fails argument validation.
        error_text = self.call_tool_expecting_error(
            hamlet, "get_messages", {"narrow": [{"operator": "channel"}]}
        )
        self.assertIn("Invalid arguments", error_text)

        # Unknown keys in a term are rejected, so misspellings fail loudly.
        error_text = self.call_tool_expecting_error(
            hamlet,
            "get_messages",
            {"narrow": [{"operator": "channel", "operand": "Denmark", "negate": True}]},
        )
        self.assertIn("Invalid arguments", error_text)


class MCPMessageRangeTest(MCPEndpointTestCase):
    def send_numbered_messages(self, sender: UserProfile, channel: str, count: int) -> list[int]:
        self.subscribe(sender, channel)
        return [
            self.send_stream_message(sender, channel, content=f"message {i}", topic_name="range")
            for i in range(count)
        ]

    def test_anchor_on_message_id_returns_surrounding_context(self) -> None:
        hamlet = self.example_user("hamlet")
        message_ids = self.send_numbered_messages(hamlet, "mcp-range", 5)
        payload = self.call_get_messages(
            hamlet,
            [{"operator": "channel", "operand": "mcp-range"}],
            anchor=message_ids[2],
            num_before=1,
            num_after=1,
        )
        self.assertEqual([message["id"] for message in payload["messages"]], message_ids[1:4])
        self.assertEqual(payload["anchor"], message_ids[2])
        self.assertTrue(payload["found_anchor"])
        self.assertFalse(payload["found_oldest"])
        self.assertFalse(payload["found_newest"])
        self.assertFalse(payload["history_limited"])

    def test_paging_backward_from_a_message_already_fetched(self) -> None:
        hamlet = self.example_user("hamlet")
        message_ids = self.send_numbered_messages(hamlet, "mcp-paging", 6)
        narrow = [{"operator": "channel", "operand": "mcp-paging"}]

        first_page = self.call_get_messages(hamlet, narrow, num_before=2)
        self.assertEqual([message["id"] for message in first_page["messages"]], message_ids[4:])
        self.assertTrue(first_page["found_newest"])
        self.assertFalse(first_page["found_oldest"])

        # Excluding the anchor means the page boundary is not returned twice.
        second_page = self.call_get_messages(
            hamlet,
            narrow,
            anchor=first_page["messages"][0]["id"],
            include_anchor=False,
            num_before=2,
        )
        self.assertEqual([message["id"] for message in second_page["messages"]], message_ids[2:4])
        self.assertFalse(second_page["found_oldest"])

        # A page shorter than requested is how the caller learns it has
        # reached the start of the narrow.
        last_page = self.call_get_messages(
            hamlet,
            narrow,
            anchor=second_page["messages"][0]["id"],
            include_anchor=False,
            num_before=3,
        )
        self.assertEqual([message["id"] for message in last_page["messages"]], message_ids[:2])
        self.assertTrue(last_page["found_oldest"])

    def test_anchor_oldest_reads_forward(self) -> None:
        hamlet = self.example_user("hamlet")
        message_ids = self.send_numbered_messages(hamlet, "mcp-forward", 4)
        payload = self.call_get_messages(
            hamlet,
            [{"operator": "channel", "operand": "mcp-forward"}],
            anchor="oldest",
            num_before=0,
            num_after=2,
        )
        # The "oldest" anchor is not itself a message, so the range is just
        # the requested num_after messages.
        self.assertEqual([message["id"] for message in payload["messages"]], message_ids[:2])
        self.assertTrue(payload["found_oldest"])
        self.assertFalse(payload["found_newest"])

    def test_anchor_first_unread(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.subscribe(cordelia, "mcp-unread")
        message_ids = self.send_numbered_messages(hamlet, "mcp-unread", 3)
        narrow = [{"operator": "channel", "operand": "mcp-unread"}]

        payload = self.call_get_messages(
            cordelia, narrow, anchor="first_unread", num_before=0, num_after=10
        )
        self.assertEqual([message["id"] for message in payload["messages"]], message_ids)
        self.assertEqual(payload["anchor"], message_ids[0])

        do_update_message_flags(cordelia, "add", "read", message_ids[:2])
        payload = self.call_get_messages(
            cordelia, narrow, anchor="first_unread", num_before=0, num_after=10
        )
        self.assertEqual([message["id"] for message in payload["messages"]], message_ids[2:])
        self.assertEqual(payload["anchor"], message_ids[2])

    def test_with_operator_resolves_the_conversation(self) -> None:
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "mcp-with")
        message_id = self.send_stream_message(
            hamlet, "mcp-with", content="moved here", topic_name="actual topic"
        )
        # A stale channel/topic pair plus `with` resolves to the conversation
        # that actually contains the message, as in GET /messages.
        payload = self.call_get_messages(
            hamlet,
            [
                {"operator": "channel", "operand": "mcp-with"},
                {"operator": "topic", "operand": "stale topic"},
                {"operator": "with", "operand": message_id},
            ],
        )
        self.assertEqual([message["id"] for message in payload["messages"]], [message_id])
        self.assertEqual(payload["messages"][0]["topic"], "actual topic")

    def test_range_larger_than_rest_api_maximum(self) -> None:
        hamlet = self.example_user("hamlet")
        error_text = self.call_tool_expecting_error(
            hamlet,
            "get_messages",
            {"num_before": MAX_MESSAGES_PER_FETCH, "num_after": 1},
        )
        self.assertEqual(
            error_text,
            f"Too many messages requested (maximum {MAX_MESSAGES_PER_FETCH}).",
        )

    def test_anchor_can_only_be_excluded_at_an_end_of_the_range(self) -> None:
        hamlet = self.example_user("hamlet")
        error_text = self.call_tool_expecting_error(
            hamlet,
            "get_messages",
            {"num_before": 1, "num_after": 1, "include_anchor": False},
        )
        self.assertEqual(error_text, "The anchor can only be excluded at an end of the range")

    def test_invalid_anchor(self) -> None:
        hamlet = self.example_user("hamlet")
        error_text = self.call_tool_expecting_error(hamlet, "get_messages", {"anchor": "yesterday"})
        self.assertIn("Invalid arguments", error_text)


class MCPDirectoryToolsTest(MCPEndpointTestCase):
    def test_list_channels(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.make_stream("mcp-hidden", invite_only=True)
        self.subscribe(cordelia, "mcp-hidden")
        self.make_stream("mcp-mine", invite_only=True)
        self.subscribe(hamlet, "mcp-mine")

        payload = self.call_tool_expecting_success(hamlet, "list_channels", {})
        channels = {channel["name"]: channel for channel in payload["channels"]}
        self.assertIn("Denmark", channels)
        self.assertFalse(channels["Denmark"]["is_private"])
        self.assertNotIn("mcp-hidden", channels)
        self.assertTrue(channels["mcp-mine"]["is_private"])
        denmark = channels["Denmark"]
        self.assertEqual(
            sorted(denmark.keys()),
            ["channel_id", "description", "is_private", "is_web_public", "name"],
        )

    def test_list_topics(self) -> None:
        hamlet = self.example_user("hamlet")
        self.subscribe(hamlet, "mcp-topics")
        self.send_stream_message(hamlet, "mcp-topics", content="one", topic_name="planning")
        second_id = self.send_stream_message(
            hamlet, "mcp-topics", content="two", topic_name="launch"
        )

        payload = self.call_tool_expecting_success(hamlet, "list_topics", {"channel": "mcp-topics"})
        # Topics are returned newest first.
        self.assertEqual(payload["topics"][0], {"name": "launch", "max_message_id": second_id})
        self.assertEqual({topic["name"] for topic in payload["topics"]}, {"planning", "launch"})

    def test_list_topics_inaccessible_channel(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        self.make_stream("mcp-private-3", invite_only=True)
        self.subscribe(cordelia, "mcp-private-3")
        error_text = self.call_tool_expecting_error(
            hamlet, "list_topics", {"channel": "mcp-private-3"}
        )
        self.assertEqual(error_text, "Invalid channel name 'mcp-private-3'")

    def test_list_linkifiers(self) -> None:
        hamlet = self.example_user("hamlet")
        do_add_linkifier(
            hamlet.realm,
            "#(?P<id>[0-9]+)",
            "https://github.com/zulip/zulip/issues/{id}",
            acting_user=None,
        )

        payload = self.call_tool_expecting_success(hamlet, "list_linkifiers", {})
        self.assertIn(
            {
                "pattern": "#(?P<id>[0-9]+)",
                "url_template": "https://github.com/zulip/zulip/issues/{id}",
            },
            payload["linkifiers"],
        )
        # Just what an agent needs to interpret a bare pattern in message text.
        self.assertEqual(
            {key for linkifier in payload["linkifiers"] for key in linkifier},
            {"pattern", "url_template"},
        )

    def test_get_users(self) -> None:
        hamlet = self.example_user("hamlet")
        cordelia = self.example_user("cordelia")
        payload = self.call_tool_expecting_success(hamlet, "get_users", {"query": "cordelia"})
        self.assertEqual(
            payload["users"],
            [
                {
                    "user_id": cordelia.id,
                    "full_name": cordelia.full_name,
                    "email": cordelia.email,
                    "is_bot": False,
                }
            ],
        )

    def test_get_users_by_email_and_limit(self) -> None:
        hamlet = self.example_user("hamlet")
        # The test realm hides email addresses, so .email is a dummy
        # address; only that address is matched, never delivery_email.
        assert hamlet.email != hamlet.delivery_email
        payload = self.call_tool_expecting_success(hamlet, "get_users", {"query": hamlet.email})
        self.assertEqual([user["user_id"] for user in payload["users"]], [hamlet.id])

        payload = self.call_tool_expecting_success(
            hamlet, "get_users", {"query": hamlet.delivery_email}
        )
        self.assertEqual(payload["users"], [])

        payload = self.call_tool_expecting_success(hamlet, "get_users", {"limit": 1})
        self.assert_length(payload["users"], 1)

    def test_get_users_includes_bots(self) -> None:
        hamlet = self.example_user("hamlet")
        payload = self.call_tool_expecting_success(hamlet, "get_users", {"query": "webhook"})
        self.assertTrue(all(user["is_bot"] for user in payload["users"]))
        self.assertIn(
            self.example_user("webhook_bot").id, [user["user_id"] for user in payload["users"]]
        )

    def test_get_users_unrestricted_for_members(self) -> None:
        # set_up_db_for_testing_user_access limits which users guests can
        # see; members and administrators still see the whole organization.
        self.set_up_db_for_testing_user_access()
        hamlet = self.example_user("hamlet")
        polonius = self.example_user("polonius")
        # Subscriptions would make this user accessible to everyone in the
        # shared channels, which is what we need to test around.
        stranger = do_create_user(
            "stranger@zulip.com",
            "password",
            get_realm("zulip"),
            "Stranger",
            acting_user=None,
            add_initial_stream_subscriptions=False,
        )

        payload = self.call_tool_expecting_success(hamlet, "get_users", {"limit": 200})
        self.assertIn(stranger.id, {user["user_id"] for user in payload["users"]})

        payload = self.call_tool_expecting_success(polonius, "get_users", {"limit": 200})
        self.assertNotIn(stranger.id, {user["user_id"] for user in payload["users"]})

    def test_get_users_respects_restricted_access(self) -> None:
        self.set_up_db_for_testing_user_access()
        realm = get_realm("zulip")
        polonius = self.example_user("polonius")
        cordelia = self.example_user("cordelia")
        hamlet = self.example_user("hamlet")

        payload = self.call_tool_expecting_success(polonius, "get_users", {"limit": 200})
        returned_ids = {user["user_id"] for user in payload["users"] if not user["is_bot"]}
        self.assertIn(hamlet.id, returned_ids)
        self.assertNotIn(cordelia.id, returned_ids)
        accessible_ids = set(get_accessible_user_ids(realm, polonius))
        self.assertTrue(returned_ids.issubset(accessible_ids))
