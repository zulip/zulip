# Webhooks for external integrations.
from datetime import datetime
from typing import Any, Dict

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import webhook_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

OPEN_TEMPLATE = """
Incident **opened** for condition: **{condition_name}** at <time:{iso_timestamp}>
``` quote
{details}
```
[View incident]({incident_url})
""".strip()

DEFAULT_TEMPLATE = """Incident **{status}** for condition: **{condition_name}**""".strip()

TOPIC_TEMPLATE = """{policy_name} ({incident_id})""".strip()

@webhook_view("NewRelic")
@has_request_variables
def api_newrelic_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    payload: Dict[str, Any]=REQ(argument_type='body')
) -> HttpResponse:

    info = {
        "condition_name": payload.get('condition_name', 'Unknown condition'),
        "details": payload.get('details', 'No details.'),
        "incident_url": payload.get('incident_url', 'https://alerts.newrelic.com'),
        "incident_acknowledge_url": payload.get('incident_acknowledge_url', 'https://alerts.newrelic.com'),
        "status": payload.get('current_state', 'None'),
        "iso_timestamp": '',
    }

    unix_time = payload.get('timestamp', None)
    if unix_time is None:
        return json_error(_("The newrelic webhook requires timestamp in milliseconds"))

    duration = payload.get('duration', None)
    if duration is None:
        return json_error(_("The newrelic webhook requires duration in milliseconds"))

    try:
        # Timestamp - duration to get time alert started
        # timestamps from NewRelic are in ms
        iso_timestamp = datetime.fromtimestamp((unix_time - duration) / 1000)
        info['iso_timestamp'] = iso_timestamp
    except ValueError:
        return json_error(_("The newrelic webhook expects timestamp and duration in milliseconds"))
    except TypeError:
        return json_error(_("The newrelic webhook expects timestamp and duration in milliseconds"))

    # These are the three promised current_state values
    if 'open' in info['status']:
        content = OPEN_TEMPLATE.format(**info)
    elif 'acknowledged' in info['status']:
        content = DEFAULT_TEMPLATE.format(**info)
    elif 'closed' in info['status']:
        content = DEFAULT_TEMPLATE.format(**info)
    else:
        return json_error(_("The newrelic webhook requires current_state be in [open|acknowledged|closed]"))

    topic_info = {
        "policy_name": payload.get('policy_name', 'Unknown Policy'),
        "incident_id": payload.get('incident_id', 'Unknown ID'),
    }
    topic = TOPIC_TEMPLATE.format(**topic_info)

    check_send_webhook_message(request, user_profile, topic, content)
    return json_success()
