from typing import Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict, check_list, check_string
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


@webhook_view("OpsGenie", all_event_types=ALL_EVENT_TYPES)
@has_request_variables
def api_opsgenie_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, object] = REQ(argument_type="body", json_validator=check_dict()),
) -> HttpResponse:
    alert = check_dict()("alert", payload.get("alert"))

    # construct the body of the message
    info = {
        "additional_info": "",
        "alert_type": check_string("action", payload.get("action")),
        "alert_id": check_string("alert alertId", alert.get("alertId")),
        "integration_name": check_string("integrationName", payload.get("integrationName")),
        "tags": ", ".join(
            "`" + tag + "`" for tag in check_list(check_string)("alert tags", alert.get("tags", []))
        ),
    }

    topic = info["integration_name"]
    bullet_template = "* **{key}**: {value}\n"

    if "note" in alert:
        info["additional_info"] += bullet_template.format(
            key="Note",
            value=alert["note"],
        )
    if "recipient" in alert:
        info["additional_info"] += bullet_template.format(
            key="Recipient",
            value=alert["recipient"],
        )
    if "addedTags" in alert:
        info["additional_info"] += bullet_template.format(
            key="Tags added",
            value=alert["addedTags"],
        )
    if "team" in alert:
        info["additional_info"] += bullet_template.format(
            key="Team added",
            value=alert["team"],
        )
    if "owner" in alert:
        info["additional_info"] += bullet_template.format(
            key="Assigned owner",
            value=alert["owner"],
        )
    if "escalationName" in payload:
        info["additional_info"] += bullet_template.format(
            key="Escalation",
            value=payload["escalationName"],
        )
    if "removedTags" in alert:
        info["additional_info"] += bullet_template.format(
            key="Tags removed",
            value=alert["removedTags"],
        )
    if "message" in alert:
        info["additional_info"] += bullet_template.format(
            key="Message",
            value=alert["message"],
        )
    if info["tags"]:
        info["additional_info"] += bullet_template.format(
            key="Tags",
            value=info["tags"],
        )

    body_template = """
[OpsGenie alert for {integration_name}](https://app.opsgenie.com/alert/V2#/show/{alert_id}):
* **Type**: {alert_type}
{additional_info}
""".strip()

    body = body_template.format(**info)
    check_send_webhook_message(request, user_profile, topic, body, info["alert_type"])

    return json_success()
