from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import AnomalousWebhookPayloadError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

EVENTS: dict[str, str] = {
    "project:created": "project",
    "project:updated": "project",
    "work_package:created": "work_package",
    "work_package:updated": "work_package",
    "time_entry:created": "time_entry",
    "attachment:created": "attachment",
}

WORKPACKAGE_TYPES: list[str] = [
    "Task",
    "Milestone",
    "Phase",
]

PROJECT_MESSAGE_TEMPLATE = """
Project **{name}** was {action_status}.
"""

WORK_PACKAGE_MESSAGE_TEMPLATE = """
Work Package **{subject}** of type **{type}** was {action_status}.
"""

ATTATCHMENT_MESSAGE_TEMPLATE = """
A file **{filename}** was uploaded.
"""

TIME_ENTRY_MESSAGE_TEMPLATE = """
A time entry of **{hours}** was {action_status} for project **{project}**.
"""

ALL_EVENT_TYPES: list[str] = list(EVENTS.keys())


@webhook_view("OpenProject", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_openproject_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    try:
        action: str = payload["action"].tame(check_string)

        action_status: str = action.split(":")[1]

        action_data: WildValue = payload[EVENTS[action]]
        topic: str = EVENTS[action].replace("_", " ").title()

        match EVENTS[action]:
            case "project":
                message = PROJECT_MESSAGE_TEMPLATE.format(
                    name=action_data["name"].tame(check_string),
                    action_status=action_status,
                )
            case "work_package":
                message = WORK_PACKAGE_MESSAGE_TEMPLATE.format(
                    subject=action_data["subject"].tame(check_string),
                    type=action_data["_embedded"]["type"]["name"].tame(check_string),
                    action_status=action_status,
                )
            case "attachment":
                message = ATTATCHMENT_MESSAGE_TEMPLATE.format(
                    filename=action_data["fileName"].tame(check_string)
                )
            case "time_entry":
                message = TIME_ENTRY_MESSAGE_TEMPLATE.format(
                    hours=action_data["hours"].tame(check_string).split("T")[1],
                    project=action_data["_embedded"]["project"]["name"].tame(check_string),
                    action_status=action_status,
                )

        check_send_webhook_message(request, user_profile, topic, message)
        return json_success(request)
    except ValidationError:
        raise AnomalousWebhookPayloadError
