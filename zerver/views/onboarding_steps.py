from datetime import timedelta

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from pydantic import Json

from zerver.actions.onboarding_steps import do_mark_onboarding_step_as_read
from zerver.actions.scheduled_messages import check_schedule_message
from zerver.decorator import human_users_only
from zerver.lib.exceptions import JsonableError
from zerver.lib.onboarding_steps import ALL_ONBOARDING_STEPS
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile
from zerver.models.clients import get_client
from zerver.models.users import get_system_bot


@human_users_only
@typed_endpoint
def mark_onboarding_step_as_read(
    request: HttpRequest,
    user: UserProfile,
    *,
    onboarding_step: str,
    schedule_navigation_tour_video_reminder_delay: Json[int] | None = None,
) -> HttpResponse:
    if not any(step.name == onboarding_step for step in ALL_ONBOARDING_STEPS):
        raise JsonableError(
            _("Unknown onboarding_step: {onboarding_step}").format(onboarding_step=onboarding_step)
        )

    if schedule_navigation_tour_video_reminder_delay is not None:
        assert onboarding_step == "navigation_tour_video"

        realm = user.realm
        sender = get_system_bot(settings.WELCOME_BOT, realm.id)
        client = get_client("Internal")
        message_content = _("""
You asked to watch the [Welcome to Zulip video]({navigation_tour_video_url}) later. Is this a good time?
""").format(navigation_tour_video_url=settings.NAVIGATION_TOUR_VIDEO_URL)
        deliver_at = timezone_now() + timedelta(
            seconds=schedule_navigation_tour_video_reminder_delay
        )

        check_schedule_message(
            sender,
            client,
            "private",
            [user.id],
            None,
            message_content,
            deliver_at,
            realm,
            skip_events=True,
        )

    do_mark_onboarding_step_as_read(user, onboarding_step)
    return json_success(request)
