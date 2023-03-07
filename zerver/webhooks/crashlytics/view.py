# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import WildValue, check_int, check_string, to_wild_value
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

CRASHLYTICS_TOPIC_TEMPLATE = "{display_id}: {title}"
CRASHLYTICS_MESSAGE_TEMPLATE = "[Issue]({url}) impacts at least {impacted_devices_count} device(s)."

CRASHLYTICS_SETUP_TOPIC_TEMPLATE = "Setup"
CRASHLYTICS_SETUP_MESSAGE_TEMPLATE = "Webhook has been successfully configured."

VERIFICATION_EVENT = "verification"


@webhook_view("Crashlytics")
@has_request_variables
def api_crashlytics_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: WildValue = REQ(argument_type="body", converter=to_wild_value),
) -> HttpResponse:
    event = payload["event"]
    if event == VERIFICATION_EVENT:
        subject = CRASHLYTICS_SETUP_TOPIC_TEMPLATE
        body = CRASHLYTICS_SETUP_MESSAGE_TEMPLATE
    else:
        issue_body = payload["payload"]
        subject = CRASHLYTICS_TOPIC_TEMPLATE.format(
            display_id=issue_body["display_id"].tame(check_int),
            title=issue_body["title"].tame(check_string),
        )
        body = CRASHLYTICS_MESSAGE_TEMPLATE.format(
            impacted_devices_count=issue_body["impacted_devices_count"].tame(check_int),
            url=issue_body["url"].tame(check_string),
        )

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success(request)
