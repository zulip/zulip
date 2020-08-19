# Webhooks for external integrations.
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import MAX_TOPIC_NAME_LENGTH, UserProfile

MESSAGE_TEMPLATE = """
Splunk alert from saved search:
* **Search**: [{search}]({link})
* **Host**: {host}
* **Source**: `{source}`
* **Raw**: `{raw}`
""".strip()

@webhook_view('Splunk')
@has_request_variables
def api_splunk_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    # use default values if expected data is not provided
    search_name = payload.get('search_name', 'Missing search_name')
    results_link = payload.get('results_link', 'Missing results_link')
    host = payload.get('result', {}).get('host', 'Missing host')
    source = payload.get('result', {}).get('source', 'Missing source')
    raw = payload.get('result', {}).get('_raw', 'Missing _raw')

    # for the default topic, use search name but truncate if too long
    if len(search_name) >= MAX_TOPIC_NAME_LENGTH:
        topic = f"{search_name[:(MAX_TOPIC_NAME_LENGTH - 3)]}..."
    else:
        topic = search_name

    # construct the message body
    body = MESSAGE_TEMPLATE.format(
        search=search_name, link=results_link,
        host=host, source=source, raw=raw,
    )

    # send the message
    check_send_webhook_message(request, user_profile, topic, body)

    return json_success()
