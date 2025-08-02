import uuid
from datetime import timedelta

import orjson
import responses
from django.conf import settings
from django.test import override_settings
from django.utils.timezone import now
from nacl.encoding import Base64Encoder
from nacl.public import PublicKey, SealedBox

from zerver.lib.exceptions import (
    InvalidBouncerPublicKeyError,
    InvalidEncryptedPushRegistrationError,
    RequestExpiredError,
)
from zerver.lib.queue import queue_event_on_commit
from zerver.lib.test_classes import BouncerTestCase
from zerver.lib.test_helpers import activate_push_notification_service, mock_queue_publish
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import PushDevice
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
            "push_account_id": 2408,
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
        response_dict = self.assert_json_success(result)
        device_id = response_dict["device_id"]

        remote_push_devices = RemotePushDevice.objects.all()
        self.assert_length(remote_push_devices, 1)
        self.assertEqual(device_id, remote_push_devices[0].device_id)

        # Idempotent
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/e2ee/register",
            payload,
        )
        response_dict = self.assert_json_success(result)
        self.assertEqual(response_dict["device_id"], device_id)
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
        response_dict = self.assert_json_success(result)
        device_id = response_dict["device_id"]

        remote_push_devices = RemotePushDevice.objects.order_by("pk")
        self.assert_length(remote_push_devices, 2)
        self.assertEqual(device_id, remote_push_devices[1].device_id)

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


class RegisterPushDeviceToServer(BouncerTestCase):
    def get_register_push_device_payload(
        self,
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

        assert settings.PUSH_REGISTRATION_ENCRYPTION_KEYS
        public_key_str: str = next(iter(settings.PUSH_REGISTRATION_ENCRYPTION_KEYS.keys()))
        public_key = PublicKey(public_key_str.encode("utf-8"), Base64Encoder)
        sealed_box = SealedBox(public_key)
        encrypted_push_registration_bytes = sealed_box.encrypt(
            orjson.dumps(push_registration), Base64Encoder
        )
        encrypted_push_registration = encrypted_push_registration_bytes.decode("utf-8")

        payload: dict[str, str | int] = {
            "token_kind": token_kind,
            "push_account_id": 2408,
            "push_public_key": "push-public-key",
            "bouncer_public_key": public_key_str,
            "encrypted_push_registration": encrypted_push_registration,
        }
        return payload

    @activate_push_notification_service()
    @responses.activate
    def test_register_push_device_success(self) -> None:
        self.add_mock_response()
        self.login("hamlet")

        push_devices_count = PushDevice.objects.count()
        self.assertEqual(push_devices_count, 0)

        payload = self.get_register_push_device_payload()

        # Verify the created `PushDevice` row while the
        # `register_push_device_to_bouncer` event is still not
        # consumed by the `PushNotificationsWorker` worker.
        with mock_queue_publish("zerver.views.push_notifications.queue_event_on_commit") as m:
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        m.assert_called_once()
        push_devices = PushDevice.objects.all()
        self.assert_length(push_devices, 1)
        self.assertIsNone(push_devices[0].bouncer_device_id)
        self.assertEqual(push_devices[0].status, "pending")

        queue_name = m.call_args[0][0]
        queue_message = m.call_args[0][1]

        # Now, the `PushNotificationsWorker` worker consumes.
        with self.capture_send_event_calls(expected_num_events=1) as events:
            queue_event_on_commit(queue_name, queue_message)
        push_devices = PushDevice.objects.all()
        self.assert_length(push_devices, 1)
        self.assertIsNotNone(push_devices[0].bouncer_device_id)
        self.assertEqual(push_devices[0].status, "active")
        self.assertEqual(
            events[0]["event"],
            dict(type="push_device", push_account_id="2408", status="active"),
        )

        # Idempotent
        with self.capture_send_event_calls(expected_num_events=0):
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        push_devices = PushDevice.objects.all()
        self.assert_length(push_devices, 1)

        # For self-hosted servers. They make a network call to bouncer
        # instead of a `do_register_remote_push_device` function call.
        with (
            self.settings(ZILENCER_ENABLED=False),
            self.capture_send_event_calls(expected_num_events=1) as events,
        ):
            payload["push_account_id"] = 5555
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        push_devices = PushDevice.objects.order_by("pk")
        self.assert_length(push_devices, 2)
        self.assertIsNotNone(push_devices[1].bouncer_device_id)
        self.assertEqual(push_devices[1].status, "active")
        self.assertEqual(
            events[0]["event"],
            dict(type="push_device", push_account_id="5555", status="active"),
        )

    @override_settings(ZILENCER_ENABLED=False)
    def test_server_not_configured_for_push_notification_error(self) -> None:
        self.login("hamlet")
        payload = self.get_register_push_device_payload()

        result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_error(result, "Server is not configured to use push notification service.")

    @activate_push_notification_service()
    @override_settings(ZILENCER_ENABLED=False)
    @responses.activate
    def test_invalid_bouncer_public_key_error(self) -> None:
        self.add_mock_response()
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        push_devices_count = PushDevice.objects.count()
        self.assertEqual(push_devices_count, 0)

        payload = self.get_register_push_device_payload()

        # Verify InvalidBouncerPublicKeyError
        invalid_bouncer_public_key_payload = {**payload, "bouncer_public_key": "invalid public key"}
        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.client_post(
                "/json/mobile_push/register", invalid_bouncer_public_key_payload
            )
        self.assert_json_success(result)
        push_devices = PushDevice.objects.all()
        self.assert_length(push_devices, 1)
        self.assertEqual(push_devices[0].error_code, InvalidBouncerPublicKeyError.code.name)
        self.assertEqual(push_devices[0].status, "failed")
        self.assertEqual(
            events[0]["event"],
            dict(
                type="push_device",
                push_account_id="2408",
                status="failed",
                error_code="INVALID_BOUNCER_PUBLIC_KEY",
            ),
        )

        # Retrying with correct payload results in success.
        # `error_code` of the same PushDevice row updated to None.
        with self.capture_send_event_calls(expected_num_events=1):
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        push_devices = PushDevice.objects.all()
        self.assert_length(push_devices, 1)
        self.assertIsNone(push_devices[0].error_code)
        self.assertEqual(push_devices[0].status, "active")

    @activate_push_notification_service()
    @override_settings(ZILENCER_ENABLED=False)
    @responses.activate
    def test_invalid_encrypted_push_registration_error(self) -> None:
        self.add_mock_response()
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        push_devices_count = PushDevice.objects.count()
        self.assertEqual(push_devices_count, 0)

        # Verify InvalidEncryptedPushRegistrationError
        invalid_token_payload = self.get_register_push_device_payload(token="")
        with self.capture_send_event_calls(expected_num_events=1) as events:
            result = self.client_post("/json/mobile_push/register", invalid_token_payload)
        self.assert_json_success(result)
        push_devices = PushDevice.objects.all()
        self.assert_length(push_devices, 1)
        self.assertEqual(
            push_devices[0].error_code, InvalidEncryptedPushRegistrationError.code.name
        )
        self.assertEqual(
            events[0]["event"],
            dict(
                type="push_device",
                push_account_id="2408",
                status="failed",
                error_code="BAD_REQUEST",
            ),
        )

    @activate_push_notification_service()
    @override_settings(ZILENCER_ENABLED=False)
    @responses.activate
    def test_request_expired_error(self) -> None:
        self.add_mock_response()
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        push_devices_count = PushDevice.objects.count()
        self.assertEqual(push_devices_count, 0)

        # Verify RequestExpiredError
        liveness_timed_out_payload = self.get_register_push_device_payload(
            timestamp=datetime_to_timestamp(now() - timedelta(days=2))
        )
        with (
            self.assertLogs(level="ERROR") as m,
            self.capture_send_event_calls(expected_num_events=1) as events,
        ):
            result = self.client_post("/json/mobile_push/register", liveness_timed_out_payload)
        self.assert_json_success(result)
        push_devices = PushDevice.objects.all()
        self.assert_length(push_devices, 1)
        self.assertEqual(push_devices[0].error_code, RequestExpiredError.code.name)
        self.assertEqual(
            events[0]["event"],
            dict(
                type="push_device",
                push_account_id="2408",
                status="failed",
                error_code="REQUEST_EXPIRED",
            ),
        )
        self.assertEqual(
            m.output,
            [
                f"ERROR:root:Push device registration request for user_id={hamlet.id}, push_account_id=2408 expired."
            ],
        )

    @activate_push_notification_service()
    @override_settings(ZILENCER_ENABLED=False)
    @responses.activate
    def test_missing_remote_realm_error(self) -> None:
        self.add_mock_response()
        hamlet = self.example_user("hamlet")
        self.login_user(hamlet)

        push_devices_count = PushDevice.objects.count()
        self.assertEqual(push_devices_count, 0)

        payload = self.get_register_push_device_payload()

        # Verify MissingRemoteRealm
        # Update realm's UUID to a random UUID.
        hamlet.realm.uuid = uuid.uuid4()
        hamlet.realm.save()

        with (
            self.assertLogs(level="ERROR") as m,
            self.capture_send_event_calls(expected_num_events=0),
        ):
            result = self.client_post("/json/mobile_push/register", payload)
        self.assert_json_success(result)
        push_devices = PushDevice.objects.all()
        self.assert_length(push_devices, 1)
        # We keep retrying until `RequestExpiredError` is raised.
        self.assertEqual(push_devices[0].status, "pending")
        self.assertEqual(
            m.output[0],
            f"ERROR:root:Push device registration request for user_id={hamlet.id}, push_account_id=2408 failed.",
        )

        # TODO: Verify that we retry for a day, then raise `RequestExpiredError`.
        # This implementation would be a follow-up. Currently `retry_event`
        # leads to 3 retries at max.
