from django.http import HttpRequest, HttpResponse, JsonResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_dict, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile


@webhook_view("OpenProject")
@typed_endpoint
def api_openproject_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    event_type_raw = next(iter(payload.values()))
    event_type = event_type_raw.tame(check_string).split(":")[1]

    heading = list(payload.keys())[1]
    data_raw = list(payload.values())[1]
    data = data_raw.tame(check_dict({}))
    _type = data.get("_type")

    if not event_type or not data or not heading:
        return JsonResponse({"error": "Missing required fields"}, status=400)  # nocoverage

    message = ""
    topic = ""

    if heading == "project":
        topic = "Project"
        name = data.get("name")
        message = f"Project **{name}** got {event_type}"
    elif heading == "work_package":
        topic = "Work Package"
        subject = data.get("subject")
        message = f"Work Package **{subject}** of type {_type} got {event_type}"
    elif heading == "time_entry":
        topic = "Time Entry"
        hours = data.get("hours")
        if not isinstance(hours, str):
            return JsonResponse(
                {"error": "Expected 'hours' to be a string"}, status=400
            )  # nocoverage

        _embedded = data.get("_embedded")
        if not isinstance(_embedded, dict):
            return JsonResponse(
                {"error": "Expected 'project' to be a dictionary"}, status=400
            )  # nocoverage
        project = _embedded["project"]["name"]
        time_entry = hours.split("T")[1]
        message = f"Time Entry of **{time_entry}** got {event_type} for project **{project}**"
    elif heading == "attachment":
        topic = "File Uploaded"
        filename = data.get("fileName")
        message = f"File Uploaded of name **{filename}**"

    check_send_webhook_message(request, user_profile, topic, message)
    return json_success(request)
