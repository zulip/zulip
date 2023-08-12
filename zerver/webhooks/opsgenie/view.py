from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
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
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    # construct the body of the message
    info = {
        "additional_info": "",
        "alert_type": payload["action"].tame(check_string),
        "alert_id": payload["alert"]["alertId"].tame(check_string),
        "integration_name": payload["integrationName"].tame(check_string),
        "tags": ", ".join(
            "`" + tag.tame(check_string) + "`" for tag in payload["alert"].get("tags", [])
        ),
    }

    topic = info["integration_name"]
    bullet_template = "* **{key}**: {value}\n"

    if "note" in payload["alert"]:
        info["additional_info"] += bullet_template.format(
            key="Note",
            value=payload["alert"]["note"].tame(check_string),
        )
    if "recipient" in payload["alert"]:
        info["additional_info"] += bullet_template.format(
            key="Recipient",
            value=payload["alert"]["recipient"].tame(check_string),
        )
    if "addedTags" in payload["alert"]:
        info["additional_info"] += bullet_template.format(
            key="Tags added",
            value=payload["alert"]["addedTags"].tame(check_string),
        )
    if "team" in payload["alert"]:
        info["additional_info"] += bullet_template.format(
            key="Team added",
            value=payload["alert"]["team"].tame(check_string),
        )
    if "owner" in payload["alert"]:
        info["additional_info"] += bullet_template.format(
            key="Assigned owner",
            value=payload["alert"]["owner"].tame(check_string),
        )
    if "escalationName" in payload:
        info["additional_info"] += bullet_template.format(
            key="Escalation",
            value=payload["escalationName"].tame(check_string),
        )
    if "removedTags" in payload["alert"]:
        info["additional_info"] += bullet_template.format(
            key="Tags removed",
            value=payload["alert"]["removedTags"].tame(check_string),
        )
    if "message" in payload["alert"]:
        info["additional_info"] += bullet_template.format(
            key="Message",
            value=payload["alert"]["message"].tame(check_string),
        )
    if info["tags"]:
        info["additional_info"] += bullet_template.format(
            key="Tags",
            value=info["tags"],
        )

    body_template = """
[Opsgenie alert for {integration_name}](https://app.opsgenie.com/alert/V2#/show/{alert_id}):
* **Type**: {alert_type}
{additional_info}
""".strip()

    body = body_template.format(**info)
    check_send_webhook_message(request, user_profile, topic, body, info["alert_type"])

    return json_success(request)
