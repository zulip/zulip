# Webhooks for external integrations.
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse

from zerver.decorator import webhook_view
from zerver.lib.exceptions import AnomalousWebhookPayloadError, UnsupportedWebhookEventTypeError
from zerver.lib.response import json_success
from zerver.lib.timestamp import datetime_to_global_time
from zerver.lib.typed_endpoint import JsonBodyPayload, typed_endpoint
from zerver.lib.validator import (
    WildValue,
    check_bool,
    check_int,
    check_iso_datetime,
    check_none_or,
    check_string,
)
from zerver.lib.webhooks.common import check_send_webhook_message
from zerver.models import UserProfile

# Assistant post-call webhooks are unsigned. Workspace and booking
# deliveries are signed with X-Famulor-Signature, but Zulip incoming
# webhooks authenticate with the bot API key and no integration view
# checks a provider HMAC.
ALL_EVENT_TYPES = [
    "booking.cancelled",
    "booking.created",
    "booking.rescheduled",
    "call.completed",
    "conversation.ended",
]
BOOKING_EVENTS = {
    "booking.created": "booked",
    "booking.cancelled": "cancelled",
    "booking.rescheduled": "rescheduled",
}
CONVERSATION_TYPE_LABELS = {
    "widget": "Widget",
    "whatsapp": "WhatsApp",
}
MAPPING_LIMIT = 8


def quantity(count: int, singular: str) -> str:
    noun = singular if count == 1 else f"{singular}s"
    return f"{count} {noun}"


def format_duration(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(quantity(hours, "hour"))
    if minutes:
        parts.append(quantity(minutes, "minute"))
    if secs or not parts:
        parts.append(quantity(secs, "second"))
    return " ".join(parts)


def format_time(value: str) -> str:
    try:
        parsed = check_iso_datetime("time", value)
    except ValidationError:
        return value
    if parsed.tzinfo is None:
        return value
    return datetime_to_global_time(parsed)


def optional_string(node: WildValue, key: str) -> str | None:
    if key not in node:
        return None
    value = node[key].tame(check_none_or(check_string))
    if value is None or not value.strip():
        return None
    return value.strip()


def optional_int(node: WildValue, key: str) -> int | None:
    if key not in node:
        return None
    return node[key].tame(check_none_or(check_int))


def optional_bool(node: WildValue, key: str) -> bool | None:
    if key not in node or not isinstance(node[key].value, bool):
        return None
    return node[key].tame(check_bool)


def optional_object(node: WildValue, key: str) -> WildValue | None:
    if key not in node or not isinstance(node[key].value, dict):
        return None
    return node[key]


def format_scalar_value(value: WildValue) -> str | None:
    raw = value.value
    # JSON booleans are integers, so they have to be matched first.
    if isinstance(raw, bool):
        return "yes" if raw else "no"
    if isinstance(raw, str):
        stripped = raw.strip()
        return stripped or None
    if isinstance(raw, int | float):
        return str(raw)
    return None


def format_mapping(mapping: WildValue, *, skip: set[str] | None = None) -> str:
    skipped = skip or set()
    shown: list[str] = []
    hidden = 0
    for key, value in mapping.items():
        if key in skipped:
            continue
        rendered = format_scalar_value(value)
        if rendered is None:
            continue
        if len(shown) < MAPPING_LIMIT:
            shown.append(f"* {key}: {rendered}")
        else:
            hidden += 1
    if hidden:
        shown.append("* and " + quantity(hidden, "field"))
    return "\n".join(shown)


def append_mapping(
    blocks: list[str],
    title: str,
    node: WildValue,
    key: str,
    *,
    skip: set[str] | None = None,
) -> None:
    mapping = optional_object(node, key)
    if mapping is None:
        return
    body = format_mapping(mapping, skip=skip)
    if body:
        blocks.append(f"**{title}**:\n{body}")


def customer_phone(data: WildValue, direction: str | None) -> str | None:
    from_number = optional_string(data, "from_number")
    to_number = optional_string(data, "to_number")
    if direction == "outbound":
        return to_number or from_number
    if direction == "inbound":
        return from_number or to_number
    return from_number or to_number


def status_label(status: str) -> str:
    return status.replace("_", " ")


def call_topic(data: WildValue, direction: str | None, call_id: str | None) -> str:
    phone = customer_phone(data, direction) or optional_string(data, "customer_phone")
    if phone:
        return phone
    if call_id:
        return f"Call {call_id}"
    return "Famulor call"


def append_failure(lines: list[str], data: WildValue) -> None:
    failure = optional_object(data, "failure")
    if failure is None:
        return
    code = optional_string(failure, "code")
    message = optional_string(failure, "message")
    operation = optional_string(failure, "operation")
    action = optional_string(failure, "action")
    retryable = optional_bool(failure, "retryable")
    if message and code:
        detail = f"{message} ({code})"
    elif message is not None:
        detail = message
    elif code is not None:
        detail = code
    else:
        return
    heading = f"Failure ({operation})" if operation else "Failure"
    lines.append(f"**{heading}**: {detail}")
    if retryable is not None:
        lines.append(f"**Retryable**: {'yes' if retryable else 'no'}")
    if action:
        lines.append(f"**Suggested action**: {action.replace('_', ' ')}")


def append_analysis(lines: list[str], data: WildValue) -> None:
    analysis = optional_object(data, "analysis")
    if analysis is None:
        return
    summary = optional_string(analysis, "summary")
    outcome = optional_string(analysis, "success_reason")
    sentiment = optional_string(analysis, "sentiment")
    success = optional_bool(analysis, "success")
    if summary:
        lines.append(f"**Summary**: {summary}")
    if outcome:
        lines.append(f"**Outcome**: {outcome}")
    if sentiment:
        lines.append(f"**Sentiment**: {sentiment}")
    if success is not None:
        lines.append(f"**Success**: {'yes' if success else 'no'}")


def append_phones(lines: list[str], data: WildValue) -> None:
    from_number = optional_string(data, "from_number")
    to_number = optional_string(data, "to_number")
    customer = optional_string(data, "customer_phone")
    assistant = optional_string(data, "assistant_phone")
    if from_number:
        lines.append(f"**From**: {from_number}")
    if to_number:
        lines.append(f"**To**: {to_number}")
    if customer:
        lines.append(f"**Customer phone**: {customer}")
    if assistant:
        lines.append(f"**Assistant phone**: {assistant}")


def append_recording(lines: list[str], data: WildValue) -> None:
    recording_url = optional_string(data, "recording_url")
    if recording_url:
        lines.append(f"**Recording**: [Recording]({recording_url})")


def handle_call_completed(data: WildValue) -> tuple[str, str]:
    direction = optional_string(data, "direction")
    status = optional_string(data, "status") or "completed"
    call_id = optional_string(data, "call_id")
    if call_id is None:
        numeric_id = optional_int(data, "id")
        call_id = str(numeric_id) if numeric_id is not None else None
    topic = call_topic(data, direction, call_id)

    if direction:
        headline = f"**{direction[:1].upper() + direction[1:]}** call **{status_label(status)}**."
    else:
        headline = f"Call **{status_label(status)}**."

    lines: list[str] = []
    duration = optional_int(data, "duration_sec")
    if duration is None:
        duration = optional_int(data, "duration")
    if duration is not None:
        lines.append(f"**Duration**: {format_duration(duration)}")
    append_phones(lines, data)
    append_recording(lines, data)
    campaign = optional_object(data, "campaign")
    if campaign is not None and (campaign_name := optional_string(campaign, "name")):
        lines.append(f"**Campaign**: {campaign_name}")
    lead = optional_object(data, "lead")
    if lead is not None:
        lead_phone = optional_string(lead, "phone_number")
        lead_status = optional_string(lead, "status")
        if lead_phone and lead_status:
            lines.append(f"**Lead**: {lead_phone} ({lead_status})")
        elif lead_phone or lead_status:
            lines.append(f"**Lead**: {lead_phone or lead_status}")
    append_analysis(lines, data)
    append_failure(lines, data)

    blocks = [headline]
    if lines:
        blocks.append("\n".join(lines))
    append_mapping(blocks, "Collected", data, "collected")
    append_mapping(blocks, "Variables", data, "variables")
    append_mapping(blocks, "Input variables", data, "input_variables")
    append_mapping(blocks, "Extracted variables", data, "extracted_variables")
    return topic, "\n\n".join(blocks)


def handle_conversation(data: WildValue) -> tuple[str, str]:
    conversation_type = optional_string(data, "type") or "conversation"
    label = CONVERSATION_TYPE_LABELS.get(conversation_type, conversation_type)
    status = optional_string(data, "status") or "ended"
    message_count = optional_int(data, "message_count")
    customer_name = optional_string(data, "customer_name")
    customer_phone_number = optional_string(data, "customer_phone")
    conversation_id = optional_string(data, "conversation_id")
    if conversation_id is None:
        numeric_id = optional_int(data, "id")
        conversation_id = str(numeric_id) if numeric_id is not None else None
    topic = (
        customer_name
        or customer_phone_number
        or (f"Conversation {conversation_id}" if conversation_id else "Famulor conversation")
    )

    count_text = f" ({quantity(message_count, 'message')})" if message_count is not None else ""
    blocks = [f"**{label}** conversation **{status_label(status)}**{count_text}."]

    lines: list[str] = []
    if customer_name:
        lines.append(f"**Customer**: {customer_name}")
    if customer_phone_number:
        lines.append(f"**Phone**: {customer_phone_number}")
    sender = optional_object(data, "sender")
    if sender is not None:
        sender_name = optional_string(sender, "display_name")
        sender_phone = optional_string(sender, "phone_number")
        if sender_name and sender_phone:
            lines.append(f"**Sender**: {sender_name} ({sender_phone})")
        elif sender_name or sender_phone:
            lines.append(f"**Sender**: {sender_name or sender_phone}")

    extracted = optional_object(data, "extracted_variables")
    skip: set[str] = set()
    if extracted is not None:
        summary = optional_string(extracted, "summary")
        objective = optional_bool(extracted, "status")
        if summary:
            lines.append(f"**Summary**: {summary}")
            skip.add("summary")
        if objective is not None:
            lines.append(f"**Objective**: {'achieved' if objective else 'not achieved'}")
            skip.add("status")
    if lines:
        blocks.append("\n".join(lines))
    if extracted is not None:
        extra = format_mapping(extracted, skip=skip)
        if extra:
            blocks.append(f"**Extracted variables**:\n{extra}")
    append_mapping(blocks, "Input variables", data, "input_variables")
    append_attachments(blocks, data)
    return topic, "\n\n".join(blocks)


def append_attachments(blocks: list[str], data: WildValue) -> None:
    if "attachments" not in data or not isinstance(data["attachments"].value, list):
        return
    lines: list[str] = []
    for attachment in data["attachments"]:
        if not isinstance(attachment.value, dict):
            continue
        label = (
            optional_string(attachment, "filename")
            or optional_string(attachment, "type")
            or "Attachment"
        )
        url = optional_string(attachment, "url")
        if url:
            lines.append(f"* [{label}]({url})")
        else:
            lines.append(f"* {label}")
    if lines:
        blocks.append("**Attachments**:\n" + "\n".join(lines))


def handle_booking(event: str, data: WildValue) -> tuple[str, str]:
    verb = BOOKING_EVENTS[event]
    title = optional_string(data, "event_type_name") or optional_string(data, "event_type_slug")
    headline = f"**{title}** {verb}." if title else f"Booking {verb}."
    invitee = optional_object(data, "invitee")
    invitee_name = optional_string(invitee, "name") if invitee is not None else None
    invitee_email = optional_string(invitee, "email") if invitee is not None else None
    invitee_phone = optional_string(invitee, "phone") if invitee is not None else None
    invitee_timezone = optional_string(invitee, "timezone") if invitee is not None else None
    booking_id = optional_string(data, "booking_id")
    topic = (
        invitee_name
        or invitee_phone
        or title
        or (f"Booking {booking_id}" if booking_id else "Famulor booking")
    )

    lines: list[str] = []
    contact_parts = [part for part in (invitee_email, invitee_phone) if part]
    if invitee_name and contact_parts:
        lines.append(f"**Invitee**: {invitee_name} ({', '.join(contact_parts)})")
    elif invitee_name or contact_parts:
        lines.append(f"**Invitee**: {invitee_name or ', '.join(contact_parts)}")
    if invitee_timezone:
        lines.append(f"**Invitee timezone**: {invitee_timezone}")

    start = optional_string(data, "start_time")
    end = optional_string(data, "end_time")
    previous = optional_string(data, "previous_start_time")
    if previous:
        lines.append(f"**Previous start**: {format_time(previous)}")
    if start and end:
        lines.append(f"**When**: {format_time(start)} to {format_time(end)}")
    elif when := start or end:
        lines.append(f"**When**: {format_time(when)}")

    status = optional_string(data, "status")
    source = optional_string(data, "source")
    call_id = optional_string(data, "call_id")
    notes = optional_string(data, "notes")
    if status:
        lines.append(f"**Status**: {status_label(status)}")
    if source:
        lines.append(f"**Source**: {source}")
    if call_id:
        lines.append(f"**Call**: {call_id}")
    if notes:
        lines.append(f"**Notes**: {notes}")

    blocks = [headline]
    if lines:
        blocks.append("\n".join(lines))
    append_mapping(blocks, "Answers", data, "answers")
    return topic, "\n\n".join(blocks)


def is_conversation(payload: WildValue) -> bool:
    return "conversation_id" in payload or (
        "formatted_transcript" in payload and "message_count" in payload
    )


def is_legacy_post_call(payload: WildValue) -> bool:
    has_timing = "duration" in payload or "customer_phone" in payload
    has_call_body = (
        "extracted_variables" in payload
        or "assistant_phone" in payload
        or "recording_url" in payload
    )
    return "status" in payload and has_timing and has_call_body


def topic_and_body(payload: WildValue) -> tuple[str, str, str]:
    event = payload.get("event").tame(check_none_or(check_string))
    if event:
        data = payload.get("data")
        if event == "call.completed" and isinstance(data.value, dict):
            topic, body = handle_call_completed(data)
            return topic, body, event
        if event in BOOKING_EVENTS and isinstance(data.value, dict):
            topic, body = handle_booking(event, data)
            return topic, body, event
        if event == "conversation.ended" and isinstance(data.value, dict) and is_conversation(data):
            topic, body = handle_conversation(data)
            return topic, body, event
        # The event name is documented, but this body is not one of the
        # published examples (for example call.variables, or a
        # conversation.ended delivery whose fields are not documented).
        raise UnsupportedWebhookEventTypeError(event)

    if is_conversation(payload):
        topic, body = handle_conversation(payload)
        return topic, body, "conversation.ended"
    if is_legacy_post_call(payload):
        topic, body = handle_call_completed(payload)
        return topic, body, "call.completed"
    raise AnomalousWebhookPayloadError


@webhook_view("Famulor", all_event_types=ALL_EVENT_TYPES)
@typed_endpoint
def api_famulor_webhook(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    payload: JsonBodyPayload[WildValue],
) -> HttpResponse:
    topic, body, event_type = topic_and_body(payload)
    check_send_webhook_message(request, user_profile, topic, body, event_type)
    return json_success(request)
