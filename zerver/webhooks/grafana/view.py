from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

NOTIFICATIONS_STATE_TYPE = ['paused', 'alerting', 'pending', 'no_data']

GRAFANA_TOPIC_TEMPLATE = '{title}: {state}'
GRAFANA_MESSAGE_TEMPLATE = '{ruleName}: {message}. Please check out the details' + \
    ' [here]({ruleUrl}) for the abnormal metrics: {detail}'

@api_key_only_webhook_view('Grafana')
@has_request_variables
def api_grafana_webhook(
    request: HttpRequest, user_profile: UserProfile,
    payload: Dict[str, Any] = REQ(argument_type='body')
) -> HttpResponse:

    state = payload['state']

    if state in NOTIFICATIONS_STATE_TYPE:

        topic = GRAFANA_TOPIC_TEMPLATE.format(
            title=payload['title'],
            state=state
        )

        metrics, detailed_message = payload['evalMatches'], ""
        for metric in metrics:
            detailed_message += metric['metric'] + \
                ": " + str(metric['value']) + "; "

        body = GRAFANA_MESSAGE_TEMPLATE.format(
            ruleName=payload['ruleName'],
            message=payload['message'],
            ruleUrl=payload['ruleUrl'],
            detail=detailed_message
        )

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()
