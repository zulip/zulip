"""
Claude-powered summarization for the "What did I miss?" catch-up view.

Calls Claude (via LiteLLM) with all missed messages and their Zulip deep-link
URLs, then returns a structured summary where every action item and topic
summary is linked back to the exact source message(s) — enabling one-click
context navigation (US-08).

Response schema
---------------
{
  "overview": "2-3 sentence overview",
  "keywords": ["kw1", ...],
  "action_items": [
    {
      "text": "...",
      "assignee": "name or null",
      "message_id": 1234,          ← exact source message
      "narrow_url": "#narrow/..."  ← deep link to that message's topic
    }
  ],
  "topics": [
    {
      "stream": "devel",
      "topic": "Sprint 2 planning",
      "summary": "1-2 sentence summary",
      "narrow_url": "#narrow/...",
      "key_messages": [
        {"id": 1001, "excerpt": "...", "narrow_url": "..."}
      ]
    }
  ]
}
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

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

        context.append({
            "id": msg.get("id"),
            "sender": msg.get("sender_full_name", ""),
            "content": msg.get("content", "")[:600],
            "stream": stream_name,
            "topic": topic,
            "narrow_url": _narrow_url(stream_id, stream_name, topic),
        })
    return context


# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an AI assistant helping a user catch up on Zulip messages they missed.

Analyse the provided messages and return ONLY a valid JSON object — no markdown fences, no explanation.

Required JSON schema:
{
  "overview": "<2-3 sentence plain-English summary of all missed activity>",
  "keywords": ["<up to 6 short keywords>"],
  "action_items": [
    {
      "text": "<concise action item>",
      "assignee": "<person's name, or null if unspecified>",
      "message_id": <integer id of the message this action came from>,
      "narrow_url": "<narrow_url value from that message — copy exactly>"
    }
  ],
  "topics": [
    {
      "stream": "<stream name>",
      "topic": "<topic name>",
      "summary": "<1-2 sentence summary>",
      "narrow_url": "<narrow_url for this topic — copy from a message in this topic>",
      "key_messages": [
        {
          "id": <integer message id>,
          "excerpt": "<10-15 word quote or paraphrase of why this message matters>",
          "narrow_url": "<narrow_url — copy exactly from the message>"
        }
      ]
    }
  ]
}

Rules:
- Include only genuine action items (TODOs, assignments, requests) found verbatim in the messages.
- Every action item must reference the exact message_id it was extracted from.
- key_messages: pick 1-3 most important messages per topic.
- narrow_url: always copy the value exactly from the input — never construct it yourself.
- Return valid JSON only.
"""


# ── Main entry point ──────────────────────────────────────────────────────────

def summarize_with_claude(
    messages: list[dict[str, Any]],
    model: str,
    api_key: str | None,
    extra_params: dict[str, Any] | None = None,
) -> CatchUpSummary:
    """
    Call Claude via LiteLLM with the full message context and return a
    structured CatchUpSummary with deep-link context references.

    Raises litellm exceptions on API errors.
    """
    import litellm  # imported here per Zulip convention (avoids DeprecationWarning)

    context = _build_context(messages)
    user_content = json.dumps(context, ensure_ascii=False)

    llm_messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Here are the {len(context)} messages the user missed:\n\n"
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


