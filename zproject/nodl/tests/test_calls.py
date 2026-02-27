import base64
import json
import uuid
from unittest.mock import ANY, MagicMock, patch

from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.utils import timezone

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile
from zproject.nodl.models import CallRecord, DeviceVoipToken


class CallRecordModelTest(TestCase):
    """Tests for the CallRecord model."""

    def setUp(self) -> None:
        users = UserProfile.objects.filter(is_active=True)[:2]
        assert len(users) >= 2
        self.caller = users[0]
        self.callee = users[1]

    def test_create_call_record(self) -> None:
        call = CallRecord.objects.create(
            room_name="call-test-123",
            caller=self.caller,
            callee=self.callee,
            status="ringing",
        )
        self.assertIsNotNone(call.id)
        self.assertEqual(call.status, "ringing")
        self.assertEqual(call.room_name, "call-test-123")
        self.assertIsNotNone(call.initiated_at)
        self.assertIsNone(call.answered_at)
        self.assertIsNone(call.ended_at)
        self.assertIsNone(call.duration_seconds)
        self.assertIsNone(call.end_reason)

    def test_uuid_primary_key(self) -> None:
        call = CallRecord.objects.create(
            room_name="call-uuid-test",
            caller=self.caller,
            callee=self.callee,
        )
        self.assertIsInstance(call.id, uuid.UUID)

    def test_status_choices(self) -> None:
        for status in ["ringing", "connected", "ended", "missed", "declined", "cancelled"]:
            call = CallRecord.objects.create(
                room_name=f"call-{status}",
                caller=self.caller,
                callee=self.callee,
                status=status,
            )
            self.assertEqual(call.status, status)

    def test_ordering(self) -> None:
        call1 = CallRecord.objects.create(
            room_name="call-old",
            caller=self.caller,
            callee=self.callee,
        )
        call2 = CallRecord.objects.create(
            room_name="call-new",
            caller=self.caller,
            callee=self.callee,
        )
        calls = list(CallRecord.objects.all())
        self.assertEqual(calls[0].id, call2.id)
        self.assertEqual(calls[1].id, call1.id)


class DeviceVoipTokenModelTest(TestCase):
    """Tests for the DeviceVoipToken model (AC:2)."""

    def setUp(self) -> None:
        self.user = UserProfile.objects.filter(is_active=True).first()
        assert self.user is not None

    def test_create_token(self) -> None:
        token = DeviceVoipToken.objects.create(
            user=self.user,
            platform="ios",
            voip_token="test-voip-token-abc",
            device_id="device-001",
        )
        self.assertIsNotNone(token.id)
        self.assertIsInstance(token.id, uuid.UUID)
        self.assertEqual(token.platform, "ios")
        self.assertEqual(token.voip_token, "test-voip-token-abc")
        self.assertIsNone(token.fcm_token)
        self.assertTrue(token.is_active)
        self.assertIsNotNone(token.created_at)
        self.assertIsNotNone(token.updated_at)

    def test_create_android_token(self) -> None:
        token = DeviceVoipToken.objects.create(
            user=self.user,
            platform="android",
            fcm_token="test-fcm-token-xyz",
            device_id="device-002",
        )
        self.assertEqual(token.platform, "android")
        self.assertEqual(token.fcm_token, "test-fcm-token-xyz")
        self.assertIsNone(token.voip_token)

    def test_unique_user_device_constraint(self) -> None:
        DeviceVoipToken.objects.create(
            user=self.user,
            platform="ios",
            voip_token="token-1",
            device_id="device-unique",
        )
        with self.assertRaises(IntegrityError):
            DeviceVoipToken.objects.create(
                user=self.user,
                platform="ios",
                voip_token="token-2",
                device_id="device-unique",  # same device_id
            )

    def test_is_active_default_true(self) -> None:
        token = DeviceVoipToken.objects.create(
            user=self.user,
            platform="ios",
            device_id="device-active-test",
        )
        self.assertTrue(token.is_active)

    def test_soft_delete(self) -> None:
        token = DeviceVoipToken.objects.create(
            user=self.user,
            platform="android",
            fcm_token="token-soft",
            device_id="device-soft",
        )
        token.is_active = False
        token.save(update_fields=["is_active"])
        token.refresh_from_db()
        self.assertFalse(token.is_active)


MOCK_LIVEKIT_ENV = {
    "LIVEKIT_URL": "wss://test.livekit.cloud",
    "LIVEKIT_API_KEY": "test-api-key",
    "LIVEKIT_API_SECRET": "test-api-secret-that-is-long-enough-for-hs256-algorithm",
}


class CallViewsTest(ZulipTestCase):
    """Tests for call signaling API endpoints."""

    def setUp(self) -> None:
        super().setUp()
        self.caller = self.example_user("hamlet")
        self.callee = self.example_user("othello")

    def _auth_headers(self, user: UserProfile | None = None) -> dict[str, str]:
        u = user or self.caller
        cred = base64.b64encode(f"{u.delivery_email}:{u.api_key}".encode()).decode()
        return {"HTTP_AUTHORIZATION": f"Basic {cred}"}

    def _create_ringing_call(self) -> CallRecord:
        """Helper: create a call in ringing state."""
        return CallRecord.objects.create(
            room_name=f"call-{uuid.uuid4()}",
            caller=self.caller,
            callee=self.callee,
            status="ringing",
        )

    def _create_connected_call(self) -> CallRecord:
        """Helper: create a call in connected state."""
        return CallRecord.objects.create(
            room_name=f"call-{uuid.uuid4()}",
            caller=self.caller,
            callee=self.callee,
            status="connected",
            answered_at=timezone.now(),
        )

    # === Happy path: initiate → accept → end ===

    @patch.dict("os.environ", MOCK_LIVEKIT_ENV)
    @patch("zproject.nodl.services.livekit_service.LIVEKIT_URL", MOCK_LIVEKIT_ENV["LIVEKIT_URL"])
    @patch(
        "zproject.nodl.services.livekit_service.LIVEKIT_API_KEY",
        MOCK_LIVEKIT_ENV["LIVEKIT_API_KEY"],
    )
    @patch(
        "zproject.nodl.services.livekit_service.LIVEKIT_API_SECRET",
        MOCK_LIVEKIT_ENV["LIVEKIT_API_SECRET"],
    )
    @patch("zproject.nodl.views.calls.create_room_sync")
    def test_happy_path_initiate_accept_end(self, mock_create_room: MagicMock) -> None:
        mock_create_room.return_value = {"name": "call-mock", "sid": "RM_test"}

        # Initiate
        result = self.client_post(
            "/nodl/calls/initiate",
            json.dumps({"callee_id": self.callee.id}),
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertIn("call_id", data)
        self.assertIn("room_name", data)
        self.assertIn("livekit_url", data)
        self.assertIn("token", data)

        # Verify create_room_sync was called with correct args
        mock_create_room.assert_called_once_with(ANY, max_participants=2, empty_timeout=35)

        call_id = data["call_id"]

        # Verify call record created
        call = CallRecord.objects.get(id=call_id)
        self.assertEqual(call.status, "ringing")
        self.assertEqual(call.caller_id, self.caller.id)
        self.assertEqual(call.callee_id, self.callee.id)

        # Accept (as callee)
        result = self.client_post(
            f"/nodl/calls/{call_id}/accept",
            content_type="application/json",
            **self._auth_headers(self.callee),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertIn("token", data)
        self.assertIn("call_id", data)
        self.assertIn("room_name", data)
        self.assertIn("livekit_url", data)

        call.refresh_from_db()
        self.assertEqual(call.status, "connected")
        self.assertIsNotNone(call.answered_at)

        # End (as caller)
        result = self.client_post(
            f"/nodl/calls/{call_id}/end",
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")

        call.refresh_from_db()
        self.assertEqual(call.status, "ended")
        self.assertIsNotNone(call.ended_at)
        self.assertIsNotNone(call.duration_seconds)
        self.assertEqual(call.end_reason, "caller_hangup")

    # === Decline flow ===

    @patch.dict("os.environ", MOCK_LIVEKIT_ENV)
    @patch("zproject.nodl.services.livekit_service.LIVEKIT_URL", MOCK_LIVEKIT_ENV["LIVEKIT_URL"])
    @patch(
        "zproject.nodl.services.livekit_service.LIVEKIT_API_KEY",
        MOCK_LIVEKIT_ENV["LIVEKIT_API_KEY"],
    )
    @patch(
        "zproject.nodl.services.livekit_service.LIVEKIT_API_SECRET",
        MOCK_LIVEKIT_ENV["LIVEKIT_API_SECRET"],
    )
    def test_decline_flow(self) -> None:
        call = self._create_ringing_call()

        result = self.client_post(
            f"/nodl/calls/{call.id}/decline",
            content_type="application/json",
            **self._auth_headers(self.callee),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")

        call.refresh_from_db()
        self.assertEqual(call.status, "declined")
        self.assertIsNotNone(call.ended_at)
        self.assertEqual(call.end_reason, "callee_declined")

    # === Cancel flow ===

    def test_cancel_flow(self) -> None:
        call = self._create_ringing_call()

        result = self.client_post(
            f"/nodl/calls/{call.id}/cancel",
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")

        call.refresh_from_db()
        self.assertEqual(call.status, "cancelled")
        self.assertIsNotNone(call.ended_at)
        self.assertEqual(call.end_reason, "caller_cancelled")

    # === Race conditions ===

    @patch.dict("os.environ", MOCK_LIVEKIT_ENV)
    @patch("zproject.nodl.services.livekit_service.LIVEKIT_URL", MOCK_LIVEKIT_ENV["LIVEKIT_URL"])
    @patch(
        "zproject.nodl.services.livekit_service.LIVEKIT_API_KEY",
        MOCK_LIVEKIT_ENV["LIVEKIT_API_KEY"],
    )
    @patch(
        "zproject.nodl.services.livekit_service.LIVEKIT_API_SECRET",
        MOCK_LIVEKIT_ENV["LIVEKIT_API_SECRET"],
    )
    def test_accept_while_cancelled(self) -> None:
        """AC:9 — accept after cancel returns error."""
        call = self._create_ringing_call()

        # Cancel first
        self.client_post(
            f"/nodl/calls/{call.id}/cancel",
            content_type="application/json",
            **self._auth_headers(self.caller),
        )

        # Try to accept
        result = self.client_post(
            f"/nodl/calls/{call.id}/accept",
            content_type="application/json",
            **self._auth_headers(self.callee),
        )
        self.assertEqual(result.status_code, 409)
        data = result.json()
        self.assertEqual(data["result"], "error")
        self.assertIn("cancelled", data["msg"])

    def test_simultaneous_end_idempotent(self) -> None:
        """AC:8 — second /end returns 200 OK."""
        call = self._create_connected_call()

        # First end
        result = self.client_post(
            f"/nodl/calls/{call.id}/end",
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 200)

        # Second end (idempotent)
        result = self.client_post(
            f"/nodl/calls/{call.id}/end",
            content_type="application/json",
            **self._auth_headers(self.callee),
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["result"], "success")

    @patch.dict("os.environ", MOCK_LIVEKIT_ENV)
    @patch("zproject.nodl.services.livekit_service.LIVEKIT_URL", MOCK_LIVEKIT_ENV["LIVEKIT_URL"])
    @patch(
        "zproject.nodl.services.livekit_service.LIVEKIT_API_KEY",
        MOCK_LIVEKIT_ENV["LIVEKIT_API_KEY"],
    )
    @patch(
        "zproject.nodl.services.livekit_service.LIVEKIT_API_SECRET",
        MOCK_LIVEKIT_ENV["LIVEKIT_API_SECRET"],
    )
    def test_multi_device_accept_first_wins(self) -> None:
        """AC:9 — multi-device accept: first wins, subsequent get error."""
        call = self._create_ringing_call()

        # First accept succeeds
        result = self.client_post(
            f"/nodl/calls/{call.id}/accept",
            content_type="application/json",
            **self._auth_headers(self.callee),
        )
        self.assertEqual(result.status_code, 200)

        # Second accept fails (status is now 'connected', not 'ringing')
        result = self.client_post(
            f"/nodl/calls/{call.id}/accept",
            content_type="application/json",
            **self._auth_headers(self.callee),
        )
        self.assertEqual(result.status_code, 409)

    # === History pagination ===

    def test_history_pagination(self) -> None:
        """AC:10 — paginated call records, newest first."""
        # Create 5 calls
        for i in range(5):
            CallRecord.objects.create(
                room_name=f"call-hist-{i}",
                caller=self.caller,
                callee=self.callee,
                status="ended",
            )

        result = self.client_get(
            "/nodl/calls/history?limit=3&offset=0",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertEqual(len(data["calls"]), 3)

        # Page 2
        result = self.client_get(
            "/nodl/calls/history?limit=3&offset=3",
            **self._auth_headers(self.caller),
        )
        data = result.json()
        self.assertEqual(len(data["calls"]), 2)

    def test_history_default_pagination(self) -> None:
        """Default limit=20, offset=0."""
        result = self.client_get(
            "/nodl/calls/history",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertIn("calls", data)

    def test_history_shows_both_directions(self) -> None:
        """User sees calls where they are caller OR callee."""
        # Call where user is caller
        CallRecord.objects.create(
            room_name="call-outgoing",
            caller=self.caller,
            callee=self.callee,
            status="ended",
        )
        # Call where user is callee
        CallRecord.objects.create(
            room_name="call-incoming",
            caller=self.callee,
            callee=self.caller,
            status="ended",
        )

        result = self.client_get(
            "/nodl/calls/history",
            **self._auth_headers(self.caller),
        )
        data = result.json()
        self.assertEqual(len(data["calls"]), 2)

    # === Authorization ===

    def test_accept_only_callee(self) -> None:
        """Caller cannot accept their own call."""
        call = self._create_ringing_call()

        result = self.client_post(
            f"/nodl/calls/{call.id}/accept",
            content_type="application/json",
            **self._auth_headers(self.caller),  # caller trying to accept
        )
        self.assertEqual(result.status_code, 403)

    def test_cancel_only_caller(self) -> None:
        """Callee cannot cancel."""
        call = self._create_ringing_call()

        result = self.client_post(
            f"/nodl/calls/{call.id}/cancel",
            content_type="application/json",
            **self._auth_headers(self.callee),  # callee trying to cancel
        )
        self.assertEqual(result.status_code, 403)

    def test_decline_only_callee(self) -> None:
        """Caller cannot decline their own call."""
        call = self._create_ringing_call()

        result = self.client_post(
            f"/nodl/calls/{call.id}/decline",
            content_type="application/json",
            **self._auth_headers(self.caller),  # caller trying to decline
        )
        self.assertEqual(result.status_code, 403)

    def test_end_only_participants(self) -> None:
        """Third party cannot end a call."""
        call = self._create_connected_call()
        third_party = self.example_user("cordelia")

        result = self.client_post(
            f"/nodl/calls/{call.id}/end",
            content_type="application/json",
            **self._auth_headers(third_party),
        )
        self.assertEqual(result.status_code, 403)

    def test_call_detail_authorization(self) -> None:
        """AC:11 — only caller or callee can view."""
        call = self._create_ringing_call()
        third_party = self.example_user("cordelia")

        # Participant can view
        result = self.client_get(
            f"/nodl/calls/{call.id}",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 200)

        # Third party cannot view
        result = self.client_get(
            f"/nodl/calls/{call.id}",
            **self._auth_headers(third_party),
        )
        self.assertEqual(result.status_code, 403)

    def test_unauthorized_request(self) -> None:
        """Endpoints require authentication."""
        result = self.client_post("/nodl/calls/initiate")
        self.assertEqual(result.status_code, 401)

    # === Response format ===

    def test_response_format_zulip_wrapper(self) -> None:
        """AC:12 — responses use Zulip wrapper format."""
        call = self._create_ringing_call()

        # Success response
        result = self.client_post(
            f"/nodl/calls/{call.id}/cancel",
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        data = result.json()
        self.assertIn("result", data)
        self.assertIn("msg", data)
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["msg"], "")

    def test_error_response_format(self) -> None:
        """Error responses also use Zulip wrapper."""
        result = self.client_post(
            "/nodl/calls/initiate",
            json.dumps({}),
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        data = result.json()
        self.assertIn("result", data)
        self.assertIn("msg", data)
        self.assertEqual(data["result"], "error")

    def test_call_detail_response_fields(self) -> None:
        """AC:11 — detail returns full record with snake_case."""
        call = self._create_connected_call()

        result = self.client_get(
            f"/nodl/calls/{call.id}",
            **self._auth_headers(self.caller),
        )
        data = result.json()
        call_data = data["call"]
        self.assertIn("call_id", call_data)
        self.assertIn("room_name", call_data)
        self.assertIn("caller_id", call_data)
        self.assertIn("callee_id", call_data)
        self.assertIn("status", call_data)
        self.assertIn("initiated_at", call_data)
        self.assertIn("answered_at", call_data)
        self.assertIn("ended_at", call_data)
        self.assertIn("duration_seconds", call_data)
        self.assertIn("end_reason", call_data)

    # === Edge cases ===

    @patch.dict("os.environ", MOCK_LIVEKIT_ENV)
    @patch("zproject.nodl.services.livekit_service.LIVEKIT_URL", MOCK_LIVEKIT_ENV["LIVEKIT_URL"])
    @patch(
        "zproject.nodl.services.livekit_service.LIVEKIT_API_KEY",
        MOCK_LIVEKIT_ENV["LIVEKIT_API_KEY"],
    )
    @patch(
        "zproject.nodl.services.livekit_service.LIVEKIT_API_SECRET",
        MOCK_LIVEKIT_ENV["LIVEKIT_API_SECRET"],
    )
    def test_initiate_invalid_callee(self) -> None:
        result = self.client_post(
            "/nodl/calls/initiate",
            json.dumps({"callee_id": 999999}),
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 400)

    @patch.dict("os.environ", MOCK_LIVEKIT_ENV)
    @patch("zproject.nodl.services.livekit_service.LIVEKIT_URL", MOCK_LIVEKIT_ENV["LIVEKIT_URL"])
    @patch(
        "zproject.nodl.services.livekit_service.LIVEKIT_API_KEY",
        MOCK_LIVEKIT_ENV["LIVEKIT_API_KEY"],
    )
    @patch(
        "zproject.nodl.services.livekit_service.LIVEKIT_API_SECRET",
        MOCK_LIVEKIT_ENV["LIVEKIT_API_SECRET"],
    )
    def test_initiate_call_self(self) -> None:
        result = self.client_post(
            "/nodl/calls/initiate",
            json.dumps({"callee_id": self.caller.id}),
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 400)
        self.assertIn("Cannot call yourself", result.json()["msg"])

    def test_call_not_found(self) -> None:
        fake_id = str(uuid.uuid4())
        result = self.client_post(
            f"/nodl/calls/{fake_id}/accept",
            content_type="application/json",
            **self._auth_headers(self.callee),
        )
        self.assertEqual(result.status_code, 404)

    def test_invalid_call_id_format(self) -> None:
        result = self.client_post(
            "/nodl/calls/not-a-uuid/accept",
            content_type="application/json",
            **self._auth_headers(self.callee),
        )
        self.assertEqual(result.status_code, 400)

    def test_callee_end_sets_callee_hangup(self) -> None:
        """End reason is callee_hangup when callee ends the call."""
        call = self._create_connected_call()

        self.client_post(
            f"/nodl/calls/{call.id}/end",
            content_type="application/json",
            **self._auth_headers(self.callee),
        )

        call.refresh_from_db()
        self.assertEqual(call.end_reason, "callee_hangup")

    def test_initiate_invalid_json(self) -> None:
        result = self.client_post(
            "/nodl/calls/initiate",
            "not-json",
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 400)

    def test_initiate_missing_callee_id(self) -> None:
        result = self.client_post(
            "/nodl/calls/initiate",
            json.dumps({}),
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 400)
        self.assertIn("callee_id", result.json()["msg"])

    def test_initiate_callee_id_string_type(self) -> None:
        """Fix #3: callee_id as non-integer string returns 400, not 500."""
        result = self.client_post(
            "/nodl/calls/initiate",
            json.dumps({"callee_id": "abc"}),
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 400)
        self.assertIn("integer", result.json()["msg"])

    def test_initiate_callee_id_float_type(self) -> None:
        """callee_id as float is cast to int."""
        result = self.client_post(
            "/nodl/calls/initiate",
            json.dumps({"callee_id": 3.14}),
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        # Should not be a 500 — either 400 (not found) or 200 depending on user existence
        self.assertNotEqual(result.status_code, 500)
