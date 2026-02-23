import time
import unittest
from unittest import mock

import jwt
from django.core.cache import cache
from django.db import IntegrityError
from django.test import override_settings

from nodl.auth.middleware import SupabaseJWTMiddleware
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile
from zerver.models.realms import get_realm

TEST_JWT_SECRET = "test-supabase-jwt-secret-for-testing"
TEST_SUPABASE_URL = "https://testproject.supabase.co"


def make_jwt(
    payload: dict | None = None,
    secret: str = TEST_JWT_SECRET,
    algorithm: str = "HS256",
    **overrides: object,
) -> str:
    """Helper to create a signed JWT token for testing."""
    now = int(time.time())
    default_payload = {
        "sub": "test-supabase-uuid-1234",
        "email": "bridge-test@example.com",
        "phone": "+15551234567",
        "aud": "authenticated",
        "iss": f"{TEST_SUPABASE_URL}/auth/v1",
        "role": "authenticated",
        "exp": now + 3600,
        "iat": now,
    }
    if payload is not None:
        default_payload.update(payload)
    default_payload.update(overrides)
    return jwt.encode(default_payload, secret, algorithm=algorithm)


AUTH_BRIDGE_URL = "/nodl/auth/bridge"

NODL_SETTINGS = {
    "NODL_SUPABASE_JWT_SECRET": TEST_JWT_SECRET,
    "NODL_SUPABASE_URL": TEST_SUPABASE_URL,
}


@override_settings(**NODL_SETTINGS)
class AuthBridgeNewUserTest(ZulipTestCase):
    """Test: valid JWT for new user -> 200 + user created + API key returned (AC #1)"""

    def test_valid_jwt_new_user_creates_account(self) -> None:
        token = make_jwt(email="newuser-bridge@nodl.local", phone="+15559999999")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 200)
        data = self.assert_json_success(result)
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["msg"], "")
        self.assertIn("api_key", data)
        self.assertIn("user_id", data)
        self.assertEqual(data["email"], "newuser-bridge@nodl.local")

        # Verify user actually exists in DB
        realm = get_realm("zulip")
        user = UserProfile.objects.get(delivery_email="newuser-bridge@nodl.local", realm=realm)
        self.assertTrue(user.is_active)
        self.assertEqual(data["user_id"], user.id)
        self.assertEqual(data["api_key"], user.api_key)

    def test_phone_only_user_derives_email(self) -> None:
        token = make_jwt(email="", phone="+15558888888", sub="phone-only-uuid")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 200)
        data = self.assert_json_success(result)
        self.assertEqual(data["email"], "+15558888888@nodl.local")


@override_settings(**NODL_SETTINGS)
class AuthBridgeExistingUserTest(ZulipTestCase):
    """Test: valid JWT for existing user -> 200 + same user (AC #2)"""

    def test_existing_user_returns_same_api_key(self) -> None:
        email = "existing-bridge@nodl.local"
        # First request creates the user
        token = make_jwt(email=email, sub="existing-uuid")
        result1 = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result1.status_code, 200)
        data1 = self.assert_json_success(result1)

        # Second request returns the same user
        result2 = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result2.status_code, 200)
        data2 = self.assert_json_success(result2)

        self.assertEqual(data1["user_id"], data2["user_id"])
        self.assertEqual(data1["api_key"], data2["api_key"])
        self.assertEqual(data1["email"], data2["email"])

        # Verify only one user exists
        realm = get_realm("zulip")
        count = UserProfile.objects.filter(delivery_email=email, realm=realm).count()
        self.assertEqual(count, 1)


@override_settings(**NODL_SETTINGS)
class AuthBridgeInvalidJWTTest(ZulipTestCase):
    """Test error cases for invalid JWTs (AC #3)"""

    def test_expired_jwt_returns_401(self) -> None:
        token = make_jwt(exp=int(time.time()) - 3600)
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 401)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["msg"], "Invalid JWT token")
        self.assertEqual(data["code"], "UNAUTHORIZED")

    def test_malformed_jwt_returns_401(self) -> None:
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION="Bearer not.a.valid.jwt",
        )
        self.assertEqual(result.status_code, 401)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["code"], "UNAUTHORIZED")

    def test_missing_auth_header_returns_401(self) -> None:
        result = self.client_post(AUTH_BRIDGE_URL)
        self.assertEqual(result.status_code, 401)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["code"], "UNAUTHORIZED")

    def test_wrong_audience_returns_401(self) -> None:
        token = make_jwt(aud="wrong-audience")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 401)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["code"], "UNAUTHORIZED")

    def test_wrong_secret_returns_401(self) -> None:
        token = make_jwt(secret="wrong-secret")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 401)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["code"], "UNAUTHORIZED")

    def test_missing_exp_claim_returns_401(self) -> None:
        """Tokens without exp claim must be rejected (Finding 3)."""
        now = int(time.time())
        payload = {
            "sub": "no-exp-uuid",
            "email": "noexp@nodl.local",
            "aud": "authenticated",
            "iss": f"{TEST_SUPABASE_URL}/auth/v1",
            "iat": now,
        }
        # Encode without exp
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 401)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["code"], "UNAUTHORIZED")

    def test_get_method_not_allowed(self) -> None:
        result = self.client_get(AUTH_BRIDGE_URL)
        self.assertEqual(result.status_code, 405)


@override_settings(**NODL_SETTINGS)
class AuthBridgeRateLimitTest(ZulipTestCase):
    """Test: rate limiting -> 429 after 10+ rapid requests (AC #5)"""

    def test_rate_limit_exceeded_returns_429(self) -> None:
        token = make_jwt()
        # Make 10 requests (should all succeed)
        for i in range(10):
            result = self.client_post(
                AUTH_BRIDGE_URL,
                HTTP_AUTHORIZATION=f"Bearer {token}",
                REMOTE_ADDR="192.0.2.100",
            )
            self.assertEqual(result.status_code, 200, f"Request {i+1} failed")

        # 11th request should be rate limited
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
            REMOTE_ADDR="192.0.2.100",
        )
        self.assertEqual(result.status_code, 429)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["msg"], "Rate limit exceeded")
        self.assertEqual(data["code"], "RATE_LIMIT_HIT")
        self.assertIn("Retry-After", result.headers)

    def test_different_ips_not_rate_limited(self) -> None:
        token = make_jwt()
        # Requests from different IPs should not interfere
        for i in range(5):
            result = self.client_post(
                AUTH_BRIDGE_URL,
                HTTP_AUTHORIZATION=f"Bearer {token}",
                REMOTE_ADDR=f"192.0.2.{i+1}",
            )
            self.assertEqual(result.status_code, 200)


@override_settings(**NODL_SETTINGS)
class AuthBridgeConcurrencyTest(ZulipTestCase):
    """Test: concurrent requests for same user don't create duplicates (AC #1, #2)"""

    def test_integrity_error_fallback_returns_existing_user(self) -> None:
        """Simulate race condition: do_create_user raises IntegrityError,
        fallback lookup returns existing user."""
        email = "concurrent-bridge@nodl.local"
        token = make_jwt(email=email, sub="concurrent-uuid")

        # First request creates the user normally
        result1 = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result1.status_code, 200)
        data1 = self.assert_json_success(result1)

        # Second request: mock do_create_user to raise IntegrityError
        # simulating a race where two requests pass the .get() check simultaneously
        with mock.patch(
            "zproject.nodl.actions.do_create_user",
            side_effect=IntegrityError(
                "duplicate key value violates unique constraint on delivery_email"
            ),
        ):
            # Also mock the initial .get() to raise DoesNotExist so we enter the create path
            original_get = UserProfile.objects.get

            def mock_get_first_call(*args: object, **kwargs: object) -> UserProfile:
                """First call raises DoesNotExist, triggering create path."""
                if "delivery_email__iexact" in kwargs:
                    # First lookup (before create) raises DoesNotExist
                    mock_get_first_call._called += 1  # type: ignore[attr-defined]
                    if mock_get_first_call._called == 1:  # type: ignore[attr-defined]
                        raise UserProfile.DoesNotExist
                return original_get(*args, **kwargs)

            mock_get_first_call._called = 0  # type: ignore[attr-defined]

            with mock.patch.object(
                UserProfile.objects, "get", side_effect=mock_get_first_call
            ):
                result2 = self.client_post(
                    AUTH_BRIDGE_URL,
                    HTTP_AUTHORIZATION=f"Bearer {token}",
                )

        self.assertEqual(result2.status_code, 200)
        data2 = self.assert_json_success(result2)

        # Both requests return the same user
        self.assertEqual(data1["user_id"], data2["user_id"])
        self.assertEqual(data1["email"], data2["email"])

        # Only one user exists in the database
        realm = get_realm("zulip")
        count = UserProfile.objects.filter(delivery_email=email, realm=realm).count()
        self.assertEqual(count, 1)


@override_settings(**NODL_SETTINGS)
class AuthBridgeResponseFormatTest(ZulipTestCase):
    """Test: response format matches Zulip's structure (AC #1)"""

    def test_success_response_format(self) -> None:
        token = make_jwt(email="format-test@nodl.local", sub="format-uuid")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        data = result.json()
        # Verify exact keys present
        self.assertIn("result", data)
        self.assertIn("msg", data)
        self.assertIn("api_key", data)
        self.assertIn("user_id", data)
        self.assertIn("email", data)
        # Verify types
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["msg"], "")
        self.assertIsInstance(data["api_key"], str)
        self.assertIsInstance(data["user_id"], int)
        self.assertIsInstance(data["email"], str)

    def test_error_response_format(self) -> None:
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION="Bearer invalid",
        )
        data = result.json()
        self.assertIn("result", data)
        self.assertIn("msg", data)
        self.assertIn("code", data)
        self.assertEqual(data["result"], "error")
        self.assertIsInstance(data["msg"], str)
        self.assertIsInstance(data["code"], str)


class MiddlewareExemptPathTest(unittest.TestCase):
    """Test _is_exempt correctly distinguishes exact vs prefix paths."""

    def setUp(self) -> None:
        self.middleware = SupabaseJWTMiddleware(lambda r: None)

    def test_auth_bridge_exact_match_is_exempt(self) -> None:
        self.assertTrue(self.middleware._is_exempt("/nodl/auth/bridge"))

    def test_auth_bridge_suffix_is_not_exempt(self) -> None:
        self.assertFalse(self.middleware._is_exempt("/nodl/auth/bridgeevil"))

    def test_user_uploads_subpath_is_exempt(self) -> None:
        self.assertTrue(self.middleware._is_exempt("/user_uploads/foo/bar"))

    def test_thumbnail_subpath_is_exempt(self) -> None:
        self.assertTrue(self.middleware._is_exempt("/thumbnail/300x200"))

    def test_health_exact_is_exempt(self) -> None:
        self.assertTrue(self.middleware._is_exempt("/health"))

    def test_unknown_path_is_not_exempt(self) -> None:
        self.assertFalse(self.middleware._is_exempt("/api/v1/messages"))


@override_settings(**NODL_SETTINGS)
class AuthBridgeRateLimitFallbackTest(ZulipTestCase):
    """Test rate limiting still works when cache.incr raises ValueError."""

    def test_rate_limit_with_incr_fallback(self) -> None:
        token = make_jwt(email="fallback-rl@nodl.local", sub="fallback-rl-uuid")
        cache.clear()

        with mock.patch.object(
            cache, "incr", side_effect=ValueError("incr not supported")
        ):
            for i in range(10):
                result = self.client_post(
                    AUTH_BRIDGE_URL,
                    HTTP_AUTHORIZATION=f"Bearer {token}",
                    REMOTE_ADDR="192.0.2.200",
                )
                self.assertEqual(
                    result.status_code, 200, f"Request {i+1} failed"
                )

            # 11th request should be rate limited even with fallback
            result = self.client_post(
                AUTH_BRIDGE_URL,
                HTTP_AUTHORIZATION=f"Bearer {token}",
                REMOTE_ADDR="192.0.2.200",
            )
            self.assertEqual(result.status_code, 429)
