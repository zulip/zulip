"""
Claude-powered summarization for the "What did I miss?" catch-up view.

Calls Claude (via LiteLLM) with all missed messages and their Zulip deep-link
URLs, then returns a structured summary where every action item and topic
summary is linked back to the exact source message(s) — enabling one-click
context navigation (US-08).

Response schema
---------------
{
  "overview": "one ultra-short paragraph (see system prompt length limits)",
  "keywords": ["kw1", ...],
  "action_items": [...],
  "topics": [...]
}
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from zerver.lib.url_encoding import encode_channel, encode_hash_component


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ContextLink:
    message_id: int
    narrow_url: str
    excerpt: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.message_id,
            "excerpt": self.excerpt,
            "narrow_url": self.narrow_url,
        }


@dataclass
class ActionItem:
    text: str
    assignee: str | None
    message_id: int | None
    narrow_url: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "assignee": self.assignee,
            "message_id": self.message_id,
            "narrow_url": self.narrow_url,
        }


@dataclass
class TopicSummary:
    stream: str
    topic: str
    summary: str
    narrow_url: str
    key_messages: list[ContextLink] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stream": self.stream,
            "topic": self.topic,
            "summary": self.summary,
            "narrow_url": self.narrow_url,
            "key_messages": [km.to_dict() for km in self.key_messages],
        }


@dataclass
class CatchUpSummary:
    overview: str
    keywords: list[str]
    action_items: list[ActionItem]
    topics: list[TopicSummary]
    model_used: str = ""
    message_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "overview": self.overview,
            "keywords": self.keywords,
            "action_items": [a.to_dict() for a in self.action_items],
            "topics": [t.to_dict() for t in self.topics],
            "model_used": self.model_used,
            "message_count": self.message_count,
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _narrow_url(stream_id: int, stream_name: str, topic: str) -> str:
    return f"#narrow/{encode_channel(stream_id, stream_name, with_operator=True)}/topic/{encode_hash_component(topic)}"


def _mention_kind_for_reader(flags: list[str]) -> str | None:
    """How this message notified the reader, from UserMessage API flags."""
    if "mentioned" in flags:
        return "user"
    if "group_mentioned" in flags:
        return "group"
    if "stream_wildcard_mentioned" in flags:
        return "stream_wildcard"
    if "topic_wildcard_mentioned" in flags:
        return "topic_wildcard"
    return None


def _build_context(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert raw Zulip message dicts into a compact context list for Claude.
    Each entry includes the message ID and a pre-built narrow_url so Claude
    can echo them back verbatim in the structured response.
    """
    context = []
    for msg in messages:
        stream_id = msg.get("stream_id", 0)
        raw_recipient = msg.get("display_recipient", "")
        stream_name = (
            raw_recipient
            if isinstance(raw_recipient, str)
            else (raw_recipient[0].get("name", "") if raw_recipient else "")
        )
        topic = msg.get("subject", "")
        flags = msg.get("flags") if isinstance(msg.get("flags"), list) else []

        context.append({
            "id": msg.get("id"),
            "sender": msg.get("sender_full_name", ""),
            "content": msg.get("content", "")[:600],
            "stream": stream_name,
            "topic": topic,
            "narrow_url": _narrow_url(stream_id, stream_name, topic),
            "mention_to_reader": _mention_kind_for_reader(flags),
        })
    return context


# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an AI assistant helping ONE specific person catch up on Zulip messages they missed.

The user message will name that person (the reader). Write the entire summary as if you are speaking to them directly: use "you" and "your"; never refer to the reader in the third person (no "they/them" for the reader).

Be extremely brief. They want a skim, not an essay.

Each input message may include "mention_to_reader": if set, that message notified the reader — how they were pinged matters for tone:
- "user" — the sender @-mentioned them by name (say things like "<Sender> tagged you" or "@-mentioned you").
- "group" — a user group they belong to was @-mentioned (say they were mentioned via that group).
- "stream_wildcard" / "topic_wildcard" — a stream-wide or topic-wide @-mention reached them (say e.g. "@**topic** included you" or "you were pinged with everyone in this topic").

When summarizing a thread where the reader was personally notified, prefer lines like "<Sender> tagged you in this thread …" or "You were @-mentioned because …" instead of flat third-person reportage ("Aaron said to Shiv …"). If they were not mentioned, you may still use second person ("You missed …", "People discussed …").

Analyse the provided messages and return ONLY a valid JSON object — no markdown fences, no explanation.

Required JSON schema:
{
  "overview": "<at most 2 short sentences OR roughly 50 words total — what mattered most to YOU (the reader), period>",
  "keywords": ["<up to 5 single-word or two-word keywords>"],
  "action_items": [
    {
      "text": "<max ~12 words — the action only>",
      "assignee": "<person's name, or null if unspecified>",
      "message_id": <integer id of the message this action came from>,
      "narrow_url": "<narrow_url value from that message — copy exactly>"
    }
  ],
  "topics": [
    {
      "stream": "<stream name>",
      "topic": "<topic name>",
      "summary": "<one short sentence, max ~20 words, addressed to the reader when a ping/mention applies>",
      "narrow_url": "<narrow_url for this topic — copy from a message in this topic>",
      "key_messages": [
        {
          "id": <integer message id>,
          "excerpt": "<max ~8 words>",
          "narrow_url": "<narrow_url — copy exactly from the message>"
        }
      ]
    }
  ]
}

Rules:
- Include only genuine action items (TODOs, assignments, requests) grounded in the messages.
- Every action item must reference the exact message_id it was extracted from.
- key_messages: at most 2 entries per topic unless the user preferences explicitly ask for more detail.
- narrow_url: always copy the value exactly from the input — never construct it yourself.
- If the user provided preferences in their message, follow them for tone and focus, but still respect the brevity limits above.
- Return valid JSON only.
"""


# ── Main entry point ──────────────────────────────────────────────────────────

def summarize_with_claude(
    messages: list[dict[str, Any]],
    model: str,
    api_key: str | None,
    extra_params: dict[str, Any] | None = None,
    user_preferences: str | None = None,
    *,
    reader_full_name: str = "",
) -> CatchUpSummary:
    """
    Call Claude via LiteLLM with the full message context and return a
    structured CatchUpSummary with deep-link context references.

    Raises litellm exceptions on API errors.
    """
    import litellm  # imported here per Zulip convention (avoids DeprecationWarning)

    if settings.DEBUG:
        # Option B from LiteLLM docs: verbose request/response logging. Can leak API
        # keys and message text into the console — only when Django DEBUG is on.
        turn_on_debug = getattr(litellm, "_turn_on_debug", None)
        if callable(turn_on_debug):
            turn_on_debug()
        else:
            litellm.set_verbose(True)

    context = _build_context(messages)
    user_content = json.dumps(context, ensure_ascii=False)

    reader_line = ""
    name = reader_full_name.strip()
    if name:
        reader_line = (
            f"You are summarizing for the reader named «{name}». "
            "Address all overview and topic text to them as «you»; they are the one catching up.\n\n"
        )

    preference_block = ""
    if user_preferences and user_preferences.strip():
        preference_block = (
            "User preferences for this summary (apply when they do not conflict with "
            "schema or safety; still keep output very short):\n"
            f"{user_preferences.strip()}\n\n"
        )

    llm_messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"{reader_line}"
                f"{preference_block}"
                f"Here are the {len(context)} messages they missed:\n\n"
                f"{user_content}\n\n"
                "Return the JSON summary."
            ),
        },
    ]

    call_params: dict[str, Any] = {
        "model": model,
        "messages": llm_messages,
    }
    # json_object response format works for Claude and most OpenAI-compatible models
    if "anthropic" in model or "claude" in model.lower():
        # Claude doesn't support response_format kwarg; JSON is enforced via the prompt
        pass
    else:
        call_params["response_format"] = {"type": "json_object"}

    if api_key:
        call_params["api_key"] = api_key
    if extra_params:
        call_params.update(extra_params)

    response = litellm.completion(**call_params)
    raw: str = response["choices"][0]["message"]["content"]

    # Parse — strip accidental markdown fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw.strip())

    try:
        data: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        # Last-resort: extract first {...} block
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            data = json.loads(m.group())
        else:
            raise ValueError(f"Claude returned non-JSON response: {raw[:300]}")

    # ── Build action items ────────────────────────────────────────────────────
    action_items = [
        ActionItem(
            text=item.get("text", ""),
            assignee=item.get("assignee") or None,
            message_id=item.get("message_id"),
            narrow_url=item.get("narrow_url"),
        )
        for item in data.get("action_items", [])
        if item.get("text")
    ]

    # ── Build topic summaries ─────────────────────────────────────────────────
    topics = []
    for t in data.get("topics", []):
        key_messages = [
            ContextLink(
                message_id=int(km.get("id", 0)),
                narrow_url=km.get("narrow_url", ""),
                excerpt=km.get("excerpt", ""),
            )
            for km in t.get("key_messages", [])
            if km.get("id")
        ]
        topics.append(
            TopicSummary(
                stream=t.get("stream", ""),
                topic=t.get("topic", ""),
                summary=t.get("summary", ""),
                narrow_url=t.get("narrow_url", ""),
                key_messages=key_messages,
            )
        )

    return CatchUpSummary(
        overview=data.get("overview", ""),
        keywords=data.get("keywords", []),
        action_items=action_items,
        topics=topics,
        model_used=model,
        message_count=len(messages),
    )


