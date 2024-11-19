# Webhooks for external integrations.
import re
from collections.abc import Callable
from functools import wraps
from typing import Concatenate

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.translation import gettext as _
from typing_extensions import ParamSpec

from zerver.data_import.slack_message_conversion import (
    convert_slack_formatting,
    render_attachment,
    render_block,
    replace_links,
)
from zerver.decorator import webhook_view
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import RequestVariableMissingError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.lib.validator import check_string, to_wild_value
from zerver.lib.webhooks.common import OptionalUserSpecifiedTopicStr, check_send_webhook_message
from zerver.models import UserProfile

ParamT = ParamSpec("ParamT")


def slack_error_handler(
    view_func: Callable[Concatenate[HttpRequest, ParamT], HttpResponse],
) -> Callable[Concatenate[HttpRequest, ParamT], HttpResponse]:
    """
    A decorator that catches JsonableError exceptions and returns a
    Slack-compatible error response in the format:
    {ok: false, error: "error message"}.
    """

    @wraps(view_func)
    def wrapped_view(
        request: HttpRequest, /, *args: ParamT.args, **kwargs: ParamT.kwargs
    ) -> HttpResponse:
        try:
            return view_func(request, *args, **kwargs)
        except JsonableError as error:
            return JsonResponse({"ok": False, "error": error.msg}, status=error.http_status_code)

    return wrapped_view


@webhook_view("SlackIncoming")
@typed_endpoint
@slack_error_handler
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

    pieces: list[str] = []
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
        body = convert_slack_formatting(replace_links(body).strip())
        check_send_webhook_message(request, user_profile, user_specified_topic, body)
    return json_success(request, data={"ok": True})
