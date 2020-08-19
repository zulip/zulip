# Webhooks for external integrations.
from typing import Any, Dict, Optional

from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import UnsupportedWebhookEventType
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.lib.validator import check_dict
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

ALERT_TEMPLATE = "{long_description} ([view alert]({alert_url}))."

DEPLOY_TEMPLATE = """
**{revision}** deployed by **{deployed_by}**:

``` quote
{description}
```

Changelog:

``` quote
{changelog}
```
""".strip()

@webhook_view("NewRelic")
@has_request_variables
def api_newrelic_webhook(request: HttpRequest, user_profile: UserProfile,
                         alert: Optional[Dict[str, Any]]=REQ(validator=check_dict([]), default=None),
                         deployment: Optional[Dict[str, Any]]=REQ(validator=check_dict([]), default=None),
                         ) -> HttpResponse:
    if alert:
        # Use the message as the subject because it stays the same for
        # "opened", "acknowledged", and "closed" messages that should be
        # grouped.
        subject = alert['message']
        content = ALERT_TEMPLATE.format(**alert)
    elif deployment:
        subject = "{} deploy".format(deployment['application_name'])
        content = DEPLOY_TEMPLATE.format(**deployment)
    else:
        raise UnsupportedWebhookEventType('Unknown Event Type')

    check_send_webhook_message(request, user_profile, subject, content)
    return json_success()
