from django.http import HttpRequest, HttpResponse
from six import text_type

from zerver.decorator import authenticated_json_post_view,\
    has_request_variables, REQ, to_non_negative_int
from zerver.lib.actions import check_add_reaction
from zerver.lib.response import json_success
from zerver.models import UserProfile

@has_request_variables
def add_reaction_backend(request, user_profile, emoji_name=REQ('emoji'),
                         message_id = REQ('message_id', converter=to_non_negative_int)):
    # type: (HttpRequest, UserProfile, text_type, int) -> HttpResponse
    check_add_reaction(user_profile, emoji_name, message_id)
    return json_success()
