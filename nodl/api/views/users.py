"""API views for user endpoints.

Implements REST API for chat users with JWT authentication.
"""

import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse

from zerver.lib.rate_limiter import RateLimitedObject, RedisRateLimiterBackend
from zerver.models import UserProfile

logger = logging.getLogger(__name__)


# Rate limiting configuration
USERS_READ_LIMIT = 300  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds


class UsersRateLimitedObject(RateLimitedObject):
    """Rate limiter for users API endpoints."""

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

            rate_limiter = UsersRateLimitedObject(user.id, key_prefix, limit, window)
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


def _map_role_to_string(role: int) -> str:
    """Map Zulip role integer to frontend role string."""
    role_mapping = {
        UserProfile.ROLE_REALM_OWNER: "realm_owner",
        UserProfile.ROLE_REALM_ADMINISTRATOR: "realm_admin",
        UserProfile.ROLE_MODERATOR: "realm_admin",
        UserProfile.ROLE_MEMBER: "member",
        UserProfile.ROLE_GUEST: "guest",
    }
    return role_mapping.get(role, "member")


def _serialize_user(user: UserProfile) -> dict[str, Any]:
    """Serialize a UserProfile to the ChatUser format expected by frontend."""
    return {
        "id": user.id,
        "email": user.delivery_email,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url() if hasattr(user, "avatar_url") else None,
        "role": _map_role_to_string(user.role),
    }


@require_jwt_auth
@rate_limit(key_prefix="users_read", limit=USERS_READ_LIMIT)
def get_current_user(request: HttpRequest) -> HttpResponse:
    """Get current authenticated user's profile.

    GET /api/v1/users/me

    Response:
    {
        "result": "success",
        "id": 123,
        "email": "user@example.com",
        "full_name": "John Doe",
        "avatar_url": "...",
        "role": "member"
    }
    """
    if request.method != "GET":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "GET required"},
            status=405,
        )

    user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    user_data = _serialize_user(user)
    return JsonResponse(
        {
            "result": "success",
            **user_data,
        }
    )


@require_jwt_auth
@rate_limit(key_prefix="users_read", limit=USERS_READ_LIMIT)
def list_users(request: HttpRequest) -> HttpResponse:
    """List all users in the authenticated user's realm.

    GET /api/v1/users

    Query parameters:
    - limit: Maximum number of users to return (default: 100)
    - offset: Number of users to skip (default: 0)

    Response:
    {
        "result": "success",
        "users": [
            {
                "id": 123,
                "email": "user@example.com",
                "full_name": "John Doe",
                "avatar_url": "...",
                "role": "member"
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

    # Get all active users in the same realm
    realm_users = UserProfile.objects.filter(
        realm_id=user.realm_id,
        is_active=True,
    ).order_by("full_name")

    total = realm_users.count()
    paginated_users = realm_users[offset : offset + limit]

    users_data = [_serialize_user(u) for u in paginated_users]

    return JsonResponse(
        {
            "result": "success",
            "users": users_data,
            "count": len(users_data),
            "total": total,
        }
    )


@require_jwt_auth
@rate_limit(key_prefix="users_read", limit=USERS_READ_LIMIT)
def get_user(request: HttpRequest, user_id: int) -> HttpResponse:
    """Get a specific user's profile.

    GET /api/v1/users/{id}

    Response:
    {
        "result": "success",
        "id": 123,
        "email": "user@example.com",
        "full_name": "John Doe",
        "avatar_url": "...",
        "role": "member"
    }
    """
    if request.method != "GET":
        return JsonResponse(
            {"result": "error", "code": "METHOD_NOT_ALLOWED", "msg": "GET required"},
            status=405,
        )

    current_user: UserProfile = request.user_profile  # type: ignore[attr-defined]

    try:
        # Only allow access to users in the same realm
        target_user = UserProfile.objects.get(
            id=user_id,
            realm_id=current_user.realm_id,
            is_active=True,
        )
    except UserProfile.DoesNotExist:
        return JsonResponse(
            {"result": "error", "code": "NOT_FOUND", "msg": "User not found"},
            status=404,
        )

    user_data = _serialize_user(target_user)
    return JsonResponse(
        {
            "result": "success",
            **user_data,
        }
    )
