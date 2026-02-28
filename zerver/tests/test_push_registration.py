import base64
import hashlib
import uuid
from datetime import timedelta

import orjson
import responses
import time_machine
from django.conf import settings
from django.test import override_settings
from django.utils.timezone import now
from nacl.encoding import Base64Encoder
from nacl.public import PublicKey, SealedBox

from zerver.lib.devices import b64decode_token_id_base64
from zerver.lib.exceptions import (
    InvalidBouncerPublicKeyError,
    InvalidEncryptedPushRegistrationError,
    RequestExpiredError,
)
from zerver.lib.push_registration import check_push_key
from zerver.lib.queue import queue_event_on_commit
from zerver.lib.test_classes import BouncerTestCase
from zerver.lib.test_helpers import activate_push_notification_service, mock_queue_publish
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import Device, UserProfile
from zilencer.models import RemotePushDevice, RemoteRealm


class RegisterPushDeviceToBouncer(BouncerTestCase):
    DEFAULT_SUBDOMAIN = ""

    def get_register_push_device_payload(
        self,
        token: str = "c0ffee",
        token_kind: str = RemotePushDevice.TokenKind.APNS,
        ios_app_id: str | None = "example.app",
        timestamp: int | None = None,
    ) -> dict[str, str | int]:
        hamlet = self.example_user("hamlet")
        remote_realm = RemoteRealm.objects.get(uuid=hamlet.realm.uuid)

        if timestamp is None:
            timestamp = datetime_to_timestamp(now())

        push_registration = {
            "token": token,
            "token_kind": token_kind,
            "ios_app_id": ios_app_id,
            "timestamp": timestamp,
        }

        hash_bytes = hashlib.sha256(token.encode()).digest()
        token_id_base64 = base64.b64encode(hash_bytes[0:8]).decode()

        assert settings.PUSH_REGISTRATION_ENCRYPTION_KEYS
        public_key_str: str = next(iter(settings.PUSH_REGISTRATION_ENCRYPTION_KEYS.keys()))
        public_key = PublicKey(public_key_str.encode("utf-8"), Base64Encoder)
        sealed_box = SealedBox(public_key)
        encrypted_push_registration_bytes = sealed_box.encrypt(
            orjson.dumps(push_registration), Base64Encoder
        )
        encrypted_push_registration = encrypted_push_registration_bytes.decode("utf-8")

        payload: dict[str, str | int] = {
            "realm_uuid": str(remote_realm.uuid),
            "token_id": token_id_base64,
            "encrypted_push_registration": encrypted_push_registration,
            "bouncer_public_key": public_key_str,
        }
        return payload

    def test_register_push_device_success(self) -> None:
        remote_push_devices_count = RemotePushDevice.objects.count()
        self.assertEqual(remote_push_devices_count, 0)

        payload = self.get_register_push_device_payload()

        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            payload,
        )
        self.assert_json_success(result)

        remote_push_devices = RemotePushDevice.objects.all()
        self.assert_length(remote_push_devices, 1)
        assert type(payload["token_id"]) is str  # for mypy
        self.assertEqual(
            remote_push_devices[0].token_id, b64decode_token_id_base64(payload["token_id"])
        )

        # Idempotent
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            payload,
        )
        self.assert_json_success(result)
        remote_push_devices_count = RemotePushDevice.objects.count()
        self.assertEqual(remote_push_devices_count, 1)

        # Android
        payload = self.get_register_push_device_payload(
            token="android-tokenaz", token_kind=RemotePushDevice.TokenKind.FCM, ios_app_id=None
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            payload,
        )
        self.assert_json_success(result)

        remote_push_devices = RemotePushDevice.objects.order_by("pk")
        self.assert_length(remote_push_devices, 2)
        assert type(payload["token_id"]) is str  # for mypy
        self.assertEqual(
            remote_push_devices[1].token_id, b64decode_token_id_base64(payload["token_id"])
        )

    def test_register_push_device_error(self) -> None:
        payload = self.get_register_push_device_payload()

        invalid_realm_uuid_payload = {**payload, "realm_uuid": str(uuid.uuid4())}
        with self.assertLogs("zilencer.views", level="INFO"):
            result = self.uuid_post(
                self.server_uuid,
                "/api/v1/remotes/push/e2ee/register",
                invalid_realm_uuid_payload,
            )
        self.assert_json_error(result, "Organization not registered", status_code=403)

        invalid_bouncer_public_key_payload = {**payload, "bouncer_public_key": "invalid public key"}
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            invalid_bouncer_public_key_payload,
        )
        self.assert_json_error(result, "Invalid bouncer_public_key")

        liveness_timedout_payload = self.get_register_push_device_payload(
            timestamp=datetime_to_timestamp(now() - timedelta(days=2))
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            liveness_timedout_payload,
        )
        self.assert_json_error(result, "Request expired")

        # Test the various cases resulting in InvalidEncryptedPushRegistrationError
        payload = self.get_register_push_device_payload()
        payload["encrypted_push_registration"] = "random-string-no-encryption"
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            payload,
        )
        self.assert_json_error(result, "Invalid encrypted_push_registration")

        invalid_ios_app_id_format_payload = self.get_register_push_device_payload(
            ios_app_id="* -- +"
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            invalid_ios_app_id_format_payload,
        )
        self.assert_json_error(result, "Invalid encrypted_push_registration")

        invalid_token_kind_payload = self.get_register_push_device_payload(token_kind="xyz")
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            invalid_token_kind_payload,
        )
        self.assert_json_error(result, "Invalid encrypted_push_registration")

        missing_ios_app_id_payload = self.get_register_push_device_payload(ios_app_id=None)
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            missing_ios_app_id_payload,
        )
        self.assert_json_error(result, "Invalid encrypted_push_registration")

        set_ios_app_id_for_android_payload = self.get_register_push_device_payload(
            token_kind=RemotePushDevice.TokenKind.FCM, ios_app_id="not-null"
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            set_ios_app_id_for_android_payload,
        )
        self.assert_json_error(result, "Invalid encrypted_push_registration")

        invalid_token_payload = self.get_register_push_device_payload(token="")
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            invalid_token_payload,
        )
        self.assert_json_error(result, "Invalid encrypted_push_registration")

        invalid_token_payload = self.get_register_push_device_payload(
            token="xyz non-hex characters"
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            invalid_token_payload,
        )
        self.assert_json_error(result, "Invalid encrypted_push_registration")

        # Invalid `token_id`
        payload = self.get_register_push_device_payload()
        payload["token_id"] = "192057"
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            payload,
        )
        self.assert_json_error(result, "Invalid encrypted_push_registration")


class RegisterPushDeviceToServer(BouncerTestCase):
    def get_register_push_device_payload(
        self,
        device_user: UserProfile | None = None,
        token: str = "c0ffee",
        token_kind: str = RemotePushDevice.TokenKind.APNS,
        ios_app_id: str | None = "example.app",
        timestamp: int | None = None,
    ) -> dict[str, str | int]:
        if timestamp is None:
            timestamp = datetime_to_timestamp(now())

        push_registration = {
            "token": token,
            "token_kind": token_kind,
            "ios_app_id": ios_app_id,
            "timestamp": timestamp,
        }

        hash_bytes = hashlib.sha256(token.encode()).digest()
        token_id_base64 = base64.b64encode(hash_bytes[0:8]).decode()

        assert settings.PUSH_REGISTRATION_ENCRYPTION_KEYS
        public_key_str: str = next(iter(settings.PUSH_REGISTRATION_ENCRYPTION_KEYS.keys()))
        public_key = PublicKey(public_key_str.encode("utf-8"), Base64Encoder)
        sealed_box = SealedBox(public_key)
        encrypted_push_registration_bytes = sealed_box.encrypt(
            orjson.dumps(push_registration), Base64Encoder
        )
        encrypted_push_registration = encrypted_push_registration_bytes.decode("utf-8")

        if device_user is None:
            device_user = self.example_user("hamlet")
        device = Device.objects.create(user=device_user)

        payload: dict[str, str | int] = {
            "device_id": device.id,
            "token_kind": token_kind,
            "push_key": "MY+paNlyduYJRQFNZva8w7Gv3PkBua9kIj581F9Vr301",
            "push_key_id": 2408,
            "bouncer_public_key": public_key_str,
            "encrypted_push_registration": encrypted_push_registration,
            "token_id": token_id_base64,
        }
        return payload

    def assert_push_fields_null(self, device: Device) -> None:
        self.assertIsNone(device.push_key)
        self.assertIsNone(device.push_key_id)
        self.assertIsNone(device.push_token_id)
        self.assertIsNone(device.pending_push_token_id)
        self.assertIsNone(device.push_token_kind)
        self.assertIsNone(device.push_token_last_updated_timestamp)
        self.assertIsNone(device.push_registration_error_code)

    def test_register_push_device_success(self) -> None:
        self.login("hamlet")

        payload = self.get_register_push_device_payload()

        devices = Device.objects.all()
        self.assert_length(devices, 1)
        self.assert_push_fields_null(devices[0])

        # Verify the updated `Device` row and `device` event
        # while the `register_push_device_to_bouncer` event is still
        # not consumed by the `PushNotificationsWorker` worker.
        time_now = now()
        with (
            time_machine.travel(time_now, tick=False),
            self.capture_send_event_calls(expected_num_events=1) as events,
            mock_queue_publish("zerver.views.push_notifications.queue_event_on_commit") as m,
        ):
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        m.assert_called_once()
        devices = Device.objects.all()
        self.assert_length(devices, 1)
        device = devices[0]
        self.assertEqual(device.push_key_id, payload["push_key_id"])
        self.assertIsNone(device.push_token_id)
        assert type(payload["token_id"]) is str  # for mypy
        self.assertEqual(
            device.pending_push_token_id, b64decode_token_id_base64(payload["token_id"])
        )
        self.assertEqual(device.push_token_kind, payload["token_kind"])
        self.assertEqual(device.push_token_last_updated_timestamp, time_now)
        self.assertIsNone(device.push_registration_error_code)
        self.assertEqual(
            events[0]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_key_id=device.push_key_id,
                pending_push_token_id=payload["token_id"],
                push_token_last_updated_timestamp=datetime_to_timestamp(time_now),
                push_registration_error_code=None,
            ),
        )

        queue_name = m.call_args[0][0]
        queue_message = m.call_args[0][1]

        # Now, the `PushNotificationsWorker` worker consumes.
        with self.capture_send_event_calls(expected_num_events=1) as events:
            queue_event_on_commit(queue_name, queue_message)
        device.refresh_from_db()
        assert type(payload["token_id"]) is str  # for mypy
        self.assertEqual(device.push_token_id, b64decode_token_id_base64(payload["token_id"]))
        self.assertIsNone(device.pending_push_token_id)
        self.assertEqual(
            events[0]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_token_id=payload["token_id"],
                pending_push_token_id=None,
            ),
        )

        # Idempotent
        with self.capture_send_event_calls(expected_num_events=0):
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        pending_push_devices_count = Device.objects.filter(
            pending_push_token_id__isnull=False
        ).count()
        self.assertEqual(pending_push_devices_count, 0)

    @activate_push_notification_service()
    @responses.activate
    @override_settings(ZILENCER_ENABLED=False)
    def test_register_push_device_self_hosted_server_success(self) -> None:
        """
        Self-hosted servers make a network call to bouncer instead of
        a `do_register_remote_push_device` function call.
        """
        self.add_mock_response()
        self.login("hamlet")

        payload = self.get_register_push_device_payload()

        devices = Device.objects.all()
        self.assert_length(devices, 1)
        self.assert_push_fields_null(devices[0])

        time_now = now()
        with (
            time_machine.travel(time_now, tick=False),
            self.capture_send_event_calls(expected_num_events=2) as events,
        ):
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        devices = Device.objects.all()
        self.assert_length(devices, 1)
        device = devices[0]
        self.assertEqual(device.push_key_id, payload["push_key_id"])
        assert type(payload["token_id"]) is str  # for mypy
        self.assertEqual(device.push_token_id, b64decode_token_id_base64(payload["token_id"]))
        self.assertIsNone(device.pending_push_token_id)
        self.assertEqual(device.push_token_kind, payload["token_kind"])
        self.assertEqual(device.push_token_last_updated_timestamp, time_now)
        self.assertIsNone(device.push_registration_error_code)
        self.assertEqual(
            events[0]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_key_id=device.push_key_id,
                pending_push_token_id=payload["token_id"],
                push_token_last_updated_timestamp=datetime_to_timestamp(time_now),
                push_registration_error_code=None,
            ),
        )
        self.assertEqual(
            events[1]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_token_id=payload["token_id"],
                pending_push_token_id=None,
            ),
        )

    @override_settings(ZILENCER_ENABLED=False)
    def test_server_not_configured_for_push_notification_error(self) -> None:
        self.login("hamlet")
        payload = self.get_register_push_device_payload()

        result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_error(result, "Server is not configured to use push notification service.")

    @activate_push_notification_service()
    def test_invalid_device_error(self) -> None:
        self.login("hamlet")
        iago = self.example_user("iago")
        payload = self.get_register_push_device_payload(device_user=iago)

        result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_error(result, "Invalid `device_id`")

    @activate_push_notification_service()
    def test_missing_parameters_error(self) -> None:
        self.login("hamlet")
        payload = self.get_register_push_device_payload()

        # Payload not good for push key rotation, token rotation, or fresh registration.
        del payload["push_key_id"]
        del payload["token_id"]

        result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_error(
            result,
            "Missing parameters: must provide either all push key fields, all token fields, or both.",
        )

    @activate_push_notification_service()
    def test_invalid_push_key_error(self) -> None:
        self.login("hamlet")
        payload = self.get_register_push_device_payload()

        # Invalid Base64 alphabet in `push_key`
        invalid_push_key_payload = {**payload, "push_key": "@abcdefg"}
        result = self.client_post("/json/mobile_push/register", invalid_push_key_payload)
        self.assert_json_error(result, "Invalid `push_key`")

        # Value (which is base64 encoded to get `push_key`) is not 33 bytes in size
        invalid_push_key_payload = {**payload, "push_key": "abcd"}
        result = self.client_post("/json/mobile_push/register", invalid_push_key_payload)
        self.assert_json_error(result, "Invalid `push_key`")

        # Verify error when prefix (1st byte) is not 0x31
        push_key = payload["push_key"]
        assert type(push_key) is str  # for mypy
        valid_push_key_bytes = base64.b64decode(push_key)
        self.assertEqual(valid_push_key_bytes[0], 0x31)
        self.assert_length(valid_push_key_bytes, 33)
        # Note: Prefix changed to 0x32
        invalid_push_key_bytes = bytes([0x32]) + valid_push_key_bytes[1:]
        invalid_push_key = base64.b64encode(invalid_push_key_bytes).decode("utf-8")
        invalid_push_key_payload = {**payload, "push_key": invalid_push_key}
        result = self.client_post("/json/mobile_push/register", invalid_push_key_payload)
        self.assert_json_error(result, "Invalid `push_key`")

    @activate_push_notification_service()
    def test_invalid_push_key_id_error(self) -> None:
        self.login("hamlet")
        payload = self.get_register_push_device_payload()

        # Test negative push_key_id
        invalid_push_key_id_payload = {**payload, "push_key_id": -1}
        result = self.client_post("/json/mobile_push/register", invalid_push_key_id_payload)
        self.assert_json_error(
            result, "Invalid push_key_id: Value error, Not a valid unsigned 32-bit integer"
        )

        # Test push_key_id > 2^32 - 1
        invalid_push_key_id_payload = {**payload, "push_key_id": 4294967296}
        result = self.client_post("/json/mobile_push/register", invalid_push_key_id_payload)
        self.assert_json_error(
            result, "Invalid push_key_id: Value error, Not a valid unsigned 32-bit integer"
        )

    @activate_push_notification_service()
    def test_invalid_token_id_error(self) -> None:
        self.login("hamlet")
        payload = self.get_register_push_device_payload()

        # Invalid Base64 alphabet in `token_id`
        invalid_token_id_payload = {**payload, "token_id": "@abcdefg"}
        result = self.client_post("/json/mobile_push/register", invalid_token_id_payload)
        self.assert_json_error(result, "`token_id` is not Base64 encoded")

    @activate_push_notification_service()
    @override_settings(ZILENCER_ENABLED=False)
    @responses.activate
    def test_invalid_bouncer_public_key_error(self) -> None:
        self.add_mock_response()
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        payload = self.get_register_push_device_payload()

        devices = Device.objects.all()
        self.assert_length(devices, 1)
        self.assert_push_fields_null(devices[0])

        # Verify InvalidBouncerPublicKeyError
        time_now = now()
        invalid_bouncer_public_key_payload = {**payload, "bouncer_public_key": "invalid public key"}
        with (
            time_machine.travel(time_now, tick=False),
            self.capture_send_event_calls(expected_num_events=2) as events,
        ):
            result = self.client_post(
                "/json/mobile_push/register", invalid_bouncer_public_key_payload
            )
        self.assert_json_success(result)
        devices = Device.objects.all()
        self.assert_length(devices, 1)
        device = devices[0]
        self.assertEqual(
            device.push_registration_error_code, InvalidBouncerPublicKeyError.code.name
        )
        self.assertEqual(
            events[0]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_key_id=device.push_key_id,
                pending_push_token_id=payload["token_id"],
                push_token_last_updated_timestamp=datetime_to_timestamp(time_now),
                push_registration_error_code=None,
            ),
        )
        self.assertEqual(
            events[1]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_registration_error_code="INVALID_BOUNCER_PUBLIC_KEY",
            ),
        )

        # Retrying with correct payload results in success.
        # `push_registration_error_code` of the same Device row updated to None.
        with (
            time_machine.travel(time_now, tick=False),
            self.capture_send_event_calls(expected_num_events=2) as events,
        ):
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        device.refresh_from_db()
        self.assertIsNone(device.push_registration_error_code)
        assert type(payload["token_id"]) is str  # for mypy
        self.assertEqual(device.push_token_id, b64decode_token_id_base64(payload["token_id"]))
        self.assertIsNone(device.pending_push_token_id)
        self.assertEqual(
            events[0]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_key_id=device.push_key_id,
                pending_push_token_id=payload["token_id"],
                push_token_last_updated_timestamp=datetime_to_timestamp(time_now),
                push_registration_error_code=None,
            ),
        )
        self.assertEqual(
            events[1]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_token_id=payload["token_id"],
                pending_push_token_id=None,
            ),
        )

    @activate_push_notification_service()
    @override_settings(ZILENCER_ENABLED=False)
    @responses.activate
    def test_invalid_encrypted_push_registration_error(self) -> None:
        self.add_mock_response()
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        invalid_token_payload = self.get_register_push_device_payload(token="")

        devices = Device.objects.all()
        self.assert_length(devices, 1)
        self.assert_push_fields_null(devices[0])

        # Verify InvalidEncryptedPushRegistrationError
        time_now = now()
        with (
            time_machine.travel(time_now, tick=False),
            self.capture_send_event_calls(expected_num_events=2) as events,
        ):
            result = self.client_post("/json/mobile_push/register", invalid_token_payload)
        self.assert_json_success(result)
        devices = Device.objects.all()
        self.assert_length(devices, 1)
        device = devices[0]
        self.assertEqual(
            device.push_registration_error_code, InvalidEncryptedPushRegistrationError.code.name
        )
        self.assertEqual(
            events[0]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_key_id=device.push_key_id,
                pending_push_token_id=invalid_token_payload["token_id"],
                push_token_last_updated_timestamp=datetime_to_timestamp(time_now),
                push_registration_error_code=None,
            ),
        )
        self.assertEqual(
            events[1]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_registration_error_code="BAD_REQUEST",
            ),
        )

    @activate_push_notification_service()
    @override_settings(ZILENCER_ENABLED=False)
    @responses.activate
    def test_request_expired_error(self) -> None:
        self.add_mock_response()
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        liveness_timed_out_payload = self.get_register_push_device_payload(
            timestamp=datetime_to_timestamp(now() - timedelta(days=2))
        )

        devices = Device.objects.all()
        self.assert_length(devices, 1)
        self.assert_push_fields_null(devices[0])

        # Verify RequestExpiredError
        time_now = now()
        with (
            time_machine.travel(time_now, tick=False),
            self.assertLogs(level="ERROR") as m,
            self.capture_send_event_calls(expected_num_events=2) as events,
        ):
            result = self.client_post("/json/mobile_push/register", liveness_timed_out_payload)
        self.assert_json_success(result)
        devices = Device.objects.all()
        self.assert_length(devices, 1)
        device = devices[0]
        self.assertEqual(device.push_registration_error_code, RequestExpiredError.code.name)
        self.assertEqual(
            events[0]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_key_id=device.push_key_id,
                pending_push_token_id=liveness_timed_out_payload["token_id"],
                push_token_last_updated_timestamp=datetime_to_timestamp(time_now),
                push_registration_error_code=None,
            ),
        )
        self.assertEqual(
            events[1]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_registration_error_code="REQUEST_EXPIRED",
            ),
        )
        self.assertEqual(
            m.output,
            [f"ERROR:root:Push registration request for device_id={device.id} expired."],
        )

    @activate_push_notification_service()
    @override_settings(ZILENCER_ENABLED=False)
    @responses.activate
    def test_missing_remote_realm_error(self) -> None:
        self.add_mock_response()
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        payload = self.get_register_push_device_payload()

        devices = Device.objects.all()
        self.assert_length(devices, 1)
        self.assert_push_fields_null(devices[0])

        # Verify MissingRemoteRealm
        # Update realm's UUID to a random UUID.
        hamlet.realm.uuid = uuid.uuid4()
        hamlet.realm.save()

        time_now = now()
        with (
            time_machine.travel(time_now, tick=False),
            self.assertLogs(level="ERROR") as m,
            self.capture_send_event_calls(expected_num_events=1) as events,
        ):
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        devices = Device.objects.all()
        self.assert_length(devices, 1)
        device = devices[0]
        # We keep retrying until `RequestExpiredError` is raised.
        self.assertIsNotNone(device.pending_push_token_id)
        self.assertIsNone(device.push_registration_error_code)
        self.assertEqual(
            events[0]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_key_id=device.push_key_id,
                pending_push_token_id=payload["token_id"],
                push_token_last_updated_timestamp=datetime_to_timestamp(time_now),
                push_registration_error_code=None,
            ),
        )
        self.assertEqual(
            m.output[0],
            f"ERROR:root:Push device registration request for device_id={device.id} failed.",
        )

        # TODO: Verify that we retry for a day, then raise `RequestExpiredError`.
        # This implementation would be a follow-up. Currently `retry_event`
        # leads to 3 retries at max.

    @activate_push_notification_service()
    def test_push_key_rotation(self) -> None:
        self.login("hamlet")
        payload = self.get_register_push_device_payload()
        device = Device.objects.get(id=payload["device_id"])
        self.assert_push_fields_null(device)

        # Attempt to set only `push_key` and `push_key_id` fields.
        rotate_push_key_payload = {
            "device_id": device.id,
            "push_key": "MTaUDJDMWypQ1WufZ1NRTHSSvgYtXh1qVNSjN3aBiEFt",
            "push_key_id": 1144,
        }
        result = self.client_post("/json/mobile_push/register", rotate_push_key_payload)
        self.assert_json_error(result, "No push registration exists to rotate key for.")

        # Fresh push registration.
        with self.capture_send_event_calls(expected_num_events=2):
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        device.refresh_from_db()
        assert device.push_key is not None
        assert type(payload["push_key"]) is str  # for mypy
        self.assertEqual(bytes(device.push_key), check_push_key(payload["push_key"]))
        self.assertEqual(device.push_key_id, payload["push_key_id"])

        # Rotate push key for the registration.
        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.client_post("/json/mobile_push/register", rotate_push_key_payload)
        self.assert_json_success(result)
        device.refresh_from_db()
        assert device.push_key is not None
        assert type(rotate_push_key_payload["push_key"]) is str  # for mypy
        self.assertEqual(
            bytes(device.push_key), check_push_key(rotate_push_key_payload["push_key"])
        )
        self.assertEqual(device.push_key_id, rotate_push_key_payload["push_key_id"])
        self.assertEqual(
            events[0]["event"],
            dict(type="device", op="update", device_id=device.id, push_key_id=device.push_key_id),
        )

        # Idempotent
        with self.capture_send_event_calls(expected_num_events=0):
            result = self.client_post("/json/mobile_push/register", rotate_push_key_payload)
        self.assert_json_success(result)

    @activate_push_notification_service()
    def test_token_rotation(self) -> None:
        self.login("hamlet")
        payload = self.get_register_push_device_payload()
        device = Device.objects.get(id=payload["device_id"])
        self.assert_push_fields_null(device)

        # Attempt to set only token fields.
        push_registration: dict[str, str | int] = {
            "token": "abcdef",
            "token_kind": Device.PushTokenKind.APNS,
            "ios_app_id": "example.app",
            "timestamp": datetime_to_timestamp(now()),
        }
        assert settings.PUSH_REGISTRATION_ENCRYPTION_KEYS
        public_key_str: str = next(iter(settings.PUSH_REGISTRATION_ENCRYPTION_KEYS.keys()))
        public_key = PublicKey(public_key_str.encode("utf-8"), Base64Encoder)
        sealed_box = SealedBox(public_key)
        encrypted_push_registration_bytes = sealed_box.encrypt(
            orjson.dumps(push_registration), Base64Encoder
        )
        encrypted_push_registration = encrypted_push_registration_bytes.decode("utf-8")
        assert type(push_registration["token"]) is str  # for mypy
        hash_bytes = hashlib.sha256(push_registration["token"].encode()).digest()
        token_id_base64 = base64.b64encode(hash_bytes[0:8]).decode()
        rotate_token_payload = {
            "device_id": device.id,
            "token_kind": Device.PushTokenKind.APNS,
            "bouncer_public_key": public_key_str,
            "encrypted_push_registration": encrypted_push_registration,
            "token_id": token_id_base64,
        }
        result = self.client_post("/json/mobile_push/register", rotate_token_payload)
        self.assert_json_error(result, "No push registration exists to rotate token for.")

        # Fresh push registration.
        with self.capture_send_event_calls(expected_num_events=2):
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        device.refresh_from_db()
        assert type(payload["token_id"]) is str  # for mypy
        self.assertEqual(device.push_token_id, b64decode_token_id_base64(payload["token_id"]))

        # Rotate token for the registration.
        time_now = now()
        with (
            time_machine.travel(time_now, tick=False),
            self.capture_send_event_calls(expected_num_events=2) as events,
        ):
            result = self.client_post("/json/mobile_push/register", rotate_token_payload)
        self.assert_json_success(result)
        device.refresh_from_db()
        assert type(rotate_token_payload["token_id"]) is str  # for mypy
        self.assertEqual(
            device.push_token_id, b64decode_token_id_base64(rotate_token_payload["token_id"])
        )
        self.assertEqual(
            events[0]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                pending_push_token_id=rotate_token_payload["token_id"],
                push_token_last_updated_timestamp=datetime_to_timestamp(time_now),
                push_registration_error_code=None,
            ),
        )
        self.assertEqual(
            events[1]["event"],
            dict(
                type="device",
                op="update",
                device_id=device.id,
                push_token_id=rotate_token_payload["token_id"],
                pending_push_token_id=None,
            ),
        )

        # Idempotent
        with self.capture_send_event_calls(expected_num_events=0):
            result = self.client_post("/json/mobile_push/register", rotate_token_payload)
        self.assert_json_success(result)

    @activate_push_notification_service()
    def test_avoid_parallel_registration_request_to_bouncer(self) -> None:
        self.login("hamlet")
        payload = self.get_register_push_device_payload()

        # Fresh registration request, `register_push_device_to_bouncer` event
        # not consumed by the `PushNotificationsWorker` worker yet.
        with (
            self.capture_send_event_calls(expected_num_events=1),
            mock_queue_publish("zerver.views.push_notifications.queue_event_on_commit") as m,
        ):
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        m.assert_called_once()

        # Another registration request is not processed.
        with (
            self.capture_send_event_calls(expected_num_events=0),
            mock_queue_publish("zerver.views.push_notifications.queue_event_on_commit") as m,
        ):
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_error(result, "A registration for the device already in progress.")
        m.assert_not_called()
