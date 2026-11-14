# Webhooks for external integrations.

from typing import Annotated

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import ApiParamConfig, JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message, format_spoiler
from zerver.models import UserProfile


@webhook_view("Alertmanager")
@typed_endpoint
def api_alertmanager_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    name_field: Annotated[str, ApiParamConfig("name")] = "instance",
    desc_field: Annotated[str, ApiParamConfig("desc")] = "alertname",
    summary_field: Annotated[str, ApiParamConfig("summary")] = "summary",
    severity_field: Annotated[str, ApiParamConfig("severity")] = "severity",
) -> HttpResponse:
    topics: dict[str, list[str]] = {}
    shown_fields = {desc_field, summary_field, severity_field}

    for alert in payload["alerts"]:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        status = alert["status"].tame(check_string)

        name = labels.get(name_field, annotations.get(name_field, "(unknown)")).tame(check_string)
        desc = labels.get(
            desc_field, annotations.get(desc_field, f"<missing field: {desc_field}>")
        ).tame(check_string)
        summary = labels.get(summary_field, annotations.get(summary_field, desc)).tame(check_string)
        severity = labels.get(severity_field, annotations.get(severity_field, status)).tame(
            check_string
        )

        if status == "firing":
            icon = ":alert:"
            title = severity.upper()
        else:
            icon = ":squared_ok:"
            title = "RESOLVED"

        if "generatorURL" in alert:
            url = alert["generatorURL"].tame(check_string).replace("tab=1", "tab=0")
            header = f"{summary} ([source]({url}))"
        else:
            header = summary

        details = ["**Description:**", desc]
        if labels:
            details.append("\n**Labels:**")
            for key, value in sorted(labels.items()):
                if key not in shown_fields:
                    details.append(f"- {key}: {value.tame(check_string)}")
        if annotations:
            details.append("\n**Annotations:**")
            for key, value in sorted(annotations.items()):
                if key not in shown_fields:
                    details.append(f"- {key}: {value.tame(check_string)}")

        spoiler = format_spoiler("Details", "\n".join(details))
        body = f"{icon} **{title}: {header}**\n{spoiler}"

        if name not in topics:
            topics[name] = []
        topics[name].append(body)

    for topic_name, messages in topics.items():
        for body in messages:
            check_send_webhook_message(request, user_profile, topic_name, body)

    return json_success(request)
