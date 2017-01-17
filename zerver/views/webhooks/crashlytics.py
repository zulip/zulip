# Webhooks for external integrations.
from __future__ import absolute_import
from typing import Any, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import (REQ, api_key_only_webhook_view,
                              has_request_variables)
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_error, json_success
from zerver.models import Client, UserProfile

CRASHLYTICS_SUBJECT_TEMPLATE = '{display_id}: {title}'
CRASHLYTICS_MESSAGE_TEMPLATE = '[Issue]({url}) impacts at least {impacted_devices_count} device(s).'

VERIFICATION_EVENT = 'verification'


@api_key_only_webhook_view('Crashlytics')
@has_request_variables
def api_crashlytics_webhook(request, user_profile, client, payload=REQ(argument_type='body'),
                            stream=REQ(default='crashlytics')):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Any], Text) -> HttpResponse
    try:
        event = payload['event']
        if event == VERIFICATION_EVENT:
            return json_success()
        issue_body = payload['payload']
        subject = CRASHLYTICS_SUBJECT_TEMPLATE.format(
            display_id=issue_body['display_id'],
            title=issue_body['title']
        )
        body = CRASHLYTICS_MESSAGE_TEMPLATE.format(
            impacted_devices_count=issue_body['impacted_devices_count'],
            url=issue_body['url']
        )
    except KeyError as e:
        return json_error(_("Missing key {} in JSON".format(str(e))))

    check_send_message(user_profile, client, 'stream', [stream],
                       subject, body)
    return json_success()
