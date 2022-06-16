# Webhooks for external integrations.
import re
from typing import Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import REQ, RequestVariableMissingError, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, WildValueDict, check_string, check_url, to_wild_value
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
    block_type = block["type"].tame(check_string)
    if block_type == "section":
        body = ""
        if "text" in block:
            text = block["text"]
            while isinstance(text, WildValueDict):
                text = text["text"]
            body += "\n\n" + text.tame(check_string)

        if "accessory" in block:
            accessory = block["accessory"]
            accessory_type = accessory["type"].tame(check_string)
            if accessory_type == "image":
                # This should become ![text](url) once proper Markdown images are supported
                alt_text = accessory["alt_text"].tame(check_string)
                image_url = accessory["image_url"].tame(check_url)
                body += f"\n[{alt_text}]({image_url})"
        return body

    return ""


def render_attachment(attachment: WildValue) -> str:
    attachment_body = ""
    if "title" in attachment and "title_link" in attachment:
        title = attachment["title"].tame(check_string)
        title_link = attachment["title_link"].tame(check_string)
        attachment_body += f"[{title}]({title_link})\n"
    if "text" in attachment:
        attachment_body += attachment["text"].tame(check_string)

    return attachment_body


def replace_links(text: str) -> str:
    return re.sub(r"<(\w+?:\/\/.*?)\|(.*?)>", r"[\2](\1)", text)


def replace_formatting(text: str) -> str:
    # Slack uses *text* for bold, whereas Zulip interprets that as italics
    text = re.sub(r"([^\w])\*(?!\s+)([^\*^\n]+)(?<!\s)\*([^\w])", r"\1**\2**\3", text)

    # Slack uses _text_ for emphasis, whereas Zulip interprets that as nothing
    text = re.sub(r"([^\w])[_](?!\s+)([^\_\^\n]+)(?<!\s)[_]([^\w])", r"\1*\2*\3", text)
    return text
