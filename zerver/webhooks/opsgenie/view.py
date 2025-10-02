from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ALL_EVENT_TYPES = [
    "AddTeam",
    "UnAcknowledge",
    "AddNote",
    "TestAction",
    "Close",
    "Escalate",
    "AddRecipient",
    "RemoveTags",
    "Acknowledge",
    "Delete",
    "AddTags",
    "TakeOwnership",
    "Create",
    "AssignOwnership",
]


@webhook_view("Opsgenie", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_opsgenie_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
    eu_region: Json[bool] = False,
) -> HttpResponse:
    # construct the body of the message
    info = {
        "additional_info": "",
        "url_region": "eu." if eu_region else "",
        "alert_type": payload["action"].tame(check_string),
        "alert_id": payload["alert"]["alertId"].tame(check_string),
        "integration_name": payload["integrationName"].tame(check_string),
        "tags": ", ".join(
            "`" + tag.tame(check_string) + "`" for tag in payload["alert"].get("tags", [])
        ),
    }

    topic_name = info["integration_name"]
    bullet_template = "* **{key}**: {value}\n"

    fields = {
        "note": "Note",
        "recipient": "Recipient",
        "addedTags": "Tags added",
        "team": "Team added",
        "owner": "Assigned owner",
        "removedTags": "Tags removed",
        "message": "Message",
        "tags": "Tags",
        "escalationName": "Escalation",
    }

    for field, display_name in fields.items():
        if field == "tags" and info["tags"]:
            value = info["tags"]
        elif field == "escalationName" and field in payload:
            value = payload[field].tame(check_string)
        elif field in payload.get("alert", {}) and field != "tags":
            value = payload["alert"][field].tame(check_string)
        else:
            continue
        info["additional_info"] += bullet_template.format(key=display_name, value=value)

    body_template = """
[Opsgenie alert for {integration_name}](https://app.{url_region}opsgenie.com/alert/V2#/show/{alert_id}):
* **Type**: {alert_type}
{additional_info}
""".strip()

    body = body_template.format(**info)
    check_send_webhook_message(request, user_profile, topic_name, body, info["alert_type"])

    return json_success(request)
