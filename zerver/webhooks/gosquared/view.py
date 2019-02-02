from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message, \
    UnexpectedWebhookEventType
from zerver.models import UserProfile

TRAFFIC_SPIKE_TEMPLATE = '[{website_name}]({website_url}) has {user_num} visitors online.'
CHAT_MESSAGE_TEMPLATE = """
The {status} **{name}** messaged:

``` quote
{content}
```
""".strip()


@api_key_only_webhook_view('GoSquared')
@has_request_variables
def api_gosquared_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Dict[str, Dict[str, Any]]=REQ(argument_type='body')) -> HttpResponse:
    body = ""
    topic = ""

    # Unfortunately, there is no other way to infer the event type
    # than just inferring it from the payload's attributes
    # Traffic spike/dip event
    if (payload.get('concurrents') is not None and
            payload.get('siteDetails') is not None):
        domain_name = payload['siteDetails']['domain']
        user_num = payload['concurrents']
        user_acc = payload['siteDetails']['acct']
        acc_url = 'https://www.gosquared.com/now/' + user_acc
        body = TRAFFIC_SPIKE_TEMPLATE.format(website_name=domain_name,
                                             website_url=acc_url,
                                             user_num=user_num)
        topic = 'GoSquared - {website_name}'.format(website_name=domain_name)
        check_send_webhook_message(request, user_profile, topic, body)

    # Live chat message event
    elif (payload.get('message') is not None and
          payload.get('person') is not None):
        # Only support non-private messages
        if not payload['message']['private']:
            session_title = payload['message']['session']['title']
            topic = 'Live Chat Session - {}'.format(session_title)
            body = CHAT_MESSAGE_TEMPLATE.format(
                status=payload['person']['status'],
                name=payload['person']['_anon']['name'],
                content=payload['message']['content']
            )
            check_send_webhook_message(request, user_profile, topic, body)
    else:
        raise UnexpectedWebhookEventType('GoSquared', 'unknown_event')

    return json_success()
