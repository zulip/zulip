from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from analytics.lib.counts import COUNT_STATS
from zerver.actions.message_recap import do_generate_recap
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint_without_parameters
from zerver.models import UserProfile


@typed_endpoint_without_parameters
def get_messages_recap(
    request: HttpRequest,
    user_profile: UserProfile,
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

    recap = do_generate_recap(user_profile)
    if recap is None:
        return json_success(
            request,
            {
                "recap": "<p>You have no unread messages to recap! You are all caught up.</p>",
                "has_unreads": False,
            },
        )

    return json_success(request, {"recap": recap, "has_unreads": True})
