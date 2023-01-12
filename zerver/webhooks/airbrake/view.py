# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

AIRBRAKE_TOPIC_TEMPLATE = "{project_name}"
AIRBRAKE_MESSAGE_TEMPLATE = '[{error_class}]({error_url}): "{error_message}" occurred.'


@webhook_view("Airbrake")
@has_request_variables
def api_airbrake_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    subject = get_subject(payload)
    body = get_body(payload)
    check_send_webhook_message(request, user_profile, subject, body)
    return json_success(request)


def get_subject(payload: WildValue) -> str:
    return AIRBRAKE_TOPIC_TEMPLATE.format(
        project_name=payload["error"]["project"]["name"].tame(check_string)
    )


def get_body(payload: WildValue) -> str:
    data = {
        "error_url": payload["airbrake_error_url"].tame(check_string),
        "error_class": payload["error"]["error_class"].tame(check_string),
        "error_message": payload["error"]["error_message"].tame(check_string),
    }
    return AIRBRAKE_MESSAGE_TEMPLATE.format(**data)
