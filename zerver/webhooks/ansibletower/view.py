import operator
from typing import Dict, List

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_bool, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ANSIBLETOWER_DEFAULT_MESSAGE_TEMPLATE = "{friendly_name}: [#{id} {name}]({url}) {status}."


ANSIBLETOWER_JOB_MESSAGE_TEMPLATE = """
{friendly_name}: [#{id} {name}]({url}) {status}:
{hosts_final_data}
""".strip()

ANSIBLETOWER_JOB_HOST_ROW_TEMPLATE = "* {hostname}: {status}\n"


@webhook_view("AnsibleTower")
@typed_endpoint
def api_ansibletower_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    body = get_body(payload)
    topic = payload["name"].tame(check_string)

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)


def extract_friendly_name(payload: WildValue) -> str:
    tentative_job_name = payload.get("friendly_name", "").tame(check_string)
    if not tentative_job_name:
        url = payload["url"].tame(check_string)
        segments = url.split("/")
        tentative_job_name = segments[-3]
        if tentative_job_name == "jobs":
            tentative_job_name = "Job"
    return tentative_job_name


def get_body(payload: WildValue) -> str:
    friendly_name = extract_friendly_name(payload)
    if friendly_name == "Job":
        hosts_data = []
        for host, host_data in payload["hosts"].items():
            if host_data["failed"].tame(check_bool):
                hoststatus = "Failed"
            else:
                hoststatus = "Success"
            hosts_data.append(
                {
                    "hostname": host,
                    "status": hoststatus,
                }
            )

        if payload["status"] == "successful":
            status = "was successful"
        else:
            status = "failed"

        return ANSIBLETOWER_JOB_MESSAGE_TEMPLATE.format(
            name=payload["name"].tame(check_string),
            friendly_name=friendly_name,
            id=payload["id"].tame(check_int),
            url=payload["url"].tame(check_string),
            status=status,
            hosts_final_data=get_hosts_content(hosts_data),
        )

    else:
        if payload["status"].tame(check_string) == "successful":
            status = "was successful"
        else:
            status = "failed"

        data = {
            "name": payload["name"].tame(check_string),
            "friendly_name": friendly_name,
            "id": payload["id"].tame(check_int),
            "url": payload["url"].tame(check_string),
            "status": status,
        }

        return ANSIBLETOWER_DEFAULT_MESSAGE_TEMPLATE.format(**data)


def get_hosts_content(hosts_data: List[Dict[str, str]]) -> str:
    hosts_data = sorted(hosts_data, key=operator.itemgetter("hostname"))
    hosts_content = ""
    for host in hosts_data:
        hosts_content += ANSIBLETOWER_JOB_HOST_ROW_TEMPLATE.format(
            hostname=host["hostname"],
            status=host["status"],
        )
    return hosts_content
