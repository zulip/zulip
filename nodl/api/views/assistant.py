"""Internal assistant API: task-stream reads and send-as-bot (Epic 2, Story 2.1).

Service-authenticated endpoints consumed by nodl-backend's summarizer,
Ask AI grounding, and task supervisor. Reads are pull-based and on-demand
(AD-1) and must work on archived (deactivated) task streams — completed
tasks have archived streams, and summarization order vs. archive order
must never matter (AD-6).

Privacy note (AD-11): the service may read any task stream, including
privacy-tagged ones. Every downstream consumer in nodl-backend enforces
the single TaskKnowledgeACL contract (task detail, Ask AI, cross-task
retrieval, awareness projection) — no consumer defines its own ad-hoc
privacy rule.
"""

import json
import logging
import uuid
from typing import Any, cast

from django.db import transaction
from django.db.models import Max
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pydantic import BaseModel, ValidationError

from nodl.api.views.card_schemas import (
    UnknownCardTypeError,
    build_card_message_content,
)
from nodl.api.views.internal import require_service_auth
from nodl.extensions.models import (
    NodlRealmExtension,
    NodlRealmUserExtension,
    NodlTaskStreamExtension,
)
from zerver.actions.create_user import do_create_user
from zerver.actions.message_edit import do_update_message
from zerver.actions.message_send import check_send_message
from zerver.actions.streams import bulk_add_subscriptions
from zerver.lib.exceptions import JsonableError
from zerver.lib.markdown import render_message_markdown
from zerver.lib.mention import MentionBackend, MentionData
from zerver.lib.types import StreamMessageEditRequest
from zerver.models import Message, Realm, Subscription, UserProfile
from zerver.models.clients import get_client

logger = logging.getLogger(__name__)

ASSISTANT_BOT_NAME = "nodl Assistant"
MAX_MESSAGES_PER_PAGE = 500


class AssistantSendPayload(BaseModel):
    workspace_id: str
    task_id: str
    topic: str = "task"
    content: str
    card_type: str | None = None
    card_payload: dict[str, Any] | None = None


class AssistantUpdateCardPayload(BaseModel):
    workspace_id: str
    task_id: str
    content: str
    card_type: str
    card_payload: dict[str, Any]


def _assistant_bot_email(realm: Realm) -> str:
    return f"assistant-bot@{realm.string_id}.nodl.internal"


def ensure_assistant_bot(realm: Realm, extension: NodlRealmExtension) -> UserProfile:
    """Get or create the realm's nodl Assistant bot, idempotently (AC3)."""
    bot = cast(UserProfile | None, extension.assistant_bot)
    if bot is not None and bot.is_active and bot.realm_id == realm.id:
        return bot

    bot = cast(
        UserProfile | None,
        UserProfile.objects.filter(
            realm=realm,
            delivery_email__iexact=_assistant_bot_email(realm),
            is_bot=True,
            is_active=True,
        ).first(),
    )
    if bot is None:
        bot = do_create_user(
            email=_assistant_bot_email(realm),
            password=None,
            realm=realm,
            full_name=ASSISTANT_BOT_NAME,
            bot_type=UserProfile.DEFAULT_BOT,
            acting_user=None,
        )
        logger.info("Created assistant bot %d for realm %d", bot.id, realm.id)

    extension.assistant_bot = bot
    extension.save(update_fields=["assistant_bot"])
    return bot


def _get_task_stream_extension(
    task_id: uuid.UUID, workspace_id: str
) -> NodlTaskStreamExtension | None:
    extension = cast(
        NodlTaskStreamExtension | None,
        NodlTaskStreamExtension.objects.select_related("zulip_stream", "zulip_realm")
        .filter(nodl_task_id=task_id)
        .first(),
    )
    if extension is None:
        return None
    try:
        if extension.nodl_workspace_id != uuid.UUID(workspace_id):
            # Cross-tenant probe: indistinguishable from "not found".
            return None
    except ValueError:
        return None
    return extension


@csrf_exempt  # type: ignore[untyped-decorator]
@require_service_auth  # type: ignore[untyped-decorator]
def get_task_stream_messages(request: HttpRequest, task_id: uuid.UUID) -> HttpResponse:
    """Read a task stream's messages after an anchor, for the assistant.

    GET /api/v1/internal/task-streams/<task_id>/messages
        ?workspace_id=<uuid>&anchor=<message_id>&num_after=<n>

    Returns raw markdown content (not rendered HTML) ascending by id, plus
    AD-10 metadata: `latest_human_anchor` (max message id excluding bot
    senders — bot posts never advance any anchor) and `last_edit_time`
    (stream-wide max edit timestamp for staleness checks). Callers key
    caches on these, never on the raw latest message id.

    Works on archived streams: resolution goes through
    NodlTaskStreamExtension, which survives stream deactivation.
    """
    if request.method != "GET":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "GET required"},
            status=405,
        )

    workspace_id = request.GET.get("workspace_id", "")
    if not workspace_id:
        return JsonResponse(
            {"result": "error", "code": "VALIDATION_ERROR", "msg": "workspace_id required"},
            status=400,
        )

    try:
        anchor = int(request.GET.get("anchor", 0))
        num_after = int(request.GET.get("num_after", MAX_MESSAGES_PER_PAGE))
    except ValueError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_PARAMS", "msg": "Invalid pagination parameters"},
            status=400,
        )
    num_after = min(max(1, num_after), MAX_MESSAGES_PER_PAGE)

    extension = _get_task_stream_extension(task_id, workspace_id)
    if extension is None:
        return JsonResponse(
            {"result": "error", "code": "TASK_STREAM_NOT_FOUND", "msg": "Task stream not found"},
            status=404,
        )

    stream = extension.zulip_stream
    stream_messages = Message.objects.filter(
        realm_id=extension.zulip_realm_id,
        recipient_id=stream.recipient_id,
    )

    page = list(
        stream_messages.filter(id__gt=anchor)
        .select_related("sender")
        .order_by("id")[: num_after + 1]
    )
    found_newest = len(page) <= num_after
    page = page[:num_after]

    sender_ids = {message.sender_id for message in page}
    supabase_by_zulip_id = {
        zulip_user_id: str(supabase_user_id)
        for zulip_user_id, supabase_user_id in NodlRealmUserExtension.objects.filter(
            zulip_user_id__in=sender_ids
        ).values_list("zulip_user_id", "supabase_user_id")
    }

    messages = [
        {
            "message_id": message.id,
            "sender": {
                "zulip_user_id": message.sender_id,
                "supabase_user_id": supabase_by_zulip_id.get(message.sender_id),
                "full_name": message.sender.full_name,
                "is_bot": message.sender.is_bot,
            },
            "timestamp": message.date_sent.isoformat(),
            "topic": message.topic_name(),
            "content": message.content,
        }
        for message in page
    ]

    human_messages = stream_messages.exclude(sender__is_bot=True)
    latest_human_anchor = human_messages.aggregate(Max("id"))["id__max"] or 0
    # Human messages only, like the anchor: bot card rewrites (e.g. a
    # check-in flipping to its answered state) are system bookkeeping and
    # must not look like pre-anchor edits to AD-10 staleness checks.
    last_edit_time = human_messages.aggregate(Max("last_edit_time"))["last_edit_time__max"]

    return JsonResponse(
        {
            "result": "success",
            "messages": messages,
            "found_newest": found_newest,
            "latest_human_anchor": latest_human_anchor,
            "last_edit_time": last_edit_time.isoformat() if last_edit_time else None,
            "stream_archived": stream.deactivated,
        },
        status=200,
    )


@csrf_exempt  # type: ignore[untyped-decorator]
@require_service_auth  # type: ignore[untyped-decorator]
def send_assistant_message(request: HttpRequest) -> HttpResponse:
    """Post a message to a task stream as the realm's nodl Assistant bot.

    POST /api/v1/internal/messages/send
    Body: {workspace_id, task_id, topic?, content, card_type?, card_payload?}

    `content` is the human-readable markdown; when `card_type`/`card_payload`
    are given the payload is schema-validated and embedded per AD-12 as
    `<!-- nodl-card:v1:{base64url-json} -->` ahead of the markdown fallback.
    Sends via check_send_message so the normal event queue delivers it to
    connected clients in real time.
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    try:
        payload = AssistantSendPayload(**json.loads(request.body))
    except json.JSONDecodeError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_JSON", "msg": "Invalid JSON body"},
            status=400,
        )
    except ValidationError as exc:
        return JsonResponse(
            {"result": "error", "code": "VALIDATION_ERROR", "msg": str(exc)},
            status=400,
        )

    try:
        task_uuid = uuid.UUID(payload.task_id)
    except ValueError:
        return JsonResponse(
            {"result": "error", "code": "VALIDATION_ERROR", "msg": "Invalid task_id"},
            status=400,
        )

    extension = _get_task_stream_extension(task_uuid, payload.workspace_id)
    if extension is None:
        return JsonResponse(
            {"result": "error", "code": "TASK_STREAM_NOT_FOUND", "msg": "Task stream not found"},
            status=404,
        )

    stream = extension.zulip_stream
    if stream.deactivated:
        return JsonResponse(
            {"result": "error", "code": "STREAM_ARCHIVED", "msg": "Task stream is archived"},
            status=409,
        )

    if payload.card_type is not None:
        try:
            content = build_card_message_content(
                payload.card_type, payload.card_payload or {}, payload.content
            )
        except (UnknownCardTypeError, ValidationError) as exc:
            return JsonResponse(
                {"result": "error", "code": "INVALID_CARD", "msg": str(exc)},
                status=400,
            )
    else:
        content = payload.content

    try:
        realm = extension.zulip_realm
        realm_extension = NodlRealmExtension.objects.select_related("assistant_bot").get(
            zulip_realm=realm
        )
        bot = ensure_assistant_bot(realm, realm_extension)

        if not Subscription.objects.filter(
            user_profile=bot,
            recipient=stream.recipient,
            active=True,
        ).exists():
            bulk_add_subscriptions(
                realm,
                [stream],
                [bot],
                from_user_creation=True,
                acting_user=None,
            )

        result = check_send_message(
            sender=bot,
            client=get_client("nodl-api"),
            recipient_type_name="stream",
            message_to=[stream.id],
            topic_name=payload.topic,
            message_content=content,
            realm=realm,
        )
        return JsonResponse(
            {"result": "success", "message_id": result.message_id},
            status=200,
        )
    except NodlRealmExtension.DoesNotExist:
        return JsonResponse(
            {"result": "error", "code": "REALM_NOT_FOUND", "msg": "Workspace realm not found"},
            status=404,
        )
    except JsonableError as exc:
        return JsonResponse(
            {"result": "error", "code": "SEND_FAILED", "msg": str(exc)},
            status=400,
        )
    except Exception as exc:
        logger.exception("assistant_send_failed")
        return JsonResponse(
            {"result": "error", "code": "SEND_FAILED", "msg": str(exc)},
            status=500,
        )


@csrf_exempt  # type: ignore[untyped-decorator]
@require_service_auth  # type: ignore[untyped-decorator]
def update_assistant_card(request: HttpRequest, message_id: int) -> HttpResponse:
    """Re-encode an assistant card message in place (review fix #2).

    POST /api/v1/internal/messages/<message_id>/update-card
    Body: {workspace_id, task_id, content, card_type, card_payload}

    Used to make check-in cards durable: after a participant responds, the
    backend rewrites the original card payload (status=responded) so every
    client renders the answered state after reload — not just the local
    component that clicked the button. Only messages sent by the realm's
    assistant bot in the task's own stream can be updated.
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    try:
        payload = AssistantUpdateCardPayload(**json.loads(request.body))
    except json.JSONDecodeError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_JSON", "msg": "Invalid JSON body"},
            status=400,
        )
    except ValidationError as exc:
        return JsonResponse(
            {"result": "error", "code": "VALIDATION_ERROR", "msg": str(exc)},
            status=400,
        )

    try:
        task_uuid = uuid.UUID(payload.task_id)
    except ValueError:
        return JsonResponse(
            {"result": "error", "code": "VALIDATION_ERROR", "msg": "Invalid task_id"},
            status=400,
        )

    extension = _get_task_stream_extension(task_uuid, payload.workspace_id)
    if extension is None:
        return JsonResponse(
            {"result": "error", "code": "TASK_STREAM_NOT_FOUND", "msg": "Task stream not found"},
            status=404,
        )

    try:
        content = build_card_message_content(
            payload.card_type, payload.card_payload, payload.content
        )
    except (UnknownCardTypeError, ValidationError) as exc:
        return JsonResponse(
            {"result": "error", "code": "INVALID_CARD", "msg": str(exc)},
            status=400,
        )

    try:
        realm = extension.zulip_realm
        stream = extension.zulip_stream
        realm_extension = NodlRealmExtension.objects.select_related("assistant_bot").get(
            zulip_realm=realm
        )
        bot = ensure_assistant_bot(realm, realm_extension)

        with transaction.atomic():
            message = (
                Message.objects.select_for_update()
                .select_related("sender", "recipient")
                .filter(
                    id=message_id,
                    realm_id=realm.id,
                    recipient_id=stream.recipient_id,
                )
                .first()
            )
            if message is None:
                return JsonResponse(
                    {"result": "error", "code": "MESSAGE_NOT_FOUND", "msg": "Message not found"},
                    status=404,
                )
            if message.sender_id != bot.id:
                return JsonResponse(
                    {
                        "result": "error",
                        "code": "FORBIDDEN",
                        "msg": "Only assistant bot messages can be updated",
                    },
                    status=403,
                )

            rendering_result = render_message_markdown(
                message=message,
                content=content,
                realm=realm,
            )
            edit_request = StreamMessageEditRequest(
                is_content_edited=True,
                is_topic_edited=False,
                is_stream_edited=False,
                is_message_moved=False,
                topic_resolved=False,
                topic_unresolved=False,
                content=content,
                target_topic_name=message.topic_name(),
                target_stream=stream,
                orig_content=message.content,
                orig_topic_name=message.topic_name(),
                orig_stream=stream,
                propagate_mode="change_one",
            )
            mention_backend = MentionBackend(realm.id)
            mention_data = MentionData(mention_backend, content, bot)

            do_update_message(
                user_profile=bot,
                target_message=message,
                message_edit_request=edit_request,
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                rendering_result=rendering_result,
                prior_mention_user_ids=set(),
                mention_data=mention_data,
            )

        return JsonResponse({"result": "success", "message_id": message_id}, status=200)
    except NodlRealmExtension.DoesNotExist:
        return JsonResponse(
            {"result": "error", "code": "REALM_NOT_FOUND", "msg": "Workspace realm not found"},
            status=404,
        )
    except JsonableError as exc:
        return JsonResponse(
            {"result": "error", "code": "UPDATE_FAILED", "msg": str(exc)},
            status=400,
        )
    except Exception as exc:
        logger.exception("assistant_card_update_failed")
        return JsonResponse(
            {"result": "error", "code": "UPDATE_FAILED", "msg": str(exc)},
            status=500,
        )
