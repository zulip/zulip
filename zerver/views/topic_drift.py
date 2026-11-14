from typing import Annotated

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json, NonNegativeInt

from analytics.lib.counts import COUNT_STATS
from zerver.actions.topic_drift import do_check_topic_drift
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import ApiParamConfig, typed_endpoint
from zerver.models import UserProfile


@typed_endpoint
def check_topic_drift_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    stream_id: Json[NonNegativeInt],
    topic_name: str,
    message_id: Annotated[
        Json[NonNegativeInt] | None,
        ApiParamConfig("message_id", documentation_status="intentionally_undocumented"),
    ] = None,
) -> HttpResponse:
    if settings.TOPIC_SUMMARIZATION_MODEL is None:  # nocoverage
        raise JsonableError(_("AI features are not enabled on this server."))

    if not user_profile.can_summarize_topics():
        raise JsonableError(_("Insufficient permission"))

    if settings.MAX_PER_USER_MONTHLY_AI_COST is not None:
        used_credits = COUNT_STATS["ai_credit_usage::day"].current_month_accumulated_count_for_user(
            user_profile
        )
        if used_credits >= settings.MAX_PER_USER_MONTHLY_AI_COST * 1000000000:
            raise JsonableError(_("Reached monthly limit for AI credits."))

    result = do_check_topic_drift(
        user_profile=user_profile,
        stream_id=stream_id,
        topic_name=topic_name,
        latest_message_id=message_id,
    )

    return json_success(request, data=dict(result))
