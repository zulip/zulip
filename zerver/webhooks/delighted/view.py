from typing import Any, Dict

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

PROMOTER = """
Kudos! You have a new promoter. Score of {score}/10 from {email}:

``` quote
{comment}
```
""".strip()

FEEDBACK = """
Great! You have new feedback. Score of {score}/10 from {email}:

``` quote
{comment}
```
""".strip()

def body_template(score: int) -> str:
    if score >= 7:
        return PROMOTER
    else:
        return FEEDBACK

@webhook_view("Delighted")
@has_request_variables
def api_delighted_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Dict[str, Dict[str, Any]]=REQ(argument_type='body')) -> HttpResponse:
    person = payload['event_data']['person']
    selected_payload = {'email': person['email']}
    selected_payload['score'] = payload['event_data']['score']
    selected_payload['comment'] = payload['event_data']['comment']

    BODY_TEMPLATE = body_template(selected_payload['score'])
    body = BODY_TEMPLATE.format(**selected_payload)
    topic = 'Survey Response'

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success()
