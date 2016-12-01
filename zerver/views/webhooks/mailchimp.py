# Webhooks for external integrations.
from __future__ import absolute_import
from django.utils.translation import ugettext as _
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_success, json_error
from zerver.decorator import REQ, has_request_variables, api_key_only_webhook_view
from zerver.models import Client, UserProfile
from django.http import HttpRequest, HttpResponse
from six import text_type
from typing import Any

MAILCHIMP_SUBJECT_TEMPLATE = '[{fired_at}]{type}|{data[merges][EMAIL]}'
MAILCHIMP_MESSAGE_TEMPLATE = '{data[merges][FNAME]} {data[merges][LNAME]} ({data[merges][EMAIL]}) subscribed at {fired_at}'


@api_key_only_webhook_view('MailChimp')
@has_request_variables
def api_mailchimp_webhook(request, user_profile, client, payload=REQ(argument_type='body'),
                            stream=REQ(default='mailchimp')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], text_type) -> HttpResponse
    try:
        event = payload['event']
        return json_success()
        issue_body = payload['payload']
        subject = MAILCHIMP_SUBJECT_TEMPLATE.format()
        body = MAILCHIMP_MESSAGE_TEMPLATE.format()
    except KeyError as e:
        return json_error(_("Missing key {} in JSON".format(str(e))))

    check_send_message(user_profile, client, 'stream', [stream],
                       subject, body)
    return json_success()