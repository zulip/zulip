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

OLD_TOPIC_TEMPLATE = "{alert_title}"

ALERT_STATUS_TEMPLATE = "{alert_icon} **{alert_state}**\n\n"

OLD_MESSAGE_TEMPLATE = "{alert_status}[{rule_name}]({rule_url})\n\n{alert_message}{eval_matches}"

NEW_TOPIC_TEMPLATE = "[{alert_status}:{alert_count}]"

ALERT_HEADER_TEMPLATE = """\n---
**Alert {count}**"""

START_TIME_TEMPLATE = "\n\nThis alert was fired at <time:{start_time}>.\n"

END_TIME_TEMPLATE = "\nThis alert was resolved at <time:{end_time}>.\n\n"

MESSAGE_LABELS_TEMPLATE = "Labels:\n{label_information}\n"

MESSAGE_ANNOTATIONS_TEMPLATE = "Annotations:\n{annotation_information}\n"

TRUNCATED_ALERTS_TEMPLATE = "{count} alert(s) truncated.\n"

LEGACY_EVENT_TYPES = ["ok", "pending", "alerting", "paused"]

NEW_EVENT_TYPES = ["firing", "resolved"]

ALL_EVENT_TYPES = LEGACY_EVENT_TYPES + NEW_EVENT_TYPES


@webhook_view("Grafana", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_grafana_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    # Grafana alerting system.
    if "alerts" in payload:
        status = payload["status"].tame(check_string_in(["firing", "resolved"]))
        alert_count = len(payload["alerts"])

        topic = NEW_TOPIC_TEMPLATE.format(alert_status=status.upper(), alert_count=alert_count)

        if status == "firing":
            body = ALERT_STATUS_TEMPLATE.format(alert_icon=":alert:", alert_state=status.upper())
        else:
            body = ALERT_STATUS_TEMPLATE.format(alert_icon=":checkbox:", alert_state=status.upper())

        if payload["message"]:
            body += payload["message"].tame(check_string) + "\n"

        for index, alert in enumerate(payload["alerts"], 1):
            body += ALERT_HEADER_TEMPLATE.format(count=index)

            if "alertname" in alert["labels"] and alert["labels"]["alertname"]:
                body += ": " + alert["labels"]["alertname"].tame(check_string) + "."

            body += START_TIME_TEMPLATE.format(start_time=alert["startsAt"].tame(check_string))

            end_time = alert["endsAt"].tame(check_string)
            if end_time != "0001-01-01T00:00:00Z":
                body += END_TIME_TEMPLATE.format(end_time=end_time)

            if alert["labels"]:
                label_information = ""
                for key, value in alert["labels"].items():
                    label_information += "- " + key + ": " + value.tame(check_string) + "\n"
                body += MESSAGE_LABELS_TEMPLATE.format(label_information=label_information)

            if alert["annotations"]:
                annotation_information = ""
                for key, value in alert["annotations"].items():
                    annotation_information += "- " + key + ": " + value.tame(check_string) + "\n"
                body += MESSAGE_ANNOTATIONS_TEMPLATE.format(
                    annotation_information=annotation_information
                )

        if payload["truncatedAlerts"]:
            body += TRUNCATED_ALERTS_TEMPLATE.format(
                count=payload["truncatedAlerts"].tame(check_int)
            )

        check_send_webhook_message(request, user_profile, topic, body, status)

        return json_success(request)

    # Legacy Grafana alerts.
    else:
        topic = OLD_TOPIC_TEMPLATE.format(alert_title=payload["title"].tame(check_string))

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
            alert_status = ALERT_STATUS_TEMPLATE.format(
                alert_icon=":alert:", alert_state=state.upper()
            )
        elif state == "ok":
            alert_status = ALERT_STATUS_TEMPLATE.format(
                alert_icon=":squared_ok:", alert_state=state.upper()
            )
        else:
            alert_status = ALERT_STATUS_TEMPLATE.format(
                alert_icon=":info:", alert_state=state.upper()
            )

        body = OLD_MESSAGE_TEMPLATE.format(
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
