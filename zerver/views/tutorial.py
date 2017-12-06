
from django.http import HttpRequest, HttpResponse

from zerver.decorator import human_users_only
from zerver.lib.request import has_request_variables, REQ
from zerver.lib.response import json_success
from zerver.lib.validator import check_string
from zerver.models import UserProfile

@human_users_only
@has_request_variables
def set_tutorial_status(request: HttpRequest, user_profile: UserProfile,
                        status: str=REQ(validator=check_string)) -> HttpResponse:
    if status == 'started':
        user_profile.tutorial_status = UserProfile.TUTORIAL_STARTED
    elif status == 'finished':
        user_profile.tutorial_status = UserProfile.TUTORIAL_FINISHED
    user_profile.save(update_fields=["tutorial_status"])

    return json_success()
