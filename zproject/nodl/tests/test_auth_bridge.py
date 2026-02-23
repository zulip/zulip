import json
import time
from unittest import mock

import jwt
from django.core.cache import cache
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile
from zerver.models.realms import get_realm

from zproject.nodl.actions import mask_email

TEST_JWT_SECRET = "test-supabase-jwt-secret-for-testing"
TEST_SUPABASE_URL = "https://testproject.supabase.co"
TEST_SERVICE_ROLE_KEY = "test-service-role-key"


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


def make_supabase_user(
    user_id: str = "test-supabase-uuid-1234",
    email: str | None = None,
    phone: str = "+15551234567",
) -> dict:
    """Helper to create a mock Supabase user response."""
    identities = []
    if email:
        identities.append(
            {
                "provider": "email",
                "identity_data": {"email": email},
            }
        )
    identities.append(
        {
            "provider": "phone",
            "identity_data": {"phone": phone},
        }
    )
    return {
        "id": user_id,
        "email": email or "",
        "phone": phone,
        "identities": identities,
    }


AUTH_BRIDGE_URL = "/nodl/auth/bridge"

NODL_SETTINGS = {
    "NODL_SUPABASE_JWT_SECRET": TEST_JWT_SECRET,
    "NODL_SUPABASE_URL": TEST_SUPABASE_URL,
    "NODL_SUPABASE_SERVICE_ROLE_KEY": TEST_SERVICE_ROLE_KEY,
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
        user = UserProfile.objects.get(
            delivery_email="newuser-bridge@nodl.local", realm=realm
        )
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

    def test_concurrent_requests_no_duplicates(self) -> None:
        email = "concurrent-bridge@nodl.local"
        token = make_jwt(email=email, sub="concurrent-uuid")
        realm = get_realm("zulip")

        result1 = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result1.status_code, 200)

        result2 = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result2.status_code, 200)

        data1 = self.assert_json_success(result1)
        data2 = self.assert_json_success(result2)
        self.assertEqual(data1["user_id"], data2["user_id"])

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


# ======================================================================
# Story 1.4: Account Linking Tests
# ======================================================================


class EmailMaskingTest(ZulipTestCase):
    """Test email masking utility (Task 1.5)"""

    def test_standard_email(self) -> None:
        self.assertEqual(mask_email("marcus@example.com"), "m***@example.com")

    def test_short_local_part(self) -> None:
        self.assertEqual(mask_email("a@b.com"), "a***@b.com")

    def test_single_char_local(self) -> None:
        self.assertEqual(mask_email("x@domain.com"), "x***@domain.com")

    def test_empty_local_part(self) -> None:
        self.assertEqual(mask_email("@domain.com"), "*@domain.com")

    def test_no_at_symbol(self) -> None:
        self.assertEqual(mask_email("not-an-email"), "not-an-email")

    def test_long_email(self) -> None:
        self.assertEqual(
            mask_email("longusername@company.co.uk"), "l***@company.co.uk"
        )


@override_settings(**NODL_SETTINGS)
class AuthBridgeAccountDetectionTest(ZulipTestCase):
    """Test account linking detection (Task 1.1-1.3, AC #1)"""

    def _create_existing_email_user(self, email: str) -> UserProfile:
        """Helper: create a Zulip user with a given email."""
        token = make_jwt(email=email, sub="existing-email-user-uuid")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 200)
        realm = get_realm("zulip")
        return UserProfile.objects.get(delivery_email=email, realm=realm)

    @mock.patch("zproject.nodl.actions.check_duplicate_phone")
    @mock.patch("zproject.nodl.actions.get_supabase_user_by_id")
    def test_linking_available_when_email_identity_matches(
        self,
        mock_get_user: mock.MagicMock,
        mock_check_dup: mock.MagicMock,
    ) -> None:
        """When phone user has email identity matching a Zulip user, return linking_available."""
        existing_user = self._create_existing_email_user("marcus@example.com")
        mock_check_dup.return_value = False
        mock_get_user.return_value = make_supabase_user(
            user_id="phone-user-uuid",
            email="marcus@example.com",
            phone="+15557777777",
        )

        token = make_jwt(
            email="", phone="+15557777777", sub="phone-user-uuid"
        )
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertTrue(data["linking_available"])
        self.assertEqual(data["existing_email_masked"], "m***@example.com")
        self.assertEqual(data["existing_user_id"], existing_user.id)
        # Should NOT contain api_key (linking not confirmed yet)
        self.assertNotIn("api_key", data)

    @mock.patch("zproject.nodl.actions.check_duplicate_phone")
    @mock.patch("zproject.nodl.actions.get_supabase_user_by_id")
    def test_no_linking_when_no_email_identity(
        self,
        mock_get_user: mock.MagicMock,
        mock_check_dup: mock.MagicMock,
    ) -> None:
        """Phone-only Supabase user with no email identity proceeds normally."""
        mock_check_dup.return_value = False
        mock_get_user.return_value = make_supabase_user(
            user_id="phone-only-uuid",
            email=None,
            phone="+15556666666",
        )

        token = make_jwt(email="", phone="+15556666666", sub="phone-only-uuid")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        # Normal flow: should have api_key, no linking_available
        self.assertIn("api_key", data)
        self.assertNotIn("linking_available", data)

    @mock.patch("zproject.nodl.actions.check_duplicate_phone")
    @mock.patch("zproject.nodl.actions.get_supabase_user_by_id")
    def test_no_linking_when_zulip_user_not_found(
        self,
        mock_get_user: mock.MagicMock,
        mock_check_dup: mock.MagicMock,
    ) -> None:
        """Email identity exists in Supabase but no Zulip user with that email."""
        mock_check_dup.return_value = False
        mock_get_user.return_value = make_supabase_user(
            user_id="orphan-uuid",
            email="nonexistent@example.com",
            phone="+15554444444",
        )

        token = make_jwt(email="", phone="+15554444444", sub="orphan-uuid")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        # Should proceed with normal flow (no match)
        self.assertIn("api_key", data)
        self.assertNotIn("linking_available", data)


@override_settings(**NODL_SETTINGS)
class AuthBridgeDuplicatePhoneTest(ZulipTestCase):
    """Test duplicate phone detection (Task 1.4, AC #4)"""

    @mock.patch("zproject.nodl.views.auth_bridge.check_duplicate_phone")
    def test_duplicate_phone_returns_flag(
        self, mock_check_dup: mock.MagicMock
    ) -> None:
        """When phone is already registered to another user, return duplicate_phone."""
        mock_check_dup.return_value = True

        token = make_jwt(email="", phone="+15553333333", sub="new-phone-uuid")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertTrue(data["duplicate_phone"])
        self.assertNotIn("api_key", data)

    @mock.patch("zproject.nodl.views.auth_bridge.check_duplicate_phone")
    def test_no_duplicate_proceeds_normally(
        self, mock_check_dup: mock.MagicMock
    ) -> None:
        """When phone is not a duplicate, proceed with normal flow."""
        mock_check_dup.return_value = False

        token = make_jwt(
            email="unique-phone@nodl.local", phone="+15552222222", sub="unique-uuid"
        )
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertNotIn("duplicate_phone", data)
        self.assertIn("api_key", data)


@override_settings(**NODL_SETTINGS)
class AuthBridgeLinkConfirmationTest(ZulipTestCase):
    """Test link confirmation endpoint (Task 2.1-2.3, AC #2, #3)"""

    def _create_existing_email_user(self, email: str) -> UserProfile:
        """Helper: create a Zulip user with a given email."""
        token = make_jwt(email=email, sub="existing-email-user-uuid-link")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 200)
        realm = get_realm("zulip")
        return UserProfile.objects.get(delivery_email=email, realm=realm)

    @mock.patch("zproject.nodl.views.auth_bridge.link_phone_to_existing_user")
    @mock.patch("zproject.nodl.views.auth_bridge.get_supabase_user_by_id")
    def test_link_action_link_returns_existing_user(
        self,
        mock_get_user: mock.MagicMock,
        mock_link_phone: mock.MagicMock,
    ) -> None:
        """link_action='link' returns existing Zulip user's API key."""
        existing_user = self._create_existing_email_user("link-target@example.com")
        mock_get_user.return_value = make_supabase_user(
            user_id="phone-linker-uuid",
            email="link-target@example.com",
            phone="+15551111111",
        )
        mock_link_phone.return_value = True

        token = make_jwt(
            email="", phone="+15551111111", sub="phone-linker-uuid"
        )
        result = self.client_post(
            AUTH_BRIDGE_URL,
            json.dumps({"link_action": "link"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["api_key"], existing_user.api_key)
        self.assertEqual(data["user_id"], existing_user.id)
        self.assertEqual(data["email"], "link-target@example.com")
        mock_link_phone.assert_called_once()

    @mock.patch("zproject.nodl.views.auth_bridge.get_supabase_user_by_id")
    def test_link_action_create_new_provisions_user(
        self,
        mock_get_user: mock.MagicMock,
    ) -> None:
        """link_action='create_new' provisions a new Zulip account."""
        mock_get_user.return_value = None  # Not needed for create_new

        token = make_jwt(
            email="", phone="+15550000000", sub="create-new-uuid"
        )
        result = self.client_post(
            AUTH_BRIDGE_URL,
            json.dumps({"link_action": "create_new"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertIn("api_key", data)
        self.assertEqual(data["email"], "+15550000000@nodl.local")

    def test_invalid_link_action_returns_400(self) -> None:
        """Invalid link_action value returns 400."""
        token = make_jwt(email="", phone="+15559876543", sub="invalid-action-uuid")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            json.dumps({"link_action": "invalid"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 400)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["msg"], "Invalid link_action")

    @mock.patch("zproject.nodl.views.auth_bridge.link_phone_to_existing_user")
    @mock.patch("zproject.nodl.views.auth_bridge.get_supabase_user_by_id")
    def test_link_fails_when_supabase_api_fails(
        self,
        mock_get_user: mock.MagicMock,
        mock_link_phone: mock.MagicMock,
    ) -> None:
        """When Supabase admin API fails during linking, return error."""
        mock_get_user.return_value = None  # Simulates Supabase API failure

        token = make_jwt(email="", phone="+15558765432", sub="fail-link-uuid")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            json.dumps({"link_action": "link"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 500)
        data = result.json()
        self.assertEqual(data["result"], "error")
        mock_link_phone.assert_not_called()


@override_settings(**NODL_SETTINGS)
class AuthBridgeLinkRateLimitTest(ZulipTestCase):
    """Test link attempt rate limiting (Task 2.4)"""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @mock.patch("zproject.nodl.views.auth_bridge.get_supabase_user_by_id")
    def test_link_rate_limit_exceeded(
        self, mock_get_user: mock.MagicMock
    ) -> None:
        """After 5 link attempts, return 429."""
        mock_get_user.return_value = make_supabase_user(
            user_id="rate-limit-uuid",
            email="ratelimit@example.com",
            phone="+15551112222",
        )

        token = make_jwt(
            email="", phone="+15551112222", sub="rate-limit-uuid"
        )

        # Make 5 link attempts (all should succeed or fail normally)
        for _i in range(5):
            self.client_post(
                AUTH_BRIDGE_URL,
                json.dumps({"link_action": "link"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )

        # 6th attempt should be rate limited
        result = self.client_post(
            AUTH_BRIDGE_URL,
            json.dumps({"link_action": "link"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(result.status_code, 429)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["code"], "RATE_LIMIT_HIT")
        self.assertIn("Retry-After", result.headers)
