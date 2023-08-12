from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import WebhookPayload, typed_endpoint
from zerver.lib.validator import WildValue, check_int, check_string
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
@typed_endpoint
def api_delighted_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: WebhookPayload[WildValue],
) -> HttpResponse:
    person = payload["event_data"]["person"]
    email = person["email"].tame(check_string)
    score = payload["event_data"]["score"].tame(check_int)
    comment = payload["event_data"]["comment"].tame(check_string)

    BODY_TEMPLATE = body_template(score)
    body = BODY_TEMPLATE.format(email=email, score=score, comment=comment)
    topic = "Survey response"

    check_send_webhook_message(request, user_profile, topic, body)
    return json_success(request)
