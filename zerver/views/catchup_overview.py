"""
GET /json/catch-up/overview
POST /json/catch-up/overview

Returns a Claude-generated structured summary of ALL messages the user
missed across every channel — overview, keywords, action items with
source-message deep links, and per-topic summaries with jump links (US-08).

POST accepts optional `summary_preferences` (JSON-encoded string) merged
into the model prompt so the user can steer tone and focus.

This is distinct from GET /json/catch-up/summary, which generates a
per-topic summary for a single stream/topic pair.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from pydantic import Json

from zerver.lib.exceptions import JsonableError
from zerver.lib.message import messages_for_ids
from zerver.lib.narrow import AnchorInfo, fetch_messages
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint, typed_endpoint_without_parameters
from zerver.models import UserMessage, UserProfile
from zerver.models.realms import MessageEditHistoryVisibilityPolicyEnum

MAX_OVERVIEW_MESSAGES = 200
MAX_SUMMARY_PREFERENCES_LENGTH = 2000

logger = logging.getLogger(__name__)


def _client_safe_llm_error_message(exc: BaseException, *, max_len: int = 350) -> str:
    """LiteLLM/provider errors are often huge HTML/JSON blobs; keep API responses bounded."""
    text = str(exc).strip().replace("\n", " ")
    if not text:
        text = type(exc).__name__
    if len(text) > max_len:
        return f"{text[: max_len - 3]}..."
    return text


def _generate_catch_up_overview(
    request: HttpRequest,
    user_profile: UserProfile,
    summary_preferences: str | None,
) -> HttpResponse:
    model = settings.TOPIC_SUMMARIZATION_MODEL
    api_key = getattr(settings, "TOPIC_SUMMARIZATION_API_KEY", None)

    if api_key is not None and api_key != "":
        logger.info(
            "catch-up/overview: TOPIC_SUMMARIZATION_API_KEY length is %d characters",
            len(api_key),
        )
    else:
        logger.info("catch-up/overview: TOPIC_SUMMARIZATION_API_KEY is unset or empty")

    if model is None:
        raise JsonableError("AI features are not enabled on this server.")

    prefs = (summary_preferences or "").strip()
    if len(prefs) > MAX_SUMMARY_PREFERENCES_LENGTH:
        prefs = prefs[:MAX_SUMMARY_PREFERENCES_LENGTH]

    query_info = fetch_messages(
        narrow=None,
        user_profile=user_profile,
        realm=user_profile.realm,
        is_web_public_query=False,
        anchor_info=AnchorInfo(type="first_unread", value=None),
        include_anchor=True,
        num_before=0,
        num_after=MAX_OVERVIEW_MESSAGES,
    )

    if not query_info.rows:
        raise JsonableError("No unread messages to summarise.")

    result_message_ids: list[int] = [row[0] for row in query_info.rows]
    user_message_flags: dict[int, list[str]] = {mid: [] for mid in result_message_ids}
    for um in UserMessage.objects.filter(
        user_profile=user_profile,
        message_id__in=result_message_ids,
    ).only("message_id", "flags"):
        user_message_flags[um.message_id] = um.flags_list()

    message_list = messages_for_ids(
        message_ids=result_message_ids,
        user_message_flags=user_message_flags,
        search_fields={},
        apply_markdown=False,
        client_gravatar=True,
        allow_empty_topic_name=True,
        message_edit_history_visibility_policy=MessageEditHistoryVisibilityPolicyEnum.none.value,
        user_profile=user_profile,
        realm=user_profile.realm,
    )

    if not message_list:
        raise JsonableError("No messages found to summarise.")

    from zerver.lib.catchup_claude import CatchUpSummary, summarize_with_claude

    try:
        summary: CatchUpSummary = summarize_with_claude(
            messages=message_list,
            model=model,
            api_key=api_key,
            extra_params=dict(settings.TOPIC_SUMMARIZATION_PARAMETERS),
            user_preferences=prefs or None,
            reader_full_name=user_profile.full_name,
        )
    except Exception as e:
        # Full detail in server logs; clients get a short `msg` (see middleware access-log truncation).
        logger.exception("catch-up/overview: summarization failed")
        raise JsonableError(
            f"Could not generate summary: {_client_safe_llm_error_message(e)}",
        ) from e

    return json_success(request, {"structured": True, **summary.to_dict()})


@typed_endpoint_without_parameters
def get_catch_up_overview(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    """
    Generate a Claude-powered structured overview of ALL unread messages.
    Fetches all unread messages then sends them to Claude for a global
    summary with per-action-item and per-topic context links (US-08).
    """
    return _generate_catch_up_overview(request, user_profile, None)


@typed_endpoint
def post_catch_up_overview(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    summary_preferences: Json[str] = "",
) -> HttpResponse:
    """Same as GET, with optional JSON-encoded `summary_preferences` string in the POST body."""
    return _generate_catch_up_overview(request, user_profile, summary_preferences)
