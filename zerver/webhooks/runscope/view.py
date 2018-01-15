from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_stream_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.lib.validator import check_dict, check_string

from zerver.models import Client, UserProfile

from django.http import HttpRequest, HttpResponse
from typing import Dict, Any, Iterable, Optional, Text

BODY_FORMAT_STRING = """API test for `{bucket_name}: {test_name}` completed! \
[View the results]({test_run_url}), [edit the test]({test_url}) or [rerun the tests]({trigger_url})
 * **Status**: {status}
 * **Environment**: {environment}
 * **Team Name**: {team_name}
 * **Location**: {location}
 * **Total Response Time**: {total_response_time} ms
 * **Requests Executed**: {total_requests}
 * **Assertions Passed**: {assertions_passed} of {assertions_executed}
 * **Scripts Passed**: {scripts_passed} of {scripts_executed}
"""

API_STATUS_DICTIONARY = {
    'pass': 'Passed :thumbs_up:',
    'fail': 'Failed'
}

@api_key_only_webhook_view('Runscope')
@has_request_variables
def api_runscope_webhook(request: HttpRequest, user_profile: UserProfile,
                         payload: Dict[Text, Any]=REQ(argument_type='body'),
                         stream: Text=REQ(default='Runscope'),
                         topic: Text=REQ(default=None),
                         only_on: Text=REQ(default=None)) -> HttpResponse:
    if only_on is not None:
        if only_on != payload['result']:
            return json_success()

    all_response_times = [request['response_time_ms'] for request in payload['requests']]
    total_response_time = sum(filter(lambda response_time: response_time > 0, all_response_times))

    assertions_passed = sum(request['assertions']['pass'] for request in payload['requests'])
    assertions_executed = sum(request['assertions']['total'] for request in payload['requests'])

    scripts_passed = sum(request['scripts']['pass'] for request in payload['requests'])
    scripts_executed = sum(request['scripts']['total'] for request in payload['requests'])

    extracted_information = {
        'bucket_name': payload['bucket_name'],
        'test_name': payload['test_name'],
        'status': API_STATUS_DICTIONARY[payload['result']],
        'environment': payload['environment_name'],
        'team_name': payload['team_name'],
        'location': payload['region_name'],
        'total_response_time': total_response_time,
        'total_requests': len(payload['requests']),
        'assertions_passed': assertions_passed,
        'assertions_executed': assertions_executed,
        'scripts_passed': scripts_passed,
        'scripts_executed': scripts_executed,
        'test_run_url': payload['test_run_url'],
        'test_url': payload['test_url'],
        'trigger_url': payload['trigger_url'],
    }

    body = BODY_FORMAT_STRING.format(**extraced_information)

    if topic is None:
        topic = "{bucket_name}: {test_name}".format(**payload)

    check_send_stream_message(user_profile, request.client,
                              stream, topic, body)

    return json_success()
