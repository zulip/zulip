from django.http import HttpRequest, HttpResponse
from pydantic.alias_generators import to_snake

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
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
@typed_endpoint
def api_appveyor_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    body = get_body(payload)
    topic_name = get_topic_name(payload)

    check_send_webhook_message(request, user_profile, topic_name, body)
    return json_success(request)


def get_topic_name(payload: WildValue) -> str:
    event_data = payload["eventData"]
    return APPVEYOR_TOPIC_TEMPLATE.format(project_name=event_data["projectName"].tame(check_string))


def get_body(payload: WildValue) -> str:
    event_data = payload["eventData"]
    fields = [
        "projectName",
        "buildVersion",
        "status",
        "buildUrl",
        "commitUrl",
        "committerName",
        "commitDate",
        "commitMessage",
        "commitId",
        "started",
        "finished",
    ]
    data = {to_snake(field): event_data[field].tame(check_string) for field in fields}

    return APPVEYOR_MESSAGE_TEMPLATE.format(**data)
