from typing import TypedDict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

RUNDECK_MESSAGE_TEMPLATE = "{emoji}[{job_name}]({job_link}) execution [#{execution_id}]({execution_link}) for {project_name} {status}."

RUNDECK_TOPIC_TEMPLATE = "{project_name} - {job_name}"

# https://docs.rundeck.com/docs/api/#listing-running-executions:~:text=The%20%5Bstatus%5D,the%20exit%20status.
STATUS_MAP = {
    "failed": ("has failed", ":warning:"),
    "succeeded": ("has succeeded", ":check:"),
    "running": ("has started", ":running:"),
    "scheduled": ("is scheduled", ":clock:"),
    "aborted": ("was aborted", ":no_entry:"),
    "timedout": ("timed out", ":times_up:"),
    "failed-with-retry": ("failed and will retry", ":repeat:"),
}


class RundeckContext(TypedDict):
    job_name: str
    project_name: str
    job_link: str
    execution_id: int
    execution_link: str


@webhook_view("Rundeck")
@typed_endpoint
def api_rundeck_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    execution = payload["execution"]
    context = RundeckContext(
        job_name=execution["job"]["name"].tame(check_string),
        project_name=execution["project"].tame(check_string),
        job_link=execution["job"]["permalink"].tame(check_string),
        execution_id=execution["id"].tame(check_int),
        execution_link=execution["href"].tame(check_string),
    )

    topic_name = RUNDECK_TOPIC_TEMPLATE.format(**context)
    body = get_body(payload, execution, context)

    check_send_webhook_message(request, user_profile, topic_name, body)
    return json_success(request)


def get_body(payload: WildValue, execution: WildValue, context: RundeckContext) -> str:
    status_raw = execution["status"].tame(check_string)
    status_text, emoji = STATUS_MAP.get(status_raw, (f"is {status_raw}", ""))

    if status_raw == "other":
        custom_status = execution["customStatus"].tame(check_string)
        status_text = f"has status: {custom_status}"

    if status_raw == "running" and payload["trigger"].tame(check_string) == "avgduration":
        status_text = "is running long"
        emoji = ":time_ticking:"

    return RUNDECK_MESSAGE_TEMPLATE.format(
        **context, status=status_text, emoji=f"{emoji} " if emoji else ""
    )
