from django.http import HttpResponse, HttpRequest
from typing import Any, Dict

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile

ZULIP_ALERT_TEMPLATE = u"Rule Name : **{ruleName}**\n" \
                       u"Current State is `{state}`\n"
ZULIP_EVALMATCH_TEMPLATE = u"Metric : **{metric}** and its value is **{value}**\n"

@api_key_only_webhook_view('Grafana')
@has_request_variables
def api_grafana_webhook(request: HttpRequest, user_profile: UserProfile,
                        payload: Dict[str, Any] = REQ(argument_type='body')) -> HttpResponse:
    subject = payload['title']
    content = ZULIP_ALERT_TEMPLATE.format(**payload)
    for evalmatches in payload['evalMatches']:
        content = content + ZULIP_EVALMATCH_TEMPLATE.format(**evalmatches)
    check_send_webhook_message(request, user_profile, subject, content)
    return json_success()
