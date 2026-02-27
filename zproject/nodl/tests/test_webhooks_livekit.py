import base64
import json
import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile
from zproject.nodl.models import CallRecord
from zproject.nodl.views.webhooks_livekit import (
    _handle_participant_joined,
    _handle_participant_left,
    _handle_room_finished,
    insert_call_event_message,
)


# ===== insert_call_event_message tests =====


class InsertCallEventMessageTest(TestCase):
    """Tests for the call event message insertion helper."""

    def setUp(self) -> None:
        users = UserProfile.objects.filter(is_active=True)[:2]
        assert len(users) >= 2
        self.caller = users[0]
        self.callee = users[1]

    @patch("zproject.nodl.views.webhooks_livekit.internal_send_group_direct_message")
    @patch("zproject.nodl.views.webhooks_livekit.get_system_bot")
    def test_sends_dm_into_caller_callee_thread(
        self, mock_get_bot: MagicMock, mock_send: MagicMock
    ) -> None:
        mock_bot = MagicMock()
        mock_get_bot.return_value = mock_bot

        insert_call_event_message(self.caller, self.callee, "Missed voice call")

        mock_send.assert_called_once_with(
            self.caller.realm,
            mock_bot,
            "Missed voice call",
            recipient_users=[self.caller, self.callee],
        )

    @patch("zproject.nodl.views.webhooks_livekit.internal_send_group_direct_message")
    @patch("zproject.nodl.views.webhooks_livekit.get_system_bot")
    def test_exception_does_not_raise(
        self, mock_get_bot: MagicMock, mock_send: MagicMock
    ) -> None:
        """Errors in message insertion are logged but don't raise."""
        mock_get_bot.side_effect = Exception("Bot not found")

        # Should not raise
        insert_call_event_message(self.caller, self.callee, "Test")


# ===== Webhook handler tests =====


MOCK_LIVEKIT_ENV = {
    "LIVEKIT_URL": "wss://test.livekit.cloud",
    "LIVEKIT_API_KEY": "test-api-key",
    "LIVEKIT_API_SECRET": "test-api-secret-that-is-long-enough-for-hs256-algorithm",
}


class LiveKitWebhookEndpointTest(ZulipTestCase):
    """Tests for POST /nodl/webhooks/livekit."""

    @patch.dict("os.environ", MOCK_LIVEKIT_ENV)
    @patch("zproject.nodl.views.webhooks_livekit.LIVEKIT_API_KEY", MOCK_LIVEKIT_ENV["LIVEKIT_API_KEY"])
    @patch("zproject.nodl.views.webhooks_livekit.LIVEKIT_API_SECRET", MOCK_LIVEKIT_ENV["LIVEKIT_API_SECRET"])
    @patch("zproject.nodl.views.webhooks_livekit._get_webhook_receiver")
    def test_valid_webhook_returns_200(self, mock_get_receiver: MagicMock) -> None:
        """Valid webhook signature returns 200."""
        mock_event = MagicMock()
        mock_event.event = "room_started"
        mock_event.room.name = "call-test"

        mock_receiver = MagicMock()
        mock_receiver.receive.return_value = mock_event
        mock_get_receiver.return_value = mock_receiver

        result = self.client_post(
            "/nodl/webhooks/livekit",
            json.dumps({"event": "room_started"}),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["result"], "success")

    @patch.dict("os.environ", MOCK_LIVEKIT_ENV)
    @patch("zproject.nodl.views.webhooks_livekit.LIVEKIT_API_KEY", MOCK_LIVEKIT_ENV["LIVEKIT_API_KEY"])
    @patch("zproject.nodl.views.webhooks_livekit.LIVEKIT_API_SECRET", MOCK_LIVEKIT_ENV["LIVEKIT_API_SECRET"])
    @patch("zproject.nodl.views.webhooks_livekit._get_webhook_receiver")
    def test_invalid_signature_returns_401(self, mock_get_receiver: MagicMock) -> None:
        """Invalid JWT signature returns 401."""
        mock_receiver = MagicMock()
        mock_receiver.receive.side_effect = Exception("hash mismatch")
        mock_get_receiver.return_value = mock_receiver

        result = self.client_post(
            "/nodl/webhooks/livekit",
            json.dumps({"event": "test"}),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 401)

    @patch("zproject.nodl.views.webhooks_livekit.LIVEKIT_API_KEY", "")
    @patch("zproject.nodl.views.webhooks_livekit.LIVEKIT_API_SECRET", "")
    def test_unconfigured_returns_503(self) -> None:
        """No LiveKit credentials returns 503."""
        result = self.client_post(
            "/nodl/webhooks/livekit",
            json.dumps({"event": "test"}),
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 503)

    def test_get_method_returns_405(self) -> None:
        result = self.client_get("/nodl/webhooks/livekit")
        self.assertEqual(result.status_code, 405)


# ===== room_finished handler tests =====


class HandleRoomFinishedTest(TestCase):
    """Tests for _handle_room_finished webhook handler."""

    def setUp(self) -> None:
        users = UserProfile.objects.filter(is_active=True)[:2]
        assert len(users) >= 2
        self.caller = users[0]
        self.callee = users[1]

    @patch("zproject.nodl.views.webhooks_livekit.insert_call_event_message")
    def test_ringing_call_becomes_missed(self, mock_msg: MagicMock) -> None:
        """Room finished with ringing call → missed + DM message."""
        call = CallRecord.objects.create(
            room_name="call-timeout-test",
            caller=self.caller,
            callee=self.callee,
            status="ringing",
        )

        _handle_room_finished("call-timeout-test")

        call.refresh_from_db()
        self.assertEqual(call.status, "missed")
        self.assertIsNotNone(call.ended_at)
        self.assertEqual(call.end_reason, "timeout")
        mock_msg.assert_called_once()
        self.assertIn("Missed voice call", mock_msg.call_args[0][2])

    @patch("zproject.nodl.views.webhooks_livekit.insert_call_event_message")
    def test_already_ended_call_idempotent(self, mock_msg: MagicMock) -> None:
        """Room finished with already-ended call — no change."""
        call = CallRecord.objects.create(
            room_name="call-ended-test",
            caller=self.caller,
            callee=self.callee,
            status="ended",
            ended_at=timezone.now(),
            end_reason="caller_hangup",
        )

        _handle_room_finished("call-ended-test")

        call.refresh_from_db()
        self.assertEqual(call.status, "ended")
        self.assertEqual(call.end_reason, "caller_hangup")
        mock_msg.assert_not_called()

    @patch("zproject.nodl.views.webhooks_livekit.insert_call_event_message")
    def test_connected_call_not_changed(self, mock_msg: MagicMock) -> None:
        """Room finished with connected call — not changed to missed."""
        call = CallRecord.objects.create(
            room_name="call-connected-test",
            caller=self.caller,
            callee=self.callee,
            status="connected",
            answered_at=timezone.now(),
        )

        _handle_room_finished("call-connected-test")

        call.refresh_from_db()
        self.assertEqual(call.status, "connected")
        mock_msg.assert_not_called()

    @patch("zproject.nodl.views.webhooks_livekit.insert_call_event_message")
    def test_unknown_room_no_error(self, mock_msg: MagicMock) -> None:
        """Unknown room name logs warning but doesn't raise."""
        _handle_room_finished("nonexistent-room")
        mock_msg.assert_not_called()


# ===== participant_joined handler tests =====


class HandleParticipantJoinedTest(TestCase):
    """Tests for _handle_participant_joined webhook handler."""

    def setUp(self) -> None:
        users = UserProfile.objects.filter(is_active=True)[:2]
        assert len(users) >= 2
        self.caller = users[0]
        self.callee = users[1]

    def _make_event(self, identity: str) -> MagicMock:
        event = MagicMock()
        event.participant.identity = identity
        return event

    def test_callee_join_confirms_presence(self) -> None:
        """Callee joining room while still ringing → connected."""
        call = CallRecord.objects.create(
            room_name="call-join-test",
            caller=self.caller,
            callee=self.callee,
            status="ringing",
        )

        event = self._make_event(str(self.callee.id))
        _handle_participant_joined("call-join-test", event)

        call.refresh_from_db()
        self.assertEqual(call.status, "connected")
        self.assertIsNotNone(call.answered_at)

    def test_caller_join_no_change(self) -> None:
        """Caller joining doesn't trigger callee presence update."""
        call = CallRecord.objects.create(
            room_name="call-caller-join",
            caller=self.caller,
            callee=self.callee,
            status="ringing",
        )

        event = self._make_event(str(self.caller.id))
        _handle_participant_joined("call-caller-join", event)

        call.refresh_from_db()
        self.assertEqual(call.status, "ringing")

    def test_callee_join_already_connected_idempotent(self) -> None:
        """Callee join on already-connected call — no change."""
        call = CallRecord.objects.create(
            room_name="call-already-connected",
            caller=self.caller,
            callee=self.callee,
            status="connected",
            answered_at=timezone.now(),
        )

        event = self._make_event(str(self.callee.id))
        _handle_participant_joined("call-already-connected", event)

        call.refresh_from_db()
        self.assertEqual(call.status, "connected")


# ===== participant_left handler tests =====


class HandleParticipantLeftTest(TestCase):
    """Tests for _handle_participant_left webhook handler."""

    def setUp(self) -> None:
        users = UserProfile.objects.filter(is_active=True)[:2]
        assert len(users) >= 2
        self.caller = users[0]
        self.callee = users[1]

    def _make_event(self, num_participants: int) -> MagicMock:
        event = MagicMock()
        event.room.num_participants = num_participants
        return event

    def test_both_left_ends_connected_call(self) -> None:
        """Both participants left → call ended with duration."""
        call = CallRecord.objects.create(
            room_name="call-both-left",
            caller=self.caller,
            callee=self.callee,
            status="connected",
            answered_at=timezone.now(),
        )

        event = self._make_event(0)
        _handle_participant_left("call-both-left", event)

        call.refresh_from_db()
        self.assertEqual(call.status, "ended")
        self.assertIsNotNone(call.ended_at)
        self.assertIsNotNone(call.duration_seconds)
        self.assertEqual(call.end_reason, "room_empty")

    def test_one_still_in_room_no_action(self) -> None:
        """One participant still in room — no action."""
        call = CallRecord.objects.create(
            room_name="call-one-left",
            caller=self.caller,
            callee=self.callee,
            status="connected",
            answered_at=timezone.now(),
        )

        event = self._make_event(1)
        _handle_participant_left("call-one-left", event)

        call.refresh_from_db()
        self.assertEqual(call.status, "connected")

    def test_already_ended_idempotent(self) -> None:
        """Already ended call — no change."""
        call = CallRecord.objects.create(
            room_name="call-already-ended",
            caller=self.caller,
            callee=self.callee,
            status="ended",
            ended_at=timezone.now(),
            end_reason="caller_hangup",
            duration_seconds=60,
        )

        event = self._make_event(0)
        _handle_participant_left("call-already-ended", event)

        call.refresh_from_db()
        self.assertEqual(call.status, "ended")
        self.assertEqual(call.end_reason, "caller_hangup")
        self.assertEqual(call.duration_seconds, 60)

    def test_ringing_call_not_ended_by_participant_left(self) -> None:
        """Ringing call not ended by participant_left (room_finished handles that)."""
        call = CallRecord.objects.create(
            room_name="call-ringing-left",
            caller=self.caller,
            callee=self.callee,
            status="ringing",
        )

        event = self._make_event(0)
        _handle_participant_left("call-ringing-left", event)

        call.refresh_from_db()
        self.assertEqual(call.status, "ringing")


# ===== DM message integration tests for decline/cancel =====


MOCK_LIVEKIT_ENV_FOR_CALLS = {
    "LIVEKIT_URL": "wss://test.livekit.cloud",
    "LIVEKIT_API_KEY": "test-api-key",
    "LIVEKIT_API_SECRET": "test-api-secret-that-is-long-enough-for-hs256-algorithm",
}


class CallEventDmMessageTest(ZulipTestCase):
    """Tests that decline and cancel insert DM event messages."""

    def setUp(self) -> None:
        super().setUp()
        self.caller = self.example_user("hamlet")
        self.callee = self.example_user("othello")

    def _auth_headers(self, user: UserProfile) -> dict[str, str]:
        cred = base64.b64encode(f"{user.delivery_email}:{user.api_key}".encode()).decode()
        return {"HTTP_AUTHORIZATION": f"Basic {cred}"}

    def _create_ringing_call(self) -> CallRecord:
        return CallRecord.objects.create(
            room_name=f"call-{uuid.uuid4()}",
            caller=self.caller,
            callee=self.callee,
            status="ringing",
        )

    @patch("zproject.nodl.views.calls.insert_call_event_message")
    def test_decline_inserts_dm_message(self, mock_msg: MagicMock) -> None:
        call = self._create_ringing_call()

        result = self.client_post(
            f"/nodl/calls/{call.id}/decline",
            content_type="application/json",
            **self._auth_headers(self.callee),
        )
        self.assertEqual(result.status_code, 200)

        mock_msg.assert_called_once()
        args = mock_msg.call_args[0]
        self.assertEqual(args[2], "Voice call declined")

    @patch("zproject.nodl.views.calls.insert_call_event_message")
    def test_cancel_inserts_dm_message(self, mock_msg: MagicMock) -> None:
        call = self._create_ringing_call()

        result = self.client_post(
            f"/nodl/calls/{call.id}/cancel",
            content_type="application/json",
            **self._auth_headers(self.caller),
        )
        self.assertEqual(result.status_code, 200)

        mock_msg.assert_called_once()
        args = mock_msg.call_args[0]
        self.assertEqual(args[2], "Voice call cancelled")

    @patch("zproject.nodl.views.calls.insert_call_event_message")
    def test_decline_wrong_state_no_message(self, mock_msg: MagicMock) -> None:
        """Decline on non-ringing call doesn't insert message."""
        call = CallRecord.objects.create(
            room_name=f"call-{uuid.uuid4()}",
            caller=self.caller,
            callee=self.callee,
            status="connected",
            answered_at=timezone.now(),
        )

        result = self.client_post(
            f"/nodl/calls/{call.id}/decline",
            content_type="application/json",
            **self._auth_headers(self.callee),
        )
        self.assertEqual(result.status_code, 409)
        mock_msg.assert_not_called()
