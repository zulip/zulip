from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import (
    WildValue,
    check_float,
    check_int,
    check_none_or,
    check_string,
    check_string_in,
    check_union,
    to_wild_value,
)
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

GRAFANA_TOPIC_TEMPLATE = "{alert_title}"

GRAFANA_ALERT_STATUS_TEMPLATE = "{alert_icon} **{alert_state}**\n\n"

GRAFANA_MESSAGE_TEMPLATE = (
    "{alert_status}[{rule_name}]({rule_url})\n\n{alert_message}{eval_matches}"
)

ALL_EVENT_TYPES = ["ok", "pending", "alerting", "paused"]


@webhook_view("Grafana", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_grafana_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:

    topic = GRAFANA_TOPIC_TEMPLATE.format(alert_title=payload["title"].tame(check_string))

    eval_matches_text = ""
    if "evalMatches" in payload and payload["evalMatches"] is not None:
        for match in payload["evalMatches"]:
            eval_matches_text += "**{}:** {}\n".format(
                match["metric"].tame(check_string),
                match["value"].tame(check_none_or(check_union([check_int, check_float]))),
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

    body = GRAFANA_MESSAGE_TEMPLATE.format(
        alert_message=message_text,
        alert_status=alert_status,
        rule_name=payload["ruleName"].tame(check_string),
        rule_url=payload["ruleUrl"].tame(check_string),
        eval_matches=eval_matches_text,
    )

    if "imageUrl" in payload:
        body += "\n[Click to view visualization]({visualization})".format(
            visualization=payload["imageUrl"].tame(check_string)
        )

    body = body.strip()

    # send the message
    check_send_webhook_message(request, user_profile, topic, body, state)

    return json_success(request)
