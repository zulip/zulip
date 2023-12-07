from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from zerver.actions.hotspots import do_mark_onboarding_step_as_read
from zerver.decorator import human_users_only
from zerver.lib.exceptions import JsonableError
from zerver.lib.hotspots import ALL_ONBOARDING_STEPS
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile


@human_users_only
@has_request_variables
def mark_onboarding_step_as_read(
    request: HttpRequest, user: UserProfile, onboarding_step: str = REQ()
) -> HttpResponse:
    if not any(step.name == onboarding_step for step in ALL_ONBOARDING_STEPS):
        raise JsonableError(
            _("Unknown onboarding_step: {onboarding_step}").format(onboarding_step=onboarding_step)
        )
    do_mark_onboarding_step_as_read(user, onboarding_step)
    return json_success(request)
