from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import (
    check_float,
    check_int,
    check_string,
    check_string_in,
    check_union,
    check_url,
    to_wild_value,
    WildValue,
)
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile
from zerver.webhooks.alertmanager.view import alertmanager_hook

GRAFANA_TOPIC_TEMPLATE = "{alert_title}"

GRAFANA_ALERT_STATUS_TEMPLATE = "{alert_icon} **{alert_state}**\n\n"

GRAFANA8_MESSAGE_TEMPLATE = "{alert_status}{rule}\n\n{alert_message}{eval_matches}"

ALL_EVENT_TYPES = ["ok", "pending", "alerting", "paused"]


@webhook_view("Grafana", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_grafana_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:

    if "version" not in payload:
        # Version 9.0.0 changed alerting, and the payload for webhooks, significantly.  Recognize the new format via the `version` key: https://github.com/grafana/grafana/blob/v9.0.0/pkg/services/ngalert/notifier/channels/webhook.go#L98
        return grafana_v8_webhook(request, user_profile, payload)
    version = payload["version"].tame(check_string)
    if version == "1":
        return grafana_v9_webhook(request, user_profile, payload)
    else:
        raise UnsupportedWebhookEventType(f'version = "{version}"')


def grafana_v8_webhook(
    request: HttpRequest, user_profile: UserProfile, payload: WildValue
) -> HttpResponse:
    # Webhook content has no specification, but is output from
    # https://github.com/grafana/grafana/blob/v8.5.x/pkg/services/alerting/notifiers/webhook.go

    topic = GRAFANA_TOPIC_TEMPLATE.format(alert_title=payload["title"].tame(check_string))

    eval_matches_text = ""
    if "evalMatches" in payload and payload["evalMatches"]:
        for match in payload["evalMatches"]:
            eval_matches_text += "**{}:** {}\n".format(
                match["metric"].tame(check_string),
                match["value"].tame(check_union([check_float, check_int])),
            )

    message_text = ""
    if "message" in payload:
        message_text = payload["message"].tame(check_string) + "\n\n"

    state = payload["state"].tame(
        check_string_in(["no_data", "paused", "alerting", "ok", "pending", "unknown"])
    )

    if state == "alerting":
        alert_status = GRAFANA_ALERT_STATUS_TEMPLATE.format(
            alert_icon=":alert:", alert_state=state.upper()
        )
    elif state == "ok":
        alert_status = GRAFANA_ALERT_STATUS_TEMPLATE.format(
            alert_icon=":squared_ok:", alert_state=state.upper()
        )
    else:
        alert_status = GRAFANA_ALERT_STATUS_TEMPLATE.format(
            alert_icon=":info:", alert_state=state.upper()
        )

    rule = payload["ruleName"].tame(check_string)
    if "ruleUrl" in payload:
        rule = f"[{rule}]({payload['ruleUrl'].tame(check_url)})"

    body = GRAFANA8_MESSAGE_TEMPLATE.format(
        alert_message=message_text,
        alert_status=alert_status,
        rule=rule,
        eval_matches=eval_matches_text,
    )

    if "imageUrl" in payload is not None:
        body += "\n[Click to view visualization]({visualization})".format(
            visualization=payload["imageUrl"].tame(check_url)
        )

    body = body.strip()

    # send the message
    check_send_webhook_message(request, user_profile, topic, body, state)

    return json_success(request)


def grafana_v9_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue,
    name_field: str = REQ("name", default="instance"),
    desc_field: str = REQ("desc", default="alertname"),
) -> HttpResponse:
    return alertmanager_hook(request, user_profile, payload, name_field, desc_field, grafana_v9_parts)

def grafana_v9_parts(alert: WildValue) -> Dict[str, str]:
    # These use check_string and not check_url because the latter does
    # not support URLs without hostname or TLD, which may be common
    # for internal services like grafana:
    # https://code.djangoproject.com/ticket/25418

    links = {
        "alert": alert.get("generatorURL").tame(check_string),
        "silence": alert.get("silenceURL").tame(check_string),
    }
    if panel := alert.get("panelURL").tame(check_string):
        links["panel"] = panel
    if image := alert.get("imageURL","").tame(check_string):
        links["graph"] = image
    return links
