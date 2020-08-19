from typing import Any, Dict

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import REQ, has_request_variables, webhook_view
from zerver.lib.actions import send_rate_limited_pm_notification_to_bot_owner
from zerver.lib.response import json_error, json_success
from zerver.lib.send_email import FromAddress
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

MISCONFIGURED_PAYLOAD_ERROR_MESSAGE = """
Hi there! Your bot {bot_name} just received a Zabbix payload that is missing
some data that Zulip requires. This usually indicates a configuration issue
in your Zabbix webhook settings. Please make sure that you set the
**Default Message** option properly and provide all the required fields
when configuring the Zabbix webhook. Contact {support_email} if you
need further help!
"""

ZABBIX_TOPIC_TEMPLATE = '{hostname}'
ZABBIX_MESSAGE_TEMPLATE = """
{status} ({severity}) alert on [{hostname}]({link}):
* {trigger}
* {item}
""".strip()

@webhook_view('Zabbix')
@has_request_variables
def api_zabbix_webhook(request: HttpRequest, user_profile: UserProfile,
                       payload: Dict[str, Any]=REQ(argument_type='body')) -> HttpResponse:

    try:
        body = get_body_for_http_request(payload)
        subject = get_subject_for_http_request(payload)
    except KeyError:
        message = MISCONFIGURED_PAYLOAD_ERROR_MESSAGE.format(
            bot_name=user_profile.full_name,
            support_email=FromAddress.SUPPORT,
        ).strip()
        send_rate_limited_pm_notification_to_bot_owner(
            user_profile, user_profile.realm, message)

        return json_error(_("Invalid payload"))

    check_send_webhook_message(request, user_profile, subject, body)
    return json_success()

def get_subject_for_http_request(payload: Dict[str, Any]) -> str:
    return ZABBIX_TOPIC_TEMPLATE.format(hostname=payload['hostname'])

def get_body_for_http_request(payload: Dict[str, Any]) -> str:
    hostname = payload['hostname']
    severity = payload['severity']
    status = payload['status']
    item = payload['item']
    trigger = payload['trigger']
    link = payload['link']

    data = {
        "hostname": hostname,
        "severity": severity,
        "status": status,
        "item": item,
        "trigger": trigger,
        "link": link,
    }
    return ZABBIX_MESSAGE_TEMPLATE.format(**data)
