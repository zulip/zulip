from datetime import datetime, timezone

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

from analytics.lib.counts import COUNT_STATS
from zerver.actions.catch_up import do_get_catch_up_data, do_get_catch_up_summary
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


@typed_endpoint
def get_catch_up(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    since: str | None = None,
    max_topics: Json[int] = 20,
    include_muted: Json[bool] = False,
    include_extractive_summary: Json[bool] = False,
) -> HttpResponse:
    """Return catch-up data: aggregated, scored topics since the user's
    last activity (or the provided 'since' timestamp).

    When include_extractive_summary is True, each topic will include
    'key_messages' (the most important messages selected by heuristics)
    and 'keywords' (frequently-used terms). This does not require an
    AI model.
    """
    since_dt: datetime | None = None
    if since is not None:
        try:
            since_dt = datetime.fromisoformat(since)
            # Ensure the datetime is timezone-aware.
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            raise JsonableError(_("Invalid 'since' timestamp format. Use ISO 8601."))

    if max_topics < 1 or max_topics > 100:
        raise JsonableError(_("'max_topics' must be between 1 and 100."))

    data = do_get_catch_up_data(
        user_profile=user_profile,
        since=since_dt,
        max_topics=max_topics,
        include_muted=include_muted,
        include_extractive_summary=include_extractive_summary,
    )

    return json_success(request, data=data)


@typed_endpoint
def get_catch_up_summary(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    stream_id: Json[int],
    topic_name: str,
) -> HttpResponse:
    """Generate an AI summary for a specific topic in the catch-up view.

    Reuses the existing topic summarization infrastructure.
    """
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

    summary = do_get_catch_up_summary(
        user_profile=user_profile,
        stream_id=stream_id,
        topic_name=topic_name,
    )

    if summary is None:  # nocoverage
        raise JsonableError(_("No messages in this topic to summarize."))

    return json_success(request, data={"summary": summary})
