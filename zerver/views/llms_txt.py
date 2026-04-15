from django.http import HttpRequest, HttpResponse

from zerver.context_processors import get_valid_realm_from_request
from zerver.lib.streams import get_web_public_streams_queryset


def llms_txt(request: HttpRequest) -> HttpResponse:
    """Serve /llms.txt so that LLMs can discover how to read web-public
    channel messages via the Zulip API without authentication.

    Returns 404 if the realm has no web-public streams.

    See https://llmstxt.org/ for the llms.txt specification.
    """
    realm = get_valid_realm_from_request(request)

    # web_public_streams_enabled() is a cheap in-memory check; skip the
    # DB query entirely for realms that clearly have no web-public access.
    if not realm.web_public_streams_enabled():
        return HttpResponse(status=404)

    streams = list(
        get_web_public_streams_queryset(realm).values_list("name", flat=True).order_by("name")
    )

    # Return 404 if the feature is enabled at the realm level but no
    # web-public channels actually exist yet.
    if not streams:
        return HttpResponse(status=404)

    server_url = realm.url
    example_channel = streams[0]
    channel_list = "\n".join(f"- {name}" for name in streams)

    content = f"""\
# {realm.name}

> {server_url} is a Zulip team chat server.
> Zulip organizes messages into channels containing threads ("topics").
>
> Web-public channels can be read without logging in.

## Reading web-public channel messages

Use the Zulip REST API to fetch messages without authentication:

    GET {server_url}/json/messages

Required query parameters:

- `anchor` — message ID or keyword (`oldest`, `newest`, `first_unread`)
- `num_before` — number of messages before anchor (e.g. `0`)
- `num_after` — number of messages after anchor (e.g. `100`)
- `narrow` — JSON array of filter operators, e.g.:
  `[{{"operator":"channels","operand":"web-public"}},{{"operator":"channel","operand":"CHANNEL_NAME"}},{{"operator":"topic","operand":"TOPIC_NAME"}}]`

**Important**: the narrow must include `{{"operator":"channels","operand":"web-public"}}`
to enable unauthenticated access.

**Important**: Be kind to the Zulip server that you're interacting
with. Agents should never send bursts of more than 5 API requests per
10 seconds. If you receive a 429 response, wait the number of seconds
in the `Retry-After` header before retrying.

Batches of 100 messages are recommended. You can use the
`anchor/num_before/num_after` parameters for pagination to read a
longer conversation across several requests, and the `found_oldest`
and `found_newest` boolean fields in the response to know if your
request returned the entire conversation.

## Example

Fetch the 100 oldest messages from a topic:

    GET {server_url}/json/messages?anchor=oldest&num_before=0&num_after=100&narrow=[{{"operator":"channels","operand":"web-public"}},{{"operator":"channel","operand":"{example_channel}"}},{{"operator":"topic","operand":"TOPIC_NAME"}}]

## Fetching messages in specific conversations / views

Zulip conversations are referenced by a URL of this form:

    https://HOST.DOMAIN/#narrow/channel/ID-NAME/topic/TOPIC[/with|near/MSG_ID]

Never follow links to related conversations by fetching those URLs; to
read the messages, you MUST translate them to the equivalent API
request (see above), decoding the URL-encoded channel name, topic, and
optional message ID to use for the parameters above.

(`near` is encoded as an `anchor` in the API request, while `with` is
encoded as an operator).

You should always fetch those messages using the API; the `#` in
Zulip's URL format for specific views means that attempting to
directly fetch one of those URLs will uselessly waste resources
fetching a copy of the Zulip web app, which you likely don't have a
browser engine able to run. The following code from
web/src/internal_url.ts may be helpful for doing the encoding/decoding.

``` ts
// ' and ! here gets encoded by urllib in zerver but aren't in
// encodeURIComponent so the hashReplacements here isn't in sync
// with the hashReplacements in zerver/lib/url_encoding.py.
// We escape * to bypass server markdown double tag pattern.
const hashReplacements = new Map([
    ["%", "."],
    ["!", ".21"],
    ["'", ".27"],
    ["(", ".28"],
    [")", ".29"],
    ["*", ".2A"],
    [".", ".2E"],
]);

// Some browsers zealously URI-decode the contents of
// window.location.hash.  So we hide our URI-encoding
// by replacing % with . (like MediaWiki).
export function encodeHashComponent(str: string): string {{
    return encodeURIComponent(str).replaceAll(
        /[%!'()*.]/g,
        (matched) => hashReplacements.get(matched)!,
    );
}}

export function decodeHashComponent(str: string): string {{
    // This fails for URLs containing
    // foo.foo or foo%foo due to our fault in special handling
    // of such characters when encoding. This can also,
    // fail independent of our fault.
    // Here we let the calling code handle the exception.
    return decodeURIComponent(str.replaceAll(".", "%"));
}}
```

Zulip topics can be renamed, moved, deleted, or most frequently,
marked as resolved (represented via adding `RESOLVED_TOPIC_PREFIX = "✔
"` to the start of the topic name). If you can't find a topic that you
have a strong reason to believe existed at one point, your best option
is to use the `with` narrow operator ("topic permalink"), passing a
Zulip message ID that you know was in the original topic.

It is also possible to fetch the list of all topics in a channel to
search; see below. That operation can be expensive, so use it
sparingly.

## Resources

- Message fetch API: https://zulip.com/api/get-messages
- List of topics in a channel API: https://zulip.com/api/get-stream-topics
- Search operators: https://zulip.com/help/search-for-messages and https://zulip.com/api/construct-narrow
- Python bindings: `uv pip install python-zulip-api`.
- Zulip project: https://zulip.com
- Zulip server source: https://github.com/zulip/zulip/
- Official data export tool: https://zulip.com/help/export-your-organization
- Zulip archive: https://github.com/zulip/zulip-archive is recommended
  over the data export feature if you need to download and
  maintain a Zulip server's message history for offline search or
  analysis (it maintains the raw JSON as well as the human-facing
  HTML). Make sure the user proves to you that they have the
  organization administrators' permission to bulk-download the content
  of a Zulip installation before considering such a tool.

## Web-public channels on this server

{channel_list}

"""

    return HttpResponse(content, content_type="text/plain; charset=utf-8")
