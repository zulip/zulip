"""Unit tests for Supabase JWT authentication middleware.

Tests cover:
- Valid token authentication (IV1)
- Expired token rejection (IV2)
- Invalid token rejection
- Missing token rejection
- Exempt paths bypass auth
- WebSocket token via query param
- Service key authentication
"""

import time
from unittest.mock import Mock

import jwt
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.test import override_settings

from nodl.auth.middleware import ServiceKeyAuthMiddleware, SupabaseJWTMiddleware

# Test constants
TEST_JWT_SECRET = "test-jwt-secret-for-testing-only"
TEST_USER_ID = "test-user-uuid-1234"
TEST_EMAIL = "test@example.com"
TEST_SERVICE_KEY = "test-service-key-for-testing"


def create_mock_request(
    path: str = "/api/v1/messages",
    auth_header: str | None = None,
    query_params: dict[str, str] | None = None,
) -> HttpRequest:
    """Create a mock Django request for testing.

    Args:
        path: The request path.
        auth_header: Optional Authorization header value.
        query_params: Optional query parameters dict.

    Returns:
        A mock HttpRequest object.
    """
    request = Mock(spec=HttpRequest)
    request.path = path

    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header

    request.headers = Mock()
    request.headers.get = lambda key, default="": headers.get(key, default)

    request.GET = Mock()
    request.GET.get = lambda key, default=None: (query_params or {}).get(key, default)

    return request


def create_valid_token(
    user_id: str = TEST_USER_ID,
    email: str = TEST_EMAIL,
    role: str = "authenticated",
    secret: str = TEST_JWT_SECRET,
    exp_offset: int = 3600,
) -> str:
    """Create a valid JWT token for testing.

    Args:
        user_id: The user ID (sub claim).
        email: The user email.
        role: The user role.
        secret: The JWT secret.
        exp_offset: Seconds from now until expiration.

    Returns:
        A JWT token string.
    """
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "aud": "authenticated",
        "exp": int(time.time()) + exp_offset,
        "iat": int(time.time()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def create_expired_token(
    user_id: str = TEST_USER_ID,
    email: str = TEST_EMAIL,
    secret: str = TEST_JWT_SECRET,
) -> str:
    """Create an expired JWT token for testing.

    Args:
        user_id: The user ID (sub claim).
        email: The user email.
        secret: The JWT secret.

    Returns:
        An expired JWT token string.
    """
    return create_valid_token(user_id, email, secret=secret, exp_offset=-3600)


class TestSupabaseJWTMiddleware:
    """Tests for SupabaseJWTMiddleware."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.get_response = Mock(return_value=HttpResponse(status=200))
        self.middleware = SupabaseJWTMiddleware(self.get_response)

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_valid_token_authenticates(self) -> None:
        """Test that a valid JWT token authenticates successfully (IV1)."""
        token = create_valid_token()
        request = create_mock_request(auth_header=f"Bearer {token}")

        response = self.middleware(request)

        assert response.status_code == 200
        assert hasattr(request, "supabase_user_id")
        assert request.supabase_user_id == TEST_USER_ID
        assert request.supabase_email == TEST_EMAIL
        assert request.supabase_role == "authenticated"
        self.get_response.assert_called_once_with(request)

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_expired_token_returns_401(self) -> None:
        """Test that an expired token returns 401 (IV2)."""
        token = create_expired_token()
        request = create_mock_request(auth_header=f"Bearer {token}")

        response = self.middleware(request)

        assert response.status_code == 401
        assert isinstance(response, JsonResponse)
        content = response.content.decode()
        assert "Token expired" in content
        assert "UNAUTHORIZED" in content
        self.get_response.assert_not_called()

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_invalid_token_returns_401(self) -> None:
        """Test that an invalid token returns 401."""
        request = create_mock_request(auth_header="Bearer invalid-token-string")

        response = self.middleware(request)

        assert response.status_code == 401
        assert isinstance(response, JsonResponse)
        content = response.content.decode()
        assert "UNAUTHORIZED" in content
        self.get_response.assert_not_called()

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_wrong_secret_returns_401(self) -> None:
        """Test that a token signed with wrong secret returns 401."""
        token = create_valid_token(secret="wrong-secret")
        request = create_mock_request(auth_header=f"Bearer {token}")

        response = self.middleware(request)

        assert response.status_code == 401
        assert isinstance(response, JsonResponse)
        self.get_response.assert_not_called()

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_missing_token_returns_401(self) -> None:
        """Test that a missing token returns 401."""
        request = create_mock_request()

        response = self.middleware(request)

        assert response.status_code == 401
        assert isinstance(response, JsonResponse)
        content = response.content.decode()
        assert "Token required" in content
        self.get_response.assert_not_called()

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_malformed_auth_header_returns_401(self) -> None:
        """Test that a malformed Authorization header returns 401."""
        request = create_mock_request(auth_header="NotBearer token")

        response = self.middleware(request)

        assert response.status_code == 401
        content = response.content.decode()
        assert "Token required" in content
        self.get_response.assert_not_called()

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_health_endpoint_bypasses_auth(self) -> None:
        """Test that /health endpoint bypasses authentication."""
        request = create_mock_request(path="/health")

        response = self.middleware(request)

        assert response.status_code == 200
        self.get_response.assert_called_once_with(request)

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_internal_api_bypasses_jwt_auth(self) -> None:
        """Test that /api/v1/internal/* endpoints bypass JWT auth."""
        request = create_mock_request(path="/api/v1/internal/sync")

        response = self.middleware(request)

        assert response.status_code == 200
        self.get_response.assert_called_once_with(request)

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_websocket_token_via_query_param(self) -> None:
        """Test that WebSocket connections can pass token via query param."""
        token = create_valid_token()
        request = create_mock_request(
            path="/api/v1/events",
            query_params={"token": token},
        )

        response = self.middleware(request)

        assert response.status_code == 200
        assert hasattr(request, "supabase_user_id")
        assert request.supabase_user_id == TEST_USER_ID
        self.get_response.assert_called_once_with(request)

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_auth_header_takes_precedence_over_query_param(self) -> None:
        """Test that Authorization header takes precedence over query param."""
        header_token = create_valid_token(user_id="header-user")
        query_token = create_valid_token(user_id="query-user")
        request = create_mock_request(
            auth_header=f"Bearer {header_token}",
            query_params={"token": query_token},
        )

        self.middleware(request)

        assert request.supabase_user_id == "header-user"

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_token_without_email_uses_none(self) -> None:
        """Test that tokens without email set email to None."""
        payload = {
            "sub": TEST_USER_ID,
            "role": "authenticated",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
        request = create_mock_request(auth_header=f"Bearer {token}")

        self.middleware(request)

        assert request.supabase_user_id == TEST_USER_ID
        assert request.supabase_email is None
        assert request.supabase_role == "authenticated"

    @override_settings(SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
    def test_token_without_role_uses_default(self) -> None:
        """Test that tokens without role use 'authenticated' default."""
        payload = {
            "sub": TEST_USER_ID,
            "email": TEST_EMAIL,
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
        request = create_mock_request(auth_header=f"Bearer {token}")

        self.middleware(request)

        assert request.supabase_role == "authenticated"


class TestServiceKeyAuthMiddleware:
    """Tests for ServiceKeyAuthMiddleware."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.get_response = Mock(return_value=HttpResponse(status=200))
        self.middleware = ServiceKeyAuthMiddleware(self.get_response)

    @override_settings(CHAT_SERVICE_KEY=TEST_SERVICE_KEY)
    def test_valid_service_key_authenticates(self) -> None:
        """Test that a valid service key authenticates internal requests."""
        request = create_mock_request(
            path="/api/v1/internal/sync",
            auth_header=f"Bearer {TEST_SERVICE_KEY}",
        )

        response = self.middleware(request)

        assert response.status_code == 200
        assert request.is_service_request is True
        self.get_response.assert_called_once_with(request)

    @override_settings(CHAT_SERVICE_KEY=TEST_SERVICE_KEY)
    def test_invalid_service_key_returns_401(self) -> None:
        """Test that an invalid service key returns 401."""
        request = create_mock_request(
            path="/api/v1/internal/sync",
            auth_header="Bearer wrong-key",
        )

        response = self.middleware(request)

        assert response.status_code == 401
        content = response.content.decode()
        assert "Invalid service key" in content
        self.get_response.assert_not_called()

    @override_settings(CHAT_SERVICE_KEY=TEST_SERVICE_KEY)
    def test_missing_service_key_returns_401(self) -> None:
        """Test that a missing service key returns 401."""
        request = create_mock_request(path="/api/v1/internal/sync")

        response = self.middleware(request)

        assert response.status_code == 401
        content = response.content.decode()
        assert "Service key required" in content
        self.get_response.assert_not_called()

    @override_settings(CHAT_SERVICE_KEY=None)
    def test_unconfigured_service_key_returns_500(self) -> None:
        """Test that unconfigured service key returns 500."""
        request = create_mock_request(
            path="/api/v1/internal/sync",
            auth_header="Bearer some-key",
        )

        response = self.middleware(request)

        assert response.status_code == 500
        content = response.content.decode()
        assert "not configured" in content
        self.get_response.assert_not_called()

    @override_settings(CHAT_SERVICE_KEY=TEST_SERVICE_KEY)
    def test_non_internal_path_bypasses_service_auth(self) -> None:
        """Test that non-internal paths bypass service key auth."""
        request = create_mock_request(path="/api/v1/messages")

        response = self.middleware(request)

        assert response.status_code == 200
        self.get_response.assert_called_once_with(request)

    @override_settings(CHAT_SERVICE_KEY=TEST_SERVICE_KEY)
    def test_malformed_auth_header_returns_401(self) -> None:
        """Test that malformed Authorization header returns 401."""
        request = create_mock_request(
            path="/api/v1/internal/sync",
            auth_header="NotBearer key",
        )

        response = self.middleware(request)

        assert response.status_code == 401
        content = response.content.decode()
        assert "Service key required" in content
