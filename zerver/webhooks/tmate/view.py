# Webhooks for external integrations.
from django.http import HttpRequest, HttpResponse

from zerver.decorator import authenticated_rest_api_view, webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

from pprint import pprint

@webhook_view('Statuspage')
def api_tmate_webhook(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    subject = "webhook test"
    message = str(request)
    check_send_webhook_message(request, user_profile, subject, message)
    return json_success()
