# Webhooks for external integrations.
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

@api_key_only_webhook_view('Sentry')
@has_request_variables
def api_sentry_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any] = REQ(argument_type='body')) -> HttpResponse:
    subject = "{}".format(payload.get('project_name'))
    body = "New {} [issue]({}): {}.".format(payload['level'].upper(),
                                            payload.get('url'),
                                            payload.get('message'))
    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()
