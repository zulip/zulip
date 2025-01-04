from collections.abc import Iterable
from typing import Dict, List, Optional, Union

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db import connection, transaction
from django.http import HttpRequest, HttpResponse
from django.utils.html import escape as escape_html
from django.utils.translation import gettext as _
from pydantic import Json, NonNegativeInt
from sqlalchemy.sql import and_, column, join, literal, literal_column, select, table
from sqlalchemy.types import Integer, Text

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
    fetch_messages,
    is_spectator_compatible,
    is_web_public_narrow,
    parse_anchor_value,
    update_narrow_terms_containing_with_operator,
)
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.lib.sqlalchemy_utils import get_sqlalchemy_connection
from zerver.lib.topic import DB_TOPIC_NAME, MATCH_TOPIC
from zerver.lib.topic_sqlalchemy import topic_column_sa
from zerver.lib.typed_endpoint import ApiParamConfig, typed_endpoint
from zerver.models import UserMessage, UserProfile
from zerver.views.message_fetch import get_messages_backend
from zproject.config import get_secret
from litellm import completion 
import json

# Maximum number of messages that can be summarized in a single request.
MAX_MESSAGES_SUMMARIZED = 100

def format_conversation(zulip_messages) -> str:
    # Note: Including timestamps seems to have no impact; including reactions
    # makes the results worse.

    zulip_messages_list = [
        {"sender": message["sender_full_name"], "content": message["content"]}
        for message in zulip_messages
    ]
    return json.dumps(zulip_messages_list)

def make_message(content: str, role: str = "user") -> Dict[str, str]:
    return {"content": content, "role": role}


def get_max_summary_length(conversation_length: int) -> int:
    return min(6, 4 + int((conversation_length - 10) / 10))

@typed_endpoint
def get_messages_summary(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    narrow: Json[list[NarrowParameter] | None] = None,
) -> HttpResponse:
    # Since there will always be a limit to how much data we want the LLM to process
    # at once, due to API limits or performance reasons atleast, we generate summaries
    # for the messages in chunks. We will be using Rolling Summaries for this purpose.
    # Rolling Summaries are summaries that are generated for a fixed number of messages
    # at a time, and then the next summary is generated for the next fixed number of
    # messages with the previous summary as the starting point. This way, we can
    # generate summaries for new messages in a single pass.
    # TODO: Come up with a plan to store these summaries in the database.

    messages_response = get_messages_backend(request, user_profile, narrow=narrow, anchor_val="newest", num_before=MAX_MESSAGES_SUMMARIZED, client_gravatar=False, apply_markdown=False)
    zulip_messages = messages_response.get_data().get("messages", [])
    if len(zulip_messages) == 0:
        return json_success(request, {"summary": "No messages in conversation to summarize"})

    # XXX: Translate input and output text to English?
    model = settings.TOPIC_SUMMARIZATION_MODEL
    api_key = get_secret("llm_api_key")
    conversation_length = len(zulip_messages)
    max_summary_length = get_max_summary_length(conversation_length)
    intro = f"The following is a chat conversation in the Zulip team chat app."
    formatted_conversation = format_conversation(zulip_messages)
    prompt = f"Succinctly summarize this conversation based only on the information provided, in up to {max_summary_length} sentences, for someone who is familiar with the context. Mention key conclusions and actions, if any. Refer to specific people as appropriate. Don't use an intro phrase."
    messages = [
        make_message(intro, "system"),
        make_message(formatted_conversation),
        make_message(prompt),
    ]

    response = completion(
        # max_tokens=args.max_tokens,
        model=model,
        messages=messages,
        api_key=api_key,
    )
    return json_success(request, {"summary": response["choices"][0]["message"]["content"]})
