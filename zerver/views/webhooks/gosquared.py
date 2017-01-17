from __future__ import absolute_import
from typing import Any, Dict, Optional, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import (REQ, api_key_only_webhook_view,
                              has_request_variables)
from zerver.lib.actions import check_send_message
from zerver.lib.response import json_error, json_success
from zerver.models import Client, UserProfile

BODY_TEMPLATE = '[{website_name}]({website_url}) has {user_num} visitors online.'

@api_key_only_webhook_view('GoSquared')
@has_request_variables
def api_gosquared_webhook(request, user_profile, client,
                          payload=REQ(argument_type='body'),
                          stream=REQ(default='gosquared'),
                          topic=REQ(default=None)):
    # type: (HttpRequest, UserProfile, Client, Dict[str, Dict[str, Any]], Text, Text) -> HttpResponse
    try:
        domain_name = payload['siteDetails']['domain']
        user_num = payload['concurrents']
        user_acc = payload['siteDetails']['acct']
        acc_url = 'https://www.gosquared.com/now/' + user_acc
    except KeyError as e:
        return json_error(_("Missing key {} in JSON").format(str(e)))

    body = BODY_TEMPLATE.format(website_name=domain_name, website_url=acc_url, user_num=user_num)
    # allows for customisable topics
    if topic is None:
        topic = 'GoSquared - {website_name}'.format(website_name=domain_name)

    check_send_message(user_profile, client, 'stream', [stream],
                       topic, body)
    return json_success()
