# Webhooks for external integrations.

from collections import defaultdict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.webhooks.git import get_short_sha
from zerver.models import UserProfile

COMMIT_INFO_TEMPLATE = """[`{commit_details}`]({commit_link}) on branch `{branch_name}`"""
TOPIC_TEMPLATE = "{pipeline} / {stage}"

SCHEDULED_BODY_TEMPLATE = """
**Pipeline {status}**: {pipeline} / {stage}
- **Commit**: {commit_details}
- **Started**: {start_time}
"""

COMPLETED_BODY_TEMPLATE = """
{emoji} **Build {status}**: {pipeline} / {stage}
- **Commit**: {commit_details}
- **Started**: {start_time}
- **Finished**: {end_time}
"""


@webhook_view("Gocd")
@typed_endpoint
def api_gocd_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    type = payload["type"].tame(check_string)
    if type == "stage":
        body = get_body(payload)
        topic_name = get_topic(payload)
        check_send_webhook_message(request, user_profile, topic_name, body)
    return json_success(request)


def get_topic(payload: WildValue) -> str:
    return TOPIC_TEMPLATE.format(
        pipeline=payload["data"]["pipeline"]["name"].tame(check_string),
        stage=payload["data"]["pipeline"]["stage"]["name"].tame(check_string),
    )


def get_commit_details(payload: WildValue) -> str:
    build = payload["data"]["pipeline"]["build-cause"][0]
    material = build["material"]
    url_base = material["git-configuration"]["url"].tame(check_string)
    revision = build["modifications"][0]["revision"].tame(check_string)
    commit_sha = get_short_sha(revision)
    url = f"{url_base}/commit/{commit_sha}"
    branch = material["git-configuration"]["branch"].tame(check_string)
    return COMMIT_INFO_TEMPLATE.format(
        commit_details=commit_sha,
        commit_link=url,
        branch_name=branch,
    )


def get_jobs_details(pipeline_data: WildValue) -> str:
    job_dict_list = pipeline_data["stage"]["jobs"]
    formatted_job_dict = defaultdict(list)
    job_details_template = ""

    for job in job_dict_list:
        job_name = job["name"].tame(check_string)
        job_result = job["result"].tame(check_string)
        formatted_job_dict[job_result].append(f"`{job_name}`")

    for key in formatted_job_dict:
        formatted_job_list = ", ".join(formatted_job_dict[key])
        job_details_template += f"- **{key}**: {formatted_job_list}\n"

    return job_details_template


def get_body(payload: WildValue) -> str:
    pipeline_data = payload["data"]["pipeline"]
    body_details = {
        "commit_details": get_commit_details(payload),
        "status": pipeline_data["stage"]["state"].tame(check_string).lower(),
        "pipeline": pipeline_data["name"].tame(check_string),
        "stage": pipeline_data["stage"]["name"].tame(check_string),
        "start_time": pipeline_data["stage"]["create-time"].tame(check_string),
    }

    if body_details["status"] == "building":
        return SCHEDULED_BODY_TEMPLATE.format(**body_details)

    result = pipeline_data["stage"]["result"].tame(check_string)
    body_details.update(
        {
            "result": result,
            "emoji": ":green_circle:" if result == "Passed" else ":red_circle:",
            "end_time": pipeline_data["stage"]["last-transition-time"].tame(check_string),
        }
    )
    body = COMPLETED_BODY_TEMPLATE.format(**body_details)

    body += get_jobs_details(pipeline_data)
    return body
