from typing import Literal

from django.http import HttpRequest, HttpResponse

from zerver.decorator import human_users_only
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


@human_users_only
@typed_endpoint
def set_tutorial_status(
    request: HttpRequest, user_profile: UserProfile, *, status: Literal["started", "finished"]
) -> HttpResponse:
    if status == "started":
        user_profile.tutorial_status = UserProfile.TUTORIAL_STARTED
    elif status == "finished":
        user_profile.tutorial_status = UserProfile.TUTORIAL_FINISHED
    user_profile.save(update_fields=["tutorial_status"])

    return json_success(request)
