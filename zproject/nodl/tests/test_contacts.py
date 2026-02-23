import hashlib
import json
import time
from unittest import mock

import jwt
from django.core.cache import cache
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile
from zerver.models.realms import get_realm

TEST_JWT_SECRET = "test-supabase-jwt-secret-for-testing"
TEST_SUPABASE_URL = "https://testproject.supabase.co"
TEST_SERVICE_ROLE_KEY = "test-service-role-key"

NODL_SETTINGS = {
    "NODL_SUPABASE_JWT_SECRET": TEST_JWT_SECRET,
    "NODL_SUPABASE_URL": TEST_SUPABASE_URL,
    "NODL_SUPABASE_SERVICE_ROLE_KEY": TEST_SERVICE_ROLE_KEY,
    "NODL_CONTACTS_MATCH_LIMIT": 500,
}

CONTACTS_MATCH_URL = "/nodl/contacts/match"
AUTH_BRIDGE_URL = "/nodl/auth/bridge"


def make_jwt(
    payload: dict | None = None,
    secret: str = TEST_JWT_SECRET,
    **overrides: object,
) -> str:
    """Create a signed JWT for testing."""
    now = int(time.time())
    default_payload = {
        "sub": "test-supabase-uuid",
        "email": "testuser@nodl.local",
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
    return jwt.encode(default_payload, secret, algorithm="HS256")


def phone_hash(phone: str) -> str:
    """Compute SHA-256 hash of an E.164 phone number."""
    return hashlib.sha256(phone.encode("utf-8")).hexdigest()


def make_supabase_users(users: list[dict]) -> list[dict]:
    """Build a list of mock Supabase user dicts for get_supabase_users_with_phones."""
    result = []
    for u in users:
        result.append(
            {
                "id": u.get("id", "sb-uuid"),
                "phone": u["phone"],
                "email": u.get("email", ""),
            }
        )
    return result


def _create_zulip_user_via_bridge(
    client: object,
    email: str,
    phone: str,
    sub: str,
) -> UserProfile:
    """Helper: create a Zulip user through the auth bridge endpoint."""
    token = make_jwt(email=email, phone=phone, sub=sub)
    # Use getattr to call client_post since client is actually ZulipTestCase's self
    result = client.client_post(  # type: ignore[attr-defined]
        AUTH_BRIDGE_URL,
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert result.status_code == 200
    realm = get_realm("zulip")
    return UserProfile.objects.get(delivery_email=email, realm=realm)


@override_settings(**NODL_SETTINGS)
class ContactsMatchSuccessTest(ZulipTestCase):
    """Test: valid request with matching hashes -> 200 + correct matches (AC #1)."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @mock.patch("zproject.nodl.contacts.get_supabase_users_with_phones")
    def test_valid_request_with_matching_hashes(self, mock_get_users: mock.MagicMock) -> None:
        """AC #1: Submit hashes, get matched user_id + display_name."""
        # Create test users via auth bridge
        user_alice = _create_zulip_user_via_bridge(
            self, "+15551111111@nodl.local", "+15551111111", "alice-uuid"
        )
        user_bob = _create_zulip_user_via_bridge(
            self, "+15552222222@nodl.local", "+15552222222", "bob-uuid"
        )

        # Mock Supabase returning these users
        mock_get_users.return_value = make_supabase_users(
            [
                {"id": "alice-uuid", "phone": "+15551111111"},
                {"id": "bob-uuid", "phone": "+15552222222"},
            ]
        )

        # Create a requesting user (different from matched users)
        requesting_user = _create_zulip_user_via_bridge(
            self, "requester@nodl.local", "+15559999999", "requester-uuid"
        )

        alice_hash = phone_hash("+15551111111")
        bob_hash = phone_hash("+15552222222")

        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": [alice_hash, bob_hash]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(requesting_user),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["msg"], "")
        self.assertEqual(len(data["matches"]), 2)

        matched_ids = {m["user_id"] for m in data["matches"]}
        self.assertIn(user_alice.id, matched_ids)
        self.assertIn(user_bob.id, matched_ids)

        for match in data["matches"]:
            self.assertIn("user_id", match)
            self.assertIn("display_name", match)
            self.assertIn("phone_hash", match)


@override_settings(**NODL_SETTINGS)
class ContactsMatchEmptyTest(ZulipTestCase):
    """Test: no matching hashes -> 200 + empty matches (AC #2)."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @mock.patch("zproject.nodl.contacts.get_supabase_users_with_phones")
    def test_no_matching_hashes(self, mock_get_users: mock.MagicMock) -> None:
        """AC #2: Non-matching hashes return empty matches array."""
        mock_get_users.return_value = []

        requesting_user = _create_zulip_user_via_bridge(
            self, "nomatch@nodl.local", "+15550000000", "nomatch-uuid"
        )

        fake_hash = "a" * 64
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": [fake_hash]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(requesting_user),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["msg"], "")
        self.assertEqual(data["matches"], [])


@override_settings(**NODL_SETTINGS)
class ContactsMatchMixedTest(ZulipTestCase):
    """Test: mixed hashes (some match, some don't) -> only matches returned (AC #1, #2)."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @mock.patch("zproject.nodl.contacts.get_supabase_users_with_phones")
    def test_mixed_hashes_only_matches_returned(self, mock_get_users: mock.MagicMock) -> None:
        user_alice = _create_zulip_user_via_bridge(
            self, "+15551111111@nodl.local", "+15551111111", "mixed-alice-uuid"
        )
        mock_get_users.return_value = make_supabase_users(
            [{"id": "mixed-alice-uuid", "phone": "+15551111111"}]
        )

        requesting_user = _create_zulip_user_via_bridge(
            self, "mixed-req@nodl.local", "+15558888888", "mixed-req-uuid"
        )

        alice_hash = phone_hash("+15551111111")
        fake_hash = "b" * 64

        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": [alice_hash, fake_hash]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(requesting_user),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(len(data["matches"]), 1)
        self.assertEqual(data["matches"][0]["user_id"], user_alice.id)


@override_settings(**NODL_SETTINGS)
class ContactsMatchUnauthenticatedTest(ZulipTestCase):
    """Test: unauthenticated request -> 401 (AC #3)."""

    def test_no_auth_header_returns_401(self) -> None:
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": ["a" * 64]}),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 401)

    def test_invalid_credentials_returns_401(self) -> None:
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": ["a" * 64]}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Basic aW52YWxpZDppbnZhbGlk",  # invalid:invalid
        )
        self.assertEqual(result.status_code, 401)


@override_settings(**NODL_SETTINGS)
class ContactsMatchBatchLimitTest(ZulipTestCase):
    """Test: >500 hashes -> 400 (AC #5)."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    def test_too_many_hashes_returns_400(self) -> None:
        requesting_user = _create_zulip_user_via_bridge(
            self, "batch-limit@nodl.local", "+15557777777", "batch-uuid"
        )
        hashes = [f"{i:064x}" for i in range(501)]
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": hashes}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(requesting_user),
        )
        self.assertEqual(result.status_code, 400)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["msg"], "Too many hashes. Maximum 500 per request.")
        self.assertEqual(data["code"], "BAD_REQUEST")


@override_settings(**NODL_SETTINGS)
class ContactsMatchInvalidFormatTest(ZulipTestCase):
    """Test: invalid hash format -> 400 (AC #6)."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    def _get_user(self) -> UserProfile:
        return _create_zulip_user_via_bridge(
            self, "fmt-test@nodl.local", "+15556666666", "fmt-uuid"
        )

    def test_wrong_length_hash_returns_400(self) -> None:
        user = self._get_user()
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": ["abc123"]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(user),
        )
        self.assertEqual(result.status_code, 400)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["code"], "BAD_REQUEST")

    def test_uppercase_hex_returns_400(self) -> None:
        user = self._get_user()
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": ["A" * 64]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(user),
        )
        self.assertEqual(result.status_code, 400)

    def test_non_hex_chars_returns_400(self) -> None:
        user = self._get_user()
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": ["g" * 64]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(user),
        )
        self.assertEqual(result.status_code, 400)

    def test_non_list_phone_hashes_returns_400(self) -> None:
        user = self._get_user()
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": "not-a-list"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(user),
        )
        self.assertEqual(result.status_code, 400)

    def test_non_string_entries_returns_400(self) -> None:
        user = self._get_user()
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": [123, 456]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(user),
        )
        self.assertEqual(result.status_code, 400)

    def test_missing_phone_hashes_key_returns_400(self) -> None:
        user = self._get_user()
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"wrong_key": []}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(user),
        )
        self.assertEqual(result.status_code, 400)


@override_settings(**NODL_SETTINGS)
class ContactsMatchEmptyListTest(ZulipTestCase):
    """Test: empty phone_hashes list -> 200 + empty matches."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @mock.patch("zproject.nodl.contacts.get_supabase_users_with_phones")
    def test_empty_list_returns_200(self, mock_get_users: mock.MagicMock) -> None:
        mock_get_users.return_value = []
        user = _create_zulip_user_via_bridge(
            self, "empty-list@nodl.local", "+15554444444", "empty-uuid"
        )
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": []}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(user),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["matches"], [])


@override_settings(**NODL_SETTINGS)
class ContactsMatchMalformedBodyTest(ZulipTestCase):
    """Test: malformed JSON body -> 400 (AC #6)."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    def test_malformed_json_returns_400(self) -> None:
        user = _create_zulip_user_via_bridge(
            self, "malformed@nodl.local", "+15553333333", "malformed-uuid"
        )
        result = self.client_post(
            CONTACTS_MATCH_URL,
            "not valid json{",
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(user),
        )
        self.assertEqual(result.status_code, 400)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["code"], "BAD_REQUEST")


@override_settings(**NODL_SETTINGS)
class ContactsMatchSelfExclusionTest(ZulipTestCase):
    """Test: requesting user is excluded from results."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @mock.patch("zproject.nodl.contacts.get_supabase_users_with_phones")
    def test_requesting_user_excluded(self, mock_get_users: mock.MagicMock) -> None:
        # The requesting user is also in Supabase
        requesting_user = _create_zulip_user_via_bridge(
            self, "+15559999999@nodl.local", "+15559999999", "self-uuid"
        )
        mock_get_users.return_value = make_supabase_users(
            [{"id": "self-uuid", "phone": "+15559999999"}]
        )

        self_hash = phone_hash("+15559999999")
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": [self_hash]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(requesting_user),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        # Should NOT include self in matches
        self.assertEqual(data["matches"], [])


@override_settings(**NODL_SETTINGS)
class ContactsMatchDualRegistrationTest(ZulipTestCase):
    """Test: only users in both Supabase AND Zulip are returned (AC #4)."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @mock.patch("zproject.nodl.contacts.get_supabase_users_with_phones")
    def test_supabase_only_users_not_returned(self, mock_get_users: mock.MagicMock) -> None:
        """Users in Supabase but not in Zulip should not appear in results."""
        # Only create one user in Zulip
        user_alice = _create_zulip_user_via_bridge(
            self, "+15551111111@nodl.local", "+15551111111", "dual-alice-uuid"
        )

        # Supabase has two users, but only Alice exists in Zulip
        mock_get_users.return_value = make_supabase_users(
            [
                {"id": "dual-alice-uuid", "phone": "+15551111111"},
                {"id": "dual-bob-uuid", "phone": "+15553333333"},  # No Zulip user
            ]
        )

        requesting_user = _create_zulip_user_via_bridge(
            self, "dual-req@nodl.local", "+15558888888", "dual-req-uuid"
        )

        alice_hash = phone_hash("+15551111111")
        bob_hash = phone_hash("+15553333333")

        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": [alice_hash, bob_hash]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(requesting_user),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(len(data["matches"]), 1)
        self.assertEqual(data["matches"][0]["user_id"], user_alice.id)


@override_settings(**NODL_SETTINGS)
class ContactsMatchResponseFormatTest(ZulipTestCase):
    """Test: response format matches Zulip's structure exactly (AC #1, #2)."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @mock.patch("zproject.nodl.contacts.get_supabase_users_with_phones")
    def test_success_response_format(self, mock_get_users: mock.MagicMock) -> None:
        mock_get_users.return_value = []
        user = _create_zulip_user_via_bridge(
            self, "format@nodl.local", "+15555555555", "format-uuid"
        )
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": []}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(user),
        )
        data = result.json()
        # Verify exact top-level keys
        self.assertIn("result", data)
        self.assertIn("msg", data)
        self.assertIn("matches", data)
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["msg"], "")
        self.assertIsInstance(data["matches"], list)

    @mock.patch("zproject.nodl.contacts.get_supabase_users_with_phones")
    def test_match_entry_format(self, mock_get_users: mock.MagicMock) -> None:
        _create_zulip_user_via_bridge(
            self, "+15551111111@nodl.local", "+15551111111", "entry-alice-uuid"
        )
        mock_get_users.return_value = make_supabase_users(
            [{"id": "entry-alice-uuid", "phone": "+15551111111"}]
        )
        requesting_user = _create_zulip_user_via_bridge(
            self, "entry-req@nodl.local", "+15558888888", "entry-req-uuid"
        )

        alice_hash = phone_hash("+15551111111")
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": [alice_hash]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(requesting_user),
        )
        data = result.json()
        self.assertEqual(len(data["matches"]), 1)
        match = data["matches"][0]
        self.assertIn("user_id", match)
        self.assertIn("display_name", match)
        self.assertIn("phone_hash", match)
        self.assertIsInstance(match["user_id"], int)
        self.assertIsInstance(match["display_name"], str)
        self.assertIsInstance(match["phone_hash"], str)
        self.assertEqual(match["phone_hash"], alice_hash)


@override_settings(**NODL_SETTINGS)
class ContactsMatchRateLimitTest(ZulipTestCase):
    """Test: rate limiting -> 429 after exceeding limit (AC from Task 4.7)."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @mock.patch("zproject.nodl.contacts.get_supabase_users_with_phones")
    def test_rate_limit_exceeded_returns_429(self, mock_get_users: mock.MagicMock) -> None:
        mock_get_users.return_value = []
        user = _create_zulip_user_via_bridge(
            self, "ratelimit@nodl.local", "+15552222222", "ratelimit-uuid"
        )

        # Make 10 requests (should all succeed)
        for i in range(10):
            result = self.client_post(
                CONTACTS_MATCH_URL,
                json.dumps({"phone_hashes": []}),
                content_type="application/json",
                HTTP_AUTHORIZATION=self.encode_user(user),
            )
            self.assertEqual(result.status_code, 200, f"Request {i+1} failed")

        # 11th request should be rate limited
        result = self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": []}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(user),
        )
        self.assertEqual(result.status_code, 429)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertEqual(data["code"], "RATE_LIMIT_HIT")
        self.assertIn("Retry-After", result.headers)


@override_settings(**NODL_SETTINGS)
class ContactsMatchSupabaseMockTest(ZulipTestCase):
    """Test: Supabase Admin API is mocked, never called for real (AC #5.14)."""

    def setUp(self) -> None:
        super().setUp()
        cache.clear()

    @mock.patch("zproject.nodl.contacts.get_supabase_users_with_phones")
    def test_supabase_is_mocked(self, mock_get_users: mock.MagicMock) -> None:
        mock_get_users.return_value = []
        user = _create_zulip_user_via_bridge(
            self, "mock-test@nodl.local", "+15553333333", "mock-uuid"
        )
        self.client_post(
            CONTACTS_MATCH_URL,
            json.dumps({"phone_hashes": ["a" * 64]}),
            content_type="application/json",
            HTTP_AUTHORIZATION=self.encode_user(user),
        )
        mock_get_users.assert_called_once()
