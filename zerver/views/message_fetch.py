from collections.abc import Iterable
from typing import Annotated

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db import connection, transaction
from django.http import HttpRequest, HttpResponse
from django.utils.html import escape as escape_html
from django.utils.translation import gettext as _
from pydantic import Json, NonNegativeInt

from zerver.context_processors import get_valid_realm_from_request
from zerver.lib.exceptions import (
    IncompatibleParametersError,
    JsonableError,
    MissingAuthenticationError,
)
from zerver.lib.message import get_first_visible_message_id, messages_for_ids
from zerver.lib.narrow import (
    NarrowParameter,
    add_narrow_conditions,
    clean_narrow_for_message_fetch,
    fetch_messages,
    is_web_public_narrow,
    parse_anchor_value,
)
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.models import UserMessage, UserProfile

MAX_MESSAGES_PER_FETCH = 5000


def highlight_string(text: str, locs: Iterable[tuple[int, int]]) -> str:
    """Highlight matched content in HTML format."""
    highlight_start = '<span class="highlight">'
    highlight_stop = "</span>"
    pos = 0
    result = []
    in_tag = False

    for offset, length in locs:
        prefix = text[pos:offset]
        match = text[offset:offset + length]

        # Handle HTML tags correctly
        for char in prefix + match:
            if char == "<":
                in_tag = True
            elif char == ">":
                in_tag = False

        if in_tag:
            result.append(prefix + match)
        else:
            result.append(prefix + highlight_start + match + highlight_stop)

        pos = offset + length

    result.append(text[pos:])
    return "".join(result)


def get_search_fields(
    rendered_content: str,
    topic_name: str,
    content_matches: Iterable[tuple[int, int]],
    topic_matches: Iterable[tuple[int, int]],
) -> dict[str, str]:
    """Highlight matched content and topic names."""
    return {
        "match_content": highlight_string(rendered_content, content_matches),
        "match_topic": highlight_string(escape_html(topic_name), topic_matches),
    }


@typed_endpoint
def get_messages_backend(
    request: HttpRequest,
    maybe_user_profile: UserProfile | AnonymousUser,
    *,
    anchor_val: Annotated[str | None, ApiParamConfig("anchor")] = None,
    include_anchor: Json[bool] = True,
    num_before: Json[NonNegativeInt] = 0,
    num_after: Json[NonNegativeInt] = 0,
    narrow: Json[list[NarrowParameter] | None] = None,
    use_first_unread_anchor_val: Annotated[Json[bool], ApiParamConfig("use_first_unread_anchor")] = False,
    client_gravatar: Json[bool] = True,
    apply_markdown: Json[bool] = True,
    allow_empty_topic_name: Json[bool] = False,
    client_requested_message_ids: Annotated[Json[list[NonNegativeInt] | None], ApiParamConfig("message_ids")] = None,
) -> HttpResponse:
    """Optimized backend logic to fetch messages with reduced SQL hits."""

    # Validate input parameters
    if (
        num_before or num_after or anchor_val is not None or use_first_unread_anchor_val
    ) and client_requested_message_ids is not None:
        raise IncompatibleParametersError(
            ["num_before", "num_after", "anchor", "message_ids", "include_anchor", "use_first_unread_anchor"]
        )

    # Determine anchor point
    anchor = None
    if client_requested_message_ids is None:
        anchor = parse_anchor_value(anchor_val, use_first_unread_anchor_val)

    # Get realm and narrow conditions
    realm = get_valid_realm_from_request(request)
    narrow = clean_narrow_for_message_fetch(narrow, realm, maybe_user_profile)

    # Validate message request size
    num_requested = (len(client_requested_message_ids) if client_requested_message_ids else (num_before + num_after))
    if num_requested > MAX_MESSAGES_PER_FETCH:
        raise JsonableError(_("Too many messages requested (maximum {max}).").format(max=MAX_MESSAGES_PER_FETCH))

    # Determine user authentication status
    if not maybe_user_profile.is_authenticated:
        if not realm.allow_web_public_streams_access() or not is_web_public_narrow(narrow):
            raise MissingAuthenticationError
        user_profile, is_web_public_query = None, True
        client_gravatar = False
    else:
        assert isinstance(maybe_user_profile, UserProfile)
        user_profile, is_web_public_query = maybe_user_profile, False

    # Optimize SQL queries with atomic transaction
    with transaction.atomic(durable=True):
        if not settings.TEST_SUITE:  # Set isolation level in production
            connection.cursor().execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")

        query_info = fetch_messages(
            narrow=narrow,
            user_profile=user_profile,
            realm=realm,
            is_web_public_query=is_web_public_query,
            anchor=anchor,
            include_anchor=include_anchor,
            num_before=num_before,
            num_after=num_after,
            client_requested_message_ids=client_requested_message_ids,
        )

        rows = query_info.rows
        result_message_ids = [row[0] for row in rows]

        # Batch fetch UserMessage flags in a single query
        user_message_flags = {}
        if user_profile and not is_web_public_query:
            um_rows = UserMessage.objects.filter(
                user_profile=user_profile, message_id__in=result_message_ids
            ).values_list("message_id", "flags")
            
            user_message_flags = {
                msg_id: UserMessage.flags_list_for_flags(flags)
                for msg_id, flags in um_rows
            }

        # Set historical flags for web-public messages
        for message_id in result_message_ids:
            if message_id not in user_message_flags:
                user_message_flags[message_id] = ["read", "historical"]

        # Efficiently fetch message contents in bulk
        search_fields = {
            row[0]: get_search_fields(*row[-4:])
            for row in rows if query_info.is_search
        }

        # Retrieve messages in batch
        message_list = messages_for_ids(
            message_ids=result_message_ids,
            user_message_flags=user_message_flags,
            search_fields=search_fields,
            apply_markdown=apply_markdown,
            client_gravatar=client_gravatar,
            allow_empty_topic_name=allow_empty_topic_name,
            message_edit_history_visibility_policy=realm.message_edit_history_visibility_policy,
            user_profile=user_profile,
            realm=realm,
        )

    # Prepare response
    return json_success(
        request,
        data={
            "messages": message_list,
            "result": "success",
            "found_anchor": query_info.found_anchor,
            "found_oldest": query_info.found_oldest,
            "found_newest": query_info.found_newest,
            "history_limited": query_info.history_limited,
            "anchor": anchor,
        },
    )
