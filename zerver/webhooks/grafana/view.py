from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import (
    WildValue,
    check_anything,
    check_float,
    check_int,
    check_none_or,
    check_string,
    check_string_in,
    check_union,
)
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

OLD_TOPIC_TEMPLATE = "{alert_title}"

ALERT_STATUS_TEMPLATE = "{alert_icon} **{alert_state}**\n\n"

OLD_MESSAGE_TEMPLATE = "{alert_status}[{rule_name}]({rule_url})\n\n{alert_message}{eval_matches}"

NEW_TOPIC_TEMPLATE = "[{alertname}]"

START_TIME_TEMPLATE = "This alert was fired at <time:{start_time}>."

END_TIME_TEMPLATE = "\n\nThis alert was resolved at <time:{end_time}>."

MESSAGE_LABELS_TEMPLATE = "\n\nLabels:\n{label_information}\n"

MESSAGE_VALUES_TEMPLATE = "Values:\n{value_information}\n"

MESSAGE_ANNOTATIONS_TEMPLATE = "Annotations:\n{annotation_information}"

MESSAGE_GENERATOR_TEMPLATE = "\n[Generator]({generator_url})"

MESSAGE_SILENCE_TEMPLATE = "\n[Silence]({silence_url})"

MESSAGE_IMAGE_TEMPLATE = "\n[Image]({image_url})"

LEGACY_EVENT_TYPES = ["ok", "pending", "alerting", "paused"]

NEW_EVENT_TYPES = ["firing", "resolved"]

ALL_EVENT_TYPES = LEGACY_EVENT_TYPES + NEW_EVENT_TYPES


@webhook_view("Grafana", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_grafana_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    # Grafana alerting system.
    if "alerts" in payload:
        # Grafana 8.0 and above alerting; works for:
        # - https://grafana.com/docs/grafana/v8.0/alerting/unified-alerting/message-templating/template-data/
        # - https://grafana.com/docs/grafana/v9.0/alerting/contact-points/notifiers/webhook-notifier/
        # - https://grafana.com/docs/grafana/v10.0/alerting/alerting-rules/manage-contact-points/webhook-notifier/
        # - https://grafana.com/docs/grafana/v11.0/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/
        for alert in payload["alerts"]:
            status = alert["status"].tame(check_string_in(["firing", "resolved"]))
            if status == "firing":
                body = ALERT_STATUS_TEMPLATE.format(
                    alert_icon=":alert:", alert_state=status.upper()
                )
            else:
                body = ALERT_STATUS_TEMPLATE.format(
                    alert_icon=":checkbox:", alert_state=status.upper()
                )

            if "alertname" in alert["labels"] and alert["labels"]["alertname"]:
                alertname = alert["labels"]["alertname"].tame(check_string)
                topic_name = NEW_TOPIC_TEMPLATE.format(alertname=alertname)
                body += "**" + alertname + "**\n\n"
            else:
                # if no alertname, fallback to the alert fingerprint
                topic_name = NEW_TOPIC_TEMPLATE.format(
                    alertname=alert["fingerprint"].tame(check_string)
                )

            body += START_TIME_TEMPLATE.format(start_time=alert["startsAt"].tame(check_string))

            end_time = alert["endsAt"].tame(check_string)
            if end_time != "0001-01-01T00:00:00Z":
                body += END_TIME_TEMPLATE.format(end_time=end_time)

            if alert["labels"]:
                label_information = ""
                for key, value in alert["labels"].items():
                    label_information += "- " + key + ": " + value.tame(check_string) + "\n"
                body += MESSAGE_LABELS_TEMPLATE.format(label_information=label_information)

            if alert.get("values"):
                value_information = ""
                for key, value in alert["values"].items():
                    value_information += "- " + key + ": " + str(value.tame(check_anything)) + "\n"
                body += MESSAGE_VALUES_TEMPLATE.format(value_information=value_information)
            elif alert.get("valueString"):
                body += (
                    MESSAGE_VALUES_TEMPLATE.format(
                        value_information=alert["valueString"].tame(check_string)
                    )
                    + "\n"
                )

            if alert["annotations"]:
                annotation_information = ""
                for key, value in alert["annotations"].items():
                    annotation_information += "- " + key + ": " + value.tame(check_string) + "\n"
                body += MESSAGE_ANNOTATIONS_TEMPLATE.format(
                    annotation_information=annotation_information
                )

            if alert["generatorURL"]:
                body += MESSAGE_GENERATOR_TEMPLATE.format(
                    generator_url=alert["generatorURL"].tame(check_string)
                )

            if alert["silenceURL"]:
                body += MESSAGE_SILENCE_TEMPLATE.format(
                    silence_url=alert["silenceURL"].tame(check_string)
                )

            if alert.get("imageURL"):
                body += MESSAGE_IMAGE_TEMPLATE.format(
                    image_url=alert["imageURL"].tame(check_string)
                )

            body += "\n"

            check_send_webhook_message(request, user_profile, topic_name, body, status)

        return json_success(request)

    else:
        # Grafana 7.0 alerts:
        # https://grafana.com/docs/grafana/v7.0/alerting/notifications/#webhook
        topic_name = OLD_TOPIC_TEMPLATE.format(alert_title=payload["title"].tame(check_string))

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
        check_send_webhook_message(request, user_profile, topic_name, body, state)

        return json_success(request)
