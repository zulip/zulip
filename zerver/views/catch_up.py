from datetime import datetime, timezone

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from pydantic import BaseModel, Json
from typing_extensions import Literal

from analytics.lib.counts import COUNT_STATS
from zerver.actions.catch_up import (
    do_get_catch_up_data,
    do_get_catch_up_summary,
    do_record_catch_up_surfaced_items,
    do_record_catch_up_usage,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile


class CatchUpUsageItem(BaseModel):
    item_type: Literal["stream_topic", "dm_personal", "dm_group"]
    stream_id: int | None = None
    topic_name: str | None = None
    dm_sender_id: int | None = None
    dm_recipient_id: int | None = None
    first_message_id: int
    last_message_id: int
    message_count: int


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


@typed_endpoint
def report_catch_up_usage(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    duration_ms: Json[int],
    items: Json[list[CatchUpUsageItem]] | None = None,
) -> HttpResponse:
    if duration_ms <= 0:
        raise JsonableError(_("'duration_ms' must be a positive integer."))

    # Guardrail to limit abuse and obvious clock bugs.
    if duration_ms > 24 * 60 * 60 * 1000:
        raise JsonableError(_("'duration_ms' must be at most 86400000 (24 hours)."))

    request_notes = RequestNotes.get_notes(request)
    assert request_notes.client is not None

    session = do_record_catch_up_usage(
        user_profile=user_profile,
        client=request_notes.client,
        duration_ms=duration_ms,
        ended_at=timezone_now(),
    )

    if items is not None:
        if len(items) > 100:
            raise JsonableError(_("Too many items."))

        do_record_catch_up_surfaced_items(
            session=session,
            user_profile=user_profile,
            items=[item.model_dump() for item in items],
        )
    return json_success(request)
