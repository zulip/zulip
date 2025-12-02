"""API views for stream endpoints.

Implements REST API for chat streams with JWT authentication.
CSRF protection is disabled for state-changing endpoints as they use
Bearer token (JWT) authentication, not browser session cookies.
"""

import json
import logging
from functools import wraps
from typing import Any, Callable

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
from zerver.actions.streams import (
    bulk_add_subscriptions,
    bulk_remove_subscriptions,
    do_change_stream_description,
    do_change_stream_permission,
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


def _get_unread_count_for_stream(user: UserProfile, stream: Stream) -> int:
    """Get unread message count for a stream."""
    from zerver.models import UserMessage
    return UserMessage.objects.filter(
        user_profile=user,
        message__recipient=stream.recipient,
        flags__andnot=UserMessage.flags.read,
    ).count()


def _get_subscribers_for_stream(stream: Stream) -> list[int]:
    """Get list of subscriber user IDs for a stream."""
    return list(
        Subscription.objects.filter(
            recipient=stream.recipient,
            active=True,
        ).values_list("user_profile_id", flat=True)
    )


@require_jwt_auth
@rate_limit(key_prefix="streams_read", limit=STREAMS_READ_LIMIT)
def list_streams(request: HttpRequest) -> HttpResponse:
    """List streams user can access with unread counts.

    GET /api/v1/streams

    Query parameters:
    - limit: Maximum number of streams to return (default: 100)
    - offset: Number of streams to skip (default: 0)

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

    # Filter streams to user's realm
    realm_streams = [s for s in streams if s.realm_id == user.realm_id]

    # Apply pagination
    paginated_streams = realm_streams[offset:offset + limit]

    # Build response with unread counts
    stream_data = []
    for stream in paginated_streams:
        unread_count = _get_unread_count_for_stream(user, stream)
        serializer = StreamListSerializer.from_stream_with_unread(
            stream,
            unread_count=unread_count,
        )
        stream_data.append(serializer.model_dump())

    return JsonResponse({
        "result": "success",
        "streams": stream_data,
        "count": len(stream_data),
        "total": len(realm_streams),
    })


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
    except Exception as e:
        return JsonResponse(
            {"result": "error", "code": "STREAM_EXISTS", "msg": f"Stream '{payload.name}' already exists"},
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
        return JsonResponse({
            "result": "success",
            "stream": serializer.model_dump(),
        }, status=201)
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
    return JsonResponse({
        "result": "success",
        "stream": serializer.model_dump(),
    })


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
            {"result": "error", "code": "FORBIDDEN", "msg": "You don't have permission to update this stream"},
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

        return JsonResponse({
            "result": "success",
            "stream": serializer.model_dump(),
        })
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
            {"result": "error", "code": "FORBIDDEN", "msg": "You don't have permission to archive this stream"},
            status=403,
        )

    try:
        do_deactivate_stream(stream, acting_user=user)
        return JsonResponse({
            "result": "success",
            "msg": "Stream archived",
        })
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

    return JsonResponse({
        "result": "success",
        "topics": topics,
    })


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
            return JsonResponse({
                "result": "success",
                "msg": "Already subscribed to stream",
            })

        return JsonResponse({
            "result": "success",
            "msg": "Subscribed to stream",
        })
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
            return JsonResponse({
                "result": "success",
                "msg": "Already not subscribed to stream",
            })

        return JsonResponse({
            "result": "success",
            "msg": "Unsubscribed from stream",
        })
    except Exception as e:
        logger.exception("Failed to unsubscribe from stream")
        return JsonResponse(
            {"result": "error", "code": "UNSUBSCRIBE_FAILED", "msg": str(e)},
            status=500,
        )
