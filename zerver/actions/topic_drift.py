import json
import logging
import re
import time
from typing import Any, Literal, TypedDict

from django.conf import settings
from django.utils.timezone import now as timezone_now
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from zerver.actions.message_summary import ai_stats_finish, ai_stats_start
from zerver.lib.streams import access_stream_by_id
from zerver.lib.topic import messages_for_topic
from zerver.models import UserProfile

logger = logging.getLogger(__name__)

# Maximum recent messages to analyze for drift detection to minimize latency & cost.
MAX_MESSAGES_FOR_DRIFT = 15
MIN_MESSAGES_FOR_DRIFT = 2
DRIFT_CACHE_COOLDOWN_SECONDS = 30.0

# In-memory cooldown cache: (stream_id, topic_name.lower()) -> (timestamp, last_message_id, cached_result)
_drift_cache: dict[tuple[int, str], tuple[float, int, dict[str, Any]]] = {}


class TopicDriftResult(TypedDict):
    has_drift: bool
    current_title: str
    suggested_title: str | None
    reason: str | None
    stream_id: int
    topic_name: str
    message_id: int | None


def make_chat_message(
    content: str, role: Literal["user", "system"] = "user"
) -> ChatCompletionMessageParam:
    if role == "system":
        return {"content": content, "role": "system"}
    return {"content": content, "role": "user"}


def clean_json_response(raw_text: str) -> str:
    """Extract JSON object from raw LLM output, handling fences or preamble."""
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    json_match = re.search(r"\{[\s\S]*\}", text)
    if json_match:
        return json_match.group(0).strip()
    return text


def do_check_topic_drift(
    user_profile: UserProfile,
    stream_id: int,
    topic_name: str,
    latest_message_id: int | None = None,
) -> TopicDriftResult:
    model = settings.TOPIC_SUMMARIZATION_MODEL
    if model is None:  # nocoverage
        return {
            "has_drift": False,
            "current_title": topic_name,
            "suggested_title": None,
            "reason": None,
            "stream_id": stream_id,
            "topic_name": topic_name,
            "message_id": latest_message_id,
        }

    # Access stream and ensure permissions
    stream, _ = access_stream_by_id(user_profile, stream_id)

    # Fetch recent messages in topic
    messages_qs = messages_for_topic(
        realm_id=user_profile.realm_id,
        stream_recipient_id=stream.recipient_id,
        topic_name=topic_name,
    ).order_by("-id")[:MAX_MESSAGES_FOR_DRIFT]

    messages = list(reversed(messages_qs))

    # Latency & Cost Optimization: Skip LLM call if conversation is too short
    if len(messages) < MIN_MESSAGES_FOR_DRIFT:
        return {
            "has_drift": False,
            "current_title": topic_name,
            "suggested_title": None,
            "reason": None,
            "stream_id": stream_id,
            "topic_name": topic_name,
            "message_id": messages[-1].id if messages else latest_message_id,
        }

    last_msg_id = messages[-1].id
    cache_key = (stream_id, topic_name.strip().lower())
    now = time.time()

    # Latency & Cost Optimization: In-memory cooldown cache
    if cache_key in _drift_cache:
        cached_time, cached_msg_id, cached_res = _drift_cache[cache_key]
        if (now - cached_time) < DRIFT_CACHE_COOLDOWN_SECONDS and cached_msg_id == last_msg_id:
            return cached_res  # type: ignore[return-value] # Cached result dictionary matches TypedDict schema.

    # Format transcript for prompt (filtering out automated system notifications and bots)
    formatted_messages = []
    for msg in messages:
        if msg.sender.is_bot:
            continue # nocoverage
        sender_name = msg.sender.full_name
        content = msg.content
        formatted_messages.append(f"[{sender_name}]: {content}")

    if not formatted_messages:  # nocoverage
        formatted_messages = [f"[{msg.sender.full_name}]: {msg.content}" for msg in messages]

    transcript = "\n".join(formatted_messages)

    system_prompt = (
        "You are an AI assistant in Zulip team chat that detects conversation topic drift.\n"
        "Topic drift occurs when recent messages diverge from the original topic title to discuss a different subject, "
        "technology, question, or new topic.\n\n"
        "Instructions:\n"
        f'1. Current Topic Title: "{topic_name}"\n'
        f"2. Channel: #{stream.name}\n"
        "3. If the recent messages have diverged onto a new subject that no longer matches the current topic title, "
        'set "has_drift" to true and suggest a concise, accurate "suggested_title" (max 50 chars, plain text).\n'
        '4. If the conversation is still relevant to the current topic title, set "has_drift" to false and "suggested_title" to null.\n'
        "5. Output ONLY valid JSON matching this schema:\n"
        "{\n"
        '  "has_drift": boolean,\n'
        '  "suggested_title": "string or null"\n'
        "}"
    )

    user_prompt = (
        f"Topic: {topic_name}\n"
        f"Channel: #{stream.name}\n\n"
        f"Conversation Messages:\n```\n{transcript}\n```\n\n"
        "Return your evaluation as a JSON object with keys 'has_drift' and 'suggested_title'."
    )

    messages_payload = [
        make_chat_message(system_prompt, "system"),
        make_chat_message(user_prompt, "user"),
    ]

    ai_stats_start()

    client = OpenAI(
        api_key=settings.TOPIC_SUMMARIZATION_API_KEY,
        base_url=settings.TOPIC_SUMMARIZATION_API_BASE,
    )

    response = client.chat.completions.create(
        model=model,
        messages=messages_payload,
        max_tokens=1000,
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    assert response.usage is not None
    input_tokens = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens

    credits_used = (output_tokens * settings.OUTPUT_COST_PER_GIGATOKEN) + (
        input_tokens * settings.INPUT_COST_PER_GIGATOKEN
    )
    ai_stats_finish()

    do_increment_logging_stat(
        user_profile, COUNT_STATS["ai_credit_usage::day"], None, timezone_now(), credits_used
    )

    content = response.choices[0].message.content
    assert content is not None

    logger.debug("TOPIC_DRIFT raw LLM response for topic '%s': %s", topic_name, content)

    has_drift = False
    suggested_title: str | None = None
    reason: str | None = None

    try:
        parsed = json.loads(clean_json_response(content))
        has_drift = bool(parsed.get("has_drift", False))
        if has_drift:
            suggested_title = parsed.get("suggested_title", "")
            if suggested_title:
                suggested_title = str(suggested_title).strip()
            # If the suggested title is identical to the current title, ignore drift
            if not suggested_title or suggested_title.lower() == topic_name.strip().lower():
                has_drift = False
                suggested_title = None
    except Exception as e:
        logger.debug("TOPIC_DRIFT JSON parse error: %s (raw content: %s)", e, content)
        has_drift = False

    result: TopicDriftResult = {
        "has_drift": has_drift,
        "current_title": topic_name,
        "suggested_title": suggested_title,
        "reason": reason,
        "stream_id": stream_id,
        "topic_name": topic_name,
        "message_id": last_msg_id,
    }

    logger.debug("TOPIC_DRIFT final evaluated result: %s", result)

    _drift_cache[cache_key] = (now, last_msg_id, result)
    return result
