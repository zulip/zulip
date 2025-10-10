import re
from urllib.parse import urljoin

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

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
        "account_id": str(payload["accountId"].tame(check_int)),
        "event_type": payload["eventType"].tame(check_string),
        "job_id": payload["data"]["jobId"].tame(check_string),
        "job_name": payload["data"]["jobName"].tame(check_string),
        "project_name": payload["data"]["projectName"].tame(check_string),
        "project_id": payload["data"]["projectId"].tame(check_string),
        "environment": payload["data"]["environmentName"].tame(check_string),
        "run_reason": payload["data"]["runReason"].tame(check_string).lower(),
        "run_id": payload["data"]["runId"].tame(check_string),
        "start_time": payload["data"]["runStartedAt"].tame(check_string),
        "run_status": payload["data"]["runStatus"].tame(check_string).lower(),
    }
    end_time = payload["data"].get("runErroredAt") or payload["data"].get("runFinishedAt")
    data["end_time"] = end_time.tame(check_string) if end_time else ""
    return data


def get_project_url(access_url: str | None, account_id: str, project_id: str) -> str | None:
    if not access_url:
        return None

    return urljoin(
        access_url,
        f"/deploy/{account_id}/projects/{project_id}",
    )


def get_job_run_body(data: dict[str, str], access_url: str | None) -> str:
    emoji, status = DBT_EVENT_TYPE_MAPPER[data["event_type"]][data["run_status"]]
    project_url = get_project_url(access_url, data["account_id"], data["project_id"])
    job_text = (
        f"[Job #{data['job_id']}]({project_url}/jobs/{data['job_id']})"
        if project_url
        else f"Job #{data['job_id']}"
    )
    run_text = f"[deployment]({project_url}/runs/{data['run_id']})" if project_url else "deployment"
    end_time_phrase = (
        f" at <time:{data['end_time']}>" if data["event_type"] != "job.run.started" else ""
    )
    template = """{emoji} {job_name} {run_text} {status} in {environment}{end_time_phrase}.
{job_text} was {run_reason} at <time:{start_time}>."""
    body = template.format(
        emoji=emoji,
        status=status,
        end_time_phrase=end_time_phrase,
        run_text=run_text,
        job_text=job_text,
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
    access_url: str | None = None,
) -> HttpResponse:
    data = extract_data_from_payload(payload)

    if access_url and not bool(
        re.fullmatch(r"^https://[a-zA-Z0-9-]+\.[a-zA-Z0-9-]+\.dbt\.com/?$", access_url)
    ):
        access_url = None

    body = get_job_run_body(data, access_url)
    topic_name = data["project_name"]
    event = data["event_type"]
    check_send_webhook_message(request, user_profile, topic_name, body, event)
    return json_success(request)
