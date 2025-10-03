from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

DBT_EVENT_TYPE_MAPPER = {
    "job.run.started": (":yellow_circle:", "started"),
    "job.run.completed": (":green_circle:", "succeeded"),
    "job.run.errored": (":cross_mark:", "failed"),
}

ALL_EVENT_TYPES = list(DBT_EVENT_TYPE_MAPPER.keys())


def extract_data_from_payload(payload: JsonBodyPayload[WildValue]) -> dict[str, str]:
    data: dict[str, str] = {
        "event_type": payload["eventType"].tame(check_string),
        "job_id": payload["data"]["jobId"].tame(check_string),
        "job_name": payload["data"]["jobName"].tame(check_string),
        "project_name": payload["data"]["projectName"].tame(check_string),
        "environment": payload["data"]["environmentName"].tame(check_string),
        "run_reason": payload["data"]["runReason"].tame(check_string).lower(),
        "start_time": payload["data"]["runStartedAt"].tame(check_string),
    }
    end_time = payload["data"].get("runErroredAt") or payload["data"].get("runFinishedAt")
    data["end_time"] = end_time.tame(check_string) if end_time else ""
    return data


def get_job_run_body(data: dict[str, str]) -> str:
    template = """{emoji} {job_name} deployment {status} in {environment}.
{job_id} was {run_reason} at <time:{start_time}>."""

    emoji, status = DBT_EVENT_TYPE_MAPPER[data["event_type"]]
    body = template.format(emoji=emoji, status=status, **data)

    if data.get("event_type") == "job.run.errored":
        body += f"\n**Failed at**: <time:{data['end_time']}>"
    elif data.get("event_type") == "job.run.completed":
        body += f"\n**Finished at**: <time:{data['end_time']}>"

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
    check_send_webhook_message(request, user_profile, topic_name, body)
    return json_success(request)
