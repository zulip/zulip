import json
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from pydantic import Json

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from zerver.lib.exceptions import JsonableError
from zerver.lib.message import messages_for_ids
from zerver.lib.narrow import (
    LARGER_THAN_MAX_MESSAGE_ID,
    NarrowParameter,
    clean_narrow_for_message_fetch,
    fetch_messages,
)
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile

# Maximum number of messages that can be summarized in a single request.
MAX_MESSAGES_SUMMARIZED = 100
# Price per token for input and output tokens.
# These values are based on the pricing of the Bedrock API
# for Llama 3.3 Instruct (70B).
# https://aws.amazon.com/bedrock/pricing/
# Unit: USD per 1 billion tokens.
#
# These values likely will want to be declared in configuration,
# rather than here in the code.
OUTPUT_COST_PER_GIGATOKEN = 720
INPUT_COST_PER_GIGATOKEN = 720


def format_zulip_messages_for_model(zulip_messages: list[dict[str, Any]]) -> str:
    # Format the Zulip messages for processing by the model.
    #
    # - We don't need to encode the recipient, since that's the same for
    #   every message in the conversation.
    # - We use full names to reference senders, since we want the
    #   model to refer to users by name. We may want to experiment
    #   with using silent-mention syntax for users if we move to
    #   Markdown-rendering what the model returns.
    # - We don't include timestamps, since experiments with current models
    #   suggest they do not make relevant use of them.
    # - We haven't figured out a useful way to include reaction metadata (either
    #   the emoji themselves or just the counter).
    # - Polls/TODO widgets are currently sent to the model as empty messages,
    #   since this logic doesn't inspect SubMessage objects.
    zulip_messages_list = [
        {"sender": message["sender_full_name"], "content": message["content"]}
        for message in zulip_messages
    ]
    return json.dumps(zulip_messages_list)


def make_message(content: str, role: str = "user") -> dict[str, str]:
    return {"content": content, "role": role}


def get_max_summary_length(conversation_length: int) -> int:
    # Longer summaries work better for longer conversation.
    # TODO: Test more with message content length.
    return min(6, 4 + int((conversation_length - 10) / 10))


@typed_endpoint
def get_messages_summary(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    narrow: Json[list[NarrowParameter] | None] = None,
) -> HttpResponse:
    if settings.TOPIC_SUMMARIZATION_MODEL is None:
        raise JsonableError(_("AI features are not enabled on this server."))

    if not (user_profile.is_moderator or user_profile.is_realm_admin):
        return json_success(request, {"summary": "Feature limited to moderators for now."})

    # TODO: This implementation does not attempt to make use of
    # caching previous summaries of the same conversation or rolling
    # summaries. Doing so correctly will require careful work around
    # invalidation of caches when messages are edited, moved, or sent.
    narrow = clean_narrow_for_message_fetch(narrow, user_profile.realm, user_profile)
    query_info = fetch_messages(
        narrow=narrow,
        user_profile=user_profile,
        realm=user_profile.realm,
        is_web_public_query=False,
        anchor=LARGER_THAN_MAX_MESSAGE_ID,
        include_anchor=True,
        num_before=MAX_MESSAGES_SUMMARIZED,
        num_after=0,
    )

    if len(query_info.rows) == 0:
        return json_success(request, {"summary": "No messages in conversation to summarize"})

    result_message_ids: list[int] = []
    user_message_flags: dict[int, list[str]] = {}
    for row in query_info.rows:
        message_id = row[0]
        result_message_ids.append(message_id)
        # We skip populating flags, since they would be ignored below anyway.
        user_message_flags[message_id] = []

    message_list = messages_for_ids(
        message_ids=result_message_ids,
        user_message_flags=user_message_flags,
        search_fields={},
        # We currently prefer the plain-text content of messages to
        apply_markdown=False,
        # Avoid wasting resources computing gravatars.
        client_gravatar=True,
        allow_empty_topic_name=False,
        # Avoid fetching edit history, which won't be passed to the model.
        allow_edit_history=False,
        user_profile=user_profile,
        realm=user_profile.realm,
    )

    # IDEA: We could consider translating input and output text to
    # English to improve results when using a summarization model that
    # is primarily trained on English.
    model = settings.TOPIC_SUMMARIZATION_MODEL
    litellm_params: dict[str, Any] = {}
    if model.startswith("huggingface"):
        assert settings.HUGGINGFACE_API_KEY is not None
        litellm_params["api_key"] = settings.HUGGINGFACE_API_KEY
    else:
        assert model.startswith("bedrock")
        litellm_params["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        litellm_params["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        litellm_params["aws_region_name"] = settings.AWS_REGION_NAME

    conversation_length = len(message_list)
    max_summary_length = get_max_summary_length(conversation_length)
    intro = "The following is a chat conversation in the Zulip team chat app."
    topic: str | None = None
    channel: str | None = None
    if narrow and len(narrow) == 2:
        for term in narrow:
            assert not term.negated
            if term.operator == "channel":
                channel = term.operand
            if term.operator == "topic":
                topic = term.operand
    if channel:
        intro += f" channel: {channel}"
    if topic:
        intro += f", topic: {topic}"

    formatted_conversation = format_zulip_messages_for_model(message_list)
    prompt = (
        f"Succinctly summarize this conversation based only on the information provided, "
        f"in up to {max_summary_length} sentences, for someone who is familiar with the context. "
        f"Mention key conclusions and actions, if any. Refer to specific people as appropriate. "
        f"Don't use an intro phrase."
    )
    messages = [
        make_message(intro, "system"),
        make_message(formatted_conversation),
        make_message(prompt),
    ]

    # We import litellm here to avoid a DeprecationWarning.
    # See these issues for more info:
    # https://github.com/BerriAI/litellm/issues/6232
    # https://github.com/BerriAI/litellm/issues/5647
    import litellm

    # Token counter is recommended by LiteLLM but mypy says it's not explicitly exported.
    # https://docs.litellm.ai/docs/completion/token_usage#3-token_counter
    # estimated_input_tokens = litellm.token_counter(model=model, messages=messages)  # type: ignore[attr-defined] # Explained above

    # TODO when implementing user plans:
    # - Before querying the model, check whether we've enough tokens left using
    # the estimated token count.
    # - Then increase the `LoggingCountStat` using the estimated token count.
    # (These first two steps should be a short database transaction that
    # locks the `LoggingCountStat` row).
    # - Then query the model.
    # - Then adjust the `LoggingCountStat` by `(actual - estimated)`,
    # being careful to avoid doing this to the next day if the query
    # happened milliseconds before midnight; changing the
    # `LoggingCountStat` we added the estimate to.
    # That way, you can't easily get extra tokens by sending
    # 25 requests all at once when you're just below the limit.

    response = litellm.completion(
        model=model,
        messages=messages,
        **litellm_params,
    )
    output_tokens = response["usage"]["completion_tokens"]

    credits_used = (output_tokens * OUTPUT_COST_PER_GIGATOKEN) + (
        input_tokens * INPUT_COST_PER_GIGATOKEN
    )
    do_increment_logging_stat(
        user_profile, COUNT_STATS["ai_credit_usage::day"], None, timezone_now(), credits_used
    )

    return json_success(request, {"summary": response["choices"][0]["message"]["content"]})
