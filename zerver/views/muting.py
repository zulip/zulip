from __future__ import absolute_import

from django.http import HttpResponse, HttpRequest
from typing import List, Text

from zerver.decorator import authenticated_json_post_view
from zerver.lib.actions import do_set_muted_topics
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success
from zerver.lib.validator import check_string, check_list
from zerver.models import UserProfile

@has_request_variables
def set_muted_topics(request, user_profile,
                     muted_topics=REQ(validator=check_list(
                         check_list(check_string, length=2)), default=[])):
    # type: (HttpRequest, UserProfile, List[List[Text]]) -> HttpResponse
    do_set_muted_topics(user_profile, muted_topics)
    return json_success()
