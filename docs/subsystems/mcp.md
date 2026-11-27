# MCP server

Zulip includes a native [Model Context Protocol](https://modelcontextprotocol.io/)
(MCP) server, which lets a user connect an AI agent to Zulip and have
it read the organization through a small set of tools, as the user
whose credentials it holds. This page documents its design and the
development workflow.

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

Building it into the server, rather than shipping a bridge process
that calls the REST API, is what lets each tool call reuse the access
control of the endpoint it corresponds to, and keeps organizations
from having to hand a user's API key to a third party to get an agent
connected. Zulip makes no AI API calls of its own here: it answers
whatever agent the user chose to point at it.

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
  is inherited rather than reimplemented. `get_messages` goes through
  `fetch_plain_text_messages_for_narrow`, shared with topic
  summarization, which is where the repeatable-read isolation and the
  choice to hydrate Markdown source without flags or edit history
  live. `get_users` applies the search filter and the realm's user
  visibility rule in SQL before calling `get_users_for_api`, which
  offers neither, so that visibility rule appears in both places; the
  shared function is what
  decides who is returned, and `format_user_row` remains the authority
  on which fields are safe to return -- consult it before adding one.

The invariant to preserve when changing this code: **an MCP request
can do nothing that the authenticated user could not already do with
the same credentials via the REST API.**

### Transport

`POST /mcp` implements the MCP Streamable HTTP transport in its
simplest, stateless form, reporting protocol revision `2025-06-18`.
`/mcp/` is the same endpoint: this URL is typed by hand into agent
configurations rather than reached through a client library, so a
trailing slash has to work rather than produce a 404.

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

### Untrusted content

Every message an agent reads through this server is text somebody else
wrote, and a model cannot reliably tell instructions inside that text
from instructions from its user. A Zulip organization is an untrusted
input source, and on an open server like chat.zulip.org, anyone who
signs up can add to it.

The read-only tool set is what limits where that can go. An agent
talked into reading a private channel has no tool here with which to
publish what it found; the remaining risk lives in whatever other
tools its user gave it. That property disappears the first time a
write tool is added, which is much of why doing so needs its own
permission and its own discussion rather than a new entry in
`MCP_TOOLS`.

### Authentication

Requests authenticate with a Zulip API key presented as a bearer
token: `Authorization: Bearer <api_key>`. The endpoint uses the same
validation path as the REST API (`validate_api_key`), including
account/subdomain checks and IP and per-user rate limits, and records
requests under a `ZulipMCP` client for analytics. Incoming webhook
bot credentials are rejected, like on other non-webhook endpoints.

Today the API key is the user's single api_key; when per-client API
tokens exist (#17939), only the token lookup should need to
change -- the endpoint and header format are already shaped for it.

### Access control

Two settings gate the endpoint, beyond authentication itself:

- `MCP_SERVER_ENABLED`: a server-level setting (default `True`),
  letting self-hosted administrators disable the endpoint entirely;
  when disabled, `/mcp` returns 404.
- `enable_mcp_read_access`: a realm setting (default `False`), so
  each organization consciously opts in to AI agent access.
  Organization administrators manage it in organization permissions
  settings. It names the access it grants, so that a write tool would
  arrive behind an `enable_mcp_write_access` rather than under this
  one: an organization that granted reading has not agreed to agents
  posting as its users.

The development environment realm has `enable_mcp_read_access`
enabled by `populate_db`, so the endpoint works there out of the box.

Neither setting is a general control over AI access to an
organization, and neither should be described as one: a user whose
API key works can point any REST-API-based agent at Zulip whatever
these are set to. What they control is whether Zulip itself offers
agents a supported way in.

## Changing the tools

While the server is experimental, tools can change freely; document
changes with an [API changelog entry](../documentation/api.md) so that
people following along know what moved. Design notes:

- Argument models set `extra="forbid"`, so a misspelled parameter
  fails loudly rather than being silently ignored.
- `get_messages` mirrors `GET /messages` rather than inventing its own
  vocabulary: the [narrow](https://zulip.com/api/construct-narrow)
  filter language instead of bespoke flat filters, and the same
  `anchor`/`anchor_date`/`include_anchor`/`num_before`/`num_after`
  range parameters, so an agent can pull the context around a specific
  message, page through a conversation, and start from a date -- which
  no narrow operator expresses. This keeps richer querying from ever
  needing new tool arguments, and leaves compatibility for the filter
  language and range semantics to the REST API's existing commitments.
  `MCPRestParityTest` asserts the two endpoints agree, so that the
  inheritance stays real rather than aspirational.
- Tools return compact, stable result objects rather than the full
  REST payloads, to keep token costs low and the committed surface
  small. Add fields deliberately.
- A result that can be cut short has to say so: `get_messages` reports
  `found_oldest`/`found_newest`, and `list_channels`, `list_topics` and
  `get_users` each take a `limit` and report `found_all` alongside a
  `total_count` of everything that matched. An agent cannot see that a
  list was truncated, and will report a partial answer as a complete
  one. All three sources already build the full list server-side, so
  the limit is protecting the agent's context rather than the database;
  the count is what lets the agent choose between raising the limit and
  narrowing the query, instead of spending a round trip to learn how
  big the list is. There is deliberately no "return everything" flag:
  `limit` has no upper bound, so it would be a second spelling of the
  same request, and one that invites pulling a channel's thousands of
  topics into context sight unseen. `list_linkifiers` is unbounded
  because a realm's linkifiers are few; anything that grows with the
  size of an organization needs a limit.
- A person in a result is always a `{user_id, full_name}` object. Full
  names are not unique in Zulip -- `require_unique_names` is off by
  default -- so a name alone identifies nobody, and the user ID is what
  the `sender` narrow operator and message recipients are given as.
- Every tool sets the `readOnlyHint` annotation, which MCP clients use
  for permission prompts, and which a future read-only credential
  scope could enforce server-side.

## Development and testing

Backend tests live in `zerver/tests/test_mcp.py`:

```bash
./tools/test-backend zerver.tests.test_mcp
```

Tool calls name their tool in the request log
(`POST 200 ... /mcp [get_messages]`), which is how to see what agents
actually do with the server while the tool set is experimental.

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
