"""Structured assistant card payloads and the nodl-card:v1 encoding (AD-12).

Cards are embedded in message content as
``<!-- nodl-card:v1:{base64url-json} -->`` followed by human-readable
markdown fallback. Base64url is used deliberately: Zulip renders message
content through markdown/HTML escaping, and raw JSON inside HTML comments
proved escape-fragile (the legacy ``<!-- meeting:{json} -->`` parser needs
three escaping variants). Base64url survives every escaping layer intact.

Unknown card types/versions must degrade to the markdown fallback on every
consumer — never hard-fail rendering.
"""

import base64
import json
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

NODL_CARD_VERSION = "v1"
NODL_CARD_PREFIX = f"<!-- nodl-card:{NODL_CARD_VERSION}:"
NODL_CARD_SUFFIX = " -->"


class AskAiAnswerCard(BaseModel):
    """Ask AI result posted back into the task stream (Story 2.3 AC5)."""

    task_id: str
    mode: Literal["assessment", "qa"]
    question: str | None = None
    answer: str
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_items: list[str] = Field(default_factory=list)
    covers_anchor: int | None = None
    generated_at: str | None = None


class CheckinCard(BaseModel):
    """Supervisor check-in card with status buttons (Story 2.5 AC2)."""

    checkin_id: str
    task_id: str
    workspace_id: str
    rule: str
    question: str
    due_date: str | None = None
    options: list[str] = Field(default_factory=lambda: ["on_track", "blocked", "needs_extension"])
    status: Literal["pending", "responded"] = "pending"
    response: str | None = None


CARD_SCHEMAS: dict[str, type[BaseModel]] = {
    "ask_ai_answer": AskAiAnswerCard,
    "checkin": CheckinCard,
}


class UnknownCardTypeError(ValueError):
    """Raised when a card_type has no registered schema."""


def validate_card_payload(card_type: str, payload: dict[str, Any]) -> BaseModel:
    """Validate a card payload against its registered schema.

    Raises UnknownCardTypeError for unregistered types and pydantic
    ValidationError for schema violations.
    """
    schema = CARD_SCHEMAS.get(card_type)
    if schema is None:
        raise UnknownCardTypeError(f"Unknown card_type: {card_type}")
    return schema(**payload)


def encode_card(card_type: str, payload: dict[str, Any]) -> str:
    """Encode a validated card payload as a nodl-card:v1 HTML comment."""
    validated = validate_card_payload(card_type, payload)
    envelope = {"card_type": card_type, "payload": validated.model_dump()}
    raw = json.dumps(envelope, separators=(",", ":"), ensure_ascii=True)
    encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
    return f"{NODL_CARD_PREFIX}{encoded}{NODL_CARD_SUFFIX}"


def build_card_message_content(
    card_type: str, payload: dict[str, Any], fallback_markdown: str
) -> str:
    """Compose full message content: encoded card + markdown fallback (AD-12)."""
    return f"{encode_card(card_type, payload)}\n\n{fallback_markdown}"


__all__ = [
    "AskAiAnswerCard",
    "CheckinCard",
    "CARD_SCHEMAS",
    "UnknownCardTypeError",
    "ValidationError",
    "validate_card_payload",
    "encode_card",
    "build_card_message_content",
]
