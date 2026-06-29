**Feature level ZF-7cc0ba**

* Added a native [Model Context Protocol](https://modelcontextprotocol.io)
  (MCP) server endpoint, `POST /api/v1/mcp`, which exposes Zulip read and
  write tools (searching and fetching messages, listing channels and topics,
  looking up users, sending messages, adding reactions, and marking messages
  as read) to MCP clients over a stateless JSON-RPC transport. Requests are
  authenticated with a personal MCP token and act as the authenticating user,
  with that user's permissions.
* Added endpoints for managing personal MCP tokens: `GET` and `POST
  /api/v1/mcp_tokens`, and `DELETE /api/v1/mcp_tokens/{token_id}`.
