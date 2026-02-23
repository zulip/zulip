import base64
import time
from datetime import timedelta
from unittest import mock

import jwt
from django.contrib.auth.hashers import check_password
from django.test import override_settings
from django.utils import timezone

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile
from zproject.nodl.models import NodlRegistrationPin

TEST_JWT_SECRET = "test-supabase-jwt-secret-for-testing"
TEST_SUPABASE_URL = "https://testproject.supabase.co"

NODL_SETTINGS = {
    "NODL_SUPABASE_JWT_SECRET": TEST_JWT_SECRET,
    "NODL_SUPABASE_URL": TEST_SUPABASE_URL,
}

PIN_SET_URL = "/nodl/pin/set"
PIN_VERIFY_URL = "/nodl/pin/verify"
AUTH_BRIDGE_URL = "/nodl/auth/bridge"


def make_jwt_token(
    payload: dict | None = None,
    secret: str = TEST_JWT_SECRET,
    **overrides: object,
) -> str:
    now = int(time.time())
    default_payload = {
        "sub": "test-supabase-uuid-1234",
        "email": "pintest@example.com",
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


def basic_auth(email: str, api_key: str) -> str:
    """Create HTTP Basic Auth header value."""
    credentials = base64.b64encode(f"{email}:{api_key}".encode()).decode()
    return f"Basic {credentials}"


class PinSetTest(ZulipTestCase):
    """Tests for POST /nodl/pin/set endpoint."""

    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")
        self.auth_header = basic_auth(self.user.delivery_email, self.user.api_key)

    def test_set_pin_success(self) -> None:
        result = self.client_post(
            PIN_SET_URL,
            {"pin": "1234"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assert_json_success(result)

        pin_record = NodlRegistrationPin.objects.get(user=self.user)
        self.assertTrue(check_password("1234", pin_record.pin_hash))
        self.assertEqual(pin_record.failed_attempts, 0)
        self.assertIsNone(pin_record.locked_until)

    def test_set_pin_stores_bcrypt_hash_not_plaintext(self) -> None:
        result = self.client_post(
            PIN_SET_URL,
            {"pin": "5678"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assert_json_success(result)

        pin_record = NodlRegistrationPin.objects.get(user=self.user)
        self.assertNotEqual(pin_record.pin_hash, "5678")
        self.assertTrue(pin_record.pin_hash.startswith("bcrypt"))

    def test_set_pin_updates_existing(self) -> None:
        self.client_post(
            PIN_SET_URL,
            {"pin": "1234"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        result = self.client_post(
            PIN_SET_URL,
            {"pin": "9876", "current_pin": "1234"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assert_json_success(result)

        pin_record = NodlRegistrationPin.objects.get(user=self.user)
        self.assertTrue(check_password("9876", pin_record.pin_hash))
        self.assertFalse(check_password("1234", pin_record.pin_hash))

    def test_set_pin_resets_failed_attempts(self) -> None:
        from django.contrib.auth.hashers import make_password

        NodlRegistrationPin.objects.create(
            user=self.user,
            pin_hash=make_password("4444", hasher="bcrypt"),
            failed_attempts=3,
            locked_until=None,
        )

        result = self.client_post(
            PIN_SET_URL,
            {"pin": "1234", "current_pin": "4444"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assert_json_success(result)

        pin_record = NodlRegistrationPin.objects.get(user=self.user)
        self.assertEqual(pin_record.failed_attempts, 0)
        self.assertIsNone(pin_record.locked_until)

    def test_set_pin_requires_auth(self) -> None:
        result = self.client_post(
            PIN_SET_URL,
            {"pin": "1234"},
            content_type="application/json",
        )
        self.assert_json_error(result, "Authentication required", status_code=401)

    def test_set_pin_rejects_too_short(self) -> None:
        result = self.client_post(
            PIN_SET_URL,
            {"pin": "123"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assert_json_error(result, "PIN must be 4-6 digits", status_code=400)

    def test_set_pin_rejects_too_long(self) -> None:
        result = self.client_post(
            PIN_SET_URL,
            {"pin": "1234567"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assert_json_error(result, "PIN must be 4-6 digits", status_code=400)

    def test_set_pin_rejects_non_numeric(self) -> None:
        result = self.client_post(
            PIN_SET_URL,
            {"pin": "abcd"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assert_json_error(result, "PIN must be 4-6 digits", status_code=400)

    def test_set_pin_accepts_six_digits(self) -> None:
        result = self.client_post(
            PIN_SET_URL,
            {"pin": "123456"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assert_json_success(result)

        pin_record = NodlRegistrationPin.objects.get(user=self.user)
        self.assertTrue(check_password("123456", pin_record.pin_hash))

    def test_set_pin_rejects_without_current_pin(self) -> None:
        """Changing an existing PIN without current_pin returns 409 PIN_EXISTS."""
        # Set initial PIN
        self.client_post(
            PIN_SET_URL,
            {"pin": "1234"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        # Try to overwrite without current_pin
        result = self.client_post(
            PIN_SET_URL,
            {"pin": "9876"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assertEqual(result.status_code, 409)
        data = result.json()
        self.assertEqual(data["code"], "PIN_EXISTS")

        # Verify original PIN is unchanged
        pin_record = NodlRegistrationPin.objects.get(user=self.user)
        self.assertTrue(check_password("1234", pin_record.pin_hash))

    def test_set_pin_locks_after_wrong_current_pin(self) -> None:
        """5 wrong current_pin attempts trigger lockout on pin_set."""
        self.client_post(
            PIN_SET_URL,
            {"pin": "1234"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        for i in range(5):
            result = self.client_post(
                PIN_SET_URL,
                {"pin": "9876", "current_pin": "0000"},
                content_type="application/json",
                HTTP_AUTHORIZATION=self.auth_header,
            )

        # Fifth attempt should show lockout or 403
        pin_record = NodlRegistrationPin.objects.get(user=self.user)
        self.assertEqual(pin_record.failed_attempts, 5)
        self.assertIsNotNone(pin_record.locked_until)

    def test_set_pin_rejects_when_locked(self) -> None:
        """pin_set rejects requests when account is locked."""
        from django.contrib.auth.hashers import make_password

        NodlRegistrationPin.objects.create(
            user=self.user,
            pin_hash=make_password("1234", hasher="bcrypt"),
            failed_attempts=5,
            locked_until=timezone.now() + timedelta(minutes=30),
        )
        result = self.client_post(
            PIN_SET_URL,
            {"pin": "9876", "current_pin": "1234"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assertEqual(result.status_code, 429)
        data = result.json()
        self.assertEqual(data["code"], "PIN_LOCKED")
        self.assertIn("retry_after_seconds", data)


class PinVerifyTest(ZulipTestCase):
    """Tests for POST /nodl/pin/verify endpoint."""

    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")
        self.auth_header = basic_auth(self.user.delivery_email, self.user.api_key)

        # Set a PIN for the user
        from django.contrib.auth.hashers import make_password

        self.pin_record = NodlRegistrationPin.objects.create(
            user=self.user,
            pin_hash=make_password("1234", hasher="bcrypt"),
        )

    def test_verify_correct_pin(self) -> None:
        result = self.client_post(
            PIN_VERIFY_URL,
            {"pin": "1234"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        data = self.assert_json_success(result)
        self.assertTrue(data["verified"])

    def test_verify_incorrect_pin(self) -> None:
        result = self.client_post(
            PIN_VERIFY_URL,
            {"pin": "9999"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assertEqual(result.status_code, 403)
        data = result.json()
        self.assertEqual(data["code"], "PIN_INCORRECT")
        self.assertFalse(data["verified"])

    def test_verify_resets_failed_attempts_on_success(self) -> None:
        self.pin_record.failed_attempts = 3
        self.pin_record.save()

        result = self.client_post(
            PIN_VERIFY_URL,
            {"pin": "1234"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assert_json_success(result)

        self.pin_record.refresh_from_db()
        self.assertEqual(self.pin_record.failed_attempts, 0)
        self.assertIsNone(self.pin_record.locked_until)

    def test_lockout_after_five_failures(self) -> None:
        for i in range(5):
            result = self.client_post(
                PIN_VERIFY_URL,
                {"pin": "9999"},
                content_type="application/json",
                HTTP_AUTHORIZATION=self.auth_header,
            )

        # Fifth attempt should trigger lockout
        data = result.json()
        self.assertEqual(result.status_code, 429)
        self.assertEqual(data["code"], "PIN_LOCKED")
        self.assertIn("retry_after_seconds", data)

        self.pin_record.refresh_from_db()
        self.assertEqual(self.pin_record.failed_attempts, 5)
        self.assertIsNotNone(self.pin_record.locked_until)

    def test_locked_account_returns_429(self) -> None:
        self.pin_record.failed_attempts = 5
        self.pin_record.locked_until = timezone.now() + timedelta(minutes=30)
        self.pin_record.save()

        result = self.client_post(
            PIN_VERIFY_URL,
            {"pin": "1234"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assertEqual(result.status_code, 429)
        data = result.json()
        self.assertEqual(data["code"], "PIN_LOCKED")
        self.assertIn("retry_after_seconds", data)
        self.assertGreater(data["retry_after_seconds"], 0)

    def test_lockout_expires_after_cooldown(self) -> None:
        self.pin_record.failed_attempts = 5
        self.pin_record.locked_until = timezone.now() - timedelta(minutes=1)
        self.pin_record.save()

        # Lockout has expired, correct PIN should work
        result = self.client_post(
            PIN_VERIFY_URL,
            {"pin": "1234"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        data = self.assert_json_success(result)
        self.assertTrue(data["verified"])

        self.pin_record.refresh_from_db()
        self.assertEqual(self.pin_record.failed_attempts, 0)

    def test_verify_requires_auth(self) -> None:
        result = self.client_post(
            PIN_VERIFY_URL,
            {"pin": "1234"},
            content_type="application/json",
        )
        self.assert_json_error(result, "Authentication required", status_code=401)

    def test_verify_no_pin_set_returns_404(self) -> None:
        self.pin_record.delete()

        result = self.client_post(
            PIN_VERIFY_URL,
            {"pin": "1234"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        self.assertEqual(result.status_code, 404)
        data = result.json()
        self.assertEqual(data["code"], "NO_PIN")

    def test_remaining_attempts_decrements(self) -> None:
        # First failure: 4 remaining
        result = self.client_post(
            PIN_VERIFY_URL,
            {"pin": "9999"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        data = result.json()
        self.assertIn("4 attempts remaining", data["msg"])

        # Second failure: 3 remaining
        result = self.client_post(
            PIN_VERIFY_URL,
            {"pin": "9999"},
            content_type="application/json",
            HTTP_AUTHORIZATION=self.auth_header,
        )
        data = result.json()
        self.assertIn("3 attempts remaining", data["msg"])


@override_settings(**NODL_SETTINGS)
class AuthBridgePinFieldsTest(ZulipTestCase):
    """Tests for has_pin and is_new_device fields in auth bridge response."""

    def test_new_user_has_no_pin(self) -> None:
        token = make_jwt_token(email="new-pin-test@nodl.local", phone="+15559999999")
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        data = self.assert_json_success(result)
        self.assertFalse(data["has_pin"])
        self.assertFalse(data["is_new_device"])

    def test_existing_user_is_new_device(self) -> None:
        token = make_jwt_token(email="existing-pin@nodl.local")
        # First call: creates user
        self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        # Second call: user exists -> is_new_device=True
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        data = self.assert_json_success(result)
        self.assertTrue(data["is_new_device"])

    def test_existing_user_with_pin(self) -> None:
        token = make_jwt_token(email="pinned-user@nodl.local")
        # Create user via auth bridge
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        data = self.assert_json_success(result)
        user_id = data["user_id"]

        # Set a PIN for this user
        user = UserProfile.objects.get(id=user_id)
        from django.contrib.auth.hashers import make_password

        NodlRegistrationPin.objects.create(
            user=user,
            pin_hash=make_password("1234", hasher="bcrypt"),
        )

        # Third call: should have has_pin=True, is_new_device=True
        result = self.client_post(
            AUTH_BRIDGE_URL,
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        data = self.assert_json_success(result)
        self.assertTrue(data["has_pin"])
        self.assertTrue(data["is_new_device"])
