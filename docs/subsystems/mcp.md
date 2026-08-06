# MCP server

Zulip includes a native [Model Context Protocol](https://modelcontextprotocol.io/)
(MCP) server, which lets AI agents read and act in a Zulip organization
with a small set of tools, acting as the user whose credentials they
hold. This page documents its design and the development workflow.

The MCP server is **experimental**: it is not officially supported for
production use, and its tools may change or be removed without the
compatibility guarantees the REST API carries. The point of that phase
is to learn from real agents what the tool set should be before
committing to it; see
[the API design process](../processes/api-design.md) for the
commitments we expect to make when it leaves this phase.

## Design

The server is a deliberately thin layer over Zulip's existing
libraries. It provides the primitives an agent needs (search and read
messages, list channels, topics, users and linkifiers); conversational
orchestration -- system prompts, multi-step workflows, "@-mention an AI
bot" experiences -- is expected to live in external services built on
top of these primitives.

The implementation has three layers:

- `zerver/views/mcp.py`: the HTTP transport. Authenticates the
  request, enforces the access-control settings, parses the JSON-RPC
  message, and serializes the response.
- `zerver/lib/mcp/protocol.py`: JSON-RPC 2.0 dispatch for the MCP
  methods the server implements (`initialize`, `ping`, `tools/list`,
  and `tools/call`), and the MCP result/error envelope for tool calls.
- `zerver/lib/mcp/tools.py`: the tool registry. Each tool is a
  Pydantic arguments model (whose JSON schema is served to clients as
  the tool's `inputSchema`) plus a handler that calls the same library
  code backing the corresponding REST endpoint, so that access control
  is inherited rather than reimplemented.

The invariant to preserve when changing this code: **an MCP request
can do nothing that the authenticated user could not already do with
the same credentials via the REST API.**

### Transport

`POST /mcp` implements the MCP Streamable HTTP transport in its
simplest, stateless form, reporting protocol revision `2025-06-18`:

- Each request carries exactly one JSON-RPC message and receives a
  single JSON response; there are no sessions and no SSE streaming.
  `GET` requests are rejected with a 405, per the specification, and
  clients requiring server-initiated streams should treat this server
  as not offering them.
- JSON-RPC messages without an `id` are notifications
  (e.g., `notifications/initialized`), acknowledged with an empty 202.
- JSON-RPC batch requests are rejected; batching was removed from the
  MCP specification in 2025.
- Tool execution failures -- including Zulip permission errors --
  are reported in-band as tool results with `isError: true` and the
  user-facing error message, so the model can see the message and
  recover. Protocol-level problems (unknown method, unknown tool,
  malformed JSON) use JSON-RPC error responses instead.

### Authentication

Requests authenticate with a Zulip API key presented as a bearer
token: `Authorization: Bearer <api_key>`. The endpoint uses the same
validation path as the REST API (`validate_api_key`), including
account/subdomain checks and IP and per-user rate limits, and records
requests under a `ZulipMCP` client for analytics. Incoming webhook
bot credentials are rejected, like on other non-webhook endpoints.

Today the API key is the user's single api_key; when per-client API
tokens exist (see #17939), only the token lookup should need to
change -- the endpoint and header format are already shaped for it.

### Access control

Two settings gate the endpoint, beyond authentication itself:

- `MCP_SERVER_ENABLED`: a server-level setting (default `True`),
  letting self-hosted administrators disable the endpoint entirely;
  when disabled, `/mcp` returns 404.
- `enable_mcp_access`: a realm setting (default `False`), so each
  organization consciously opts in to AI agent access. Organization
  administrators manage it in organization permissions settings.

The development environment realm has `enable_mcp_access` enabled by
`populate_db`, so the endpoint works there out of the box.

## Changing the tools

While the server is experimental, tools can change freely; document
changes with an [API changelog entry](../documentation/api.md) so that
people following along know what moved. Design notes:

- Argument models set `extra="forbid"`, so a misspelled parameter
  fails loudly rather than being silently ignored.
- `get_messages` mirrors `GET /messages` rather than inventing its own
  vocabulary: the [narrow](https://zulip.com/api/construct-narrow)
  filter language instead of bespoke flat filters, and the same
  `anchor`/`include_anchor`/`num_before`/`num_after` range parameters,
  so an agent can pull the context around a specific message and page
  through a conversation. This keeps richer querying from ever needing
  new tool arguments, and leaves compatibility for the filter language
  and range semantics to the REST API's existing commitments.
- Tools return compact, stable result objects rather than the full
  REST payloads, to keep token costs low and the committed surface
  small. Add fields deliberately.
- A person in a result is always a `{user_id, full_name}` object. Full
  names are not unique in Zulip -- `require_unique_names` is off by
  default -- so a name alone identifies nobody, and the user ID is what
  the `sender` narrow operator and message recipients are given as.
- Read-only tools set the `readOnlyHint` annotation, which MCP
  clients use for permission prompts, and which a future read-only
  credential scope could enforce server-side.

## Development and testing

Backend tests live in `zerver/tests/test_mcp.py`:

```bash
./tools/test-backend zerver.tests.test_mcp
```

To exercise the endpoint manually in the development environment,
grab an API key (e.g., from **Personal settings > Account & privacy**
in the web app, or `./manage.py print_initial_password
iago@zulip.com`), and issue JSON-RPC requests with curl:

```bash
key=<api key>
curl -sS http://localhost:9991/mcp \
  -H "Authorization: Bearer $key" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'

curl -sS http://localhost:9991/mcp \
  -H "Authorization: Bearer $key" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 2, "method": "tools/call",
       "params": {"name": "get_messages",
                  "arguments": {"narrow": [{"operator": "search",
                                            "operand": "lunch"}]}}}'
```

[MCP Inspector](https://github.com/modelcontextprotocol/inspector)
provides an interactive UI for the same thing: run
`npx @modelcontextprotocol/inspector`, choose the "Streamable HTTP"
transport with URL `http://localhost:9991/mcp`, and set the
`Authorization: Bearer <api key>` header.

To connect Claude Code to a Zulip organization:

```bash
claude mcp add --transport http zulip https://zulip.example.com/mcp \
  --header "Authorization: Bearer <api key>"
```
