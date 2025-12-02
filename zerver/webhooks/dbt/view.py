from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

DBT_NOTIFICATION_TEMPLATE = """
{emoji} {job_name} deployment {status} in **{environment}**.

Job #{job_id} was {run_reason} at <time:{start_time}>.
"""

DBT_EVENT_TYPE_MAPPER = {
    "job.run.started": {
        "running": (":yellow_circle:", "started"),
    },
    "job.run.completed": {
        "success": (":green_circle:", "succeeded"),
        "errored": (":cross_mark:", "completed with errors"),
    },
    "job.run.errored": {
        "errored": (":cross_mark:", "failed"),
    },
}

ALL_EVENT_TYPES = list(DBT_EVENT_TYPE_MAPPER.keys())


def extract_data_from_payload(payload: JsonBodyPayload[WildValue]) -> dict[str, str]:
    data: dict[str, str] = {
        "event_type": payload["eventType"].tame(check_string),
        "job_id": payload["data"]["jobId"].tame(check_string),
        "job_name": payload["data"]["jobName"].tame(check_string),
        "project_name": payload["data"]["projectName"].tame(check_string),
        "environment": payload["data"]["environmentName"].tame(check_string),
        "start_time": payload["data"]["runStartedAt"].tame(check_string),
        "run_status": payload["data"]["runStatus"].tame(check_string).lower(),
    }
    # We only change the capitalization of the first letter in this
    # string for the formatting of our notification template.
    run_reason = payload["data"]["runReason"].tame(check_string)
    data["run_reason"] = run_reason[:1].lower() + run_reason[1:]
    return data


def get_job_run_body(data: dict[str, str]) -> str:
    emoji, status = DBT_EVENT_TYPE_MAPPER[data["event_type"]][data["run_status"]]
    body = DBT_NOTIFICATION_TEMPLATE.format(
        emoji=emoji,
        status=status,
        **data,
    )
    return body


@webhook_view("DBT", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_dbt_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    data = extract_data_from_payload(payload)
    body = get_job_run_body(data)
    topic_name = data["project_name"]
    event = data["event_type"]
    check_send_webhook_message(request, user_profile, topic_name, body, event)
    return json_success(request)
