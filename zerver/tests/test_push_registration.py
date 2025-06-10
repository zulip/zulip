import uuid
from datetime import timedelta

import orjson
from django.conf import settings
from django.utils.timezone import now
from nacl.encoding import Base64Encoder
from nacl.public import PublicKey, SealedBox

from zerver.lib.test_classes import BouncerTestCase
from zerver.lib.timestamp import datetime_to_timestamp
from zilencer.models import RemotePushDevice, RemoteRealm


class RegisterPushDeviceToBouncer(BouncerTestCase):
    DEFAULT_SUBDOMAIN = ""

    def get_register_push_device_payload(
        self,
        token: str = "apple-tokenaz",
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
