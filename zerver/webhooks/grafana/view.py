from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

GRAFANA_TOPIC_TEMPLATE = '{alert_title}'

GRAFANA_MESSAGE_TEMPLATE = '[{rule_name}]({rule_url})\n\n{alert_message}{eval_matches}'

@webhook_view('Grafana')
@has_request_variables
def api_grafana_webhook(
        request: HttpRequest, user_profile: UserProfile,
        payload: Dict[str, Any]=REQ(argument_type='body'),
) -> HttpResponse:

    topic = GRAFANA_TOPIC_TEMPLATE.format(alert_title=payload['title'])

    eval_matches_text = ''
    eval_matches = payload.get('evalMatches')
    if eval_matches is not None:
        for match in eval_matches:
            eval_matches_text += '**{}:** {}\n'.format(match['metric'], match['value'])

    message_text = ''
    if payload.get('message') is not None:
        message_text = payload['message'] + "\n\n"

    body = GRAFANA_MESSAGE_TEMPLATE.format(alert_message=message_text,
                                           rule_name=payload['ruleName'],
                                           rule_url=payload['ruleUrl'],
                                           eval_matches=eval_matches_text)

    if payload.get('imageUrl') is not None:
        body += "\n[Click to view visualization]({visualization})".format(visualization=payload['imageUrl'])

    body = body.strip()

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()
