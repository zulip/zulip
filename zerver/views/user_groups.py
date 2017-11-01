from django.http import HttpResponse, HttpRequest

from typing import List, Text

from zerver.context_processors import get_realm_from_request
from zerver.lib.actions import check_add_user_group
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success, json_error
from zerver.lib.users import user_ids_to_users
from zerver.lib.validator import check_list, check_string, check_int, \
    check_short_string
from zerver.models import UserProfile

@has_request_variables
def add_user_group(request, user_profile,
                   name=REQ(),
                   members=REQ(validator=check_list(check_int), default=[]),
                   description=REQ()):
    # type: (HttpRequest, UserProfile, Text, List[int], Text) -> HttpResponse
    user_profiles = user_ids_to_users(members, user_profile.realm)
    check_add_user_group(user_profile.realm, name, user_profiles, description)
    return json_success()
