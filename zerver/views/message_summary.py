import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")


from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

from analytics.lib.counts import COUNT_STATS
from zerver.actions.message_summary import do_summarize_narrow
from zerver.lib.exceptions import JsonableError
from zerver.lib.narrow import NarrowParameter
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


@typed_endpoint
def get_messages_summary(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    narrow: Json[list[NarrowParameter] | None] = None,
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

    summary = do_summarize_narrow(user_profile, narrow)
    if summary is None:  # nocoverage
        raise JsonableError(_("No messages in conversation to summarize"))

    return json_success(request, {"summary": summary})
