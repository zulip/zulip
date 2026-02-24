"""API views for message endpoints.

Implements REST API for chat messages with JWT authentication.
CSRF protection is disabled for state-changing endpoints as they use
Bearer token (JWT) authentication, not browser session cookies.
"""

import json
import logging
from collections import defaultdict
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pydantic import ValidationError

from nodl.api.serializers.messages import (
    MessageCreatePayload,
    MessageSerializer,
    MessageUpdatePayload,
    ReactionSerializer,
)
from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_edit import do_update_message
from zerver.actions.message_flags import do_update_message_flags
from zerver.actions.message_send import check_send_message
from zerver.actions.muted_users import do_mute_user, do_unmute_user
from zerver.actions.reactions import check_add_reaction, do_remove_reaction
from zerver.lib.emoji import get_emoji_data
from zerver.lib.exceptions import JsonableError, ReactionDoesNotExistError, ReactionExistsError
from zerver.lib.markdown import render_message_markdown
from zerver.lib.mention import MentionBackend, MentionData
from zerver.lib.message import access_message, get_recent_private_conversations, messages_for_ids
from zerver.lib.muted_users import get_mute_object
from zerver.lib.rate_limiter import RateLimitedObject, RedisRateLimiterBackend
from zerver.lib.streams import access_stream_by_id
from zerver.lib.types import StreamMessageEditRequest
from zerver.lib.users import access_user_by_id_including_cross_realm
from zerver.models import Message, Reaction, UserMessage, UserProfile
from zerver.models.clients import get_client
from zerver.models.streams import get_stream_by_id_in_realm

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


def _build_dm_recipient_query(user: UserProfile, user_ids: list[int]):
    """Build a query for DM messages to/from specific users.

    For 1:1 DMs using Recipient.PERSONAL, we need a BIDIRECTIONAL query because:
    - When User A sends to User B: recipient_id = User B's personal recipient
    - When User B sends to User A: recipient_id = User A's personal recipient

    For group DMs (Recipient.DIRECT_MESSAGE_GROUP), a simple recipient filter works
    because all messages share the same recipient_id.
    """
    from django.db.models import Q

    from zerver.lib.recipient_users import recipient_for_user_profiles
    from zerver.models import DirectMessageGroup, Recipient

    # Include current user in the lookup
    all_user_ids = sorted(set(user_ids + [user.id]))

    # Get recipient for this exact set of users
    try:
        user_profiles = list(
            UserProfile.objects.filter(
                id__in=all_user_ids,
                realm=user.realm,
            )
        )
        if len(user_profiles) != len(all_user_ids):
            return None  # Some users not found

        recipient = recipient_for_user_profiles(
            user_profiles=user_profiles,
            forwarded_mirror_message=False,
            forwarder_user_profile=None,
            sender=user,
            create=False,  # Don't create if doesn't exist
        )

        # Group DM (DIRECT_MESSAGE_GROUP) - simple query by recipient_id
        # All messages in a group DM share the same recipient
        if recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
            return Message.objects.filter(
                realm_id=user.realm_id,
                recipient_id=recipient.id,
            )

        # 1:1 DM using PERSONAL recipient - need bidirectional query
        # Find the other participant
        other_participant = None
        for profile in user_profiles:
            if profile.id != user.id:
                other_participant = profile
                break

        if other_participant:
            # Bidirectional query: messages in BOTH directions
            # 1. Messages sent BY the other person TO me (recipient = my personal recipient)
            # 2. Messages sent BY me TO the other person (recipient = their personal recipient)
            return Message.objects.filter(
                realm_id=user.realm_id,
            ).filter(
                Q(sender_id=other_participant.id, recipient_id=user.recipient_id)
                | Q(sender_id=user.id, recipient_id=other_participant.recipient_id)
            )
        else:
            # Self DM (messaging yourself)
            return Message.objects.filter(
                realm_id=user.realm_id,
                sender_id=user.id,
                recipient_id=user.recipient_id,
            )

    except DirectMessageGroup.DoesNotExist:
        # No existing DirectMessageGroup, fall back to personal recipients for 1:1 DM
        try:
            # Get the other user (excluding current user from the list)
            other_user_ids = [uid for uid in user_ids if uid != user.id]
            if not other_user_ids:
                # Self DM case
                return Message.objects.filter(
                    realm_id=user.realm_id,
                    sender_id=user.id,
                    recipient_id=user.recipient_id,
                )

            other_user = UserProfile.objects.get(id=other_user_ids[0], realm=user.realm)

            # Bidirectional query using personal recipients
            return Message.objects.filter(
                realm_id=user.realm_id,
            ).filter(
                Q(sender_id=other_user.id, recipient_id=user.recipient_id)
                | Q(sender_id=user.id, recipient_id=other_user.recipient_id)
            )
        except (IndexError, UserProfile.DoesNotExist):
            return None
    except Exception:
        return None


@csrf_exempt
def messages_dispatch(request: HttpRequest) -> HttpResponse:
    """Dispatch /api/v1/messages by HTTP method: GET → list, POST → send."""
    if request.method == "GET":
        return list_messages(request)
    elif request.method == "POST":
        return send_message(request)
    else:
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed"},
            status=405,
        )


@require_jwt_auth
@rate_limit(key_prefix="messages_read", limit=MESSAGES_READ_LIMIT)
def list_messages(request: HttpRequest) -> HttpResponse:
    """Fetch messages with anchor-based pagination.

    GET /api/v1/messages

    Query parameters (choose one approach):

    For stream messages (legacy):
    - stream_id: Filter by stream (required)
    - topic: Filter by topic (optional)

    For DM messages (using narrow):
    - narrow: JSON array of filter operators, e.g.:
      - [{"operator":"dm","operand":[9]}] - DMs with user 9
      - [{"operator":"dm","operand":[9,12]}] - Group DM with users 9 and 12

    Common parameters:
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

    # Parse common query parameters
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

    # Check for narrow parameter (DM queries)
    narrow_str = request.GET.get("narrow")
    stream_id_str = request.GET.get("stream_id")

    base_query = None

    if narrow_str:
        # Parse narrow parameter
        try:
            narrow_terms = json.loads(narrow_str)
        except json.JSONDecodeError:
            return JsonResponse(
                {"result": "error", "code": "INVALID_PARAMS", "msg": "Invalid narrow JSON"},
                status=400,
            )

        if not isinstance(narrow_terms, list) or len(narrow_terms) == 0:
            return JsonResponse(
                {
                    "result": "error",
                    "code": "INVALID_PARAMS",
                    "msg": "narrow must be a non-empty array",
                },
                status=400,
            )

        # Parse the narrow operator
        term = narrow_terms[0]
        operator = term.get("operator", "")
        operand = term.get("operand")

        if operator == "dm":
            # DM with specific users
            if not isinstance(operand, list) or len(operand) == 0:
                return JsonResponse(
                    {
                        "result": "error",
                        "code": "INVALID_PARAMS",
                        "msg": "dm operand must be a list of user IDs",
                    },
                    status=400,
                )

            # Validate operand contains integers
            try:
                user_ids = [int(uid) for uid in operand]
            except (ValueError, TypeError):
                return JsonResponse(
                    {
                        "result": "error",
                        "code": "INVALID_PARAMS",
                        "msg": "dm operand must contain valid user IDs",
                    },
                    status=400,
                )

            base_query = _build_dm_recipient_query(user, user_ids)
            if base_query is None:
                return JsonResponse(
                    {"result": "error", "code": "NOT_FOUND", "msg": "DM conversation not found"},
                    status=404,
                )
            # Filter out bot messages from DMs (e.g., Zulip's "Welcome Bot")
            base_query = base_query.exclude(sender__is_bot=True)

        elif operator in ("channel", "stream"):
            # Channel/stream narrow - operand is the stream ID (int)
            if not isinstance(operand, int):
                try:
                    operand = int(operand)
                except (ValueError, TypeError):
                    return JsonResponse(
                        {
                            "result": "error",
                            "code": "INVALID_PARAMS",
                            "msg": "channel operand must be a valid stream ID",
                        },
                        status=400,
                    )

            try:
                stream, _ = access_stream_by_id(user, operand)
            except Exception:
                return JsonResponse(
                    {
                        "result": "error",
                        "code": "NOT_FOUND",
                        "msg": "Stream not found or access denied",
                    },
                    status=404,
                )

            base_query = Message.objects.filter(
                realm_id=user.realm_id,
                recipient_id=stream.recipient_id,
            )

            # Check for topic narrow term in remaining narrow terms
            for t in narrow_terms[1:]:
                if t.get("operator") == "topic" and t.get("operand"):
                    base_query = base_query.filter(subject__iexact=t["operand"])
                    break

        else:
            return JsonResponse(
                {
                    "result": "error",
                    "code": "INVALID_PARAMS",
                    "msg": f"Unsupported narrow operator: {operator}",
                },
                status=400,
            )

    elif stream_id_str:
        # Legacy stream-based query
        try:
            stream_id = int(stream_id_str)
        except ValueError:
            return JsonResponse(
                {"result": "error", "code": "INVALID_PARAMS", "msg": "Invalid stream_id"},
                status=400,
            )

        topic = request.GET.get("topic")

        # Verify user has access to the stream
        try:
            stream, _ = access_stream_by_id(user, stream_id)
        except Exception:
            return JsonResponse(
                {
                    "result": "error",
                    "code": "NOT_FOUND",
                    "msg": "Stream not found or access denied",
                },
                status=404,
            )

        base_query = Message.objects.filter(
            realm_id=user.realm_id,
            recipient_id=stream.recipient_id,
        )

        # Filter by topic if specified
        if topic:
            base_query = base_query.filter(subject__iexact=topic)
    else:
        return JsonResponse(
            {
                "result": "error",
                "code": "INVALID_PARAMS",
                "msg": "Either stream_id or narrow is required",
            },
            status=400,
        )

    # Apply anchor-based pagination to get message IDs
    anchor_message_id = None
    found_anchor = True
    message_ids: list[int] = []
    before_ids: list[int] = []
    after_ids: list[int] = []

    if anchor == "newest":
        # Get newest message IDs
        message_ids = list(
            base_query.order_by("-id").values_list("id", flat=True)[: num_before + 1]
        )
        message_ids.reverse()  # Put in chronological order
    elif anchor == "oldest":
        # Get oldest message IDs
        message_ids = list(base_query.order_by("id").values_list("id", flat=True)[: num_after + 1])
    elif anchor == "first_unread":
        # MVP: treat as newest — full unread tracking not implemented yet
        message_ids = list(
            base_query.order_by("-id").values_list("id", flat=True)[: num_before + 1]
        )
        message_ids.reverse()
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
            .order_by("-id")
            .values_list("id", flat=True)[:num_before]
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
            .order_by("id")
            .values_list("id", flat=True)[:num_after]
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
        # Pass through raw Zulip message dicts — Flutter expects exact Zulip format
        message_data = message_dicts
    else:
        message_data = []

    # Determine pagination state efficiently
    # Instead of extra queries, use the count of returned messages vs requested
    found_oldest = False
    found_newest = False

    if message_ids:
        # If we got fewer messages than requested, we've hit a boundary
        if anchor in ("newest", "first_unread"):
            # For newest/first_unread anchor, we're at the newest if we got messages
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

    # Compute anchor value for response (Zulip returns the resolved anchor as int)
    if anchor in ("newest", "first_unread"):
        anchor_value = message_ids[-1] if message_ids else 0
    elif anchor == "oldest":
        anchor_value = message_ids[0] if message_ids else 0
    else:
        anchor_value = anchor_message_id or 0

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "messages": message_data,
            "anchor": anchor_value,
            "found_anchor": found_anchor,
            "found_oldest": found_oldest,
            "found_newest": found_newest,
            "history_limited": False,
        }
    )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="messages_send", limit=MESSAGES_WRITE_LIMIT)
def send_message(request: HttpRequest) -> HttpResponse:
    """Send a message to a stream or direct message.

    POST /api/v1/messages

    For stream messages:
    {
        "type": "stream",  // or omit for default
        "stream_id": 42,
        "topic": "Project Updates",
        "content": "Hello **world**!"
    }

    For direct messages:
    {
        "type": "direct",
        "to": [9, 12],  // Array of recipient user IDs
        "content": "Hello!"
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
        # Try JSON first, fall back to form-encoded data (Flutter Zulip client)
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            body = {k: v for k, v in request.POST.items()}
            # Parse JSON-encoded values in form data
            for key in ("to", "stream_id"):
                if key in body and isinstance(body[key], str):
                    try:
                        body[key] = json.loads(body[key])
                    except (json.JSONDecodeError, ValueError):
                        pass
        payload = MessageCreatePayload(**body)
    except ValidationError as e:
        return JsonResponse(
            {"result": "error", "code": "VALIDATION_ERROR", "msg": str(e)},
            status=400,
        )

    client = get_client("nodl-api")

    # Handle direct messages
    if payload.type == "direct":
        if not payload.to or len(payload.to) == 0:
            return JsonResponse(
                {
                    "result": "error",
                    "code": "INVALID_PARAMS",
                    "msg": "Missing 'to' recipients for direct message",
                },
                status=400,
            )

        try:
            # Get recipient user profiles
            recipient_users = list(
                UserProfile.objects.filter(
                    id__in=payload.to,
                    realm=user.realm,
                    is_active=True,
                )
            )

            if len(recipient_users) != len(payload.to):
                return JsonResponse(
                    {
                        "result": "error",
                        "code": "NOT_FOUND",
                        "msg": "One or more recipients not found",
                    },
                    status=404,
                )

            # Send using Zulip's check_send_message with "private" type
            result = check_send_message(
                sender=user,
                client=client,
                recipient_type_name="private",
                message_to=payload.to,
                topic_name="",  # DMs don't have topics
                message_content=payload.content,
                realm=user.realm,
            )

            # Fetch the created message
            message = Message.objects.select_related("sender", "recipient").get(
                id=result.message_id
            )

            # Include sender in recipients for display_recipient
            all_users = recipient_users + [user] if user.id not in payload.to else recipient_users
            serializer = MessageSerializer.from_message(message, recipient_users=all_users)

            return JsonResponse(
                {
                    "result": "success",
                    "msg": "",
                    "id": message.id,
                },
                status=200,
            )

        except JsonableError as e:
            return JsonResponse(
                {"result": "error", "code": "SEND_FAILED", "msg": str(e)},
                status=400,
            )
        except Exception as e:
            logger.exception("Failed to send direct message")
            return JsonResponse(
                {"result": "error", "code": "SEND_FAILED", "msg": str(e)},
                status=500,
            )

    # Handle stream messages (default)
    if not payload.stream_id:
        return JsonResponse(
            {
                "result": "error",
                "code": "INVALID_PARAMS",
                "msg": "stream_id is required for stream messages",
            },
            status=400,
        )

    # Default topic to "general" if not provided
    topic = payload.topic or "general"

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
        result = check_send_message(
            sender=user,
            client=client,
            recipient_type_name="stream",
            message_to=[stream.id],
            topic_name=topic,
            message_content=payload.content,
            realm=user.realm,
        )

        # Fetch the created message to return full details
        # Include recipient to avoid N+1 query during serialization
        message = Message.objects.select_related("sender", "recipient").get(id=result.message_id)
        serializer = MessageSerializer.from_message(message)

        return JsonResponse(
            {
                "result": "success",
                "msg": "",
                "id": message.id,
            },
            status=200,
        )

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

    return JsonResponse(
        {
            "result": "success",
            "message": serializer.model_dump(),
        }
    )


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
                    {
                        "result": "error",
                        "code": "FORBIDDEN",
                        "msg": "Only the message author can edit",
                    },
                    status=403,
                )

            # Render the new content
            rendering_result = render_message_markdown(
                message=message,
                content=payload.content,
                realm=user.realm,
            )

            # Get the stream for this message
            stream = get_stream_by_id_in_realm(message.recipient.type_id, user.realm)

            # Create edit request (content-only edit)
            edit_request = StreamMessageEditRequest(
                is_content_edited=True,
                is_topic_edited=False,
                is_stream_edited=False,
                is_message_moved=False,
                topic_resolved=False,
                topic_unresolved=False,
                content=payload.content,
                target_topic_name=message.topic_name(),
                target_stream=stream,
                orig_content=message.content,
                orig_topic_name=message.topic_name(),
                orig_stream=stream,
                propagate_mode="change_one",
            )

            # Get prior mention user IDs (for notification handling)
            prior_mention_user_ids: set[int] = set()

            # Create mention data for content editing
            mention_backend = MentionBackend(user.realm_id)
            mention_data = MentionData(mention_backend, payload.content, user)

            # Perform the update
            do_update_message(
                user_profile=user,
                target_message=message,
                message_edit_request=edit_request,
                send_notification_to_old_thread=False,
                send_notification_to_new_thread=False,
                rendering_result=rendering_result,
                prior_mention_user_ids=prior_mention_user_ids,
                mention_data=mention_data,
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

    return JsonResponse(
        {
            "result": "success",
            "message": serializer.model_dump(),
        }
    )


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
            {
                "result": "error",
                "code": "FORBIDDEN",
                "msg": "Only the author or an admin can delete this message",
            },
            status=403,
        )

    # Delete the message
    try:
        do_delete_messages(user.realm, [message], acting_user=user)
        return JsonResponse(
            {
                "result": "success",
                "msg": "Message deleted",
            }
        )
    except Exception as e:
        logger.exception("Failed to delete message")
        return JsonResponse(
            {"result": "error", "code": "DELETE_FAILED", "msg": str(e)},
            status=500,
        )


@require_jwt_auth
@rate_limit(key_prefix="messages_read", limit=MESSAGES_READ_LIMIT)
def list_dm_conversations(request: HttpRequest) -> HttpResponse:
    """List DM conversations for the current user.

    GET /api/v1/dm/conversations

    Uses Zulip's get_recent_private_conversations() which correctly queries
    UserMessage with is_private flag instead of Subscription table.

    Response:
    {
        "result": "success",
        "conversations": [
            {
                "user_ids": [9],
                "users": [
                    {
                        "id": 9,
                        "full_name": "Alice",
                        "email": "alice@example.com",
                        "avatar_url": "/avatar/9",
                    }
                ],
                "last_message": {
                    "id": 12345,
                    "content": "Hello!",
                    "sender_id": 9,
                    "timestamp": 1234567890
                },
                "unread_count": 2
            }
        ]
    }
    """

    if request.method != "GET":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "GET required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        # Use Zulip's proven function that queries UserMessage with is_private flag
        recipient_map = get_recent_private_conversations(user)

        conversations = []

        for recipient_id, data in recipient_map.items():
            participant_ids = data["user_ids"]
            if not participant_ids:
                continue

            # Get participant user info (excluding bots)
            participant_users = list(
                UserProfile.objects.filter(
                    id__in=participant_ids,
                    is_active=True,
                ).values("id", "full_name", "delivery_email", "avatar_source", "is_bot")
            )

            # Filter out bot users from participants
            non_bot_users = [u for u in participant_users if not u.get("is_bot")]

            # Skip conversations where all participants are bots (e.g., Welcome Bot)
            if not non_bot_users:
                continue

            users_data = [
                {
                    "id": u["id"],
                    "full_name": u["full_name"],
                    "email": u["delivery_email"],
                    "avatar_url": f"/avatar/{u['id']}" if u.get("avatar_source") else None,
                }
                for u in non_bot_users
            ]

            # Get last message using the max_message_id from recipient_map
            last_message = (
                Message.objects.select_related("sender").filter(id=data["max_message_id"]).first()
            )

            last_message_data = None
            if last_message:
                last_message_data = {
                    "id": last_message.id,
                    "content": last_message.content[:100],  # Preview only
                    "sender_id": last_message.sender_id,
                    "sender_full_name": last_message.sender.full_name,
                    "timestamp": int(last_message.date_sent.timestamp()),
                }

            # Get unread count - handle both DM models
            # Legacy PERSONAL: messages TO me have recipient=my.recipient_id
            # Modern GROUP: all messages share the group recipient_id
            if user.recipient_id is not None:
                # Legacy PERSONAL model - filter by MY recipient and sender
                unread_count = UserMessage.objects.filter(
                    user_profile=user,
                    message__recipient_id=user.recipient_id,  # Messages sent TO me
                    message__sender_id__in=participant_ids,  # From the other user(s)
                    flags__andz=UserMessage.flags.read.mask,  # Unread
                ).count()
            else:
                # Modern DIRECT_MESSAGE_GROUP model - Stream pattern works
                unread_count = UserMessage.objects.filter(
                    user_profile=user,
                    message__recipient_id=recipient_id,  # Shared group recipient
                    flags__andz=UserMessage.flags.read.mask,  # Unread
                ).count()

            conversations.append(
                {
                    "user_ids": participant_ids,
                    "users": users_data,
                    "last_message": last_message_data,
                    "unread_count": unread_count,
                }
            )

        # Sort by last message timestamp (most recent first)
        conversations.sort(
            key=lambda c: c["last_message"]["timestamp"] if c["last_message"] else 0,
            reverse=True,
        )

        return JsonResponse(
            {
                "result": "success",
                "conversations": conversations,
            }
        )

    except Exception as e:
        logger.exception("Failed to list DM conversations")
        return JsonResponse(
            {"result": "error", "code": "FETCH_FAILED", "msg": str(e)},
            status=500,
        )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="reactions_write", limit=MESSAGES_WRITE_LIMIT)
def add_reaction(request: HttpRequest, message_id: int) -> HttpResponse:
    """Add a reaction to a message.

    POST /api/v1/messages/{message_id}/reactions

    Request body:
    {
        "emoji_name": "thumbs_up",
        "emoji_code": "1f44d",
        "reaction_type": "unicode_emoji"  // optional, defaults to unicode_emoji
    }

    Response:
    {
        "result": "success"
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
    except json.JSONDecodeError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_JSON", "msg": "Invalid JSON body"},
            status=400,
        )

    emoji_name = body.get("emoji_name")
    emoji_code = body.get("emoji_code")
    reaction_type = body.get("reaction_type", "unicode_emoji")

    if not emoji_name:
        return JsonResponse(
            {"result": "error", "code": "INVALID_PARAMS", "msg": "emoji_name is required"},
            status=400,
        )

    try:
        with transaction.atomic():
            check_add_reaction(user, message_id, emoji_name, emoji_code, reaction_type)
        return JsonResponse({"result": "success"})
    except ReactionExistsError:
        # Idempotent success - reaction already exists
        return JsonResponse({"result": "success"})
    except JsonableError as e:
        error_code = str(e.code) if hasattr(e, "code") else "ERROR"
        return JsonResponse(
            {"result": "error", "code": error_code, "msg": str(e)},
            status=400,
        )
    except Exception as e:
        logger.exception("Failed to add reaction")
        return JsonResponse(
            {"result": "error", "code": "REACTION_FAILED", "msg": str(e)},
            status=500,
        )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="reactions_write", limit=MESSAGES_WRITE_LIMIT)
def remove_reaction(request: HttpRequest, message_id: int, emoji_name: str) -> HttpResponse:
    """Remove a reaction from a message.

    DELETE /api/v1/messages/{message_id}/reactions/{emoji_name}

    Query parameters:
    - reaction_type: "unicode_emoji" (default), "realm_emoji", or "zulip_extra_emoji"

    Response:
    {
        "result": "success"
    }
    """
    if request.method != "DELETE":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "DELETE required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]
    reaction_type = request.GET.get("reaction_type", "unicode_emoji")

    try:
        with transaction.atomic():
            message = access_message(user, message_id, lock_message=True, is_modifying_message=True)
            emoji_code = get_emoji_data(message.realm_id, emoji_name).emoji_code

            # Check if reaction exists
            if not Reaction.objects.filter(
                user_profile=user,
                message=message,
                emoji_code=emoji_code,
                reaction_type=reaction_type,
            ).exists():
                # Already removed - idempotent success
                return JsonResponse({"result": "success"})

            do_remove_reaction(user, message, emoji_code, reaction_type)
        return JsonResponse({"result": "success"})
    except ReactionDoesNotExistError:
        # Already removed - idempotent success
        return JsonResponse({"result": "success"})
    except JsonableError as e:
        return JsonResponse(
            {"result": "error", "code": getattr(e, "code", "ERROR"), "msg": str(e)},
            status=400,
        )
    except Exception as e:
        logger.exception("Failed to remove reaction")
        return JsonResponse(
            {"result": "error", "code": "REACTION_FAILED", "msg": str(e)},
            status=500,
        )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="messages_write", limit=MESSAGES_WRITE_LIMIT)
def mark_messages_as_read(request: HttpRequest) -> HttpResponse:
    """Mark messages as read.

    POST /api/v1/messages/read

    Request body:
    {
        "stream_id": 42,          // Optional: mark all in stream
        "topic": "welcome",       // Optional: mark all in topic (requires stream_id)
        "message_ids": [1,2,3]    // Optional: mark specific messages
    }

    Response:
    {
        "result": "success",
        "messages_marked": 5
    }
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_JSON", "msg": "Invalid JSON body"},
            status=400,
        )

    stream_id = body.get("stream_id")
    topic = body.get("topic")
    message_ids = body.get("message_ids")

    from zerver.models import Stream

    try:
        if stream_id:
            # Mark all messages in a stream (optionally filtered by topic)
            from zerver.actions.message_flags import do_mark_stream_messages_as_read

            stream = Stream.objects.get(id=stream_id, realm=user.realm)
            count = do_mark_stream_messages_as_read(user, stream.recipient_id, topic)
        elif message_ids:
            # Mark specific messages as read
            from zerver.actions.message_flags import do_update_message_flags

            count, _ = do_update_message_flags(user, "add", "read", message_ids)
        else:
            return JsonResponse(
                {
                    "result": "error",
                    "code": "INVALID_PARAMS",
                    "msg": "Either stream_id or message_ids required",
                },
                status=400,
            )

        return JsonResponse(
            {
                "result": "success",
                "messages_marked": count,
            }
        )
    except Stream.DoesNotExist:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Stream not found"},
            status=404,
        )
    except Exception as e:
        logger.exception("Failed to mark messages as read")
        return JsonResponse(
            {"result": "error", "code": "MARK_READ_FAILED", "msg": str(e)},
            status=500,
        )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="dm_write", limit=MESSAGES_WRITE_LIMIT)
def mute_dm_user(request: HttpRequest, user_id: int) -> HttpResponse:
    """Mute a user (hide their DMs from conversation list).

    POST /api/v1/dm/{user_id}/mute

    Response:
    {
        "result": "success",
        "msg": "User muted",
        "muted_user_id": 123
    }
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    if user.id == user_id:
        return JsonResponse(
            {"result": "error", "code": "INVALID_PARAMS", "msg": "Cannot mute yourself"},
            status=400,
        )

    try:
        muted_user = access_user_by_id_including_cross_realm(
            user, user_id, allow_bots=True, allow_deactivated=True, for_admin=False
        )
    except JsonableError:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "User not found"},
            status=404,
        )

    from django.db import IntegrityError
    from django.utils.timezone import now as timezone_now

    try:
        date_muted = timezone_now()
        do_mute_user(user, muted_user, date_muted)
        return JsonResponse(
            {
                "result": "success",
                "msg": "User muted",
                "muted_user_id": user_id,
            }
        )
    except IntegrityError:
        # Already muted - idempotent success
        return JsonResponse(
            {
                "result": "success",
                "msg": "User already muted",
                "muted_user_id": user_id,
            }
        )
    except Exception as e:
        logger.exception("Failed to mute user")
        return JsonResponse(
            {"result": "error", "code": "MUTE_FAILED", "msg": str(e)},
            status=500,
        )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="dm_write", limit=MESSAGES_WRITE_LIMIT)
def unmute_dm_user(request: HttpRequest, user_id: int) -> HttpResponse:
    """Unmute a user (show their DMs in conversation list again).

    POST /api/v1/dm/{user_id}/unmute

    Response:
    {
        "result": "success",
        "msg": "User unmuted",
        "muted_user_id": 123
    }
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        muted_user = access_user_by_id_including_cross_realm(
            user, user_id, allow_bots=True, allow_deactivated=True, for_admin=False
        )
    except JsonableError:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "User not found"},
            status=404,
        )

    mute_object = get_mute_object(user, muted_user)

    if mute_object is None:
        # Already unmuted - idempotent success
        return JsonResponse(
            {
                "result": "success",
                "msg": "User not muted",
                "muted_user_id": user_id,
            }
        )

    try:
        do_unmute_user(mute_object)
        return JsonResponse(
            {
                "result": "success",
                "msg": "User unmuted",
                "muted_user_id": user_id,
            }
        )
    except Exception as e:
        logger.exception("Failed to unmute user")
        return JsonResponse(
            {"result": "error", "code": "UNMUTE_FAILED", "msg": str(e)},
            status=500,
        )


@require_jwt_auth
@rate_limit(key_prefix="messages_read", limit=MESSAGES_READ_LIMIT)
def get_unread_counts(request: HttpRequest) -> HttpResponse:
    """Get unread message counts for the current user.

    GET /api/v1/unread

    Response:
    {
        "result": "success",
        "unread_counts": {
            "123": 5,           // stream_id: count
            "123:welcome": 2    // stream_id:topic: count
        }
    }
    """
    if request.method != "GET":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "GET required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        from zerver.lib.message import get_raw_unread_data

        raw_unread = get_raw_unread_data(user)

        # Transform to frontend-expected format
        unread_counts: dict[str, int] = {}

        # Stream unread counts from stream_dict
        stream_dict = raw_unread.get("stream_dict", {})
        for stream_id, topic_dict in stream_dict.items():
            stream_count = 0
            for topic, msg_ids in topic_dict.items():
                topic_count = len(msg_ids)
                stream_count += topic_count
                # Per-topic count
                unread_counts[f"{stream_id}:{topic}"] = topic_count

            # Total stream count
            unread_counts[str(stream_id)] = stream_count

        return JsonResponse(
            {
                "result": "success",
                "unread_counts": unread_counts,
            }
        )
    except Exception:
        logger.exception("Failed to get unread counts")
        return JsonResponse(
            {
                "result": "success",
                "unread_counts": {},
            }
        )


@csrf_exempt
@require_jwt_auth
def update_flags(request: HttpRequest) -> HttpResponse:
    """POST /api/v1/messages/flags - Update message flags (read, starred, etc.).

    Proxies to Zulip's do_update_message_flags with JWT auth.
    The Flutter client calls this heavily for mark-as-read.
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    # Parse JSON body or form-encoded data
    try:
        body = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        body = {k: v for k, v in request.POST.items()}

    op = body.get("op", "")
    flag = body.get("flag", "")
    messages = body.get("messages", [])

    # Validate
    if op not in ("add", "remove"):
        return JsonResponse(
            {"result": "error", "msg": "Missing or invalid 'op' parameter"},
            status=400,
        )
    if not flag:
        return JsonResponse(
            {"result": "error", "msg": "Missing 'flag' parameter"},
            status=400,
        )

    # Parse messages list from JSON string if form-encoded
    if isinstance(messages, str):
        try:
            messages = json.loads(messages)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse(
                {"result": "error", "msg": "Invalid 'messages' parameter"},
                status=400,
            )

    if not isinstance(messages, list):
        return JsonResponse(
            {"result": "error", "msg": "'messages' must be a list of message IDs"},
            status=400,
        )

    try:
        message_ids = [int(m) for m in messages]
    except (ValueError, TypeError):
        return JsonResponse(
            {"result": "error", "msg": "'messages' must contain valid IDs"},
            status=400,
        )

    try:
        count, ignored = do_update_message_flags(user, op, flag, message_ids)
    except Exception as e:
        logger.warning("[nodl-flags] Error updating flags: %s", e)
        return JsonResponse(
            {"result": "error", "msg": str(e)},
            status=400,
        )

    return JsonResponse(
        {
            "result": "success",
            "msg": "",
            "messages": message_ids,
            "ignored_because_not_subscribed_channels": ignored,
        }
    )


@csrf_exempt
@require_jwt_auth
def update_flags_narrow(request: HttpRequest) -> HttpResponse:
    """POST /api/v1/messages/flags/narrow - Update flags for messages matching a narrow.

    Proxies to Zulip's update_message_flags_for_narrow with JWT auth.
    Injects body params into request.POST so the @typed_endpoint decorator can parse them.
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "msg": "Method not allowed"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    # Ensure RequestNotes has a client set (required by Zulip views)
    from zerver.lib.request import RequestNotes

    notes = RequestNotes.get_notes(request)
    if notes.client is None:
        notes.client = get_client("nodl-web")

    # Parse JSON body and inject into request.POST for @typed_endpoint
    try:
        body = json.loads(request.body) if request.body else {}
    except (json.JSONDecodeError, ValueError):
        body = {}

    if body:
        request.POST = request.POST.copy()
        for key in ("anchor", "flag", "include_anchor", "narrow", "num_after", "num_before", "op"):
            if key in body and key not in request.POST:
                val = body[key]
                request.POST[key] = json.dumps(val) if isinstance(val, (list, dict, bool)) else str(val)

    from zerver.views.message_flags import update_message_flags_for_narrow

    try:
        return update_message_flags_for_narrow(request, user)
    except Exception as e:
        logger.warning("[nodl-flags-narrow] Error updating flags: %s", e)
        return JsonResponse(
            {"result": "error", "msg": str(e)},
            status=400,
        )
