from django.http import HttpResponse, HttpRequest

from zerver.decorator import has_request_variables
from zerver.lib.response import json_success
from zerver.lib.actions import get_zoom_video_call_url
from zerver.models import UserProfile

@has_request_variables
def get_zoom_url(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    return json_success({'zoom_url': get_zoom_video_call_url(
        user_profile.realm
    )})
