# Webhooks for external integrations.

from django.http import HttpRequest, HttpResponse
from typing import Any, Dict, List, Mapping

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

inverse_operators = {
    'WORSE_THAN': 'should be better or equal to',
    'GREATER_THAN': 'should be less or equal to',
    'LESS_THAN': 'should be greater or equal to'
}

templates = {
    'default': u'* Metric \'{}\' computed with result: {} {} {}, status: **{}**.',
    'no_value': u'* Metric \'{}\', status: **{}**.',
}

def parse_metric_name(metric_name: str) -> str:
    return " ".join(metric_name.split('_'))

def parse_condition(condition: Mapping[str, Any]) -> str:
    metric = condition['metric']

    metric_name = parse_metric_name(metric)
    operator = condition['operator']
    operator = inverse_operators.get(operator, operator)
    value = condition.get('value', 'no value')
    status = condition['status'].lower()
    threshold = condition['errorThreshold']

    if value == 'no value':
        return templates['no_value'].format(metric_name, status)

    template = templates['default']

    return template.format(metric_name, value, operator, threshold, status)

def parse_conditions(conditions: List[Mapping[str, Any]]) -> str:
    return '\n'.join([parse_condition(condition) for condition in conditions])

def parse_payload(payload: Mapping[str, Any]) -> str:
    project_name = payload['project']['name']
    quality_gate_status = payload['qualityGate']['status'].lower()
    conditions = payload['qualityGate']['conditions']
    branch = None
    if 'branch' in payload.keys():
        branch = payload['branch'].get('name', None)

    msg = u'In project {}'.format(project_name)
    if branch:
        msg += u', on branch {},'.format(branch)
    msg += u' check completed with status **{}**.\n'.format(quality_gate_status)
    msg += parse_conditions(conditions)

    return msg


@api_key_only_webhook_view(webhook_client_name="Sonarqube")
@has_request_variables
def api_sonarqube_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:
    message = parse_payload(payload)
    topic = 'Code quality and security'
    check_send_webhook_message(request, user_profile, topic, message)
    return json_success()
