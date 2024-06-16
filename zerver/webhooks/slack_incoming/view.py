# Webhooks for external integrations.
import re
from itertools import zip_longest
from typing import List, Literal, TypedDict, cast

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import RequestVariableMissingError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.types import Validator
from zerver.lib.validator import (
    WildValue,
    check_dict,
    check_int,
    check_list,
    check_string,
    check_string_in,
    check_url,
    to_wild_value,
)
from zerver.lib.webhooks.common import OptionalUserSpecifiedTopicStr, check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("SlackIncoming")
@typed_endpoint
def api_slack_incoming_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    user_specified_topic: OptionalUserSpecifiedTopicStr = None,
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
        user_specified_topic = re.sub(r"^[@#]", "", channel)

    if user_specified_topic is None:
        user_specified_topic = "(no topic)"

    pieces: List[str] = []
    if payload.get("blocks"):
        pieces += map(render_block, payload["blocks"])

    if payload.get("attachments"):
        pieces += map(render_attachment, payload["attachments"])

    body = "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")

    if body == "" and payload.get("text"):
        if payload.get("icon_emoji"):
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
                pieces.append(element.tame(check_text_block())["text"])
        return "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")
    elif block_type == "divider":
        return "----"
    elif block_type == "header":
        return "## " + block["text"].tame(check_text_block(plain_text_only=True))["text"]
    elif block_type == "image":
        image_url = block["image_url"].tame(check_url)
        alt_text = block["alt_text"].tame(check_string)
        if "title" in block:
            alt_text = block["title"].tame(check_text_block(plain_text_only=True))["text"]
        return f"[{alt_text}]({image_url})"
    elif block_type == "input":
        # Unhandled
        pass
    elif block_type == "section":
        pieces = []
        if "text" in block:
            pieces.append(block["text"].tame(check_text_block())["text"])

        if "accessory" in block:
            pieces.append(render_block_element(block["accessory"]))

        if "fields" in block:
            fields = block["fields"].tame(check_list(check_text_block()))
            if len(fields) == 1:
                # Special-case a single field to display a bit more
                # nicely, without extraneous borders and limitations
                # on its contents.
                pieces.append(fields[0]["text"])
            else:
                # It is not possible to have newlines in a table, nor
                # escape the pipes that make it up; replace them with
                # whitespace.
                field_text = [f["text"].replace("\n", " ").replace("|", " ") for f in fields]
                # Because Slack formats this as two columns, but not
                # necessarily a table with a bold header, we emit a
                # blank header row first.
                table = "| | |\n|-|-|\n"
                # Then take the fields two-at-a-time to make the table
                iters = [iter(field_text)] * 2
                for left, right in zip_longest(*iters, fillvalue=""):
                    table += f"| {left} | {right} |\n"
                pieces.append(table)

        return "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")

    return ""


class TextField(TypedDict):
    text: str
    type: Literal["plain_text", "mrkdwn"]


def check_text_block(plain_text_only: bool = False) -> Validator[TextField]:
    if plain_text_only:
        type_validator = check_string_in(["plain_text"])
    else:
        type_validator = check_string_in(["plain_text", "mrkdwn"])

    def f(var_name: str, val: object) -> TextField:
        block = check_dict(
            [
                ("type", type_validator),
                ("text", check_string),
            ],
        )(var_name, val)

        return cast(TextField, block)

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
    if attachment.get("title"):
        title = attachment["title"].tame(check_string)
        if attachment.get("title_link"):
            title_link = attachment["title_link"].tame(check_url)
            pieces.append(f"## [{title}]({title_link})")
        else:
            pieces.append(f"## {title}")
    if attachment.get("pretext"):
        pieces.append(attachment["pretext"].tame(check_string))
    if attachment.get("text"):
        pieces.append(attachment["text"].tame(check_string))
    if "fields" in attachment:
        fields = []
        for field in attachment["fields"]:
            if "title" in field and "value" in field and field["title"] and field["value"]:
                title = field["title"].tame(check_string)
                value = field["value"].tame(check_string)
                fields.append(f"*{title}*: {value}")
            elif field.get("title"):
                title = field["title"].tame(check_string)
                fields.append(f"*{title}*")
            elif field.get("value"):
                value = field["value"].tame(check_string)
                fields.append(f"{value}")
        pieces.append("\n".join(fields))
    if attachment.get("blocks"):
        pieces += map(render_block, attachment["blocks"])
    if attachment.get("image_url"):
        pieces.append("[]({})".format(attachment["image_url"].tame(check_url)))
    if attachment.get("footer"):
        pieces.append(attachment["footer"].tame(check_string))
    if attachment.get("ts"):
        time = attachment["ts"].tame(check_int)
        pieces.append(f"<time:{time}>")

    return "\n\n".join(piece.strip() for piece in pieces if piece.strip() != "")


def replace_links(text: str) -> str:
    return re.sub(r"<(\w+?:\/\/.*?)\|(.*?)>", r"[\2](\1)", text)


def replace_formatting(text: str) -> str:
    # Slack uses *text* for bold, whereas Zulip interprets that as italics
    text = re.sub(r"([^\w]|^)\*(?!\s+)([^\*\n]+)(?<!\s)\*((?=[^\w])|$)", r"\1**\2**\3", text)

    # Slack uses _text_ for emphasis, whereas Zulip interprets that as nothing
    text = re.sub(r"([^\w]|^)[_](?!\s+)([^\_\n]+)(?<!\s)[_]((?=[^\w])|$)", r"\1*\2*\3", text)
    return text
