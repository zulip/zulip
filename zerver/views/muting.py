from __future__ import absolute_import

from django.http import HttpResponse, HttpRequest
from typing import List, Text

import ujson

from django.utils.translation import ugettext as _
from zerver.decorator import authenticated_json_post_view
from zerver.lib.actions import do_update_muted_topic
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.topic_mutes import topic_is_muted
from zerver.lib.validator import check_string, check_list
from zerver.models import UserProfile

@has_request_variables
def update_muted_topic(request, user_profile, stream=REQ(),
                       topic=REQ(), op=REQ()):
    # type: (HttpRequest, UserProfile, str, str, str) -> HttpResponse
    if op == 'add':
        if topic_is_muted(user_profile, stream, topic):
            return json_error(_("Topic already muted"))
    elif op == 'remove':
        if not topic_is_muted(user_profile, stream, topic):
            return json_error(_("Topic is not there in the muted_topics list"))

    do_update_muted_topic(user_profile, stream, topic, op)
    return json_success()
