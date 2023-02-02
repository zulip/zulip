from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

APPVEYOR_TOPIC_TEMPLATE = "{project_name}"
APPVEYOR_MESSAGE_TEMPLATE = """
[Build {project_name} {build_version} {status}]({build_url}):
* **Commit**: [{commit_id}: {commit_message}]({commit_url}) by {committer_name}
* **Started**: {started}
* **Finished**: {finished}
""".strip()


@webhook_view("Appveyor")
@has_request_variables
def api_appveyor_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    body = get_body_for_http_request(payload)
    subject = get_subject_for_http_request(payload)

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success(request)


def get_subject_for_http_request(payload: WildValue) -> str:
    event_data = payload["eventData"]
    return APPVEYOR_TOPIC_TEMPLATE.format(project_name=event_data["projectName"].tame(check_string))


def get_body_for_http_request(payload: WildValue) -> str:
    event_data = payload["eventData"]

    data = {
        "project_name": event_data["projectName"].tame(check_string),
        "build_version": event_data["buildVersion"].tame(check_string),
        "status": event_data["status"].tame(check_string),
        "build_url": event_data["buildUrl"].tame(check_string),
        "commit_url": event_data["commitUrl"].tame(check_string),
        "committer_name": event_data["committerName"].tame(check_string),
        "commit_date": event_data["commitDate"].tame(check_string),
        "commit_message": event_data["commitMessage"].tame(check_string),
        "commit_id": event_data["commitId"].tame(check_string),
        "started": event_data["started"].tame(check_string),
        "finished": event_data["finished"].tame(check_string),
    }
    return APPVEYOR_MESSAGE_TEMPLATE.format(**data)
