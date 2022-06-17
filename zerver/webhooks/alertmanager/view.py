# Webhooks for external integrations.
from typing import Callable, Dict, List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, check_url, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("Alertmanager")
@has_request_variables
def api_alertmanager_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
    name_field: str = REQ("name", default="instance"),
    desc_field: str = REQ("desc", default="alertname"),
) -> HttpResponse:
    return alertmanager_hook(
        request, user_profile, payload, name_field, desc_field, alertmanager_parts
    )


def alertmanager_parts(alert: WildValue) -> Dict[str, str]:
    # This uses check_string and not check_url because the latter does
    # not support URLs without hostname or TLD, which may be common
    # for internal services like alertmanager:
    # https://code.djangoproject.com/ticket/25418
    return {"graph": alert.get("generatorURL").tame(check_string).replace("tab=1", "tab=0")}


def alertmanager_hook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue,
    name_field: str,
    desc_field: str,
    alert_part_func: Callable[[WildValue], Dict[str, str]],
) -> HttpResponse:
    # https://prometheus.io/docs/alerting/latest/configuration/#webhook_config
    # Extended by Grafana in https://github.com/grafana/grafana/blob/main/pkg/services/ngalert/notifier/channels/template_data.go

    topics: Dict[str, Dict[str, List[str]]] = {}

    for alert in payload["alerts"]:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        name = labels.get(name_field, annotations.get(name_field, "(unknown)")).tame(check_string)
        desc = labels.get(
            desc_field, annotations.get(desc_field, f"<missing field: {str(desc_field)}>")
        ).tame(check_string)

        parts = " | ".join(f"[{k}]({v})" for k, v in sorted(alert_part_func(alert).items()))
        body = f"{desc} ({parts})"
        if name not in topics:
            topics[name] = {"firing": [], "resolved": []}
        topics[name][alert["status"].tame(check_string)].append(body)

    for topic, statuses in topics.items():
        for status, messages in statuses.items():
            if len(messages) == 0:
                continue

            if status == "firing":
                icon = ":alert:"
                title = "FIRING"
            else:
                title = "Resolved"
                icon = ":squared_ok:"

            if len(messages) == 1:
                body = f"{icon} **{title}** {messages[0]}"
            else:
                message_list = "\n".join(f"* {m}" for m in messages)
                body = f"{icon} **{title}**\n{message_list}"

            check_send_webhook_message(request, user_profile, topic, body)

    return json_success(request)
