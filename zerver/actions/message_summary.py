import time
from typing import Any, Literal

import orjson
from django.conf import settings
from django.utils.timezone import now as timezone_now
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from zerver.lib.markdown import markdown_convert
from zerver.lib.mention import MENTIONS_RE, MentionBackend, MentionData
from zerver.lib.message import messages_for_ids
from zerver.lib.narrow import (
    LARGER_THAN_MAX_MESSAGE_ID,
    AnchorInfo,
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


def rewrite_mentioned_users_to_silent_mentions(content: str) -> str:
    # Rewrite every user mention into its corresponding silent mention syntax.
    # TODO: we may want to filter out wildcards, since currently the model
    # is explicitly told that this syntax is always a user being mentioned.
    return MENTIONS_RE.sub(lambda m: "@_**{}**".format(m.group("match")), content)


def format_zulip_messages_for_model(zulip_messages: list[dict[str, Any]]) -> str:
    # Format the Zulip messages for processing by the model.
    #
    # - We don't need to encode the recipient, since that's the same for
    #   every message in the conversation.
    # - Every user the summary may name is written as a silent mention for
    #   the model to copy.
    # - We don't include timestamps, since experiments with current models
    #   suggest they do not make relevant use of them.
    # - We haven't figured out a useful way to include reaction metadata (either
    #   the emoji themselves or just the counter).
    # - Polls/TODO widgets are currently sent to the model as empty messages,
    #   since this logic doesn't inspect SubMessage objects.
    zulip_messages_list = [
        {
            "sender": f"@_**{message['sender_full_name']}|{message['sender_id']}**",
            "content": rewrite_mentioned_users_to_silent_mentions(message["content"]),
        }
        for message in zulip_messages
    ]
    return orjson.dumps(zulip_messages_list).decode()


def make_message(
    content: str, role: Literal["user", "system"] = "user"
) -> ChatCompletionMessageParam:
    if role == "system":
        return {"content": content, "role": "system"}
    return {"content": content, "role": "user"}


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
        anchor_info=AnchorInfo(type="message_id", value=LARGER_THAN_MAX_MESSAGE_ID),
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
        f"Mention key conclusions and actions, if any. "
        f"Don't use an intro phrase. You can use Zulip's CommonMark based formatting."
    )
    mention_instructions = (
        " Refer to specific people as appropriate. Every person in the conversation above is "
        "written as a mention: the prefix @_** followed by text identifying that person followed "
        "by the suffix **. A message's author appears as its sender; anyone else appears within "
        "the message content. When you refer to a person, reproduce their whole mention character for "
        "character, prefix and suffix included, and write one mention per person. Never write a "
        "mention that does not appear above; where a person is given as plain text rather than as "
        "a mention, refer to them by that plain text alone."
    )

    prompt += mention_instructions

    messages = [
        make_message(intro, "system"),
        make_message(formatted_conversation),
        make_message(prompt),
    ]

    # Stats for database queries are tracked separately.
    ai_stats_start()

    # TODO when implementing user plans:
    # - Before querying the model, check whether we've enough tokens left using
    # an estimated token count.
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

    client = OpenAI(
        api_key=settings.TOPIC_SUMMARIZATION_API_KEY,
        base_url=settings.TOPIC_SUMMARIZATION_API_BASE,
    )
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        **settings.TOPIC_SUMMARIZATION_PARAMETERS,
    )
    assert response.usage is not None
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens

    # Divide by 1 billion to get actual cost in USD.
    credits_used = (output_tokens * settings.OUTPUT_COST_PER_GIGATOKEN) + (
        input_tokens * settings.INPUT_COST_PER_GIGATOKEN
    )
    ai_stats_finish()

    do_increment_logging_stat(
        user_profile, COUNT_STATS["ai_credit_usage::day"], None, timezone_now(), credits_used
    )

    summary = response.choices[0].message.content
    assert summary is not None

    # We render the LLM summary against MentionData scoped to the acting
    # user, to handle mention permission for users (senders or mentioned)
    # that are all now mentioned in the summary, and also in
    # case the model invents inaccessible/non-existing users.
    mention_backend = MentionBackend(user_profile.realm_id)
    mention_data = MentionData(
        mention_backend=mention_backend,
        content=summary,
        message_sender=user_profile,
    )
    rendered_summary = markdown_convert(
        summary,
        message_realm=user_profile.realm,
        acting_user=user_profile,
        mention_data=mention_data,
    ).rendered_content
    return rendered_summary
