"""Supabase JWT authentication middleware for nodl-chat.

This module provides Django middleware for validating Supabase JWT tokens
and attaching user information to requests.
"""

import jwt
from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.http.response import HttpResponseBase
from django.utils.crypto import constant_time_compare

from zerver.models import UserProfile


class SupabaseJWTMiddleware:
    """Validate Supabase JWT tokens from Authorization header.

    This middleware:
    - Extracts JWT tokens from Authorization header or query parameter
    - Validates tokens using the Supabase JWT secret
    - Attaches user info (sub, email, role) to the request object
    - Returns 401 errors for expired, invalid, or missing tokens
    - Exempts health check and internal API endpoints
    """

    # Paths that bypass JWT authentication
    EXEMPT_PATHS = (
        "/health",
        "/api/v1/internal/",
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
            return self._error_response("Token required")

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
            email = payload.get("email")
            if email:
                try:
                    user_profile = UserProfile.objects.get(
                        delivery_email=email,
                        is_active=True,
                    )
                    request.user_profile = user_profile
                    request.user = user_profile  # Django's auth system expects this
                except UserProfile.DoesNotExist:
                    # User not yet synced from Supabase - views will return 401
                    pass

        except jwt.ExpiredSignatureError:
            return self._error_response("Token expired")
        except jwt.InvalidTokenError as e:
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
        return any(path.startswith(exempt) for exempt in self.EXEMPT_PATHS)

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
