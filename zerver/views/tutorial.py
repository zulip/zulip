
from django.http import HttpRequest, HttpResponse

from zerver.decorator import has_request_variables, REQ
from zerver.lib.response import json_success
from zerver.lib.validator import check_string
from zerver.models import UserProfile

@has_request_variables
def set_tutorial_status(request, user_profile,
                        status=REQ(validator=check_string)):
    # type: (HttpRequest, UserProfile, str) -> HttpResponse
    if status == 'started':
        user_profile.tutorial_status = UserProfile.TUTORIAL_STARTED
    elif status == 'finished':
        user_profile.tutorial_status = UserProfile.TUTORIAL_FINISHED
    user_profile.save(update_fields=["tutorial_status"])

    return json_success()
