import base64
import json
import threading
import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile
from zproject.nodl.models import CallRecord, DeviceVoipToken
from zproject.nodl.services.call_push_service import (
    dispatch_call_push,
    dispatch_call_push_async,
)


# ===== VoIP Token Endpoint Tests =====


class VoipTokenEndpointTest(ZulipTestCase):
    """Tests for POST /nodl/devices/voip-token and DELETE /nodl/devices/voip-token/unregister."""

    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user("hamlet")

    def _auth_headers(self, user: UserProfile | None = None) -> dict[str, str]:
        u = user or self.user
        cred = base64.b64encode(f"{u.delivery_email}:{u.api_key}".encode()).decode()
        return {"HTTP_AUTHORIZATION": f"Basic {cred}"}

    # --- Registration (POST) ---

    def test_register_ios_token(self) -> None:
        result = self.client_post(
            "/nodl/devices/voip-token",
            json.dumps({
                "platform": "ios",
                "device_id": "iphone-001",
                "voip_token": "apns-token-abc",
            }),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertEqual(data["device_id"], "iphone-001")
        self.assertTrue(data["created"])

        # Verify DB
        token = DeviceVoipToken.objects.get(user=self.user, device_id="iphone-001")
        self.assertEqual(token.platform, "ios")
        self.assertEqual(token.voip_token, "apns-token-abc")
        self.assertIsNone(token.fcm_token)
        self.assertTrue(token.is_active)

    def test_register_android_token(self) -> None:
        result = self.client_post(
            "/nodl/devices/voip-token",
            json.dumps({
                "platform": "android",
                "device_id": "pixel-001",
                "fcm_token": "fcm-token-xyz",
            }),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertTrue(data["created"])

        token = DeviceVoipToken.objects.get(user=self.user, device_id="pixel-001")
        self.assertEqual(token.platform, "android")
        self.assertEqual(token.fcm_token, "fcm-token-xyz")
        self.assertIsNone(token.voip_token)

    def test_register_upsert_updates_existing(self) -> None:
        """Re-registering same device_id updates the token (upsert)."""
        DeviceVoipToken.objects.create(
            user=self.user,
            platform="ios",
            device_id="iphone-001",
            voip_token="old-token",
            is_active=False,
        )

        result = self.client_post(
            "/nodl/devices/voip-token",
            json.dumps({
                "platform": "ios",
                "device_id": "iphone-001",
                "voip_token": "new-token",
            }),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertFalse(data["created"])  # Updated, not created

        token = DeviceVoipToken.objects.get(user=self.user, device_id="iphone-001")
        self.assertEqual(token.voip_token, "new-token")
        self.assertTrue(token.is_active)  # Re-activated

    def test_register_ios_missing_voip_token(self) -> None:
        """iOS registration without voip_token returns 400."""
        result = self.client_post(
            "/nodl/devices/voip-token",
            json.dumps({
                "platform": "ios",
                "device_id": "iphone-001",
            }),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 400)
        self.assertIn("voip_token", result.json()["msg"])

    def test_register_android_missing_fcm_token(self) -> None:
        """Android registration without fcm_token returns 400."""
        result = self.client_post(
            "/nodl/devices/voip-token",
            json.dumps({
                "platform": "android",
                "device_id": "pixel-001",
            }),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 400)
        self.assertIn("fcm_token", result.json()["msg"])

    def test_register_missing_platform(self) -> None:
        result = self.client_post(
            "/nodl/devices/voip-token",
            json.dumps({"device_id": "dev-001", "voip_token": "t"}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 400)
        self.assertIn("platform", result.json()["msg"])

    def test_register_invalid_platform(self) -> None:
        result = self.client_post(
            "/nodl/devices/voip-token",
            json.dumps({
                "platform": "windows",
                "device_id": "dev-001",
                "fcm_token": "t",
            }),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 400)
        self.assertIn("ios", result.json()["msg"])

    def test_register_missing_device_id(self) -> None:
        result = self.client_post(
            "/nodl/devices/voip-token",
            json.dumps({"platform": "ios", "voip_token": "t"}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 400)
        self.assertIn("device_id", result.json()["msg"])

    # --- Unregistration (DELETE) ---

    def test_unregister_existing_token(self) -> None:
        DeviceVoipToken.objects.create(
            user=self.user,
            platform="ios",
            device_id="iphone-001",
            voip_token="token-abc",
        )

        result = self.client_delete(
            "/nodl/devices/voip-token/unregister",
            json.dumps({"device_id": "iphone-001"}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertTrue(data["deactivated"])

        token = DeviceVoipToken.objects.get(user=self.user, device_id="iphone-001")
        self.assertFalse(token.is_active)

    def test_unregister_nonexistent_token(self) -> None:
        """Unregistering a device that doesn't exist returns success (idempotent)."""
        result = self.client_delete(
            "/nodl/devices/voip-token/unregister",
            json.dumps({"device_id": "nonexistent-device"}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["result"], "success")
        self.assertFalse(data["deactivated"])

    def test_unregister_missing_device_id(self) -> None:
        result = self.client_delete(
            "/nodl/devices/voip-token/unregister",
            json.dumps({}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 400)
        self.assertIn("device_id", result.json()["msg"])

    def test_unregister_only_own_tokens(self) -> None:
        """User can only unregister their own tokens."""
        other_user = self.example_user("othello")
        DeviceVoipToken.objects.create(
            user=other_user,
            platform="ios",
            device_id="othello-phone",
            voip_token="other-token",
        )

        result = self.client_delete(
            "/nodl/devices/voip-token/unregister",
            json.dumps({"device_id": "othello-phone"}),
            content_type="application/json",
            **self._auth_headers(),  # hamlet's auth
        )
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()["deactivated"])

        # Other user's token is still active
        token = DeviceVoipToken.objects.get(user=other_user, device_id="othello-phone")
        self.assertTrue(token.is_active)


# ===== Push Dispatch Service Tests =====


class DispatchCallPushTest(TestCase):
    """Tests for dispatch_call_push and individual push senders."""

    def setUp(self) -> None:
        users = UserProfile.objects.filter(is_active=True)[:2]
        assert len(users) >= 2
        self.caller = users[0]
        self.callee = users[1]
        self.call_id = str(uuid.uuid4())
        self.room_name = f"call-{uuid.uuid4()}"

    @patch("zproject.nodl.services.call_push_service.send_voip_push_ios")
    @patch("zproject.nodl.services.call_push_service.send_fcm_call_data")
    def test_dispatch_ios_only(self, mock_fcm: MagicMock, mock_ios: MagicMock) -> None:
        """Dispatch sends VoIP push to iOS device."""
        DeviceVoipToken.objects.create(
            user=self.callee,
            platform="ios",
            device_id="iphone-001",
            voip_token="apns-token",
        )

        dispatch_call_push(
            self.callee.id, self.call_id, self.room_name, "Caller", "https://avatar.url"
        )

        mock_ios.assert_called_once_with(
            "apns-token", self.call_id, self.room_name, "Caller", "https://avatar.url"
        )
        mock_fcm.assert_not_called()

    @patch("zproject.nodl.services.call_push_service.send_voip_push_ios")
    @patch("zproject.nodl.services.call_push_service.send_fcm_call_data")
    def test_dispatch_android_only(self, mock_fcm: MagicMock, mock_ios: MagicMock) -> None:
        """Dispatch sends FCM data message to Android device."""
        DeviceVoipToken.objects.create(
            user=self.callee,
            platform="android",
            device_id="pixel-001",
            fcm_token="fcm-token",
        )

        dispatch_call_push(
            self.callee.id, self.call_id, self.room_name, "Caller", ""
        )

        mock_fcm.assert_called_once_with(
            "fcm-token", self.call_id, self.room_name, "Caller", ""
        )
        mock_ios.assert_not_called()

    @patch("zproject.nodl.services.call_push_service.send_voip_push_ios")
    @patch("zproject.nodl.services.call_push_service.send_fcm_call_data")
    def test_dispatch_multi_device(self, mock_fcm: MagicMock, mock_ios: MagicMock) -> None:
        """Dispatch sends to all active devices (iOS + Android)."""
        DeviceVoipToken.objects.create(
            user=self.callee,
            platform="ios",
            device_id="iphone-001",
            voip_token="apns-token-1",
        )
        DeviceVoipToken.objects.create(
            user=self.callee,
            platform="android",
            device_id="pixel-001",
            fcm_token="fcm-token-1",
        )

        dispatch_call_push(
            self.callee.id, self.call_id, self.room_name, "Caller", ""
        )

        self.assertEqual(mock_ios.call_count, 1)
        self.assertEqual(mock_fcm.call_count, 1)

    @patch("zproject.nodl.services.call_push_service.send_voip_push_ios")
    @patch("zproject.nodl.services.call_push_service.send_fcm_call_data")
    def test_dispatch_skips_inactive_tokens(self, mock_fcm: MagicMock, mock_ios: MagicMock) -> None:
        """Inactive tokens are not dispatched to."""
        DeviceVoipToken.objects.create(
            user=self.callee,
            platform="ios",
            device_id="iphone-old",
            voip_token="old-token",
            is_active=False,
        )

        dispatch_call_push(
            self.callee.id, self.call_id, self.room_name, "Caller", ""
        )

        mock_ios.assert_not_called()
        mock_fcm.assert_not_called()

    @patch("zproject.nodl.services.call_push_service.send_voip_push_ios")
    @patch("zproject.nodl.services.call_push_service.send_fcm_call_data")
    def test_dispatch_no_tokens(self, mock_fcm: MagicMock, mock_ios: MagicMock) -> None:
        """No tokens for callee — dispatch logs and returns silently."""
        dispatch_call_push(
            self.callee.id, self.call_id, self.room_name, "Caller", ""
        )

        mock_ios.assert_not_called()
        mock_fcm.assert_not_called()

    @patch("zproject.nodl.services.call_push_service.send_voip_push_ios")
    @patch("zproject.nodl.services.call_push_service.send_fcm_call_data")
    def test_dispatch_skips_ios_with_missing_voip_token(
        self, mock_fcm: MagicMock, mock_ios: MagicMock
    ) -> None:
        """iOS device with null voip_token is skipped (ledger advisory)."""
        DeviceVoipToken.objects.create(
            user=self.callee,
            platform="ios",
            device_id="iphone-broken",
            voip_token=None,
        )

        dispatch_call_push(
            self.callee.id, self.call_id, self.room_name, "Caller", ""
        )

        mock_ios.assert_not_called()

    @patch("zproject.nodl.services.call_push_service.send_voip_push_ios")
    @patch("zproject.nodl.services.call_push_service.send_fcm_call_data")
    def test_dispatch_skips_android_with_missing_fcm_token(
        self, mock_fcm: MagicMock, mock_ios: MagicMock
    ) -> None:
        """Android device with null fcm_token is skipped (ledger advisory)."""
        DeviceVoipToken.objects.create(
            user=self.callee,
            platform="android",
            device_id="pixel-broken",
            fcm_token=None,
        )

        dispatch_call_push(
            self.callee.id, self.call_id, self.room_name, "Caller", ""
        )

        mock_fcm.assert_not_called()


class DispatchCallPushAsyncTest(TestCase):
    """Tests for fire-and-forget async dispatch."""

    def setUp(self) -> None:
        users = UserProfile.objects.filter(is_active=True)[:2]
        assert len(users) >= 2
        self.caller = users[0]
        self.callee = users[1]

    @patch("zproject.nodl.services.call_push_service.dispatch_call_push")
    def test_async_dispatch_spawns_thread(self, mock_dispatch: MagicMock) -> None:
        """dispatch_call_push_async spawns a daemon thread."""
        call_id = str(uuid.uuid4())
        room_name = f"call-{uuid.uuid4()}"

        dispatch_call_push_async(
            self.callee.id, call_id, room_name, "Caller", ""
        )

        # Wait for thread to complete
        for t in threading.enumerate():
            if t.daemon and t.is_alive():
                t.join(timeout=2)

        mock_dispatch.assert_called_once_with(
            self.callee.id, call_id, room_name, "Caller", ""
        )


class SendVoipPushIosTest(TestCase):
    """Tests for send_voip_push_ios."""

    def test_missing_apns_credentials_returns_false(self) -> None:
        """Returns False when APNs credentials are not configured."""
        from zproject.nodl.services.call_push_service import send_voip_push_ios

        with patch.dict("os.environ", {}, clear=False):
            result = send_voip_push_ios(
                "token", "call-id", "room", "Caller", ""
            )
            self.assertFalse(result)


class SendFcmCallDataTest(TestCase):
    """Tests for send_fcm_call_data."""

    @patch("zproject.nodl.services.call_push_service._ensure_firebase_initialized", return_value=False)
    def test_firebase_not_initialized_returns_false(self, mock_init: MagicMock) -> None:
        """Returns False when Firebase is not initialized."""
        from zproject.nodl.services.call_push_service import send_fcm_call_data

        result = send_fcm_call_data("token", "call-id", "room", "Caller", "")
        self.assertFalse(result)

    @patch("zproject.nodl.services.call_push_service._ensure_firebase_initialized", return_value=True)
    @patch("zproject.nodl.services.call_push_service.messaging")
    def test_fcm_send_success(self, mock_messaging: MagicMock, mock_init: MagicMock) -> None:
        """Sends FCM data message with correct payload."""
        from zproject.nodl.services.call_push_service import send_fcm_call_data

        mock_messaging.send.return_value = "projects/test/messages/123"

        result = send_fcm_call_data(
            "fcm-token-123", "call-id-abc", "call-room", "Hamlet", "https://avatar"
        )
        self.assertTrue(result)

        mock_messaging.Message.assert_called_once()
        call_kwargs = mock_messaging.Message.call_args
        msg_data = call_kwargs.kwargs.get("data") or call_kwargs[1].get("data")
        self.assertEqual(msg_data["type"], "incoming_call")
        self.assertEqual(msg_data["call_id"], "call-id-abc")
        self.assertEqual(msg_data["room_name"], "call-room")
        self.assertEqual(msg_data["caller_name"], "Hamlet")
        self.assertEqual(msg_data["caller_avatar_url"], "https://avatar")

    @patch("zproject.nodl.services.call_push_service._ensure_firebase_initialized", return_value=True)
    @patch("zproject.nodl.services.call_push_service.messaging")
    def test_fcm_send_exception_returns_false(
        self, mock_messaging: MagicMock, mock_init: MagicMock
    ) -> None:
        """FCM exception is caught and returns False."""
        from zproject.nodl.services.call_push_service import send_fcm_call_data

        mock_messaging.send.side_effect = Exception("FCM error")

        result = send_fcm_call_data("token", "call-id", "room", "Caller", "")
        self.assertFalse(result)


# ===== Integration: initiate_call triggers push dispatch =====


MOCK_LIVEKIT_ENV = {
    "LIVEKIT_URL": "wss://test.livekit.cloud",
    "LIVEKIT_API_KEY": "test-api-key",
    "LIVEKIT_API_SECRET": "test-api-secret-that-is-long-enough-for-hs256-algorithm",
}


class InitiateCallPushIntegrationTest(ZulipTestCase):
    """Test that initiate_call triggers fire-and-forget push dispatch."""

    def setUp(self) -> None:
        super().setUp()
        self.caller = self.example_user("hamlet")
        self.callee = self.example_user("othello")

    def _auth_headers(self, user: UserProfile | None = None) -> dict[str, str]:
        u = user or self.caller
        cred = base64.b64encode(f"{u.delivery_email}:{u.api_key}".encode()).decode()
        return {"HTTP_AUTHORIZATION": f"Basic {cred}"}

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
    @patch("zproject.nodl.views.calls.dispatch_call_push_async")
    def test_initiate_triggers_push_dispatch(
        self, mock_dispatch: MagicMock, mock_create_room: MagicMock
    ) -> None:
        """initiate_call calls dispatch_call_push_async with correct args."""
        mock_create_room.return_value = {"name": "room", "sid": "sid"}

        result = self.client_post(
            "/nodl/calls/initiate",
            json.dumps({"callee_id": self.callee.id}),
            content_type="application/json",
            **self._auth_headers(),
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["result"], "success")

        # Verify dispatch was called
        mock_dispatch.assert_called_once()
        call_args = mock_dispatch.call_args
        self.assertEqual(call_args.kwargs["callee_id"], self.callee.id)
        self.assertEqual(call_args.kwargs["room_name"], result.json()["room_name"])
        self.assertEqual(call_args.kwargs["caller_name"], self.caller.full_name)

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
    @patch("zproject.nodl.views.calls.dispatch_call_push_async")
    def test_initiate_returns_before_push_completes(
        self, mock_dispatch: MagicMock, mock_create_room: MagicMock
    ) -> None:
        """Endpoint returns immediately — dispatch is fire-and-forget."""
        mock_create_room.return_value = {"name": "room", "sid": "sid"}

        # Make dispatch block to prove endpoint doesn't wait
        event = threading.Event()
        original_dispatch = mock_dispatch.side_effect

        def slow_dispatch(**kwargs: object) -> None:
            event.wait(timeout=5)

        mock_dispatch.side_effect = slow_dispatch

        result = self.client_post(
            "/nodl/calls/initiate",
            json.dumps({"callee_id": self.callee.id}),
            content_type="application/json",
            **self._auth_headers(),
        )

        # Endpoint returned 200 even though dispatch hasn't completed
        self.assertEqual(result.status_code, 200)
        event.set()  # Unblock
