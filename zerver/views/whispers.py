from __future__ import annotations

import json
from typing import Any, Iterable, Optional

from django.http import HttpRequest, HttpResponse

from zerver.lib.response import json_success
from zerver.lib.whispers import (
    WhisperPermissionError,
    WhisperValidationError,
    add_participant_to_whisper,
    create_whisper_conversation,
    create_whisper_request,
    get_pending_whisper_requests_for_user,
    get_sent_whisper_requests_for_user,
    get_user_whisper_conversations,
    get_whisper_conversation_participants,
    get_whisper_request_by_id,
    respond_to_whisper_request,
    cancel_whisper_request,
)
from zerver.models import Recipient, UserProfile, WhisperConversation, WhisperRequest


def _parse_json(request: HttpRequest) -> dict[str, Any]:
    if request.body:
        try:
            return json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _serialize_user(user: UserProfile) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
    }


def _serialize_recipient(recipient: Recipient) -> dict[str, Any]:
    return {
        "id": recipient.id,
        "type": recipient.type,
        "type_id": recipient.type_id,
        "type_name": recipient.type_name(),
        "parent_recipient_id": recipient.parent_recipient_id,
    }


def _serialize_request(req: WhisperRequest) -> dict[str, Any]:
    return {
        "id": req.id,
        "requester": _serialize_user(req.requester),
        "recipient": _serialize_user(req.recipient),
        "parent_recipient": _serialize_recipient(req.parent_recipient),
        "status": int(req.status),
        "created_at": req.created_at,
        "whisper_conversation_id": req.whisper_conversation_id,
    }


def _serialize_conversation(conv: WhisperConversation) -> dict[str, Any]:
    return {
        "id": conv.id,
        "parent_recipient": _serialize_recipient(conv.parent_recipient),
        "realm_id": conv.realm_id,
        "created_by_id": conv.created_by_id,
        "created_at": conv.created_at,
        "is_active": conv.is_active,
        "participants_hash": conv.participants_hash,
    }


# Whisper requests endpoints

def create_whisper_request_backend(request: HttpRequest) -> HttpResponse:
    data = _parse_json(request)
    recipient_id = int(data.get("recipient_id"))
    parent_recipient_id = int(data.get("parent_recipient_id"))
    proposed_participants = list(map(int, data.get("proposed_participants", [])))

    recipient = UserProfile.objects.get(id=recipient_id)
    parent_recipient = Recipient.objects.get(id=parent_recipient_id)

    req = create_whisper_request(
        requester=request.user,  # type: ignore[arg-type]
        recipient=recipient,
        parent_recipient=parent_recipient,
        proposed_participants=proposed_participants,
    )

    return json_success(request, {"request": _serialize_request(req)})


def list_pending_whisper_requests_backend(request: HttpRequest) -> HttpResponse:
    pending = get_pending_whisper_requests_for_user(request.user)  # type: ignore[arg-type]
    return json_success(request, {"requests": [_serialize_request(r) for r in pending]})


def list_sent_whisper_requests_backend(request: HttpRequest) -> HttpResponse:
    sent = get_sent_whisper_requests_for_user(request.user)  # type: ignore[arg-type]
    return json_success(request, {"requests": [_serialize_request(r) for r in sent]})


def respond_whisper_request_backend(request: HttpRequest, request_id: int) -> HttpResponse:
    data = _parse_json(request)
    accept = bool(data.get("accept", False))
    additional_participants = data.get("additional_participants") or []
    additional_ids = list(map(int, additional_participants)) if additional_participants else None

    req = get_whisper_request_by_id(request_id, request.user)  # type: ignore[arg-type]
    conversation = respond_to_whisper_request(
        req,
        request.user,  # type: ignore[arg-type]
        accept=accept,
        additional_participants=additional_ids,
    )

    return json_success(
        request,
        {
            "request": _serialize_request(req),
            "conversation": _serialize_conversation(conversation) if conversation else None,
        },
    )


def cancel_whisper_request_backend(request: HttpRequest, request_id: int) -> HttpResponse:
    req = get_whisper_request_by_id(request_id, request.user)  # type: ignore[arg-type]
    cancel_whisper_request(req, request.user)  # type: ignore[arg-type]
    return json_success(request, {"request": _serialize_request(req)})


# Whisper conversations endpoints

def list_whisper_conversations_backend(request: HttpRequest) -> HttpResponse:
    data = request.GET
    parent_recipient_id = data.get("parent_recipient_id")
    parent: Optional[Recipient] = None
    if parent_recipient_id is not None:
        parent = Recipient.objects.get(id=int(parent_recipient_id))

    conversations = get_user_whisper_conversations(request.user, parent)  # type: ignore[arg-type]
    return json_success(request, {"conversations": [_serialize_conversation(c) for c in conversations]})


def create_whisper_conversation_backend(request: HttpRequest) -> HttpResponse:
    data = _parse_json(request)
    participant_user_ids = list(map(int, data.get("participant_user_ids", [])))
    parent_recipient_id = int(data.get("parent_recipient_id"))

    parent_recipient = Recipient.objects.get(id=parent_recipient_id)
    conversation = create_whisper_conversation(
        request.user,  # type: ignore[arg-type]
        participant_user_ids,
        parent_recipient,
    )
    return json_success(request, {"conversation": _serialize_conversation(conversation)})


def list_whisper_conversation_participants_backend(
    request: HttpRequest, conversation_id: int
) -> HttpResponse:
    conversation = WhisperConversation.objects.get(id=conversation_id)
    participants = get_whisper_conversation_participants(conversation)
    return json_success(request, {"participants": [_serialize_user(u) for u in participants]})


def add_whisper_participant_backend(request: HttpRequest, conversation_id: int) -> HttpResponse:
    data = _parse_json(request)
    new_participant_id = int(data.get("participant_id"))
    conversation = WhisperConversation.objects.get(id=conversation_id)
    participant = UserProfile.objects.get(id=new_participant_id)

    added = add_participant_to_whisper(conversation, request.user, participant)  # type: ignore[arg-type]
    return json_success(request, {"participant": _serialize_user(added.user_profile)})


def remove_whisper_participant_backend(request: HttpRequest, conversation_id: int) -> HttpResponse:
    from zerver.lib.whispers import remove_participant_from_whisper

    data = _parse_json(request)
    participant_id = data.get("participant_id")
    conversation = WhisperConversation.objects.get(id=conversation_id)
    participant: Optional[UserProfile] = None
    if participant_id is not None:
        participant = UserProfile.objects.get(id=int(participant_id))

    still_active = remove_participant_from_whisper(
        conversation,
        request.user,  # type: ignore[arg-type]
        participant,
    )
    return json_success(request, {"active": still_active})


