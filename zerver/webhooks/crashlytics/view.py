# Webhooks for external integrations.
from typing import Any, Dict, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

CRASHLYTICS_SUBJECT_TEMPLATE = '{display_id}: {title}'
CRASHLYTICS_MESSAGE_TEMPLATE = '[Issue]({url}) impacts at least {impacted_devices_count} device(s).'

CRASHLYTICS_SETUP_SUBJECT_TEMPLATE = "Setup"
CRASHLYTICS_SETUP_MESSAGE_TEMPLATE = "Webhook has been successfully configured."

VERIFICATION_EVENT = 'verification'


@api_key_only_webhook_view('Crashlytics')
@has_request_variables
def api_crashlytics_webhook(request: HttpRequest, user_profile: UserProfile,
                            payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    event = payload['event']
    if event == VERIFICATION_EVENT:
        subject = CRASHLYTICS_SETUP_SUBJECT_TEMPLATE
        body = CRASHLYTICS_SETUP_MESSAGE_TEMPLATE
    else:
        issue_body = payload['payload']
        subject = CRASHLYTICS_SUBJECT_TEMPLATE.format(
            display_id=issue_body['display_id'],
            title=issue_body['title']
        )
        body = CRASHLYTICS_MESSAGE_TEMPLATE.format(
            impacted_devices_count=issue_body['impacted_devices_count'],
            url=issue_body['url']
        )

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()
