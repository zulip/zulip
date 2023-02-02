# Webhooks for external integrations.
import re
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, RequestVariableMissingError, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.types import Validator
from zerver.lib.validator import (
    WildValue,
    check_dict,
    check_int,
    check_string,
    check_string_in,
    check_url,
    to_wild_value,
)
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("SlackIncoming")
@has_request_variables
def api_slack_incoming_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    user_specified_topic: Optional[str] = REQ("topic", default=None),
) -> HttpResponse:
    # Slack accepts webhook payloads as payload="encoded json" as
    # application/x-www-form-urlencoded, as well as in the body as
    # application/json.
    if request.content_type == "application/json":
        try:
            val = request.body.decode(request.encoding or "utf-8")
        except UnicodeDecodeError:  # nocoverage
            raise JsonableError(_("Malformed payload"))
    else:
        req_var = "payload"
        if req_var in request.POST:
            val = request.POST[req_var]
        elif req_var in request.GET:  # nocoverage
            val = request.GET[req_var]
        else:
            raise RequestVariableMissingError(req_var)

    payload = to_wild_value("payload", val)

    if user_specified_topic is None and "channel" in payload:
        channel = payload["channel"].tame(check_string)
        user_specified_topic = re.sub("^[@#]", "", channel)

    if user_specified_topic is None:
        user_specified_topic = "(no topic)"

    pieces = []
    if "blocks" in payload and payload["blocks"]:
        for block in payload["blocks"]:
            pieces.append(render_block(block))

    if "attachments" in payload and payload["attachments"]:
        for attachment in payload["attachments"]:
            pieces.append(render_attachment(attachment))

    body = "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")

    if body == "" and "text" in payload and payload["text"]:
        if "icon_emoji" in payload and payload["icon_emoji"]:
            body = payload["icon_emoji"].tame(check_string) + " "
        body += payload["text"].tame(check_string)
        body = body.strip()

    if body != "":
        body = replace_formatting(replace_links(body).strip())
        check_send_webhook_message(request, user_profile, user_specified_topic, body)
    return json_success(request)


def render_block(block: WildValue) -> str:
    # https://api.slack.com/reference/block-kit/blocks
    block_type = block["type"].tame(
        check_string_in(["actions", "context", "divider", "header", "image", "input", "section"])
    )
    if block_type == "actions":
        # Unhandled
        return ""
    elif block_type == "context" and block.get("elements"):
        pieces = []
        # Slack renders these pieces left-to-right, packed in as
        # closely as possible.  We just render them above each other,
        # for simplicity.
        for element in block["elements"]:
            element_type = element["type"].tame(check_string_in(["image", "plain_text", "mrkdwn"]))
            if element_type == "image":
                pieces.append(render_block_element(element))
            else:
                pieces.append(element.tame(check_text_block()))
        return "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")
    elif block_type == "divider":
        return "----"
    elif block_type == "header":
        return "## " + block["text"].tame(check_text_block(plain_text_only=True))
    elif block_type == "image":
        image_url = block["image_url"].tame(check_url)
        alt_text = block["alt_text"].tame(check_string)
        if "title" in block:
            alt_text = block["title"].tame(check_text_block(plain_text_only=True))
        return f"[{alt_text}]({image_url})"
    elif block_type == "input":
        # Unhandled
        pass
    elif block_type == "section":
        pieces = []
        if "text" in block:
            pieces.append(block["text"].tame(check_text_block()))

        if "accessory" in block:
            pieces.append(render_block_element(block["accessory"]))

        if "fields" in block:
            # TODO -- these should be rendered in two columns,
            # left-to-right.  We could render them sequentially,
            # except some may be Title1 / Title2 / value1 / value2,
            # which would be nonsensical when rendered sequentially.
            pass

        return "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")

    return ""


def check_text_block(plain_text_only: bool = False) -> Validator[str]:
    if plain_text_only:
        type_validator = check_string_in(["plain_text"])
    else:
        type_validator = check_string

    def f(var_name: str, val: object) -> str:
        block = check_dict(
            [
                ("type", type_validator),
                ("text", check_string),
            ],
        )(var_name, val)

        # We can't use `value_validator=check_string` above to let
        # mypy know this is a str, because there's an optional boolean
        # `emoji` key which can appear -- hence the assert.
        text = block["text"]
        assert isinstance(text, str)

        # Ideally we would escape the content if it was plain text,
        # but out flavor of Markdown doesn't support escapes. :(
        return text

    return f


def render_block_element(element: WildValue) -> str:
    # https://api.slack.com/reference/block-kit/block-elements
    # Zulip doesn't support interactive elements, so we only render images here
    element_type = element["type"].tame(check_string)
    if element_type == "image":
        image_url = element["image_url"].tame(check_url)
        alt_text = element["alt_text"].tame(check_string)
        return f"[{alt_text}]({image_url})"
    else:
        # Unsupported
        return ""


def render_attachment(attachment: WildValue) -> str:
    # https://api.slack.com/reference/messaging/attachments
    # Slack recommends the usage of "blocks" even within attachments; the
    # rest of the fields we handle here are legacy fields. These fields are
    # optional and may contain null values.
    pieces = []
    if "title" in attachment and attachment["title"]:
        title = attachment["title"].tame(check_string)
        if "title_link" in attachment and attachment["title_link"]:
            title_link = attachment["title_link"].tame(check_url)
            pieces.append(f"## [{title}]({title_link})")
        else:
            pieces.append(f"## {title}")
    if "pretext" in attachment and attachment["pretext"]:
        pieces.append(attachment["pretext"].tame(check_string))
    if "text" in attachment and attachment["text"]:
        pieces.append(attachment["text"].tame(check_string))
    if "fields" in attachment:
        fields = []
        for field in attachment["fields"]:
            if field["title"] and field["value"]:
                title = field["title"].tame(check_string)
                value = field["value"].tame(check_string)
                fields.append(f"*{title}*: {value}")
            elif field["title"]:
                title = field["title"].tame(check_string)
                fields.append(f"*{title}*")
            elif field["value"]:
                value = field["value"].tame(check_string)
                fields.append(f"{value}")
        pieces.append("\n".join(fields))
    if "blocks" in attachment and attachment["blocks"]:
        for block in attachment["blocks"]:
            pieces.append(render_block(block))
    if "image_url" in attachment and attachment["image_url"]:
        pieces.append("[]({})".format(attachment["image_url"].tame(check_url)))
    if "footer" in attachment and attachment["footer"]:
        pieces.append(attachment["footer"].tame(check_string))
    if "ts" in attachment and attachment["ts"]:
        time = attachment["ts"].tame(check_int)
        pieces.append(f"<time:{time}>")

    return "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")


def replace_links(text: str) -> str:
    return re.sub(r"<(\w+?:\/\/.*?)\|(.*?)>", r"[\2](\1)", text)


def replace_formatting(text: str) -> str:
    # Slack uses *text* for bold, whereas Zulip interprets that as italics
    text = re.sub(r"([^\w])\*(?!\s+)([^\*^\n]+)(?<!\s)\*([^\w])", r"\1**\2**\3", text)

    # Slack uses _text_ for emphasis, whereas Zulip interprets that as nothing
    text = re.sub(r"([^\w])[_](?!\s+)([^\_\^\n]+)(?<!\s)[_]([^\w])", r"\1*\2*\3", text)
    return text
