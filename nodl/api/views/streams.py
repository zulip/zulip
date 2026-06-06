"""API views for stream endpoints.

Implements REST API for chat streams with JWT authentication.
CSRF protection is disabled for state-changing endpoints as they use
Bearer token (JWT) authentication, not browser session cookies.
"""

import json
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from pydantic import ValidationError

from nodl.api.serializers.streams import (
    StreamCreatePayload,
    StreamListSerializer,
    StreamSerializer,
    StreamUpdatePayload,
    TopicSerializer,
)
from nodl.extensions.models import NodlTaskStreamExtension
from zerver.actions.streams import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_change_stream_description,
    do_change_stream_permission,
    do_change_subscription_property,
    do_deactivate_stream,
    do_rename_stream,
)
from zerver.lib.rate_limiter import RateLimitedObject, RedisRateLimiterBackend
from zerver.lib.streams import (
    access_stream_by_id,
    access_stream_for_delete_or_update_requiring_metadata_access,
    check_stream_name_available,
    create_stream_if_needed,
    get_streams_for_user,
)
from zerver.lib.topic import get_topic_history_for_stream
from zerver.models import Stream, Subscription, UserProfile

logger = logging.getLogger(__name__)


# Rate limiting configuration
STREAMS_READ_LIMIT = 300  # requests per minute
STREAMS_WRITE_LIMIT = 60  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds


class StreamsRateLimitedObject(RateLimitedObject):
    """Rate limiter for streams API endpoints."""

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

            rate_limiter = StreamsRateLimitedObject(user.id, key_prefix, limit, window)
            try:
                rate_limiter.rate_limit_request(request)
            except Exception:
                return JsonResponse(
                    {"result": "error", "code": "RATE_LIMITED", "msg": "Too many requests"},
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


def _get_unread_counts_for_streams(user: UserProfile, streams: list[Stream]) -> dict[int, int]:
    """Get unread message counts for multiple streams in a single query.

    Returns a dict mapping recipient_id -> unread_count.
    This eliminates N+1 query problem when listing streams.
    """
    from django.db.models import Count

    from zerver.models import UserMessage

    if not streams:
        return {}

    recipient_ids = [s.recipient_id for s in streams]

    # Single aggregated query for all streams
    unread_counts = (
        UserMessage.objects.filter(
            user_profile=user,
            message__recipient_id__in=recipient_ids,
            flags__andz=UserMessage.flags.read.mask,  # andz = "and zero" - flag NOT set
        )
        .values("message__recipient_id")
        .annotate(count=Count("id"))
    )

    return {r["message__recipient_id"]: r["count"] for r in unread_counts}


def _get_subscribers_for_stream(stream: Stream) -> list[int]:
    """Get list of subscriber user IDs for a stream."""
    return list(
        Subscription.objects.filter(
            recipient=stream.recipient,
            active=True,
        ).values_list("user_profile_id", flat=True)
    )


def _parse_bool(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "on"}


@require_jwt_auth
@rate_limit(key_prefix="streams_read", limit=STREAMS_READ_LIMIT)
def list_streams(request: HttpRequest) -> HttpResponse:
    """List streams user can access with unread counts.

    GET /api/v1/streams

    Query parameters:
    - limit: Maximum number of streams to return (default: 100)
    - offset: Number of streams to skip (default: 0)
    - include_task_streams: Include task-owned streams in a separate response list.

    Response:
    {
        "result": "success",
        "streams": [
            {
                "id": 42,
                "name": "general",
                "description": "General discussion",
                "is_private": false,
                "unread_count": 5,
                ...
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
    include_task_streams = _parse_bool(request.GET.get("include_task_streams"))

    # Parse pagination parameters
    try:
        limit = int(request.GET.get("limit", 100))
        offset = int(request.GET.get("offset", 0))
    except ValueError:
        return JsonResponse(
            {"result": "error", "code": "INVALID_PARAMS", "msg": "Invalid pagination parameters"},
            status=400,
        )

    # Get streams user can access
    streams = get_streams_for_user(
        user,
        include_public=True,
        include_subscribed=True,
        include_web_public=False,
        exclude_archived=True,
    )

    task_stream_lookup = {
        stream_id: str(task_id)
        for stream_id, task_id in NodlTaskStreamExtension.objects.filter(
            zulip_realm_id=user.realm_id
        ).values_list(
            "zulip_stream_id",
            "nodl_task_id",
        )
    }
    task_stream_ids = set(task_stream_lookup)

    task_realm_streams = [
        s for s in streams
        if s.realm_id == user.realm_id and s.id in task_stream_ids
    ]
    normal_realm_streams = [
        s for s in streams
        if s.realm_id == user.realm_id and s.id not in task_stream_ids
    ]

    if include_task_streams:
        stream_counts = normal_realm_streams + task_realm_streams
    else:
        stream_counts = normal_realm_streams

    # Get all unread counts in a single query (fixes N+1 problem)
    unread_by_recipient = _get_unread_counts_for_streams(user, stream_counts)

    # Get user's subscription preferences (mute, pin) in a single query
    recipient_ids = [s.recipient_id for s in stream_counts]
    subscriptions = Subscription.objects.filter(
        user_profile=user,
        recipient_id__in=recipient_ids,
        active=True,
    ).values("recipient_id", "is_muted", "pin_to_top")
    sub_prefs_by_recipient = {
        sub["recipient_id"]: {"is_muted": sub["is_muted"], "pin_to_top": sub["pin_to_top"]}
        for sub in subscriptions
    }

    def serialize_streams(source_streams: list[Stream], *, is_task_stream: bool) -> list[dict]:
        stream_data = []
        for stream in source_streams:
            unread_count = unread_by_recipient.get(stream.recipient_id, 0)
            sub_prefs = sub_prefs_by_recipient.get(
                stream.recipient_id, {"is_muted": False, "pin_to_top": False}
            )
            serializer = StreamListSerializer.from_stream_with_unread(
                stream,
                unread_count=unread_count,
                is_muted=sub_prefs["is_muted"],
                pin_to_top=sub_prefs["pin_to_top"],
                is_task_stream=is_task_stream,
                task_id=task_stream_lookup.get(stream.id) if is_task_stream else None,
            )
            stream_data.append(serializer.model_dump())
        return stream_data

    # Filter streams to user's realm and hide task-owned streams from normal chat navigation.
    realm_streams = normal_realm_streams

    # Apply pagination to normal streams only; task streams are returned as a separate,
    # usually-small list for the task discussion section.
    paginated_streams = realm_streams[offset : offset + limit]
    stream_data = serialize_streams(paginated_streams, is_task_stream=False)
    task_stream_data = (
        serialize_streams(task_realm_streams, is_task_stream=True)
        if include_task_streams
        else []
    )

    return JsonResponse(
        {
            "result": "success",
            "streams": stream_data,
            "task_streams": task_stream_data,
            "count": len(stream_data),
            "total": len(realm_streams),
        }
    )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="streams_write", limit=STREAMS_WRITE_LIMIT)
def create_stream(request: HttpRequest) -> HttpResponse:
    """Create a new stream.

    POST /api/v1/streams

    Request body:
    {
        "name": "new-stream",
        "description": "A new stream",
        "is_private": false,
        "is_announcement_only": false
    }

    Response:
    {
        "result": "success",
        "stream": {...}
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
        payload = StreamCreatePayload(**body)
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

    # Check if stream name is available
    try:
        check_stream_name_available(user.realm, payload.name)
    except Exception:
        return JsonResponse(
            {
                "result": "error",
                "code": "STREAM_EXISTS",
                "msg": f"Stream '{payload.name}' already exists",
            },
            status=400,
        )

    # Create the stream
    try:
        stream, created = create_stream_if_needed(
            user.realm,
            payload.name,
            invite_only=payload.is_private,
            stream_description=payload.description,
            history_public_to_subscribers=payload.history_public_to_subscribers,
            acting_user=user,
        )

        # Auto-subscribe creator
        bulk_add_subscriptions(
            user.realm,
            [stream],
            [user],
            acting_user=user,
        )

        serializer = StreamSerializer.from_stream(stream, subscribers=[user.id])
        return JsonResponse(
            {
                "result": "success",
                "stream": serializer.model_dump(),
            },
            status=201,
        )
    except Exception as e:
        logger.exception("Failed to create stream")
        return JsonResponse(
            {"result": "error", "code": "CREATION_FAILED", "msg": str(e)},
            status=500,
        )


@require_jwt_auth
@rate_limit(key_prefix="streams_read", limit=STREAMS_READ_LIMIT)
def get_stream(request: HttpRequest, stream_id: int) -> HttpResponse:
    """Get stream details including subscribers.

    GET /api/v1/streams/{id}

    Response:
    {
        "result": "success",
        "stream": {
            "id": 42,
            "name": "general",
            "description": "General discussion",
            "subscribers": [678, 901, 234],
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

    try:
        stream, _ = access_stream_by_id(user, stream_id)
    except Exception:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Stream not found or access denied"},
            status=404,
        )

    # Get subscribers if stream is visible
    subscribers = _get_subscribers_for_stream(stream)

    serializer = StreamSerializer.from_stream(stream, subscribers=subscribers)
    return JsonResponse(
        {
            "result": "success",
            "stream": serializer.model_dump(),
        }
    )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="streams_write", limit=STREAMS_WRITE_LIMIT)
def update_stream(request: HttpRequest, stream_id: int) -> HttpResponse:
    """Update stream settings (admin only).

    PATCH /api/v1/streams/{id}

    Request body:
    {
        "name": "renamed-stream",
        "description": "Updated description",
        "is_private": true
    }

    Response:
    {
        "result": "success",
        "stream": {...}
    }
    """
    if request.method != "PATCH":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "PATCH required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        stream, _ = access_stream_for_delete_or_update_requiring_metadata_access(user, stream_id)
    except Exception:
        return JsonResponse(
            {
                "result": "error",
                "code": "FORBIDDEN",
                "msg": "You don't have permission to update this stream",
            },
            status=403,
        )

    try:
        body = json.loads(request.body)
        payload = StreamUpdatePayload(**body)
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

    try:
        # Update name if provided
        if payload.name is not None and payload.name != stream.name:
            do_rename_stream(stream, payload.name, user)

        # Update description if provided
        if payload.description is not None and payload.description != stream.description:
            do_change_stream_description(stream, payload.description, acting_user=user)

        # Update privacy if provided
        if payload.is_private is not None and payload.is_private != stream.invite_only:
            do_change_stream_permission(
                stream,
                invite_only=payload.is_private,
                history_public_to_subscribers=not payload.is_private,
                is_web_public=False,
                acting_user=user,
            )

        # Refresh stream from DB
        stream.refresh_from_db()
        subscribers = _get_subscribers_for_stream(stream)
        serializer = StreamSerializer.from_stream(stream, subscribers=subscribers)

        return JsonResponse(
            {
                "result": "success",
                "stream": serializer.model_dump(),
            }
        )
    except Exception as e:
        logger.exception("Failed to update stream")
        return JsonResponse(
            {"result": "error", "code": "UPDATE_FAILED", "msg": str(e)},
            status=500,
        )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="streams_write", limit=STREAMS_WRITE_LIMIT)
def archive_stream(request: HttpRequest, stream_id: int) -> HttpResponse:
    """Archive stream (admin only).

    DELETE /api/v1/streams/{id}

    Response:
    {
        "result": "success",
        "msg": "Stream archived"
    }
    """
    if request.method != "DELETE":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "DELETE required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        stream, _ = access_stream_for_delete_or_update_requiring_metadata_access(user, stream_id)
    except Exception:
        return JsonResponse(
            {
                "result": "error",
                "code": "FORBIDDEN",
                "msg": "You don't have permission to archive this stream",
            },
            status=403,
        )

    try:
        do_deactivate_stream(stream, acting_user=user)
        return JsonResponse(
            {
                "result": "success",
                "msg": "Stream archived",
            }
        )
    except Exception as e:
        logger.exception("Failed to archive stream")
        return JsonResponse(
            {"result": "error", "code": "ARCHIVE_FAILED", "msg": str(e)},
            status=500,
        )


@require_jwt_auth
@rate_limit(key_prefix="streams_read", limit=STREAMS_READ_LIMIT)
def get_stream_topics(request: HttpRequest, stream_id: int) -> HttpResponse:
    """Get topics in stream with message counts.

    GET /api/v1/streams/{id}/topics

    Response:
    {
        "result": "success",
        "topics": [
            {
                "name": "Welcome",
                "max_id": 12345,
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
        stream, _ = access_stream_by_id(user, stream_id)
    except Exception:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Stream not found or access denied"},
            status=404,
        )

    # Get topic history
    public_history = stream.is_history_realm_public() or stream.history_public_to_subscribers
    topic_history = get_topic_history_for_stream(
        user,
        stream.recipient_id,
        public_history,
        allow_empty_topic_name=True,
    )

    # Convert to TopicSerializer format
    topics = [
        TopicSerializer(
            name=topic["name"],
            max_id=topic["max_id"],
            unread_count=0,  # Known limitation: per-topic unread counts not implemented
        ).model_dump()
        for topic in topic_history
    ]

    return JsonResponse(
        {
            "result": "success",
            "topics": topics,
        }
    )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="streams_write", limit=STREAMS_WRITE_LIMIT)
def subscribe_to_stream(request: HttpRequest, stream_id: int) -> HttpResponse:
    """Subscribe current user to stream.

    POST /api/v1/streams/{id}/subscribe

    Response:
    {
        "result": "success",
        "msg": "Subscribed to stream"
    }
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        stream, _ = access_stream_by_id(user, stream_id)
    except Exception:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Stream not found or access denied"},
            status=404,
        )

    try:
        result = bulk_add_subscriptions(
            user.realm,
            [stream],
            [user],
            acting_user=user,
        )

        # Check if already subscribed
        already_subscribed = any(
            sub_info[0] == user and sub_info[1] == stream
            for sub_info in result[1]  # already_subscribed list
        )

        if already_subscribed:
            return JsonResponse(
                {
                    "result": "success",
                    "msg": "Already subscribed to stream",
                }
            )

        return JsonResponse(
            {
                "result": "success",
                "msg": "Subscribed to stream",
            }
        )
    except Exception as e:
        logger.exception("Failed to subscribe to stream")
        return JsonResponse(
            {"result": "error", "code": "SUBSCRIBE_FAILED", "msg": str(e)},
            status=500,
        )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="streams_write", limit=STREAMS_WRITE_LIMIT)
def unsubscribe_from_stream(request: HttpRequest, stream_id: int) -> HttpResponse:
    """Unsubscribe current user from stream.

    DELETE /api/v1/streams/{id}/subscribe

    Response:
    {
        "result": "success",
        "msg": "Unsubscribed from stream"
    }
    """
    if request.method != "DELETE":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "DELETE required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        stream, _ = access_stream_by_id(user, stream_id)
    except Exception:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Stream not found or access denied"},
            status=404,
        )

    try:
        removed, not_subscribed = bulk_remove_subscriptions(
            user.realm,
            [user],
            [stream],
            acting_user=user,
        )

        # Check if was not subscribed
        if any(sub_info[0] == user and sub_info[1] == stream for sub_info in not_subscribed):
            return JsonResponse(
                {
                    "result": "success",
                    "msg": "Already not subscribed to stream",
                }
            )

        return JsonResponse(
            {
                "result": "success",
                "msg": "Unsubscribed from stream",
            }
        )
    except Exception as e:
        logger.exception("Failed to unsubscribe from stream")
        return JsonResponse(
            {"result": "error", "code": "UNSUBSCRIBE_FAILED", "msg": str(e)},
            status=500,
        )


def _get_user_subscription(user: UserProfile, stream: Stream) -> Subscription | None:
    """Get the subscription object for user's stream subscription."""
    try:
        return Subscription.objects.get(
            user_profile=user,
            recipient=stream.recipient,
            active=True,
        )
    except Subscription.DoesNotExist:
        return None


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="streams_write", limit=STREAMS_WRITE_LIMIT)
def mute_stream(request: HttpRequest, stream_id: int) -> HttpResponse:
    """Mute a stream for the current user.

    POST /api/v1/streams/{id}/mute

    Response:
    {
        "result": "success",
        "msg": "Stream muted",
        "is_muted": true
    }
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        stream, _ = access_stream_by_id(user, stream_id)
    except Exception:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Stream not found or access denied"},
            status=404,
        )

    sub = _get_user_subscription(user, stream)
    if sub is None:
        return JsonResponse(
            {
                "result": "error",
                "code": "NOT_SUBSCRIBED",
                "msg": "You are not subscribed to this stream",
            },
            status=400,
        )

    try:
        do_change_subscription_property(
            user,
            sub,
            stream,
            "is_muted",
            True,
            acting_user=user,
        )
        return JsonResponse(
            {
                "result": "success",
                "msg": "Stream muted",
                "is_muted": True,
            }
        )
    except Exception as e:
        logger.exception("Failed to mute stream")
        return JsonResponse(
            {"result": "error", "code": "MUTE_FAILED", "msg": str(e)},
            status=500,
        )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="streams_write", limit=STREAMS_WRITE_LIMIT)
def unmute_stream(request: HttpRequest, stream_id: int) -> HttpResponse:
    """Unmute a stream for the current user.

    POST /api/v1/streams/{id}/unmute

    Response:
    {
        "result": "success",
        "msg": "Stream unmuted",
        "is_muted": false
    }
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        stream, _ = access_stream_by_id(user, stream_id)
    except Exception:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Stream not found or access denied"},
            status=404,
        )

    sub = _get_user_subscription(user, stream)
    if sub is None:
        return JsonResponse(
            {
                "result": "error",
                "code": "NOT_SUBSCRIBED",
                "msg": "You are not subscribed to this stream",
            },
            status=400,
        )

    try:
        do_change_subscription_property(
            user,
            sub,
            stream,
            "is_muted",
            False,
            acting_user=user,
        )
        return JsonResponse(
            {
                "result": "success",
                "msg": "Stream unmuted",
                "is_muted": False,
            }
        )
    except Exception as e:
        logger.exception("Failed to unmute stream")
        return JsonResponse(
            {"result": "error", "code": "UNMUTE_FAILED", "msg": str(e)},
            status=500,
        )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="streams_write", limit=STREAMS_WRITE_LIMIT)
def pin_stream(request: HttpRequest, stream_id: int) -> HttpResponse:
    """Pin a stream to top of sidebar for the current user.

    POST /api/v1/streams/{id}/pin

    Response:
    {
        "result": "success",
        "msg": "Stream pinned",
        "pin_to_top": true
    }
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        stream, _ = access_stream_by_id(user, stream_id)
    except Exception:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Stream not found or access denied"},
            status=404,
        )

    sub = _get_user_subscription(user, stream)
    if sub is None:
        return JsonResponse(
            {
                "result": "error",
                "code": "NOT_SUBSCRIBED",
                "msg": "You are not subscribed to this stream",
            },
            status=400,
        )

    try:
        do_change_subscription_property(
            user,
            sub,
            stream,
            "pin_to_top",
            True,
            acting_user=user,
        )
        return JsonResponse(
            {
                "result": "success",
                "msg": "Stream pinned",
                "pin_to_top": True,
            }
        )
    except Exception as e:
        logger.exception("Failed to pin stream")
        return JsonResponse(
            {"result": "error", "code": "PIN_FAILED", "msg": str(e)},
            status=500,
        )


@csrf_exempt
@require_jwt_auth
@rate_limit(key_prefix="streams_write", limit=STREAMS_WRITE_LIMIT)
def unpin_stream(request: HttpRequest, stream_id: int) -> HttpResponse:
    """Unpin a stream from top of sidebar for the current user.

    POST /api/v1/streams/{id}/unpin

    Response:
    {
        "result": "success",
        "msg": "Stream unpinned",
        "pin_to_top": false
    }
    """
    if request.method != "POST":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "POST required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        stream, _ = access_stream_by_id(user, stream_id)
    except Exception:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "Stream not found or access denied"},
            status=404,
        )

    sub = _get_user_subscription(user, stream)
    if sub is None:
        return JsonResponse(
            {
                "result": "error",
                "code": "NOT_SUBSCRIBED",
                "msg": "You are not subscribed to this stream",
            },
            status=400,
        )

    try:
        do_change_subscription_property(
            user,
            sub,
            stream,
            "pin_to_top",
            False,
            acting_user=user,
        )
        return JsonResponse(
            {
                "result": "success",
                "msg": "Stream unpinned",
                "pin_to_top": False,
            }
        )
    except Exception as e:
        logger.exception("Failed to unpin stream")
        return JsonResponse(
            {"result": "error", "code": "UNPIN_FAILED", "msg": str(e)},
            status=500,
        )
