from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ALL_EVENT_TYPES: list[str] = [
    "project:created",
    "project:updated",
    "work_package:created",
    "work_package:updated",
    "time_entry:created",
    "attachment:created",
]

WORKPACKAGE_TYPES: list[str] = ["Task", "Milestone", "Phase"]

PROJECT_MESSAGE_TEMPLATE = "Project **{name}** was {action}{parent_project_message}."

WORK_PACKAGE_MESSAGE_TEMPLATE = (
    "**{type}** work package **{subject}** was {action} by **{author}**."
)

ATTACHMENT_MESSAGE_TEMPLATE = (
    "**{author}** uploaded **{filename}** in {container_type} **{container_name}**."
)

TIME_ENTRY_MESSAGE_TEMPLATE = (
    "**{user}** {action} a time entry of **{hours}**{workpackage_message}."
)


@webhook_view("OpenProject", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_openproject_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    event_type: str = payload["action"].tame(check_string)

    item, action = event_type.split(":")

    action_data: WildValue = payload[item]
    topic: str

    match item:
        case "project":
            parent_project_message: str = ""
            parent_project: str = (
                action_data.get("_embedded", {})
                .get("parent", {})
                .get("name", "")
                .tame(check_string)
            )
            if parent_project and action == "created":
                parent_project_message = f" in project **{parent_project}**"
            message = PROJECT_MESSAGE_TEMPLATE.format(
                name=action_data["name"].tame(check_string),
                action=action,
                parent_project_message=parent_project_message,
            )
            topic = action_data["name"].tame(check_string)
        case "work_package":
            message = WORK_PACKAGE_MESSAGE_TEMPLATE.format(
                subject=action_data["subject"].tame(check_string),
                type=action_data["_embedded"]["type"]["name"].tame(check_string),
                action=action,
                author=action_data["_embedded"]["author"]["name"].tame(check_string),
            )
            topic = action_data["_embedded"]["project"]["name"].tame(check_string)
        case "attachment":
            message = ATTACHMENT_MESSAGE_TEMPLATE.format(
                filename=action_data["fileName"].tame(check_string),
                author=action_data["_embedded"]["author"]["name"].tame(check_string),
                container_type=action_data["_embedded"]["container"]["_type"]
                .tame(check_string)
                .lower(),
                container_name=action_data["_embedded"]["container"]["subject"].tame(check_string),
            )
            topic = action_data["_embedded"]["container"]["_links"]["project"]["title"].tame(
                check_string
            )
        case "time_entry":
            workpackage_message: str = ""
            workpackage: str = (
                action_data.get("_embedded", {})
                .get("workPackage", {})
                .get("subject", "")
                .tame(check_string)
            )
            if workpackage:
                workpackage_message = f" for **{workpackage}**"
            message = TIME_ENTRY_MESSAGE_TEMPLATE.format(
                hours=action_data["hours"].tame(check_string).split("T")[1],
                action=action,
                user=action_data["_embedded"]["user"]["name"].tame(check_string),
                workpackage_message=workpackage_message,
            )
            topic = action_data["_embedded"]["project"]["name"].tame(check_string)

    check_send_webhook_message(request, user_profile, topic, message)
    return json_success(request)
