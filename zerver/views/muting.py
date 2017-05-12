from __future__ import absolute_import

from django.http import HttpResponse, HttpRequest
from typing import List, Text

import ujson

from django.utils.translation import ugettext as _
from zerver.decorator import authenticated_json_post_view
from zerver.lib.actions import do_set_muted_topics, do_update_muted_topic
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.validator import check_string, check_list
from zerver.models import UserProfile

@has_request_variables
def set_muted_topics(request, user_profile,
                     muted_topics=REQ(validator=check_list(
                         check_list(check_string, length=2)), default=[])):
    # type: (HttpRequest, UserProfile, List[List[Text]]) -> HttpResponse
    do_set_muted_topics(user_profile, muted_topics)
    return json_success()

@has_request_variables
def update_muted_topic(request, user_profile, stream=REQ(),
                       topic=REQ(), op=REQ()):
    # type: (HttpRequest, UserProfile, str, str, str) -> HttpResponse
    muted_topics = ujson.loads(user_profile.muted_topics)
    if op == 'add':
        if [stream, topic] in muted_topics:
            return json_error(_("Topic already muted"))
        muted_topics.append([stream, topic])
    elif op == 'remove':
        if [stream, topic] not in muted_topics:
            return json_error(_("Topic is not there in the muted_topics list"))
        muted_topics.remove([stream, topic])

    do_update_muted_topic(user_profile, stream, topic, op)
    return json_success()
