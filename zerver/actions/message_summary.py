import time
from typing import Any

import orjson
from django.conf import settings
from django.utils.timezone import now as timezone_now

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from zerver.lib.markdown import markdown_convert
from zerver.lib.message import messages_for_ids
from zerver.lib.narrow import (
    LARGER_THAN_MAX_MESSAGE_ID,
    NarrowParameter,
    clean_narrow_for_message_fetch,
    fetch_messages,
)
from zerver.models import UserProfile
from zerver.models.realms import MessageEditHistoryVisibilityPolicyEnum

# Maximum number of messages that can be summarized in a single request.
MAX_MESSAGES_SUMMARIZED = 100

ai_time_start = 0.0
ai_total_time = 0.0
ai_total_requests = 0


def get_ai_time() -> float:
    return ai_total_time


def ai_stats_start() -> None:
    global ai_time_start
    ai_time_start = time.time()


def get_ai_requests() -> int:
    return ai_total_requests


def ai_stats_finish() -> None:
    global ai_total_time, ai_total_requests
    ai_total_requests += 1
    ai_total_time += time.time() - ai_time_start


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
    return orjson.dumps(zulip_messages_list).decode()


def make_message(content: str, role: str = "user") -> dict[str, str]:
    return {"content": content, "role": role}


def get_max_summary_length(conversation_length: int) -> int:
    # Longer summaries work better for longer conversation.
    # TODO: Test more with message content length.
    return min(6, 4 + int((conversation_length - 10) / 10))


def do_summarize_narrow(
    user_profile: UserProfile,
    narrow: list[NarrowParameter] | None,
) -> str | None:
    model = settings.TOPIC_SUMMARIZATION_MODEL
    if model is None:  # nocoverage
        return None

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

    if len(query_info.rows) == 0:  # nocoverage
        return None

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
        message_edit_history_visibility_policy=MessageEditHistoryVisibilityPolicyEnum.none.value,
        user_profile=user_profile,
        realm=user_profile.realm,
    )

    # IDEA: We could consider translating input and output text to
    # English to improve results when using a summarization model that
    # is primarily trained on English.
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
        f"Don't use an intro phrase. You can use Zulip's CommonMark based formatting."
    )
    messages = [
        make_message(intro, "system"),
        make_message(formatted_conversation),
        make_message(prompt),
    ]

    # Stats for database queries are tracked separately.
    ai_stats_start()
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

    litellm_params: dict[str, object] = settings.TOPIC_SUMMARIZATION_PARAMETERS
    api_key = settings.TOPIC_SUMMARIZATION_API_KEY
    response = litellm.completion(
        model=model,
        messages=messages,
        api_key=api_key,
        **litellm_params,
    )
    input_tokens = response["usage"]["prompt_tokens"]
    output_tokens = response["usage"]["completion_tokens"]

    # Divide by 1 billion to get actual cost in USD.
    credits_used = (output_tokens * settings.OUTPUT_COST_PER_GIGATOKEN) + (
        input_tokens * settings.INPUT_COST_PER_GIGATOKEN
    )
    ai_stats_finish()

    do_increment_logging_stat(
        user_profile, COUNT_STATS["ai_credit_usage::day"], None, timezone_now(), credits_used
    )

    summary = response["choices"][0]["message"]["content"]
    # TODO: This may want to fetch `MentionData`, in order to be able
    # to process channel or user mentions that might be in the
    # content. Requires a prompt that supports it.
    rendered_summary = markdown_convert(summary, message_realm=user_profile.realm).rendered_content
    return rendered_summary
