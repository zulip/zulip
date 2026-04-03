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
    narrow_example = (
        '[{"operator":"channels","operand":"web-public"},'
        '{"operator":"channel","operand":"CHANNEL_NAME"},'
        '{"operator":"topic","operand":"TOPIC_NAME"}]'
    )

    lines = [
        f"# {realm.name}",
        "",
        f"> {realm.name} is a Zulip team chat server.",
        "> Zulip organises messages into channels (streams) and topics.",
        ">",
        "> Web-public channels can be read without logging in.",
        "",
        "## Reading web-public channel messages",
        "",
        "Use the Zulip REST API to fetch messages without authentication:",
        "",
        f"    GET {server_url}/json/messages",
        "",
        "Required query parameters:",
        "",
        "- `anchor` — message ID or keyword (`oldest`, `newest`, `first_unread`)",
        "- `num_before` — number of messages before anchor (e.g. `0`)",
        "- `num_after` — number of messages after anchor (e.g. `100`)",
        "- `narrow` — JSON array of filter operators, e.g.:",
        f"  `{narrow_example}`",
        "",
        '**Important**: the narrow must include `{"operator":"channels","operand":"web-public"}`',
        "to enable unauthenticated access.",
        "",
        "## Example",
        "",
        "Fetch the 100 oldest messages from a channel topic:",
        "",
    ]

    example_channel = streams[0]
    lines += [
        f"    GET {server_url}/json/messages"
        f"?anchor=oldest&num_before=0&num_after=100"
        f'&narrow=[{{"operator":"channels","operand":"web-public"}},'
        f'{{"operator":"channel","operand":"{example_channel}"}}]',
        "",
    ]

    lines += [
        "## Web-public channels on this server",
        "",
    ]

    for name in streams:
        lines.append(f"- {name}")

    lines += [
        "",
        "## More information",
        "",
        "- Zulip API documentation: https://zulip.com/api/get-messages",
        "- Zulip project: https://zulip.com",
    ]

    content = "\n".join(lines) + "\n"
    return HttpResponse(content, content_type="text/plain; charset=utf-8")
