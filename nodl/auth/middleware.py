"""Supabase JWT authentication middleware for nodl-chat.

This module provides Django middleware for validating Supabase JWT tokens
and attaching user information to requests.
"""

import logging

import jwt
from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, JsonResponse
from django.http.response import HttpResponseBase
from django.utils.crypto import constant_time_compare

from zerver.models import UserProfile

logger = logging.getLogger(__name__)

# Cache timeout for user profile lookups (in seconds)
# Short timeout to ensure changes propagate quickly while still reducing DB load
USER_PROFILE_CACHE_TIMEOUT = 60  # 1 minute


class SupabaseJWTMiddleware:
    """Validate Supabase JWT tokens from Authorization header.

    This middleware:
    - Extracts JWT tokens from Authorization header or query parameter
    - Validates tokens using the Supabase JWT secret
    - Attaches user info (sub, email, role) to the request object
    - Returns 401 errors for expired, invalid, or missing tokens
    - Exempts health check and internal API endpoints
    """

    # Paths that bypass JWT authentication — exact match
    EXEMPT_EXACT = {
        "/health",
        "/nodl/auth/bridge",  # Auth bridge handles its own Supabase JWT validation
    }

    # Paths that bypass JWT authentication — prefix match
    EXEMPT_PREFIXES = (
        "/api/v1/internal/",
        "/api/v1/events/internal",  # Zulip internal Django→Tornado (uses SHARED_SECRET)
        "/user_uploads",  # Browser img/file requests don't include auth headers
        "/thumbnail",  # Thumbnail requests - Zulip's view handles permission checks
        "/nodl/auth/bridge",  # Auth bridge handles its own Supabase JWT validation
    )

    def __init__(self, get_response: callable) -> None:
        """Initialize the middleware.

        Args:
            get_response: The next middleware or view in the chain.
        """
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        """Process the request and validate JWT token.

        Args:
            request: The incoming HTTP request.

        Returns:
            The response from the next middleware/view, or a 401 error response.
        """
        # Skip auth for exempt paths
        if self._is_exempt(request.path):
            return self.get_response(request)

        token = self._extract_token(request)
        if not token:
            logger.warning(f"[nodl-auth] No token in request to {request.path}")
            return self._error_response("Token required")

        # Check if JWT secret is configured
        if not settings.SUPABASE_JWT_SECRET:
            logger.error("[nodl-auth] SUPABASE_JWT_SECRET is not configured!")
            return self._error_response("Server configuration error")

        try:
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )

            # Attach user info to request
            request.supabase_user_id = payload["sub"]
            request.supabase_email = payload.get("email")
            request.supabase_role = payload.get("role", "authenticated")

            # Look up the corresponding Zulip UserProfile
            # This bridges Supabase JWT auth to Zulip's user system
            # Uses caching to avoid DB query on every request
            email = payload.get("email")
            # Optional workspace_id header for multi-realm disambiguation
            workspace_id = request.headers.get("X-Workspace-Id")
            if email:
                user_profile = self._get_user_profile_cached(email, workspace_id)
                if user_profile:
                    request.user_profile = user_profile
                    request.user = user_profile  # Django's auth system expects this
                    logger.info(
                        f"[nodl-auth] JWT auth success for {email} (user_id={user_profile.id})"
                    )
                else:
                    # User not yet synced from Supabase - views will return 401
                    logger.warning(f"[nodl-auth] JWT valid but UserProfile not found for {email}")
            else:
                logger.warning("[nodl-auth] JWT valid but no email in payload")

        except jwt.ExpiredSignatureError:
            logger.warning(f"[nodl-auth] Expired token for {request.path}")
            return self._error_response("Token expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"[nodl-auth] Invalid token: {e}")
            return self._error_response(str(e))

        return self.get_response(request)

    def _extract_token(self, request: HttpRequest) -> str | None:
        """Extract JWT token from request.

        Checks Authorization header first (Bearer token), then falls back
        to query parameter for WebSocket connections.

        Args:
            request: The incoming HTTP request.

        Returns:
            The JWT token string, or None if not found.
        """
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        # Fall back to query param for WebSocket connections
        return request.GET.get("token")

    def _is_exempt(self, path: str) -> bool:
        """Check if the request path is exempt from authentication.

        Args:
            path: The request path.

        Returns:
            True if the path should bypass authentication.
        """
        if path in self.EXEMPT_EXACT:
            return True
        return any(
            path == prefix or path.startswith(prefix + "/") for prefix in self.EXEMPT_PREFIXES
        )

    def _get_user_profile_cached(
        self, email: str, workspace_id: str | None = None
    ) -> UserProfile | None:
        """Get UserProfile by email, with caching to reduce DB queries.

        Args:
            email: The user's email address.
            workspace_id: Optional workspace ID to disambiguate users in multiple realms.

        Returns:
            The UserProfile if found, None otherwise.
        """
        # Include workspace_id in cache key if provided for proper isolation
        cache_key = f"jwt_user_profile:{email}:{workspace_id or 'any'}"

        # Try cache first
        user_profile = cache.get(cache_key)
        if user_profile is not None:
            # Cache hit - verify user is still active (cache stores the object)
            if isinstance(user_profile, UserProfile) and user_profile.is_active:
                return user_profile
            # Cached "not found" marker or inactive user
            if user_profile == "NOT_FOUND":
                return None

        # Cache miss - query database
        try:
            queryset = UserProfile.objects.filter(
                delivery_email=email,
                is_active=True,
            )

            # If workspace_id provided, filter by realm string_id
            if workspace_id:
                # Realm string_id is first 20 chars of workspace_id
                realm_string_id = workspace_id[:20].lower()
                queryset = queryset.filter(realm__string_id=realm_string_id)

            user_profile = queryset.get()
            cache.set(cache_key, user_profile, USER_PROFILE_CACHE_TIMEOUT)
            return user_profile

        except UserProfile.DoesNotExist:
            # Cache the "not found" result to avoid repeated queries
            cache.set(cache_key, "NOT_FOUND", USER_PROFILE_CACHE_TIMEOUT)
            return None

        except UserProfile.MultipleObjectsReturned:
            # User exists in multiple realms - return most recently created
            # This can happen when same email is used across workspaces
            logger.warning(
                f"[nodl-auth] Multiple UserProfiles found for {email}, "
                "using most recently created. Consider passing X-Workspace-Id header."
            )
            user_profile = queryset.order_by("-id").first()
            if user_profile:
                cache.set(cache_key, user_profile, USER_PROFILE_CACHE_TIMEOUT)
            return user_profile

    def _error_response(self, message: str) -> JsonResponse:
        """Create a standardized error response.

        Args:
            message: The error message.

        Returns:
            A JSON response with 401 status.
        """
        return JsonResponse(
            {"result": "error", "code": "UNAUTHORIZED", "msg": message},
            status=401,
        )


class ServiceKeyAuthMiddleware:
    """Authenticate internal API requests using service key.

    This middleware validates requests to /api/v1/internal/* endpoints
    using a shared service key. It should run after SupabaseJWTMiddleware
    to handle the internal paths that JWT middleware exempts.
    """

    INTERNAL_PATH_PREFIX = "/api/v1/internal/"

    def __init__(self, get_response: callable) -> None:
        """Initialize the middleware.

        Args:
            get_response: The next middleware or view in the chain.
        """
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        """Process the request and validate service key.

        Args:
            request: The incoming HTTP request.

        Returns:
            The response from the next middleware/view, or a 401 error response.
        """
        # Only validate internal API requests
        if not request.path.startswith(self.INTERNAL_PATH_PREFIX):
            return self.get_response(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return self._error_response("Service key required")

        provided_key = auth_header[7:]
        expected_key = getattr(settings, "CHAT_SERVICE_KEY", None)

        if not expected_key:
            return JsonResponse(
                {"result": "error", "code": "INTERNAL_ERROR", "msg": "Service key not configured"},
                status=500,
            )

        if not constant_time_compare(provided_key, expected_key):
            return self._error_response("Invalid service key")

        # Mark request as service-authenticated
        request.is_service_request = True

        return self.get_response(request)

    def _error_response(self, message: str) -> JsonResponse:
        """Create a standardized error response.

        Args:
            message: The error message.

        Returns:
            A JSON response with 401 status.
        """
        return JsonResponse(
            {"result": "error", "code": "UNAUTHORIZED", "msg": message},
            status=401,
        )
