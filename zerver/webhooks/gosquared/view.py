from typing import Any, Dict, Optional, Text

from django.http import HttpRequest, HttpResponse
from django.utils.translation import ugettext as _

from zerver.decorator import api_key_only_webhook_view
from zerver.lib.actions import check_send_stream_message
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_error, json_success
from zerver.models import UserProfile

BODY_TEMPLATE = '[{website_name}]({website_url}) has {user_num} visitors online.'

@api_key_only_webhook_view('GoSquared')
@has_request_variables
def api_gosquared_webhook(request: HttpRequest, user_profile: UserProfile,
                          payload: Dict[str, Dict[str, Any]]=REQ(argument_type='body'),
                          stream: Text=REQ(default='gosquared'),
                          topic: Optional[Text]=REQ(default=None, type=str)) -> HttpResponse:
    domain_name = payload['siteDetails']['domain']
    user_num = payload['concurrents']
    user_acc = payload['siteDetails']['acct']
    acc_url = 'https://www.gosquared.com/now/' + user_acc
    body = BODY_TEMPLATE.format(website_name=domain_name, website_url=acc_url, user_num=user_num)
    # allows for customisable topics
    if topic is None:
        topic = 'GoSquared - {website_name}'.format(website_name=domain_name)

    check_send_stream_message(user_profile, request.client, stream,
                              topic, body)
    return json_success()
