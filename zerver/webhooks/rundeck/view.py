from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

RUNDECK_MESSAGE_TEMPLATE = "[{job_name}]({job_link}) execution [#{execution_id}]({execution_link}) for {project_name} {status}. :{emoji}:"
RUNDECK_TOPIC_TEMPLATE = "{job_name}"


@webhook_view("Rundeck")
@typed_endpoint
def api_rundeck_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    topic = get_topic(payload)
    body = get_body(payload)

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)


def get_topic(payload: WildValue) -> str:
    return RUNDECK_TOPIC_TEMPLATE.format(
        job_name=payload["execution"]["job"]["name"].tame(check_string)
    )


def get_body(payload: WildValue) -> str:
    message_data = {
        "job_name": payload["execution"]["job"]["name"].tame(check_string),
        "job_link": payload["execution"]["job"]["permalink"].tame(check_string),
        "execution_id": payload["execution"]["id"].tame(check_int),
        "execution_link": payload["execution"]["href"].tame(check_string),
        "project_name": payload["execution"]["project"].tame(check_string),
        "status": payload["execution"]["status"].tame(check_string),
    }
    status = payload["execution"]["status"].tame(check_string)

    if status == "failed":
        message_data["status"] = "has failed"
        message_data["emoji"] = "cross_mark"

    if status == "succeeded":
        message_data["status"] = "has succeeded"
        message_data["emoji"] = "check"

    if status == "running":
        if payload["trigger"].tame(check_string) == "avgduration":
            message_data["status"] = "is running long"
            message_data["emoji"] = "time_ticking"
        else:
            message_data["status"] = "has started"
            message_data["emoji"] = "running"

    if status == "scheduled":
        message_data["status"] = "has started"
        message_data["emoji"] = "running"

    return RUNDECK_MESSAGE_TEMPLATE.format(**message_data)
