"""
GET /json/catch-up/overview

Returns a Claude-generated structured summary of ALL messages the user
missed across every channel — overview, keywords, action items with
source-message deep links, and per-topic summaries with jump links (US-08).

This is distinct from GET /json/catch-up/summary, which generates a
per-topic summary for a single stream/topic pair.
"""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from zerver.lib.exceptions import JsonableError
from zerver.lib.message import messages_for_ids
from zerver.lib.narrow import AnchorInfo, fetch_messages
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint_without_parameters
from zerver.models import UserProfile
from zerver.models.realms import MessageEditHistoryVisibilityPolicyEnum

MAX_OVERVIEW_MESSAGES = 200


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
    model = settings.TOPIC_SUMMARIZATION_MODEL
    api_key = getattr(settings, "TOPIC_SUMMARIZATION_API_KEY", None)

    if model is None:
        raise JsonableError("AI features are not enabled on this server.")

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
            extra_params={},
        )
    except Exception as e:
        raise JsonableError(f"Claude API error: {e}") from e

    return json_success(request, {"structured": True, **summary.to_dict()})
