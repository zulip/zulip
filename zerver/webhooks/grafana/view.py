from typing import Any, Dict, Iterable, Optional

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.validator import check_dict, check_string
from zerver.models import UserProfile

@api_key_only_webhook_view(webhook_client_name="Grafana")
@has_request_variables
def api_grafana_webhook(request: HttpRequest, user_profile: UserProfile,
                        payload: Dict[str, Iterable[Dict[str, Any]]]=REQ(argument_type='body')
) -> HttpResponse:
    """ 
    Grafana's webhooks are used to communicate state change.
    Possible values for alert state are:
        ok, paused, alerting, pending, no_data

    Source: https://zulipchat.com/api/incoming-webhooks-overview
    """
    topic = "Grafana alert: {title}"
    body_template = "\nRule: **[{ruleName}]({ruleUrl})**\n"
    body_template += "Rule ID: {ruleId}\n"
    body_template += "State: {state}\n"
    body_template += "Message: {message}"
    # Not including evalMatches at the moment...

    body = body_template.format(**payload)A
    
    check_and_send_webhook_message(request, user_profile, topic, body)

    return json_success()
