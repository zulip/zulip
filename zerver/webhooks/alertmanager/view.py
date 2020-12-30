# Webhooks for external integrations.
from typing import Any, Dict, List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view('Alertmanager')
@has_request_variables
def api_alertmanager_webhook(request: HttpRequest, user_profile: UserProfile,
                             payload: Dict[str, Any] = REQ(argument_type='body')) -> HttpResponse:
    name_field = request.GET.get("name", "instance")
    desc_field = request.GET.get("desc", "alertname")
    topics: Dict[str, Dict[str, List[str]]] = {}

    for alert in payload["alerts"]:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        name = labels.get(
            name_field, annotations.get(name_field, "(unknown)"))
        desc = labels.get(
            desc_field, annotations.get(desc_field, f"<missing field: {desc_field}>"))

        url = alert.get("generatorURL").replace("tab=1", "tab=0")

        body = f"{desc} ([graph]({url}))"
        if name not in topics:
            topics[name] = {"firing": [], "resolved": []}
        topics[name][alert["status"]].append(body)

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

    return json_success()
