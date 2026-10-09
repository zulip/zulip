# Webhooks for external integrations.

from typing import Annotated

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import ApiParamConfig, JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ALERTMANAGER_SEVERITY_EMOJI = {
    "critical": ":alert:",
    "emergency": ":alert:",
    "fatal": ":alert:",
    "error": ":alert:",
    "warning": ":warning:",
    "warn": ":warning:",
    "major": ":warning:",
    "info": ":info:",
    "notice": ":info:",
    "low": ":info:",
    "debug": ":info:",
}


@webhook_view("Alertmanager")
@typed_endpoint
def api_alertmanager_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    name_field: Annotated[str, ApiParamConfig("name")] = "instance",
    desc_field: Annotated[str, ApiParamConfig("desc")] = "alertname",
) -> HttpResponse:
    topics: dict[str, dict[str, list[str]]] = {}

    for alert in payload["alerts"]:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        name = labels.get(name_field, annotations.get(name_field, "(unknown)")).tame(check_string)
        desc = labels.get(
            desc_field, annotations.get(desc_field, f"<missing field: {desc_field}>")
        ).tame(check_string)

        if "generatorURL" in alert:
            url = alert["generatorURL"].tame(check_string).replace("tab=1", "tab=0")
            body = f"{desc} ([source]({url}))"
        else:
            body = desc

        status_str = alert["status"].tame(check_string)
        if status_str == "resolved":
            emoji = ":squared_ok:"
        else:
            severity = ""
            if "severity" in labels:
                severity = labels["severity"].tame(check_string).lower()
            emoji = ALERTMANAGER_SEVERITY_EMOJI.get(severity, ":alert:")

        body = f"{emoji} {body}"

        if name not in topics:
            topics[name] = {"firing": [], "resolved": []}
        topics[name][status_str].append(body)

    for topic_name, statuses in topics.items():
        for status, messages in statuses.items():
            if len(messages) == 0:
                continue

            if status == "firing":
                title = "FIRING"
            else:
                title = "Resolved"

            if len(messages) == 1:
                body = f"**{title}** {messages[0]}".strip()
            else:
                message_list = "\n".join(f"* {m}" for m in messages)
                body = f"**{title}**\n{message_list}".strip()

            check_send_webhook_message(request, user_profile, topic_name, body)

    return json_success(request)
