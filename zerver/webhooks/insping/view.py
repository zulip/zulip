import time
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import REQ, has_request_variables, webhook_view
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MESSAGE_TEMPLATE = """
State changed to **{state}**:
* **URL**: {url}
* **Response time**: {response_time} ms
* **Timestamp**: {timestamp}
""".strip()

@webhook_view('Insping')
@has_request_variables
def api_insping_webhook(
        request: HttpRequest, user_profile: UserProfile,
        payload: Dict[str, Dict[str, Any]]=REQ(argument_type='body'),
) -> HttpResponse:

    data = payload['webhook_event_data']

    state_name = data['check_state_name']
    url_tested = data['request_url']
    response_time = data['response_time']
    timestamp = data['request_start_time']

    time_formatted = time.strftime("%c", time.strptime(timestamp,
                                                       "%Y-%m-%dT%H:%M:%S.%f+00:00"))

    body = MESSAGE_TEMPLATE.format(
        state=state_name, url=url_tested,
        response_time=response_time, timestamp=time_formatted,
    )

    topic = 'insping'

    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()
