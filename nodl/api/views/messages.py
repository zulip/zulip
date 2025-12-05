"""API views for message endpoints.

Implements REST API for chat messages with JWT authentication.
CSRF protection is disabled for state-changing endpoints as they use
Bearer token (JWT) authentication, not browser session cookies.
"""

import json
import logging
from collections import defaultdict
from functools import wraps
from typing import Any, Callable

from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pydantic import ValidationError

from nodl.api.serializers.messages import (
    MessageCreatePayload,
    MessageListSerializer,
    MessageSerializer,
    MessageUpdatePayload,
    ReactionSerializer,
)
from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_edit import do_update_message
from zerver.actions.message_send import check_send_message
from zerver.lib.exceptions import JsonableError
from zerver.lib.markdown import render_message_markdown
from zerver.lib.message import access_message, messages_for_ids
from zerver.lib.rate_limiter import RateLimitedObject, RedisRateLimiterBackend
from zerver.lib.streams import access_stream_by_id
from zerver.lib.types import StreamMessageEditRequest
from zerver.models import Message, Reaction, UserMessage, UserProfile
from zerver.models.clients import get_client

logger = logging.getLogger(__name__)


# Rate limiting configuration
MESSAGES_READ_LIMIT = 300  # requests per minute
MESSAGES_WRITE_LIMIT = 60  # messages per minute
RATE_LIMIT_WINDOW = 60  # seconds


class MessagesRateLimitedObject(RateLimitedObject):
    """Rate limiter for messages API endpoints."""

    def __init__(self, user_id: int, key_prefix: str, limit: int, window: int) -> None:
        super().__init__(RedisRateLimiterBackend)
        self.user_id = user_id
        self.key_prefix = key_prefix
        self.limit = limit
        self.window = window

    def key(self) -> str:
        return f"{self.key_prefix}:{self.user_id}"

    def rules(self) -> list[tuple[int, int]]:
        return [(self.window, self.limit)]


def rate_limit(key_prefix: str, limit: int, window: int = RATE_LIMIT_WINDOW) -> Callable:
    """Decorator for rate limiting API endpoints."""
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
            user = getattr(request, "user_profile", None)
            if user is None:
                return JsonResponse(
                    {"result": "error", "code": "UNAUTHORIZED", "msg": "Authentication required"},
                    status=401,
                )

            rate_limiter = MessagesRateLimitedObject(user.id, key_prefix, limit, window)
            try:
                rate_limiter.rate_limit_request(request)
            except Exception:
                return JsonResponse(
                    {
                        "result": "error",
                        "code": "RATE_LIMITED",
                        "msg": "Too many requests. Please wait before sending more messages.",
                        "retry_after": window,
                    },
                    status=429,
                )

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def require_jwt_auth(view_func: Callable) -> Callable:
    """Decorator to require JWT authentication.

    Expects that authentication middleware has already validated the JWT
    and set request.user_profile.
    """
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        user = getattr(request, "user_profile", None)
        if user is None or not user.is_authenticated:
            return JsonResponse(
                {"result": "error", "code": "UNAUTHORIZED", "msg": "Authentication required"},
                status=401,
            )
        return view_func(request, *args, **kwargs)
    return wrapper


def _get_reactions_for_message(message_id: int) -> list[ReactionSerializer]:
    """Get reactions for a message, grouped by emoji."""
    reactions_data = Reaction.get_raw_db_rows([message_id])

    # Group reactions by emoji
    emoji_users: dict[tuple[str, str], list[int]] = defaultdict(list)
    for reaction in reactions_data:
        key = (reaction["emoji_name"], reaction["emoji_code"])
        emoji_users[key].append(reaction["user_profile_id"])

    return [
        ReactionSerializer(
            emoji_name=emoji_name,
            emoji_code=emoji_code,
            user_ids=user_ids,
        )
        for (emoji_name, emoji_code), user_ids in emoji_users.items()
    ]


def _get_message_flags(user: UserProfile, message_id: int) -> list[str]:
    """Get message flags for a user (read, starred, etc.)."""
    try:
        user_message = UserMessage.objects.get(user_profile=user, message_id=message_id)
        flags = []
        if user_message.flags.read:
            flags.append("read")
        if user_message.flags.starred:
            flags.append("starred")
        if user_message.flags.mentioned:
            flags.append("mentioned")
        return flags
    except UserMessage.DoesNotExist:
        return []


@require_jwt_auth
@rate_limit(key_prefix="messages_read", limit=MESSAGES_READ_LIMIT)
def list_messages(request: HttpRequest) -> HttpResponse:
    """Fetch messages with anchor-based pagination.

    GET /api/v1/messages

    Query parameters:
    - stream_id: Filter by stream (required)
    - topic: Filter by topic (optional)
    - anchor: 'newest', 'oldest', or message_id (default: 'newest')
    - num_before: Messages before anchor (default: 50)
    - num_after: Messages after anchor (default: 0)

    Response:
    {
        "result": "success",
        "messages": [...],
        "found_anchor": true,
        "found_oldest": false,
        "found_newest": true
    }
    """
    if request.method != "GET":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "GET required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    # Parse query parameters
    stream_id_str = request.GET.get("stream_id")
    if not stream_id_str:
        return JsonResponse(
            {"result": "error", "code": "INVALID_PARAMS", "msg": "stream_id is required"},
            status=400,
        )

    try:
        stream_id = int(stream_id_str)
    except ValueError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_PARAMS", "msg": "Invalid stream_id"},
            status=400,
        )

    topic = request.GET.get("topic")
    anchor = request.GET.get("anchor", "newest")

    try:
        num_before = int(request.GET.get("num_before", 50))
        num_after = int(request.GET.get("num_after", 0))
    except ValueError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_PARAMS", "msg": "Invalid pagination parameters"},
            status=400,
        )

    # Validate limits
    num_before = min(max(0, num_before), 200)
    num_after = min(max(0, num_after), 200)

    # Verify user has access to the stream
    try:
        stream, _ = access_stream_by_id(user, stream_id)
    except Exception:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Stream not found or access denied"},
            status=404,
        )

    # Build base query for messages in this stream (IDs only for efficiency)
    base_query = Message.objects.filter(
        realm_id=user.realm_id,
        recipient_id=stream.recipient_id,
    )

    # Filter by topic if specified
    if topic:
        base_query = base_query.filter(subject__iexact=topic)

    # Apply anchor-based pagination to get message IDs
    anchor_message_id = None
    found_anchor = True
    message_ids: list[int] = []

    if anchor == "newest":
        # Get newest message IDs
        message_ids = list(
            base_query.order_by("-id").values_list("id", flat=True)[:num_before + 1]
        )
        message_ids.reverse()  # Put in chronological order
    elif anchor == "oldest":
        # Get oldest message IDs
        message_ids = list(
            base_query.order_by("id").values_list("id", flat=True)[:num_after + 1]
        )
    else:
        # Anchor is a message ID
        try:
            anchor_message_id = int(anchor)
        except ValueError:
            return JsonResponse(
                {"result": "error", "code": "INVALID_PARAMS", "msg": "Invalid anchor value"},
                status=400,
            )

        # Get message IDs before anchor
        before_ids = list(
            base_query.filter(id__lt=anchor_message_id)
            .order_by("-id").values_list("id", flat=True)[:num_before]
        )
        before_ids.reverse()

        # Check if anchor message exists
        anchor_exists = base_query.filter(id=anchor_message_id).exists()
        if anchor_exists:
            anchor_ids = [anchor_message_id]
        else:
            anchor_ids = []
            found_anchor = False

        # Get message IDs after anchor
        after_ids = list(
            base_query.filter(id__gt=anchor_message_id)
            .order_by("id").values_list("id", flat=True)[:num_after]
        )

        message_ids = before_ids + anchor_ids + after_ids

    # Fetch messages from cache using Zulip's cache layer
    if message_ids:
        message_dicts = messages_for_ids(
            message_ids=message_ids,
            user_message_flags={mid: [] for mid in message_ids},
            search_fields={},
            apply_markdown=True,
            client_gravatar=False,
            allow_empty_topic_name=False,
            message_edit_history_visibility_policy=1,  # UserProfile.POLICY_ALLOW_ANYONE
            user_profile=user,
            realm=user.realm,
        )
        # Serialize messages from cached dicts
        message_data = [MessageListSerializer.from_dict(msg).model_dump() for msg in message_dicts]
    else:
        message_data = []

    # Determine pagination state efficiently
    # Instead of extra queries, use the count of returned messages vs requested
    found_oldest = False
    found_newest = False

    if message_ids:
        # If we got fewer messages than requested, we've hit a boundary
        if anchor == "newest":
            # For newest anchor, we're at the newest if we got messages
            found_newest = True
            # We're at oldest if we got fewer than requested
            found_oldest = len(message_ids) < num_before + 1
        elif anchor == "oldest":
            # For oldest anchor, we're at the oldest
            found_oldest = True
            # We're at newest if we got fewer than requested
            found_newest = len(message_ids) < num_after + 1
        else:
            # For specific anchor, check both directions
            # This is an approximation - frontend can refine if needed
            found_oldest = len(before_ids) < num_before
            found_newest = len(after_ids) < num_after

    return JsonResponse({
        "result": "success",
        "messages": message_data,
        "found_anchor": found_anchor,
        "found_oldest": found_oldest,
        "found_newest": found_newest,
    })


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="messages_send", limit=MESSAGES_WRITE_LIMIT)
def send_message(request: HttpRequest) -> HttpResponse:
    """Send a message to a stream.

    POST /api/v1/messages

    Request body:
    {
        "stream_id": 42,
        "topic": "Project Updates",
        "content": "Hello **world**!"
    }

    Response:
    {
        "result": "success",
        "id": 12345,
        "message": {...}
    }
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        body = json.loads(request.body)
        payload = MessageCreatePayload(**body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_JSON", "msg": "Invalid JSON body"},
            status=400,
        )
    except ValidationError as e:
        return JsonResponse(
            {"result": "error", "code": "VALIDATION_ERROR", "msg": str(e)},
            status=400,
        )

    # Verify user has access to the stream
    try:
        stream, _ = access_stream_by_id(user, payload.stream_id)
    except Exception:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Stream not found or access denied"},
            status=404,
        )

    # Send the message using Zulip's check_send_message
    try:
        client = get_client("nodl-api")
        result = check_send_message(
            sender=user,
            client=client,
            recipient_type_name="stream",
            message_to=[stream.id],
            topic_name=payload.topic,
            message_content=payload.content,
            realm=user.realm,
        )

        # Fetch the created message to return full details
        # Include recipient to avoid N+1 query during serialization
        message = Message.objects.select_related("sender", "recipient").get(id=result.message_id)
        serializer = MessageSerializer.from_message(message)

        return JsonResponse({
            "result": "success",
            "id": message.id,
            "message": serializer.model_dump(),
        }, status=201)

    except JsonableError as e:
        return JsonResponse(
            {"result": "error", "code": "SEND_FAILED", "msg": str(e)},
            status=400,
        )
    except Exception as e:
        logger.exception("Failed to send message")
        return JsonResponse(
            {"result": "error", "code": "SEND_FAILED", "msg": str(e)},
            status=500,
        )


@require_jwt_auth
@rate_limit(key_prefix="messages_read", limit=MESSAGES_READ_LIMIT)
def get_message(request: HttpRequest, message_id: int) -> HttpResponse:
    """Get a single message with reactions.

    GET /api/v1/messages/{id}

    Response:
    {
        "result": "success",
        "message": {
            "id": 12345,
            "sender_id": 678,
            "reactions": [...],
            ...
        }
    }
    """
    if request.method != "GET":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "GET required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    # Access the message (verifies user has permission)
    try:
        message = access_message(user, message_id, is_modifying_message=False)
    except JsonableError:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Message not found or access denied"},
            status=404,
        )

    # Get reactions and flags
    reactions = _get_reactions_for_message(message_id)
    flags = _get_message_flags(user, message_id)

    serializer = MessageSerializer.from_message(message, reactions=reactions, flags=flags)

    return JsonResponse({
        "result": "success",
        "message": serializer.model_dump(),
    })


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="messages_write", limit=MESSAGES_WRITE_LIMIT)
def edit_message(request: HttpRequest, message_id: int) -> HttpResponse:
    """Edit a message (owner only).

    PATCH /api/v1/messages/{id}

    Request body:
    {
        "content": "Updated content"
    }

    Response:
    {
        "result": "success",
        "message": {...}
    }
    """
    if request.method != "PATCH":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "PATCH required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        body = json.loads(request.body)
        payload = MessageUpdatePayload(**body)
    except json.JSONDecodeError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_JSON", "msg": "Invalid JSON body"},
            status=400,
        )
    except ValidationError as e:
        return JsonResponse(
            {"result": "error", "code": "VALIDATION_ERROR", "msg": str(e)},
            status=400,
        )

    # Access the message with lock for modification
    try:
        with transaction.atomic():
            message = access_message(user, message_id, lock_message=True, is_modifying_message=True)

            # Check if user is the message owner
            if message.sender_id != user.id:
                return JsonResponse(
                    {"result": "error", "code": "FORBIDDEN", "msg": "Only the message author can edit"},
                    status=403,
                )

            # Render the new content
            rendering_result = render_message_markdown(
                message=message,
                content=payload.content,
                realm=user.realm,
            )

            # Create edit request
            edit_request = StreamMessageEditRequest(
                content=payload.content,
                rendered_content=rendering_result.rendered_content,
            )

            # Get prior mention user IDs (for notification handling)
            prior_mention_user_ids: set[int] = set()

            # Perform the update
            do_update_message(
                user_profile=user,
                target_message=message,
                message_edit_request=edit_request,
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                rendering_result=rendering_result,
                prior_mention_user_ids=prior_mention_user_ids,
            )

            # Refresh message from DB
            message.refresh_from_db()

    except JsonableError as e:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": str(e)},
            status=404,
        )
    except Exception as e:
        logger.exception("Failed to edit message")
        return JsonResponse(
            {"result": "error", "code": "EDIT_FAILED", "msg": str(e)},
            status=500,
        )

    # Return updated message
    reactions = _get_reactions_for_message(message_id)
    flags = _get_message_flags(user, message_id)
    serializer = MessageSerializer.from_message(message, reactions=reactions, flags=flags)

    return JsonResponse({
        "result": "success",
        "message": serializer.model_dump(),
    })


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="messages_write", limit=MESSAGES_WRITE_LIMIT)
def delete_message(request: HttpRequest, message_id: int) -> HttpResponse:
    """Delete a message (owner or admin only).

    DELETE /api/v1/messages/{id}

    Response:
    {
        "result": "success",
        "msg": "Message deleted"
    }
    """
    if request.method != "DELETE":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "DELETE required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    # Access the message
    try:
        message = access_message(user, message_id, is_modifying_message=True)
    except JsonableError:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Message not found or access denied"},
            status=404,
        )

    # Check if user is owner or admin
    is_owner = message.sender_id == user.id
    is_admin = user.role in [UserProfile.ROLE_REALM_OWNER, UserProfile.ROLE_REALM_ADMINISTRATOR]

    if not is_owner and not is_admin:
        return JsonResponse(
            {"result": "error", "code": "FORBIDDEN", "msg": "Only the author or an admin can delete this message"},
            status=403,
        )

    # Delete the message
    try:
        do_delete_messages(user.realm, [message], acting_user=user)
        return JsonResponse({
            "result": "success",
            "msg": "Message deleted",
        })
    except Exception as e:
        logger.exception("Failed to delete message")
        return JsonResponse(
            {"result": "error", "code": "DELETE_FAILED", "msg": str(e)},
            status=500,
        )
