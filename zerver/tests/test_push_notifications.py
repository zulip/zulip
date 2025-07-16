import base64
import uuid
from collections.abc import Mapping
from datetime import timedelta
from typing import Any
from unittest import mock, skipUnless

import aioapns
import firebase_admin.messaging as firebase_messaging
import orjson
import requests
import responses
import time_machine
from django.conf import settings
from django.db.models import F, Q
from django.test import override_settings
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from dns.resolver import NoAnswer as DNSNoAnswer
from firebase_admin import exceptions as firebase_exceptions
from requests.exceptions import ConnectionError
from typing_extensions import override

from analytics.models import RealmCount
from zerver.actions.message_flags import do_mark_stream_messages_as_read, do_update_message_flags
from zerver.actions.user_groups import check_add_user_group
from zerver.actions.user_settings import do_regenerate_api_key
from zerver.lib.avatar import absolute_avatar_url, get_avatar_for_inaccessible_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.push_notifications import (
    DeviceToken,
    InvalidRemotePushDeviceTokenError,
    UserPushIdentityCompat,
    get_apns_badge_count,
    get_apns_badge_count_future,
    get_apns_context,
    get_base_payload,
    get_message_payload_apns,
    get_message_payload_gcm,
    get_mobile_push_content,
    modernize_apns_payload,
    parse_fcm_options,
    send_android_push_notification_to_user,
    send_apple_push_notification,
    send_notifications_to_bouncer,
)
from zerver.lib.remote_server import (
    PushNotificationBouncerError,
    PushNotificationBouncerRetryLaterError,
    PushNotificationBouncerServerError,
    get_realms_info_for_push_bouncer,
    prepare_for_registration_transfer_challenge,
    send_to_push_bouncer,
)
from zerver.lib.response import json_response_from_error
from zerver.lib.send_email import FromAddress
from zerver.lib.test_classes import BouncerTestCase, PushNotificationTestCase, ZulipTestCase
from zerver.lib.test_helpers import (
    activate_push_notification_service,
    mock_queue_publish,
    reset_email_visibility_to_everyone_in_zulip_realm,
)
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import (
    Message,
    PushDeviceToken,
    RealmAuditLog,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
)
from zerver.models.clients import get_client
from zerver.models.realm_audit_logs import AuditLogEventType
from zerver.models.realms import get_realm
from zerver.models.recipients import get_or_create_direct_message_group
from zerver.models.scheduled_jobs import NotificationTriggers
from zerver.models.streams import get_stream
from zilencer.auth import (
    REMOTE_SERVER_TAKEOVER_TOKEN_VALIDITY_SECONDS,
    generate_registration_transfer_verification_secret,
)
from zilencer.models import RemoteZulipServerAuditLog
from zilencer.views import DevicesToCleanUpDict

if settings.ZILENCER_ENABLED:
    from zilencer.models import (
        RemotePushDeviceToken,
        RemoteRealm,
        RemoteRealmAuditLog,
        RemoteZulipServer,
    )
    from zilencer.views import update_remote_realm_data_for_server


class SendTestPushNotificationEndpointTest(BouncerTestCase):
    @activate_push_notification_service()
    @responses.activate
    def test_send_test_push_notification_api_invalid_token(self) -> None:
        # What happens when the mobile device isn't registered with its server,
        # and makes a request to this API:
        user = self.example_user("cordelia")
        result = self.api_post(
            user, "/api/v1/mobile_push/test_notification", {"token": "invalid"}, subdomain="zulip"
        )
        self.assert_json_error(result, "Device not recognized")
        self.assertEqual(orjson.loads(result.content)["code"], "INVALID_PUSH_DEVICE_TOKEN")

        # What response the server receives when it makes a request to the bouncer
        # to the /test_notification endpoint:
        payload = {
            "realm_uuid": str(user.realm.uuid),
            "user_uuid": str(user.uuid),
            "user_id": user.id,
            "token": "invalid",
            "token_kind": PushDeviceToken.FCM,
            "base_payload": get_base_payload(user),
        }
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/test_notification",
            payload,
            subdomain="",
            content_type="application/json",
        )
        self.assert_json_error(result, "Device not recognized by the push bouncer")
        self.assertEqual(orjson.loads(result.content)["code"], "INVALID_REMOTE_PUSH_DEVICE_TOKEN")

        # Finally, test the full scenario where the mobile device is registered with its
        # server, but for some reason the server failed to register it with the bouncer.

        token = "111222"
        token_kind = PushDeviceToken.FCM
        # We create a PushDeviceToken object, but no RemotePushDeviceToken object, to simulate
        # a missing registration on the bouncer.
        PushDeviceToken.objects.create(user=user, token=token, kind=token_kind)

        # As verified above, this is the response the server receives from the bouncer in this kind of case.
        # We have to simulate it with a response mock.
        error_response = json_response_from_error(InvalidRemotePushDeviceTokenError())
        responses.add(
            responses.POST,
            f"{settings.ZULIP_SERVICES_URL}/api/v1/remotes/push/test_notification",
            body=error_response.content,
            status=error_response.status_code,
        )

        result = self.api_post(
            user, "/api/v1/mobile_push/test_notification", {"token": token}, subdomain="zulip"
        )
        self.assert_json_error(result, "Device not recognized by the push bouncer")
        self.assertEqual(orjson.loads(result.content)["code"], "INVALID_REMOTE_PUSH_DEVICE_TOKEN")

    def test_send_test_push_notification_api_no_bouncer_config(self) -> None:
        """
        Tests the endpoint on a server that doesn't use the bouncer, due to having its
        own ability to send push notifications to devices directly.
        """
        user = self.example_user("cordelia")

        android_token = "111222"
        android_token_kind = PushDeviceToken.FCM
        apple_token = "111223"
        apple_token_kind = PushDeviceToken.APNS
        android_device = PushDeviceToken.objects.create(
            user=user, token=android_token, kind=android_token_kind
        )
        apple_device = PushDeviceToken.objects.create(
            user=user, token=apple_token, kind=apple_token_kind
        )

        endpoint = "/api/v1/mobile_push/test_notification"
        time_now = now()

        # 1. First test for an android device.
        # 2. Then test for an apple device.
        # 3. Then test without submitting a specific token,
        #    meaning both devices should get notified.

        with (
            mock.patch(
                "zerver.lib.push_notifications.send_android_push_notification"
            ) as mock_send_android_push_notification,
            time_machine.travel(time_now, tick=False),
        ):
            result = self.api_post(user, endpoint, {"token": android_token}, subdomain="zulip")

        expected_android_payload = {
            "server": "testserver",
            "realm_id": user.realm_id,
            "realm_name": "Zulip Dev",
            "realm_uri": "http://zulip.testserver",
            "realm_url": "http://zulip.testserver",
            "user_id": user.id,
            "event": "test",
            "time": datetime_to_timestamp(time_now),
        }
        expected_gcm_options = {"priority": "high"}
        mock_send_android_push_notification.assert_called_once_with(
            UserPushIdentityCompat(user_id=user.id, user_uuid=str(user.uuid)),
            [android_device],
            expected_android_payload,
            expected_gcm_options,
            remote=None,
        )
        self.assert_json_success(result)

        with (
            mock.patch(
                "zerver.lib.push_notifications.send_apple_push_notification"
            ) as mock_send_apple_push_notification,
            time_machine.travel(time_now, tick=False),
        ):
            result = self.api_post(user, endpoint, {"token": apple_token}, subdomain="zulip")

        expected_apple_payload = {
            "alert": {
                "title": "Test notification",
                "body": "This is a test notification from Zulip Dev (http://zulip.testserver).",
            },
            "sound": "default",
            "custom": {
                "zulip": {
                    "server": "testserver",
                    "realm_id": user.realm_id,
                    "realm_name": "Zulip Dev",
                    "realm_uri": "http://zulip.testserver",
                    "realm_url": "http://zulip.testserver",
                    "user_id": user.id,
                    "event": "test",
                }
            },
        }
        mock_send_apple_push_notification.assert_called_once_with(
            UserPushIdentityCompat(user_id=user.id, user_uuid=str(user.uuid)),
            [apple_device],
            expected_apple_payload,
            remote=None,
        )
        self.assert_json_success(result)

        # Test without submitting a token value. Both devices should get notified.
        with (
            mock.patch(
                "zerver.lib.push_notifications.send_apple_push_notification"
            ) as mock_send_apple_push_notification,
            mock.patch(
                "zerver.lib.push_notifications.send_android_push_notification"
            ) as mock_send_android_push_notification,
            time_machine.travel(time_now, tick=False),
        ):
            result = self.api_post(user, endpoint, subdomain="zulip")

        mock_send_android_push_notification.assert_called_once_with(
            UserPushIdentityCompat(user_id=user.id, user_uuid=str(user.uuid)),
            [android_device],
            expected_android_payload,
            expected_gcm_options,
            remote=None,
        )
        mock_send_apple_push_notification.assert_called_once_with(
            UserPushIdentityCompat(user_id=user.id, user_uuid=str(user.uuid)),
            [apple_device],
            expected_apple_payload,
            remote=None,
        )
        self.assert_json_success(result)

    @activate_push_notification_service()
    @responses.activate
    def test_send_test_push_notification_api_with_bouncer_config(self) -> None:
        """
        Tests the endpoint on a server that uses the bouncer. This will simulate the
        end-to-end flow:
        1. First we simulate a request from the mobile device to the remote server's
        endpoint for a test notification.
        2. As a result, the remote server makes a request to the bouncer to send that
        notification.

        We verify that the appropriate function for sending the notification to the
        device is called on the bouncer as the ultimate result of the flow.
        """

        self.add_mock_response()

        user = self.example_user("cordelia")
        server = self.server
        remote_realm = RemoteRealm.objects.get(server=server, uuid=user.realm.uuid)

        token = "111222"
        token_kind = PushDeviceToken.FCM
        PushDeviceToken.objects.create(user=user, token=token, kind=token_kind)
        remote_device = RemotePushDeviceToken.objects.create(
            server=server, user_uuid=str(user.uuid), token=token, kind=token_kind
        )

        endpoint = "/api/v1/mobile_push/test_notification"
        time_now = now()
        with (
            mock.patch(
                "zerver.lib.push_notifications.send_android_push_notification"
            ) as mock_send_android_push_notification,
            time_machine.travel(time_now, tick=False),
        ):
            result = self.api_post(user, endpoint, {"token": token}, subdomain="zulip")
        expected_payload = {
            "server": "testserver",
            "realm_id": user.realm_id,
            "realm_name": "Zulip Dev",
            "realm_uri": "http://zulip.testserver",
            "realm_url": "http://zulip.testserver",
            "user_id": user.id,
            "event": "test",
            "time": datetime_to_timestamp(time_now),
        }
        expected_gcm_options = {"priority": "high"}
        user_identity = UserPushIdentityCompat(user_id=user.id, user_uuid=str(user.uuid))
        mock_send_android_push_notification.assert_called_once_with(
            user_identity,
            [remote_device],
            expected_payload,
            expected_gcm_options,
            remote=server,
        )
        self.assert_json_success(result)

        remote_realm.refresh_from_db()
        self.assertEqual(remote_realm.last_request_datetime, time_now)


class PushBouncerNotificationTest(BouncerTestCase):
    DEFAULT_SUBDOMAIN = ""

    def test_unregister_remote_push_user_params(self) -> None:
        token = "111222"
        token_kind = PushDeviceToken.FCM

        endpoint = "/api/v1/remotes/push/unregister"
        result = self.uuid_post(self.server_uuid, endpoint, {"token_kind": token_kind})
        self.assert_json_error(result, "Missing 'token' argument")
        result = self.uuid_post(self.server_uuid, endpoint, {"token": token})
        self.assert_json_error(result, "Missing 'token_kind' argument")

        # We need the root ('') subdomain to be in use for this next
        # test, since the push bouncer API is only available there:
        hamlet = self.example_user("hamlet")
        realm = get_realm("zulip")
        realm.string_id = ""
        realm.save()

        result = self.api_post(
            hamlet,
            endpoint,
            dict(user_id=15, token=token, token_kind=token_kind),
            subdomain="",
        )
        self.assert_json_error(result, "Must validate with valid Zulip server API key")

        # Try with deactivated remote servers
        self.server.deactivated = True
        self.server.save()
        result = self.uuid_post(self.server_uuid, endpoint, self.get_generic_payload("unregister"))
        self.assert_json_error_contains(
            result,
            "The mobile push notification service registration for your server has been deactivated",
            401,
        )

    def test_register_remote_push_user_params(self) -> None:
        token = "111222"
        user_id = 11
        token_kind = PushDeviceToken.FCM

        endpoint = "/api/v1/remotes/push/register"

        result = self.uuid_post(
            self.server_uuid, endpoint, {"user_id": user_id, "token_kind": token_kind}
        )
        self.assert_json_error(result, "Missing 'token' argument")
        result = self.uuid_post(self.server_uuid, endpoint, {"user_id": user_id, "token": token})
        self.assert_json_error(result, "Missing 'token_kind' argument")
        result = self.uuid_post(
            self.server_uuid, endpoint, {"token": token, "token_kind": token_kind}
        )
        self.assert_json_error(result, "Missing user_id or user_uuid")
        result = self.uuid_post(
            self.server_uuid, endpoint, {"user_id": user_id, "token": token, "token_kind": 17}
        )
        self.assert_json_error(result, "Invalid token type")

        hamlet = self.example_user("hamlet")

        # We need the root ('') subdomain to be in use for this next
        # test, since the push bouncer API is only available there:
        realm = get_realm("zulip")
        realm.string_id = ""
        realm.save()

        result = self.api_post(
            hamlet,
            endpoint,
            dict(user_id=user_id, token_kind=token_kind, token=token),
        )
        self.assert_json_error(result, "Must validate with valid Zulip server API key")

        result = self.uuid_post(
            self.server_uuid,
            endpoint,
            dict(user_id=user_id, token_kind=token_kind, token=token),
            subdomain="zulip",
        )
        self.assert_json_error(
            result, "Invalid subdomain for push notifications bouncer", status_code=401
        )

        # We do a bit of hackery here to the API_KEYS cache just to
        # make the code simple for sending an incorrect API key.
        self.API_KEYS[self.server_uuid] = "invalid"
        result = self.uuid_post(
            self.server_uuid, endpoint, dict(user_id=user_id, token_kind=token_kind, token=token)
        )
        self.assert_json_error(
            result,
            "Zulip server auth failure: key does not match role 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe",
            status_code=401,
        )

        del self.API_KEYS[self.server_uuid]

        self.API_KEYS["invalid_uuid"] = "invalid"
        result = self.uuid_post(
            "invalid_uuid",
            endpoint,
            dict(user_id=user_id, token_kind=token_kind, token=token),
            subdomain="zulip",
        )
        self.assert_json_error(
            result,
            "Zulip server auth failure: invalid_uuid is not registered -- did you run `manage.py register_server`?",
            status_code=401,
        )
        del self.API_KEYS["invalid_uuid"]

        credentials_uuid = str(uuid.uuid4())
        credentials = "{}:{}".format(credentials_uuid, "invalid")
        api_auth = "Basic " + base64.b64encode(credentials.encode()).decode()
        result = self.client_post(
            endpoint,
            {"user_id": user_id, "token_kind": token_kind, "token": token},
            HTTP_AUTHORIZATION=api_auth,
        )
        self.assert_json_error(
            result,
            f"Zulip server auth failure: {credentials_uuid} is not registered -- did you run `manage.py register_server`?",
            status_code=401,
        )

        # Try with deactivated remote servers
        self.server.deactivated = True
        self.server.save()
        result = self.uuid_post(self.server_uuid, endpoint, self.get_generic_payload("register"))
        self.assert_json_error_contains(
            result,
            "The mobile push notification service registration for your server has been deactivated",
            401,
        )

    def test_register_require_ios_app_id(self) -> None:
        endpoint = "/api/v1/remotes/push/register"
        args = {"user_id": 11, "token": "1122"}

        result = self.uuid_post(
            self.server_uuid,
            endpoint,
            {**args, "token_kind": PushDeviceToken.APNS},
        )
        self.assert_json_error(result, "Missing ios_app_id")

        result = self.uuid_post(
            self.server_uuid,
            endpoint,
            {**args, "token_kind": PushDeviceToken.APNS, "ios_app_id": "example.app"},
        )
        self.assert_json_success(result)

        result = self.uuid_post(
            self.server_uuid,
            endpoint,
            {**args, "token_kind": PushDeviceToken.FCM},
        )
        self.assert_json_success(result)

    def test_register_validate_ios_app_id(self) -> None:
        endpoint = "/api/v1/remotes/push/register"
        args = {
            "user_id": 11,
            "token": "1122",
            "token_kind": PushDeviceToken.APNS,
            "ios_app_id": "'; tables --",
        }

        result = self.uuid_post(self.server_uuid, endpoint, args)
        self.assert_json_error(result, "ios_app_id has invalid format")

        args["ios_app_id"] = "com.zulip.apple"
        result = self.uuid_post(self.server_uuid, endpoint, args)
        self.assert_json_success(result)

    def test_register_device_deduplication(self) -> None:
        hamlet = self.example_user("hamlet")
        token = "111222"
        user_id = hamlet.id
        user_uuid = str(hamlet.uuid)
        token_kind = PushDeviceToken.FCM

        endpoint = "/api/v1/remotes/push/register"

        # First we create a legacy user_id registration.
        result = self.uuid_post(
            self.server_uuid,
            endpoint,
            {"user_id": user_id, "token_kind": token_kind, "token": token},
        )
        self.assert_json_success(result)

        registrations = list(RemotePushDeviceToken.objects.filter(token=token))
        self.assert_length(registrations, 1)
        self.assertEqual(registrations[0].user_id, user_id)
        self.assertEqual(registrations[0].user_uuid, None)

        # Register same user+device with uuid now. The old registration should be deleted
        # to avoid duplication.
        result = self.uuid_post(
            self.server_uuid,
            endpoint,
            {"user_id": user_id, "user_uuid": user_uuid, "token_kind": token_kind, "token": token},
        )
        registrations = list(RemotePushDeviceToken.objects.filter(token=token))
        self.assert_length(registrations, 1)
        self.assertEqual(registrations[0].user_id, None)
        self.assertEqual(str(registrations[0].user_uuid), user_uuid)

    def test_remote_push_user_endpoints(self) -> None:
        endpoints = [
            ("/api/v1/remotes/push/register", "register"),
            ("/api/v1/remotes/push/unregister", "unregister"),
        ]

        for endpoint, method in endpoints:
            payload = self.get_generic_payload(method)

            # Verify correct results are success
            result = self.uuid_post(self.server_uuid, endpoint, payload)
            self.assert_json_success(result)

            remote_tokens = RemotePushDeviceToken.objects.filter(token=payload["token"])
            token_count = 1 if method == "register" else 0
            self.assert_length(remote_tokens, token_count)

            # Try adding/removing tokens that are too big...
            broken_token = "x" * 5000  # too big
            payload["token"] = broken_token
            result = self.uuid_post(self.server_uuid, endpoint, payload)
            self.assert_json_error(result, "Empty or invalid length token")

    def test_send_notification_endpoint_sets_remote_realm_for_devices(self) -> None:
        hamlet = self.example_user("hamlet")
        server = self.server

        remote_realm = RemoteRealm.objects.get(server=server, uuid=hamlet.realm.uuid)

        android_token = RemotePushDeviceToken.objects.create(
            kind=RemotePushDeviceToken.FCM,
            token="aaaa",
            user_uuid=hamlet.uuid,
            server=server,
        )
        apple_token = RemotePushDeviceToken.objects.create(
            kind=RemotePushDeviceToken.APNS,
            token="bbbb",
            user_uuid=hamlet.uuid,
            server=server,
        )
        payload = {
            "user_id": hamlet.id,
            "user_uuid": str(hamlet.uuid),
            "realm_uuid": str(hamlet.realm.uuid),
            "gcm_payload": {},
            "apns_payload": {},
            "gcm_options": {},
        }
        with (
            mock.patch("zilencer.views.send_android_push_notification", return_value=1),
            mock.patch("zilencer.views.send_apple_push_notification", return_value=1),
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=10,
            ),
            self.assertLogs("zilencer.views", level="INFO"),
        ):
            result = self.uuid_post(
                self.server_uuid,
                "/api/v1/remotes/push/notify",
                payload,
                content_type="application/json",
            )
        self.assert_json_success(result)

        android_token.refresh_from_db()
        apple_token.refresh_from_db()

        self.assertEqual(android_token.remote_realm, remote_realm)
        self.assertEqual(apple_token.remote_realm, remote_realm)

    def test_send_notification_endpoint(self) -> None:
        hamlet = self.example_user("hamlet")
        server = self.server
        remote_realm = RemoteRealm.objects.get(server=server, uuid=hamlet.realm.uuid)

        token = "aaaa"
        android_tokens = []
        uuid_android_tokens = []
        for i in ["aa", "bb"]:
            android_tokens.append(
                RemotePushDeviceToken.objects.create(
                    kind=RemotePushDeviceToken.FCM,
                    token=token + i,
                    user_id=hamlet.id,
                    server=server,
                )
            )

            # Create a duplicate, newer uuid-based registration for the same user to verify
            # the bouncer will handle that correctly, without triggering a duplicate notification,
            # and will delete the old, legacy registration.
            uuid_android_tokens.append(
                RemotePushDeviceToken.objects.create(
                    kind=RemotePushDeviceToken.FCM,
                    token=token + i,
                    user_uuid=str(hamlet.uuid),
                    server=server,
                )
            )

        apple_token = RemotePushDeviceToken.objects.create(
            kind=RemotePushDeviceToken.APNS,
            token=token,
            user_id=hamlet.id,
            server=server,
        )
        many_ids = ",".join(str(i) for i in range(1, 250))
        payload = {
            "user_id": hamlet.id,
            "user_uuid": str(hamlet.uuid),
            "realm_uuid": str(hamlet.realm.uuid),
            "gcm_payload": {"event": "remove", "zulip_message_ids": many_ids},
            "apns_payload": {
                "badge": 0,
                "custom": {"zulip": {"event": "remove", "zulip_message_ids": many_ids}},
            },
            "gcm_options": {},
        }

        time_sent = now()
        with (
            mock.patch(
                "zilencer.views.send_android_push_notification", return_value=2
            ) as android_push,
            mock.patch("zilencer.views.send_apple_push_notification", return_value=1) as apple_push,
            mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=10,
            ),
            time_machine.travel(time_sent, tick=False),
            self.assertLogs("zilencer.views", level="INFO") as logger,
        ):
            result = self.uuid_post(
                self.server_uuid,
                "/api/v1/remotes/push/notify",
                payload,
                content_type="application/json",
            )
        data = self.assert_json_success(result)
        self.assertEqual(
            {
                "result": "success",
                "msg": "",
                "total_android_devices": 2,
                "total_apple_devices": 1,
                "deleted_devices": {"android_devices": [], "apple_devices": []},
                "realm": {"can_push": True, "expected_end_timestamp": None},
            },
            data,
        )
        self.assertEqual(
            logger.output,
            [
                "INFO:zilencer.views:"
                f"Deduplicating push registrations for server id:{server.id} user id:{hamlet.id} uuid:{hamlet.uuid} and tokens:{sorted(t.token for t in android_tokens)}",
                "INFO:zilencer.views:"
                f"Sending mobile push notifications for remote user 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{hamlet.id}><uuid:{hamlet.uuid}>: "
                "2 via FCM devices, 1 via APNs devices",
            ],
        )

        user_identity = UserPushIdentityCompat(user_id=hamlet.id, user_uuid=str(hamlet.uuid))
        apple_push.assert_called_once_with(
            user_identity,
            [apple_token],
            {
                "badge": 0,
                "custom": {
                    "zulip": {
                        "event": "remove",
                        "zulip_message_ids": ",".join(str(i) for i in range(50, 250)),
                    }
                },
            },
            remote=server,
        )
        android_push.assert_called_once_with(
            user_identity,
            uuid_android_tokens,
            {"event": "remove", "zulip_message_ids": ",".join(str(i) for i in range(50, 250))},
            {},
            remote=server,
        )

        remote_realm.refresh_from_db()
        server.refresh_from_db()
        self.assertEqual(remote_realm.last_request_datetime, time_sent)
        self.assertEqual(server.last_request_datetime, time_sent)

    def test_send_notification_endpoint_on_free_plans(self) -> None:
        hamlet = self.example_user("hamlet")
        remote_server = self.server
        RemotePushDeviceToken.objects.create(
            kind=RemotePushDeviceToken.FCM,
            token="aaaaaa",
            user_id=hamlet.id,
            server=remote_server,
        )

        current_time = now()
        message = Message(
            sender=hamlet,
            recipient=self.example_user("othello").recipient,
            realm_id=hamlet.realm_id,
            content="This is test content",
            rendered_content="This is test content",
            date_sent=current_time,
            sending_client=get_client("test"),
        )
        message.save()

        # Test old zulip server case.
        self.assertIsNone(remote_server.last_api_feature_level)
        old_apns_payload = {
            "alert": {
                "title": "King Hamlet",
                "subtitle": "",
                "body": message.content,
            },
            "badge": 0,
            "sound": "default",
            "custom": {
                "zulip": {
                    "message_ids": [message.id],
                    "recipient_type": "private",
                    "sender_email": hamlet.email,
                    "sender_id": hamlet.id,
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": hamlet.realm.id,
                    "realm_uri": hamlet.realm.url,
                    "realm_url": hamlet.realm.url,
                    "user_id": self.example_user("othello").id,
                }
            },
        }
        old_gcm_payload = {
            "user_id": self.example_user("othello").id,
            "event": "message",
            "alert": "New private message from King Hamlet",
            "zulip_message_id": message.id,
            "time": datetime_to_timestamp(message.date_sent),
            "content": message.content,
            "content_truncated": False,
            "server": settings.EXTERNAL_HOST,
            "realm_id": hamlet.realm.id,
            "realm_uri": hamlet.realm.url,
            "realm_url": hamlet.realm.url,
            "sender_id": hamlet.id,
            "sender_email": hamlet.email,
            "sender_full_name": "King Hamlet",
            "sender_avatar_url": absolute_avatar_url(message.sender),
            "recipient_type": "private",
        }
        payload = {
            "user_id": hamlet.id,
            "gcm_payload": old_gcm_payload,
            "apns_payload": old_apns_payload,
            "gcm_options": {"priority": "high"},
        }

        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/notify",
            payload,
            content_type="application/json",
        )
        self.assertEqual(orjson.loads(result.content)["code"], "INVALID_ZULIP_SERVER")

        remote_server.last_api_feature_level = 235
        remote_server.save()

        gcm_payload, gcm_options = get_message_payload_gcm(hamlet, message)
        apns_payload = get_message_payload_apns(
            hamlet, message, NotificationTriggers.DIRECT_MESSAGE
        )
        payload = {
            "user_id": hamlet.id,
            "user_uuid": str(hamlet.uuid),
            "gcm_payload": gcm_payload,
            "apns_payload": apns_payload,
            "gcm_options": gcm_options,
        }

        # Test the case when there is no data about users.
        self.assertIsNone(remote_server.last_audit_log_update)
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/notify",
            payload,
            content_type="application/json",
        )
        self.assert_json_error(
            result,
            "Your plan doesn't allow sending push notifications. Reason provided by the server: Missing data",
        )
        self.assertEqual(orjson.loads(result.content)["code"], "PUSH_NOTIFICATIONS_DISALLOWED")

        human_counts = {
            str(UserProfile.ROLE_REALM_ADMINISTRATOR): 1,
            str(UserProfile.ROLE_REALM_OWNER): 1,
            str(UserProfile.ROLE_MODERATOR): 0,
            str(UserProfile.ROLE_MEMBER): 7,
            str(UserProfile.ROLE_GUEST): 2,
        }
        RemoteRealmAuditLog.objects.create(
            server=remote_server,
            event_type=AuditLogEventType.USER_CREATED,
            event_time=current_time - timedelta(minutes=10),
            extra_data={RealmAuditLog.ROLE_COUNT: {RealmAuditLog.ROLE_COUNT_HUMANS: human_counts}},
        )
        remote_server.last_audit_log_update = current_time - timedelta(minutes=10)
        remote_server.save()

        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/push/notify",
            payload,
            content_type="application/json",
        )
        self.assert_json_error(
            result,
            "Your plan doesn't allow sending push notifications. Reason provided by the server: Push notifications access with 10+ users requires signing up for a plan. https://zulip.com/plans/",
        )
        self.assertEqual(orjson.loads(result.content)["code"], "PUSH_NOTIFICATIONS_DISALLOWED")

        # Check that sponsored realms are allowed to send push notifications.
        remote_server.plan_type = RemoteRealm.PLAN_TYPE_COMMUNITY
        remote_server.save()
        with self.assertLogs("zilencer.views", level="INFO") as logger:
            result = self.uuid_post(
                self.server_uuid,
                "/api/v1/remotes/push/notify",
                payload,
                content_type="application/json",
            )
        data = self.assert_json_success(result)
        self.assertEqual(
            {
                "result": "success",
                "msg": "",
                "realm": None,
                "total_android_devices": 1,
                "total_apple_devices": 0,
                "deleted_devices": {"android_devices": [], "apple_devices": []},
            },
            data,
        )
        self.assertIn(
            "INFO:zilencer.views:"
            f"Sending mobile push notifications for remote user 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{hamlet.id}><uuid:{hamlet.uuid}>: "
            "1 via FCM devices, 0 via APNs devices",
            logger.output,
        )

        # Reset the plan_type to test remaining cases.
        remote_server.plan_type = RemoteRealm.PLAN_TYPE_SELF_MANAGED
        remote_server.save()

        human_counts = {
            str(UserProfile.ROLE_REALM_ADMINISTRATOR): 1,
            str(UserProfile.ROLE_REALM_OWNER): 1,
            str(UserProfile.ROLE_MODERATOR): 0,
            str(UserProfile.ROLE_MEMBER): 6,
            str(UserProfile.ROLE_GUEST): 2,
        }

        RemoteRealmAuditLog.objects.create(
            server=remote_server,
            event_type=AuditLogEventType.USER_DEACTIVATED,
            event_time=current_time - timedelta(minutes=8),
            extra_data={RealmAuditLog.ROLE_COUNT: {RealmAuditLog.ROLE_COUNT_HUMANS: human_counts}},
        )
        remote_server.last_audit_log_update = current_time - timedelta(minutes=8)
        remote_server.save()

        with self.assertLogs("zilencer.views", level="INFO") as logger:
            result = self.uuid_post(
                self.server_uuid,
                "/api/v1/remotes/push/notify",
                payload,
                content_type="application/json",
            )
        data = self.assert_json_success(result)
        self.assertEqual(
            {
                "result": "success",
                "msg": "",
                "realm": None,
                "total_android_devices": 1,
                "total_apple_devices": 0,
                "deleted_devices": {"android_devices": [], "apple_devices": []},
            },
            data,
        )
        self.assertIn(
            "INFO:zilencer.views:"
            f"Sending mobile push notifications for remote user 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{hamlet.id}><uuid:{hamlet.uuid}>: "
            "1 via FCM devices, 0 via APNs devices",
            logger.output,
        )

    def test_subsecond_timestamp_format(self) -> None:
        hamlet = self.example_user("hamlet")
        RemotePushDeviceToken.objects.create(
            kind=RemotePushDeviceToken.FCM,
            token="aaaaaa",
            user_id=hamlet.id,
            server=self.server,
        )

        time_sent = now().replace(microsecond=234000)
        with time_machine.travel(time_sent, tick=False):
            message = Message(
                sender=hamlet,
                recipient=self.example_user("othello").recipient,
                realm_id=hamlet.realm_id,
                content="This is test content",
                rendered_content="This is test content",
                date_sent=now(),
                sending_client=get_client("test"),
            )
            message.set_topic_name("Test topic")
            message.save()
            gcm_payload, gcm_options = get_message_payload_gcm(hamlet, message)
            apns_payload = get_message_payload_apns(
                hamlet, message, NotificationTriggers.DIRECT_MESSAGE
            )

        # Reconfigure like recent versions, which had subsecond-granularity
        # timestamps.
        self.assertIsNotNone(gcm_payload.get("time"))
        gcm_payload["time"] = float(gcm_payload["time"] + 0.234)
        self.assertEqual(gcm_payload["time"], time_sent.timestamp())
        self.assertIsNotNone(apns_payload["custom"]["zulip"].get("time"))
        apns_payload["custom"]["zulip"]["time"] = gcm_payload["time"]

        payload = {
            "user_id": hamlet.id,
            "user_uuid": str(hamlet.uuid),
            "gcm_payload": gcm_payload,
            "apns_payload": apns_payload,
            "gcm_options": gcm_options,
        }
        time_received = time_sent + timedelta(seconds=1, milliseconds=234)
        with (
            time_machine.travel(time_received, tick=False),
            mock.patch("zilencer.views.send_android_push_notification", return_value=1),
            mock.patch("zilencer.views.send_apple_push_notification", return_value=1),
            mock.patch(
                "corporate.lib.stripe.RemoteServerBillingSession.current_count_for_billed_licenses",
                return_value=10,
            ),
            self.assertLogs("zilencer.views", level="INFO") as logger,
        ):
            result = self.uuid_post(
                self.server_uuid,
                "/api/v1/remotes/push/notify",
                payload,
                content_type="application/json",
            )
        self.assert_json_success(result)
        self.assertEqual(
            logger.output[0],
            "INFO:zilencer.views:"
            f"Remote queuing latency for 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{hamlet.id}><uuid:{hamlet.uuid}> "
            "is 1.234 seconds",
        )

    def test_remote_push_unregister_all(self) -> None:
        payload = self.get_generic_payload("register")

        # Verify correct results are success
        result = self.uuid_post(self.server_uuid, "/api/v1/remotes/push/register", payload)
        self.assert_json_success(result)

        remote_tokens = RemotePushDeviceToken.objects.filter(token=payload["token"])
        self.assert_length(remote_tokens, 1)
        result = self.uuid_post(
            self.server_uuid, "/api/v1/remotes/push/unregister/all", dict(user_id=10)
        )
        self.assert_json_success(result)

        remote_tokens = RemotePushDeviceToken.objects.filter(token=payload["token"])
        self.assert_length(remote_tokens, 0)

    def test_invalid_apns_token(self) -> None:
        payload = {
            "user_id": 10,
            "token": "xyz uses non-hex characters",
            "token_kind": PushDeviceToken.APNS,
        }
        result = self.uuid_post(self.server_uuid, "/api/v1/remotes/push/register", payload)
        self.assert_json_error(result, "Invalid APNS token")

    def test_initialize_push_notifications(self) -> None:
        realm = get_realm("zulip")
        realm.push_notifications_enabled = False
        realm.save()

        from zerver.lib.push_notifications import initialize_push_notifications

        with mock.patch(
            "zerver.lib.push_notifications.sends_notifications_directly", return_value=True
        ):
            initialize_push_notifications()

            realm = get_realm("zulip")
            self.assertTrue(realm.push_notifications_enabled)

        with (
            mock.patch(
                "zerver.lib.push_notifications.push_notifications_configured", return_value=False
            ),
            self.assertLogs("zerver.lib.push_notifications", level="WARNING") as warn_log,
        ):
            initialize_push_notifications()

            not_configured_warn_log = (
                "WARNING:zerver.lib.push_notifications:"
                "Mobile push notifications are not configured.\n  "
                "See https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html"
            )
            realm = get_realm("zulip")
            self.assertFalse(realm.push_notifications_enabled)
            self.assertEqual(
                warn_log.output[0],
                not_configured_warn_log,
            )

        with (
            activate_push_notification_service(),
            mock.patch("zerver.lib.remote_server.send_to_push_bouncer") as m,
        ):
            post_response = {
                "realms": {realm.uuid: {"can_push": True, "expected_end_timestamp": None}}
            }
            get_response = {
                "last_realm_count_id": 0,
                "last_installation_count_id": 0,
                "last_realmauditlog_id": 0,
            }

            def mock_send_to_push_bouncer_response(method: str, *args: Any) -> dict[str, Any]:
                if method == "POST":
                    return post_response
                return get_response

            m.side_effect = mock_send_to_push_bouncer_response

            initialize_push_notifications()

            realm = get_realm("zulip")
            self.assertTrue(realm.push_notifications_enabled)
            self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

    @activate_push_notification_service()
    @responses.activate
    def test_register_token_realm_uuid_belongs_to_different_server(self) -> None:
        self.add_mock_response()
        user = self.example_user("cordelia")
        self.login_user(user)

        # Create a simulated second server. We will take user's RemoteRealm registration
        # and change its server to this second server. This means that when the bouncer
        # is processing the token registration request, it will find a RemoteRealm matching
        # the realm_uuid in the request, but that RemoteRealm will be registered to a
        # different server than the one making the request (self.server).
        # This will make it log a warning, raise an exception when trying to get
        # remote realm via get_remote_realm_helper and thus, not register the token.
        second_server = RemoteZulipServer.objects.create(
            uuid=uuid.uuid4(),
            api_key="magic_secret_api_key2",
            hostname="demo2.example.com",
            last_updated=now(),
        )

        remote_realm = RemoteRealm.objects.get(server=self.server, uuid=user.realm.uuid)
        remote_realm.server = second_server
        remote_realm.save()

        endpoint = "/json/users/me/apns_device_token"
        token = "c0ffee"
        with self.assertLogs("zilencer.views", level="WARN") as warn_log:
            result = self.client_post(
                endpoint, {"token": token, "appid": "org.zulip.Zulip"}, subdomain="zulip"
            )
            self.assert_json_error_contains(
                result,
                "Your organization is registered to a different Zulip server. Please contact Zulip support",
            )
        self.assertEqual(
            warn_log.output,
            [
                "WARNING:zilencer.views:/api/v1/remotes/push/register: "
                f"Realm {remote_realm.uuid!s} exists, but not registered to server {self.server.id}"
            ],
        )

        self.assert_length(RemotePushDeviceToken.objects.filter(token=token), 0)

    @activate_push_notification_service()
    @responses.activate
    def test_push_bouncer_api(self) -> None:
        """This is a variant of the below test_push_api, but using the full
        push notification bouncer flow
        """
        self.add_mock_response()
        user = self.example_user("cordelia")
        self.login_user(user)
        server = self.server

        endpoints: list[tuple[str, str, int, Mapping[str, str]]] = [
            (
                "/json/users/me/apns_device_token",
                "c0ffee",
                RemotePushDeviceToken.APNS,
                {"appid": "org.zulip.Zulip"},
            ),
            ("/json/users/me/android_gcm_reg_id", "android-token", RemotePushDeviceToken.FCM, {}),
        ]

        # Test error handling
        for endpoint, token, kind, appid in endpoints:
            # Try adding/removing tokens that are too big...
            broken_token = "a" * 5000  # too big
            result = self.client_post(endpoint, {"token": broken_token, **appid}, subdomain="zulip")
            self.assert_json_error(result, "Empty or invalid length token")

            result = self.client_delete(endpoint, {"token": broken_token}, subdomain="zulip")
            self.assert_json_error(result, "Empty or invalid length token")

            # Try adding with missing or invalid appid...
            if appid:
                result = self.client_post(endpoint, {"token": token}, subdomain="zulip")
                self.assert_json_error(result, "Missing 'appid' argument")

                result = self.client_post(
                    endpoint, {"token": token, "appid": "'; tables --"}, subdomain="zulip"
                )
                self.assert_json_error(result, "appid has invalid format")

            # Try to remove a non-existent token...
            result = self.client_delete(endpoint, {"token": "abcd1234"}, subdomain="zulip")
            self.assert_json_error(result, "Token does not exist")

            assert settings.ZULIP_SERVICES_URL is not None
            URL = settings.ZULIP_SERVICES_URL + "/api/v1/remotes/push/register"
            with responses.RequestsMock() as resp, self.assertLogs(level="ERROR") as error_log:
                resp.add(responses.POST, URL, body=ConnectionError(), status=502)
                with self.assertRaisesRegex(
                    PushNotificationBouncerRetryLaterError,
                    r"^ConnectionError while trying to connect to push notification bouncer$",
                ):
                    self.client_post(endpoint, {"token": token, **appid}, subdomain="zulip")
                self.assertIn(
                    f"ERROR:django.request:Bad Gateway: {endpoint}\nTraceback",
                    error_log.output[0],
                )

            with responses.RequestsMock() as resp, self.assertLogs(level="WARNING") as warn_log:
                resp.add(responses.POST, URL, body=orjson.dumps({"msg": "error"}), status=500)
                with self.assertRaisesRegex(
                    PushNotificationBouncerServerError,
                    r"Received 500 from push notification bouncer$",
                ):
                    self.client_post(endpoint, {"token": token, **appid}, subdomain="zulip")
                self.assertEqual(
                    warn_log.output[0],
                    "WARNING:root:Received 500 from push notification bouncer",
                )
                self.assertIn(
                    f"ERROR:django.request:Bad Gateway: {endpoint}\nTraceback", warn_log.output[1]
                )

        # Add tokens
        for endpoint, token, kind, appid in endpoints:
            # First register a token without having a RemoteRealm registration:
            RemoteRealm.objects.all().delete()
            with self.assertLogs("zilencer.views", level="INFO") as info_log:
                result = self.client_post(endpoint, {"token": token, **appid}, subdomain="zulip")
            self.assert_json_success(result)
            self.assertIn(
                "INFO:zilencer.views:/api/v1/remotes/push/register: Received request for "
                f"unknown realm {user.realm.uuid!s}, server {server.id}",
                info_log.output,
            )

            # The registration succeeded, but RemotePushDeviceToken doesn't have remote_realm set:
            tokens = list(
                RemotePushDeviceToken.objects.filter(
                    user_uuid=user.uuid, token=token, server=server
                )
            )
            self.assert_length(tokens, 1)
            self.assertEqual(tokens[0].kind, kind)
            self.assertEqual(tokens[0].user_uuid, user.uuid)

            # Delete it to clean up.
            RemotePushDeviceToken.objects.filter(
                user_uuid=user.uuid, token=token, server=server
            ).delete()

            # Create the expected RemoteRealm registration and proceed with testing with a
            # normal setup.
            update_remote_realm_data_for_server(self.server, get_realms_info_for_push_bouncer())

            time_sent = now()
            with time_machine.travel(time_sent, tick=False):
                result = self.client_post(endpoint, {"token": token, **appid}, subdomain="zulip")
                self.assert_json_success(result)

                # Test that we can push more times
                result = self.client_post(endpoint, {"token": token, **appid}, subdomain="zulip")
                self.assert_json_success(result)

            tokens = list(
                RemotePushDeviceToken.objects.filter(
                    user_uuid=user.uuid, token=token, server=server
                )
            )
            self.assert_length(tokens, 1)
            self.assertEqual(tokens[0].kind, kind)
            # These new registrations have .remote_realm set properly.
            assert tokens[0].remote_realm is not None
            remote_realm = tokens[0].remote_realm
            self.assertEqual(remote_realm.uuid, user.realm.uuid)
            self.assertEqual(tokens[0].ios_app_id, appid.get("appid"))

            # Both RemoteRealm and RemoteZulipServer should have last_request_datetime
            # updated.
            self.assertEqual(remote_realm.last_request_datetime, time_sent)
            server.refresh_from_db()
            self.assertEqual(server.last_request_datetime, time_sent)

        # User should have tokens for both devices now.
        tokens = list(RemotePushDeviceToken.objects.filter(user_uuid=user.uuid, server=server))
        self.assert_length(tokens, 2)

        # Remove tokens
        time_sent += timedelta(minutes=1)
        for endpoint, token, kind, appid in endpoints:
            with time_machine.travel(time_sent, tick=False):
                result = self.client_delete(endpoint, {"token": token}, subdomain="zulip")
            self.assert_json_success(result)
            tokens = list(
                RemotePushDeviceToken.objects.filter(
                    user_uuid=user.uuid, token=token, server=server
                )
            )
            self.assert_length(tokens, 0)

            remote_realm.refresh_from_db()
            self.assertEqual(remote_realm.last_request_datetime, time_sent)

        # Re-add copies of those tokens
        for endpoint, token, kind, appid in endpoints:
            result = self.client_post(endpoint, {"token": token, **appid}, subdomain="zulip")
            self.assert_json_success(result)
        tokens = list(RemotePushDeviceToken.objects.filter(user_uuid=user.uuid, server=server))
        self.assert_length(tokens, 2)

        # Now we want to remove them using the bouncer after an API key change.
        # First we test error handling in case of issues with the bouncer:
        with (
            mock.patch(
                "zerver.worker.deferred_work.clear_push_device_tokens",
                side_effect=PushNotificationBouncerRetryLaterError("test"),
            ),
            mock.patch("zerver.worker.deferred_work.retry_event") as mock_retry,
        ):
            with self.captureOnCommitCallbacks(execute=True):
                do_regenerate_api_key(user, user)
            mock_retry.assert_called()

            # We didn't manage to communicate with the bouncer, to the tokens are still there:
            tokens = list(RemotePushDeviceToken.objects.filter(user_uuid=user.uuid, server=server))
            self.assert_length(tokens, 2)

        # Now we successfully remove them:
        time_sent += timedelta(minutes=1)
        with (
            time_machine.travel(time_sent, tick=False),
            self.captureOnCommitCallbacks(execute=True),
        ):
            do_regenerate_api_key(user, user)
        tokens = list(RemotePushDeviceToken.objects.filter(user_uuid=user.uuid, server=server))
        self.assert_length(tokens, 0)

        remote_realm.refresh_from_db()
        self.assertEqual(remote_realm.last_request_datetime, time_sent)


class TestAPNs(PushNotificationTestCase):
    def devices(self) -> list[DeviceToken]:
        return list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.APNS)
        )

    def send(
        self,
        devices: list[PushDeviceToken | RemotePushDeviceToken] | None = None,
        payload_data: Mapping[str, Any] = {},
    ) -> None:
        send_apple_push_notification(
            UserPushIdentityCompat(user_id=self.user_profile.id),
            devices if devices is not None else self.devices(),
            payload_data,
        )

    def test_get_apns_context(self) -> None:
        """This test is pretty hacky, and needs to carefully reset the state
        it modifies in order to avoid leaking state that can lead to
        nondeterministic results for other tests.
        """
        import zerver.lib.push_notifications

        zerver.lib.push_notifications.get_apns_context.cache_clear()
        try:
            with (
                self.settings(APNS_CERT_FILE="/foo.pem"),
                mock.patch("ssl.SSLContext.load_cert_chain") as mock_load_cert_chain,
            ):
                apns_context = get_apns_context()
                assert apns_context is not None
                try:
                    mock_load_cert_chain.assert_called_once_with("/foo.pem")
                    assert apns_context.apns.pool.loop == apns_context.loop
                finally:
                    apns_context.loop.close()
        finally:
            # Reset the cache for `get_apns_context` so that we don't
            # leak changes to the rest of the world.
            zerver.lib.push_notifications.get_apns_context.cache_clear()

    def test_not_configured(self) -> None:
        self.setup_apns_tokens()
        with (
            mock.patch("zerver.lib.push_notifications.get_apns_context") as mock_get,
            self.assertLogs("zerver.lib.push_notifications", level="DEBUG") as logger,
        ):
            mock_get.return_value = None
            self.send()
            notification_drop_log = (
                "DEBUG:zerver.lib.push_notifications:"
                "APNs: Dropping a notification because nothing configured.  "
                "Set ZULIP_SERVICES_URL (or APNS_CERT_FILE)."
            )

            from zerver.lib.push_notifications import initialize_push_notifications

            initialize_push_notifications()
            mobile_notifications_not_configured_log = (
                "WARNING:zerver.lib.push_notifications:"
                "Mobile push notifications are not configured.\n  "
                "See https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html"
            )

            self.assertEqual(
                [notification_drop_log, mobile_notifications_not_configured_log], logger.output
            )

    def test_success(self) -> None:
        self.setup_apns_tokens()
        with (
            self.mock_apns() as (apns_context, send_notification),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as logger,
        ):
            send_notification.return_value.is_successful = True
            self.send()
            for device in self.devices():
                self.assertIn(
                    f"INFO:zerver.lib.push_notifications:APNs: Success sending for user <id:{self.user_profile.id}> to device {device.token}",
                    logger.output,
                )

    def test_http_retry_eventually_fails(self) -> None:
        self.setup_apns_tokens()
        with (
            self.mock_apns() as (apns_context, send_notification),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as logger,
        ):
            send_notification.side_effect = aioapns.exceptions.ConnectionError()
            self.send(devices=self.devices()[0:1])
            self.assertIn(
                f"ERROR:zerver.lib.push_notifications:APNs: ConnectionError sending for user <id:{self.user_profile.id}> to device {self.devices()[0].token}; check certificate expiration",
                logger.output,
            )

    def test_other_exception(self) -> None:
        self.setup_apns_tokens()
        with (
            self.mock_apns() as (apns_context, send_notification),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as logger,
        ):
            send_notification.side_effect = IOError
            self.send(devices=self.devices()[0:1])
            self.assertIn(
                f"ERROR:zerver.lib.push_notifications:APNs: Error sending for user <id:{self.user_profile.id}> to device {self.devices()[0].token}",
                logger.output[1],
            )

    def test_internal_server_error(self) -> None:
        self.setup_apns_tokens()
        with (
            self.mock_apns() as (apns_context, send_notification),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as logger,
        ):
            send_notification.return_value.is_successful = False
            send_notification.return_value.description = "InternalServerError"
            self.send(devices=self.devices()[0:1])
            self.assertIn(
                f"WARNING:zerver.lib.push_notifications:APNs: Failed to send for user <id:{self.user_profile.id}> to device {self.devices()[0].token}: InternalServerError",
                logger.output,
            )

    def test_log_missing_ios_app_id(self) -> None:
        device = RemotePushDeviceToken.objects.create(
            kind=RemotePushDeviceToken.APNS,
            token="1234",
            ios_app_id=None,
            user_id=self.user_profile.id,
            server=self.server,
        )
        with (
            self.mock_apns() as (apns_context, send_notification),
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as logger,
        ):
            send_notification.return_value.is_successful = True
            self.send(devices=[device])
            self.assertIn(
                f"ERROR:zerver.lib.push_notifications:APNs: Missing ios_app_id for user <id:{self.user_profile.id}> device {device.token}",
                logger.output,
            )

    def test_modernize_apns_payload(self) -> None:
        payload = {
            "alert": "Message from Hamlet",
            "badge": 0,
            "custom": {"zulip": {"message_ids": [3]}},
        }
        self.assertEqual(
            modernize_apns_payload(
                {"alert": "Message from Hamlet", "message_ids": [3], "badge": 0}
            ),
            payload,
        )
        self.assertEqual(modernize_apns_payload(payload), payload)

    @mock.patch("zerver.lib.push_notifications.push_notifications_configured", return_value=True)
    def test_apns_badge_count(self, mock_push_notifications: mock.MagicMock) -> None:
        user_profile = self.example_user("othello")
        # Test APNs badge count for personal messages.
        message_ids = [
            self.send_personal_message(self.sender, user_profile, "Content of message")
            for i in range(3)
        ]
        self.assertEqual(get_apns_badge_count(user_profile), 0)
        self.assertEqual(get_apns_badge_count_future(user_profile), 3)
        # Similarly, test APNs badge count for stream mention.
        stream = self.subscribe(user_profile, "Denmark")
        message_ids += [
            self.send_stream_message(
                self.sender, stream.name, "Hi, @**Othello, the Moor of Venice**"
            )
            for i in range(2)
        ]
        self.assertEqual(get_apns_badge_count(user_profile), 0)
        self.assertEqual(get_apns_badge_count_future(user_profile), 5)

        num_messages = len(message_ids)
        # Mark the messages as read and test whether
        # the count decreases correctly.
        for i, message_id in enumerate(message_ids):
            with self.captureOnCommitCallbacks(execute=True):
                do_update_message_flags(user_profile, "add", "read", [message_id])
            self.assertEqual(get_apns_badge_count(user_profile), 0)
            self.assertEqual(get_apns_badge_count_future(user_profile), num_messages - i - 1)

        mock_push_notifications.assert_called()


class TestGetAPNsPayload(PushNotificationTestCase):
    def test_get_message_payload_apns_personal_message(self) -> None:
        user_profile = self.example_user("othello")
        message_id = self.send_personal_message(
            self.sender,
            user_profile,
            "Content of personal message",
        )
        message = Message.objects.get(id=message_id)
        payload = get_message_payload_apns(
            user_profile, message, NotificationTriggers.DIRECT_MESSAGE
        )
        expected = {
            "alert": {
                "title": "King Hamlet",
                "subtitle": "",
                "body": message.content,
            },
            "badge": 0,
            "sound": "default",
            "custom": {
                "zulip": {
                    "message_ids": [message.id],
                    "recipient_type": "private",
                    "sender_email": self.sender.email,
                    "sender_id": self.sender.id,
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": self.sender.realm.url,
                    "realm_url": self.sender.realm.url,
                    "user_id": user_profile.id,
                    "time": datetime_to_timestamp(message.date_sent),
                },
            },
        }
        self.assertDictEqual(payload, expected)

    def test_get_message_payload_apns_personal_message_using_direct_message_group(self) -> None:
        user_profile = self.example_user("othello")

        direct_message_group = get_or_create_direct_message_group(
            id_list=[self.sender.id, user_profile.id],
        )

        message_id = self.send_personal_message(
            self.sender,
            user_profile,
            "Content of personal message",
        )
        message = Message.objects.get(id=message_id)
        self.assertEqual(message.recipient, direct_message_group.recipient)
        payload = get_message_payload_apns(
            user_profile, message, NotificationTriggers.DIRECT_MESSAGE
        )
        expected = {
            "alert": {
                "title": "King Hamlet",
                "subtitle": "",
                "body": message.content,
            },
            "badge": 0,
            "sound": "default",
            "custom": {
                "zulip": {
                    "message_ids": [message.id],
                    "recipient_type": "private",
                    "sender_email": self.sender.email,
                    "sender_id": self.sender.id,
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": self.sender.realm.url,
                    "realm_url": self.sender.realm.url,
                    "user_id": user_profile.id,
                    "time": datetime_to_timestamp(message.date_sent),
                },
            },
        }
        self.assertDictEqual(payload, expected)

    @mock.patch("zerver.lib.push_notifications.push_notifications_configured", return_value=True)
    def test_get_message_payload_apns_group_direct_message(
        self, mock_push_notifications: mock.MagicMock
    ) -> None:
        user_profile = self.example_user("othello")
        message_id = self.send_group_direct_message(
            self.sender, [self.example_user("othello"), self.example_user("cordelia")]
        )
        message = Message.objects.get(id=message_id)
        payload = get_message_payload_apns(
            user_profile, message, NotificationTriggers.DIRECT_MESSAGE
        )
        expected = {
            "alert": {
                "title": "Cordelia, Lear's daughter, King Hamlet, Othello, the Moor of Venice",
                "subtitle": "King Hamlet:",
                "body": message.content,
            },
            "sound": "default",
            "badge": 0,
            "custom": {
                "zulip": {
                    "message_ids": [message.id],
                    "recipient_type": "private",
                    "pm_users": ",".join(
                        str(user_profile_id)
                        for user_profile_id in sorted(
                            s.user_profile_id
                            for s in Subscription.objects.filter(recipient=message.recipient)
                        )
                    ),
                    "sender_email": self.sender.email,
                    "sender_id": self.sender.id,
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": self.sender.realm.url,
                    "realm_url": self.sender.realm.url,
                    "user_id": user_profile.id,
                    "time": datetime_to_timestamp(message.date_sent),
                },
            },
        }
        self.assertDictEqual(payload, expected)
        mock_push_notifications.assert_called()

    def _test_get_message_payload_apns_stream_message(
        self, trigger: str, empty_string_topic: bool = False
    ) -> None:
        stream = Stream.objects.filter(name="Verona").get()
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)
        topic_display_name = message.topic_name()
        if empty_string_topic:
            message.set_topic_name("")
            message.save()
            topic_display_name = Message.EMPTY_TOPIC_FALLBACK_NAME

        payload = get_message_payload_apns(self.sender, message, trigger)
        expected = {
            "alert": {
                "title": f"#Verona > {topic_display_name}",
                "subtitle": "King Hamlet:",
                "body": message.content,
            },
            "sound": "default",
            "badge": 0,
            "custom": {
                "zulip": {
                    "message_ids": [message.id],
                    "recipient_type": "stream",
                    "sender_email": self.sender.email,
                    "sender_id": self.sender.id,
                    "stream": stream.name,
                    "stream_id": stream.id,
                    "topic": topic_display_name,
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": self.sender.realm.url,
                    "realm_url": self.sender.realm.url,
                    "user_id": self.sender.id,
                    "time": datetime_to_timestamp(message.date_sent),
                },
            },
        }
        self.assertDictEqual(payload, expected)

    def test_get_message_payload_apns_stream_message(self) -> None:
        self._test_get_message_payload_apns_stream_message(NotificationTriggers.STREAM_PUSH)

    def test_get_message_payload_apns_followed_topic_message(self) -> None:
        self._test_get_message_payload_apns_stream_message(NotificationTriggers.FOLLOWED_TOPIC_PUSH)

    def test_get_message_payload_apns_empty_string_topic(self) -> None:
        self._test_get_message_payload_apns_stream_message(
            NotificationTriggers.STREAM_PUSH, empty_string_topic=True
        )

    def test_get_message_payload_apns_stream_mention(self) -> None:
        user_profile = self.example_user("othello")
        stream = Stream.objects.filter(name="Verona").get()
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)
        payload = get_message_payload_apns(user_profile, message, NotificationTriggers.MENTION)
        expected = {
            "alert": {
                "title": "#Verona > Test topic",
                "subtitle": "King Hamlet mentioned you:",
                "body": message.content,
            },
            "sound": "default",
            "badge": 0,
            "custom": {
                "zulip": {
                    "message_ids": [message.id],
                    "recipient_type": "stream",
                    "sender_email": self.sender.email,
                    "sender_id": self.sender.id,
                    "stream": stream.name,
                    "stream_id": stream.id,
                    "topic": message.topic_name(),
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": self.sender.realm.url,
                    "realm_url": self.sender.realm.url,
                    "user_id": user_profile.id,
                    "time": datetime_to_timestamp(message.date_sent),
                },
            },
        }
        self.assertDictEqual(payload, expected)

    def test_get_message_payload_apns_user_group_mention(self) -> None:
        user_profile = self.example_user("othello")
        user_group = check_add_user_group(
            get_realm("zulip"), "test_user_group", [user_profile], acting_user=user_profile
        )
        stream = Stream.objects.filter(name="Verona").get()
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)
        payload = get_message_payload_apns(
            user_profile, message, NotificationTriggers.MENTION, user_group.id, user_group.name
        )
        expected = {
            "alert": {
                "title": "#Verona > Test topic",
                "subtitle": "King Hamlet mentioned @test_user_group:",
                "body": message.content,
            },
            "sound": "default",
            "badge": 0,
            "custom": {
                "zulip": {
                    "message_ids": [message.id],
                    "recipient_type": "stream",
                    "sender_email": self.sender.email,
                    "sender_id": self.sender.id,
                    "stream": stream.name,
                    "stream_id": stream.id,
                    "topic": message.topic_name(),
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": self.sender.realm.url,
                    "realm_url": self.sender.realm.url,
                    "user_id": user_profile.id,
                    "mentioned_user_group_id": user_group.id,
                    "mentioned_user_group_name": user_group.name,
                    "time": datetime_to_timestamp(message.date_sent),
                }
            },
        }
        self.assertDictEqual(payload, expected)

    def _test_get_message_payload_apns_wildcard_mention(self, trigger: str) -> None:
        user_profile = self.example_user("othello")
        stream = Stream.objects.filter(name="Verona").get()
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)
        payload = get_message_payload_apns(
            user_profile,
            message,
            trigger,
        )
        expected = {
            "alert": {
                "title": "#Verona > Test topic",
                "subtitle": "King Hamlet mentioned everyone:",
                "body": message.content,
            },
            "sound": "default",
            "badge": 0,
            "custom": {
                "zulip": {
                    "message_ids": [message.id],
                    "recipient_type": "stream",
                    "sender_email": self.sender.email,
                    "sender_id": self.sender.id,
                    "stream": stream.name,
                    "stream_id": stream.id,
                    "topic": message.topic_name(),
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": self.sender.realm.url,
                    "realm_url": self.sender.realm.url,
                    "user_id": user_profile.id,
                    "time": datetime_to_timestamp(message.date_sent),
                },
            },
        }
        self.assertDictEqual(payload, expected)

    def test_get_message_payload_apns_topic_wildcard_mention_in_followed_topic(self) -> None:
        self._test_get_message_payload_apns_wildcard_mention(
            NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
        )

    def test_get_message_payload_apns_stream_wildcard_mention_in_followed_topic(self) -> None:
        self._test_get_message_payload_apns_wildcard_mention(
            NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC
        )

    def test_get_message_payload_apns_topic_wildcard_mention(self) -> None:
        self._test_get_message_payload_apns_wildcard_mention(
            NotificationTriggers.TOPIC_WILDCARD_MENTION
        )

    def test_get_message_payload_apns_stream_wildcard_mention(self) -> None:
        self._test_get_message_payload_apns_wildcard_mention(
            NotificationTriggers.STREAM_WILDCARD_MENTION
        )

    @override_settings(PUSH_NOTIFICATION_REDACT_CONTENT=True)
    def test_get_message_payload_apns_redacted_content(self) -> None:
        user_profile = self.example_user("othello")
        message_id = self.send_group_direct_message(
            self.sender, [self.example_user("othello"), self.example_user("cordelia")]
        )
        message = Message.objects.get(id=message_id)
        payload = get_message_payload_apns(
            user_profile, message, NotificationTriggers.DIRECT_MESSAGE
        )
        expected = {
            "alert": {
                "title": "Cordelia, Lear's daughter, King Hamlet, Othello, the Moor of Venice",
                "subtitle": "King Hamlet:",
                "body": "New message",
            },
            "sound": "default",
            "badge": 0,
            "custom": {
                "zulip": {
                    "message_ids": [message.id],
                    "recipient_type": "private",
                    "pm_users": ",".join(
                        str(user_profile_id)
                        for user_profile_id in sorted(
                            s.user_profile_id
                            for s in Subscription.objects.filter(recipient=message.recipient)
                        )
                    ),
                    "sender_email": self.sender.email,
                    "sender_id": self.sender.id,
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": self.sender.realm.url,
                    "realm_url": self.sender.realm.url,
                    "user_id": user_profile.id,
                    "time": datetime_to_timestamp(message.date_sent),
                },
            },
        }
        self.assertDictEqual(payload, expected)

    def test_get_message_payload_apns_stream_message_from_inaccessible_user(self) -> None:
        self.set_up_db_for_testing_user_access()

        # Unsubscribe hamlet so that the guest user cannot access hamlet.
        self.unsubscribe(self.sender, "test_stream1")

        # Reset email visibility to everyone so that we can make sure
        # that sender_email field is not set to real email.
        reset_email_visibility_to_everyone_in_zulip_realm()

        hamlet = self.example_user("hamlet")
        polonius = self.example_user("polonius")

        stream = Stream.objects.get(name="test_stream1")
        # We reset the self.sender field here such that it is set
        # to the UserProfile object with latest "realm" field.
        self.sender = hamlet
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)

        payload = get_message_payload_apns(
            polonius, message, NotificationTriggers.STREAM_PUSH, can_access_sender=False
        )
        expected = {
            "alert": {
                "title": "#test_stream1 > Test topic",
                "subtitle": "Unknown user:",
                "body": message.content,
            },
            "sound": "default",
            "badge": 0,
            "custom": {
                "zulip": {
                    "message_ids": [message.id],
                    "recipient_type": "stream",
                    "sender_email": f"user{hamlet.id}@zulip.testserver",
                    "sender_id": hamlet.id,
                    "stream": stream.name,
                    "stream_id": stream.id,
                    "topic": message.topic_name(),
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": hamlet.realm.id,
                    "realm_name": hamlet.realm.name,
                    "realm_uri": hamlet.realm.url,
                    "realm_url": hamlet.realm.url,
                    "user_id": polonius.id,
                    "time": datetime_to_timestamp(message.date_sent),
                }
            },
        }
        self.assertDictEqual(payload, expected)


class TestGetGCMPayload(PushNotificationTestCase):
    def _test_get_message_payload_gcm_stream_message(
        self,
        truncate_content: bool = False,
        mentioned_user_group_id: int | None = None,
        mentioned_user_group_name: str | None = None,
        empty_string_topic: bool = False,
    ) -> None:
        stream = Stream.objects.filter(name="Verona").get()
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)

        content = message.content
        if truncate_content:
            message.content = "a" * 210
            message.rendered_content = "a" * 210
            message.save()
            content = "a" * 200 + "…"

        topic_display_name = message.topic_name()
        if empty_string_topic:
            message.set_topic_name("")
            message.save()
            topic_display_name = Message.EMPTY_TOPIC_FALLBACK_NAME

        hamlet = self.example_user("hamlet")
        payload, gcm_options = get_message_payload_gcm(
            hamlet, message, mentioned_user_group_id, mentioned_user_group_name
        )
        expected_payload = {
            "user_id": hamlet.id,
            "event": "message",
            "zulip_message_id": message.id,
            "time": datetime_to_timestamp(message.date_sent),
            "content": content,
            "content_truncated": truncate_content,
            "server": settings.EXTERNAL_HOST,
            "realm_id": hamlet.realm.id,
            "realm_name": hamlet.realm.name,
            "realm_uri": hamlet.realm.url,
            "realm_url": hamlet.realm.url,
            "sender_id": hamlet.id,
            "sender_email": hamlet.email,
            "sender_full_name": "King Hamlet",
            "sender_avatar_url": absolute_avatar_url(message.sender),
            "recipient_type": "stream",
            "stream": stream.name,
            "stream_id": stream.id,
            "topic": topic_display_name,
        }

        if mentioned_user_group_id is not None:
            expected_payload["mentioned_user_group_id"] = mentioned_user_group_id
            expected_payload["mentioned_user_group_name"] = mentioned_user_group_name
        self.assertDictEqual(payload, expected_payload)
        self.assertDictEqual(
            gcm_options,
            {
                "priority": "high",
            },
        )

    # Here, the payload is notification trigger independent. This test covers
    # the case when the trigger for push notifications is personal mention,
    # wildcard mention, stream push, or followed topic push.
    def test_get_message_payload_gcm_stream_message(self) -> None:
        self._test_get_message_payload_gcm_stream_message()

    def test_get_message_payload_gcm_stream_message_truncate_content(self) -> None:
        self._test_get_message_payload_gcm_stream_message(truncate_content=True)

    def test_get_message_payload_gcm_user_group_mention(self) -> None:
        # Note that the @mobile_team user group doesn't actually
        # exist; this test is just verifying the formatting logic.
        self._test_get_message_payload_gcm_stream_message(
            mentioned_user_group_id=3,
            mentioned_user_group_name="mobile_team",
        )

    def test_get_message_payload_gcm_empty_string_topic(self) -> None:
        self._test_get_message_payload_gcm_stream_message(empty_string_topic=True)

    def test_get_message_payload_gcm_direct_message(self) -> None:
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        hamlet = self.example_user("hamlet")
        payload, gcm_options = get_message_payload_gcm(hamlet, message)
        self.assertDictEqual(
            payload,
            {
                "user_id": hamlet.id,
                "event": "message",
                "zulip_message_id": message.id,
                "time": datetime_to_timestamp(message.date_sent),
                "content": message.content,
                "content_truncated": False,
                "server": settings.EXTERNAL_HOST,
                "realm_id": hamlet.realm.id,
                "realm_name": hamlet.realm.name,
                "realm_uri": hamlet.realm.url,
                "realm_url": hamlet.realm.url,
                "sender_id": hamlet.id,
                "sender_email": hamlet.email,
                "sender_full_name": "King Hamlet",
                "sender_avatar_url": absolute_avatar_url(message.sender),
                "recipient_type": "private",
            },
        )
        self.assertDictEqual(
            gcm_options,
            {
                "priority": "high",
            },
        )

    @override_settings(PUSH_NOTIFICATION_REDACT_CONTENT=True)
    def test_get_message_payload_gcm_redacted_content(self) -> None:
        stream = Stream.objects.get(name="Denmark")
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)
        hamlet = self.example_user("hamlet")
        payload, gcm_options = get_message_payload_gcm(hamlet, message)
        self.assertDictEqual(
            payload,
            {
                "user_id": hamlet.id,
                "event": "message",
                "zulip_message_id": message.id,
                "time": datetime_to_timestamp(message.date_sent),
                "content": "New message",
                "content_truncated": False,
                "server": settings.EXTERNAL_HOST,
                "realm_id": hamlet.realm.id,
                "realm_name": hamlet.realm.name,
                "realm_uri": hamlet.realm.url,
                "realm_url": hamlet.realm.url,
                "sender_id": hamlet.id,
                "sender_email": hamlet.email,
                "sender_full_name": "King Hamlet",
                "sender_avatar_url": absolute_avatar_url(message.sender),
                "recipient_type": "stream",
                "topic": "Test topic",
                "stream": "Denmark",
                "stream_id": stream.id,
            },
        )
        self.assertDictEqual(
            gcm_options,
            {
                "priority": "high",
            },
        )

    def test_get_message_payload_gcm_stream_message_from_inaccessible_user(self) -> None:
        self.set_up_db_for_testing_user_access()

        # Unsubscribe hamlet so that the guest user cannot access hamlet.
        self.unsubscribe(self.sender, "test_stream1")

        # Reset email visibility to everyone so that we can make sure
        # that sender_email field is not set to real email.
        reset_email_visibility_to_everyone_in_zulip_realm()

        hamlet = self.example_user("hamlet")
        polonius = self.example_user("polonius")

        stream = Stream.objects.get(name="test_stream1")
        # We reset the self.sender field here such that it is set
        # to the UserProfile object with latest "realm" field.
        self.sender = hamlet
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)

        payload, gcm_options = get_message_payload_gcm(polonius, message, can_access_sender=False)
        self.assertDictEqual(
            payload,
            {
                "user_id": polonius.id,
                "event": "message",
                "zulip_message_id": message.id,
                "time": datetime_to_timestamp(message.date_sent),
                "content": message.content,
                "content_truncated": False,
                "server": settings.EXTERNAL_HOST,
                "realm_id": hamlet.realm.id,
                "realm_name": hamlet.realm.name,
                "realm_uri": hamlet.realm.url,
                "realm_url": hamlet.realm.url,
                "sender_id": hamlet.id,
                "sender_email": f"user{hamlet.id}@zulip.testserver",
                "sender_full_name": "Unknown user",
                "sender_avatar_url": get_avatar_for_inaccessible_user(),
                "recipient_type": "stream",
                "stream": stream.name,
                "stream_id": stream.id,
                "topic": message.topic_name(),
            },
        )
        self.assertDictEqual(
            gcm_options,
            {
                "priority": "high",
            },
        )


class TestSendNotificationsToBouncer(PushNotificationTestCase):
    def test_send_notifications_to_bouncer_when_no_devices(self) -> None:
        user = self.example_user("hamlet")

        with (
            mock.patch("zerver.lib.remote_server.send_to_push_bouncer") as mock_send,
            self.assertLogs("zerver.lib.push_notifications", level="INFO") as mock_logging_info,
        ):
            send_notifications_to_bouncer(
                user, {"apns": True}, {"gcm": True}, {}, android_devices=[], apple_devices=[]
            )

        self.assertIn(
            f"INFO:zerver.lib.push_notifications:Skipping contacting the bouncer for user {user.id} because there are no registered devices",
            mock_logging_info.output,
        )
        mock_send.assert_not_called()

    @mock.patch("zerver.lib.remote_server.send_to_push_bouncer")
    def test_send_notifications_to_bouncer(self, mock_send: mock.MagicMock) -> None:
        user = self.example_user("hamlet")

        self.setup_apns_tokens()
        self.setup_fcm_tokens()

        android_devices = PushDeviceToken.objects.filter(kind=PushDeviceToken.FCM)
        apple_devices = PushDeviceToken.objects.filter(kind=PushDeviceToken.APNS)

        self.assertNotEqual(android_devices.count(), 0)
        self.assertNotEqual(apple_devices.count(), 0)

        mock_send.return_value = {
            "total_android_devices": 1,
            "total_apple_devices": 3,
            # This response tests the logic of the server taking
            # deleted_devices from the bouncer and deleting the
            # corresponding PushDeviceTokens - because the bouncer is
            # communicating that those devices have been deleted due
            # to failures from Apple/Google and have no further user.
            "deleted_devices": DevicesToCleanUpDict(
                android_devices=[device.token for device in android_devices],
                apple_devices=[device.token for device in apple_devices],
            ),
            "realm": {"can_push": True, "expected_end_timestamp": None},
        }
        with self.assertLogs("zerver.lib.push_notifications", level="INFO") as mock_logging_info:
            send_notifications_to_bouncer(
                user, {"apns": True}, {"gcm": True}, {}, list(android_devices), list(apple_devices)
            )
        post_data = {
            "user_uuid": user.uuid,
            "user_id": user.id,
            "realm_uuid": user.realm.uuid,
            "apns_payload": {"apns": True},
            "gcm_payload": {"gcm": True},
            "gcm_options": {},
            "android_devices": [device.token for device in android_devices],
            "apple_devices": [device.token for device in apple_devices],
        }
        mock_send.assert_called_with(
            "POST",
            "push/notify",
            orjson.dumps(post_data),
            extra_headers={"Content-type": "application/json"},
        )
        self.assertIn(
            f"INFO:zerver.lib.push_notifications:Sent mobile push notifications for user {user.id} through bouncer: 1 via FCM devices, 3 via APNs devices",
            mock_logging_info.output,
        )

        remote_realm_count = RealmCount.objects.values("property", "subgroup", "value").last()
        self.assertEqual(
            remote_realm_count,
            dict(
                property="mobile_pushes_sent::day",
                subgroup=None,
                value=4,
            ),
        )

        self.assertEqual(PushDeviceToken.objects.filter(kind=PushDeviceToken.APNS).count(), 0)
        self.assertEqual(PushDeviceToken.objects.filter(kind=PushDeviceToken.FCM).count(), 0)

        # Now simulating getting "can_push" as False from the bouncer and verify
        # that we update the realm value.
        mock_send.return_value = {
            "total_android_devices": 1,
            "total_apple_devices": 3,
            "realm": {"can_push": False, "expected_end_timestamp": None},
            "deleted_devices": DevicesToCleanUpDict(
                android_devices=[],
                apple_devices=[],
            ),
        }
        send_notifications_to_bouncer(
            user, {"apns": True}, {"gcm": True}, {}, list(android_devices), list(apple_devices)
        )
        user.realm.refresh_from_db()
        self.assertEqual(user.realm.push_notifications_enabled, False)


@activate_push_notification_service()
class TestSendToPushBouncer(ZulipTestCase):
    def add_mock_response(
        self, body: bytes = orjson.dumps({"msg": "error"}), status: int = 200
    ) -> None:
        assert settings.ZULIP_SERVICES_URL is not None
        URL = settings.ZULIP_SERVICES_URL + "/api/v1/remotes/register"
        responses.add(responses.POST, URL, body=body, status=status)

    @responses.activate
    def test_500_error(self) -> None:
        self.add_mock_response(status=500)
        with self.assertLogs(level="WARNING") as m:
            with self.assertRaises(PushNotificationBouncerServerError):
                send_to_push_bouncer("POST", "register", {"data": "true"})
            self.assertEqual(m.output, ["WARNING:root:Received 500 from push notification bouncer"])

    @responses.activate
    def test_400_error(self) -> None:
        self.add_mock_response(status=400)
        with self.assertRaises(JsonableError) as exc:
            send_to_push_bouncer("POST", "register", {"msg": "true"})
        self.assertEqual(exc.exception.msg, "error")

    @responses.activate
    def test_400_error_invalid_server_key(self) -> None:
        from zilencer.auth import InvalidZulipServerError

        # This is the exception our decorator uses for an invalid Zulip server
        error_response = json_response_from_error(InvalidZulipServerError("testRole"))
        self.add_mock_response(body=error_response.content, status=error_response.status_code)
        with self.assertRaises(PushNotificationBouncerError) as exc:
            send_to_push_bouncer("POST", "register", {"msg": "true"})
        self.assertEqual(
            str(exc.exception),
            "Push notifications bouncer error: "
            "Zulip server auth failure: testRole is not registered -- did you run `manage.py register_server`?",
        )

    @responses.activate
    def test_400_error_when_content_is_not_serializable(self) -> None:
        self.add_mock_response(body=b"/", status=400)
        with self.assertRaises(orjson.JSONDecodeError):
            send_to_push_bouncer("POST", "register", {"msg": "true"})

    @responses.activate
    def test_300_error(self) -> None:
        self.add_mock_response(body=b"/", status=300)
        with self.assertRaises(PushNotificationBouncerError) as exc:
            send_to_push_bouncer("POST", "register", {"msg": "true"})
        self.assertEqual(
            str(exc.exception), "Push notification bouncer returned unexpected status code 300"
        )


class TestAddRemoveDeviceTokenAPI(BouncerTestCase):
    @responses.activate
    def test_add_and_remove_device_tokens_api_error_handling(self) -> None:
        user = self.example_user("cordelia")
        self.login_user(user)

        endpoints: list[tuple[str, str, Mapping[str, str]]] = [
            ("/json/users/me/apns_device_token", "c0ffee", {"appid": "org.zulip.Zulip"}),
            ("/json/users/me/android_gcm_reg_id", "android-token", {}),
        ]

        # Test error handling
        for endpoint, label, appid in endpoints:
            # Try adding/removing tokens that are too big...
            broken_token = "a" * 5000  # too big
            result = self.client_post(endpoint, {"token": broken_token, **appid})
            self.assert_json_error(result, "Empty or invalid length token")

            if "apns" in endpoint:
                result = self.client_post(
                    endpoint, {"token": "xyz has non-hex characters", **appid}
                )
                self.assert_json_error(result, "Invalid APNS token")

            result = self.client_delete(endpoint, {"token": broken_token})
            self.assert_json_error(result, "Empty or invalid length token")

            # Try adding with missing or invalid appid...
            if appid:
                result = self.client_post(endpoint, {"token": label})
                self.assert_json_error(result, "Missing 'appid' argument")

                result = self.client_post(endpoint, {"token": label, "appid": "'; tables --"})
                self.assert_json_error(result, "appid has invalid format")

            # Try to remove a non-existent token...
            result = self.client_delete(endpoint, {"token": "abcd1234"})
            self.assert_json_error(result, "Token does not exist")

            # Use push notification bouncer and try to remove non-existing tokens.
            with (
                activate_push_notification_service(),
                responses.RequestsMock() as resp,
            ):
                assert settings.ZULIP_SERVICES_URL is not None
                URL = settings.ZULIP_SERVICES_URL + "/api/v1/remotes/push/unregister"
                resp.add_callback(responses.POST, URL, callback=self.request_callback)
                result = self.client_delete(endpoint, {"token": "abcd1234"})
                self.assert_json_error(result, "Token does not exist")
                self.assertTrue(resp.assert_call_count(URL, 1))

    @responses.activate
    def test_add_and_remove_device_tokens_api(self) -> None:
        user = self.example_user("cordelia")
        self.login_user(user)

        no_bouncer_requests: list[tuple[str, str, Mapping[str, str]]] = [
            ("/json/users/me/apns_device_token", "c0ffee01", {"appid": "org.zulip.Zulip"}),
            ("/json/users/me/android_gcm_reg_id", "android-token-1", {}),
        ]

        bouncer_requests: list[tuple[str, str, Mapping[str, str]]] = [
            ("/json/users/me/apns_device_token", "c0ffee02", {"appid": "org.zulip.Zulip"}),
            ("/json/users/me/android_gcm_reg_id", "android-token-2", {}),
        ]

        # Add tokens without using push notification bouncer.
        for endpoint, token, appid in no_bouncer_requests:
            # Test that we can push twice.
            result = self.client_post(endpoint, {"token": token, **appid})
            self.assert_json_success(result)

            result = self.client_post(endpoint, {"token": token, **appid})
            self.assert_json_success(result)

            tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
            self.assert_length(tokens, 1)
            self.assertEqual(tokens[0].token, token)

        with activate_push_notification_service():
            self.add_mock_response()
            # Enable push notification bouncer and add tokens.
            for endpoint, token, appid in bouncer_requests:
                # Test that we can push twice.
                result = self.client_post(endpoint, {"token": token, **appid})
                self.assert_json_success(result)

                result = self.client_post(endpoint, {"token": token, **appid})
                self.assert_json_success(result)

                tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
                self.assert_length(tokens, 1)
                self.assertEqual(tokens[0].token, token)

                remote_tokens = list(
                    RemotePushDeviceToken.objects.filter(user_uuid=user.uuid, token=token)
                )
                self.assert_length(remote_tokens, 1)
                self.assertEqual(remote_tokens[0].token, token)

        # PushDeviceToken will include all the device tokens.
        token_values = list(PushDeviceToken.objects.values_list("token", flat=True))
        self.assertEqual(
            token_values, ["c0ffee01", "android-token-1", "c0ffee02", "android-token-2"]
        )

        # RemotePushDeviceToken will only include tokens of
        # the devices using push notification bouncer.
        remote_token_values = list(RemotePushDeviceToken.objects.values_list("token", flat=True))
        self.assertEqual(sorted(remote_token_values), ["android-token-2", "c0ffee02"])

        # Test removing tokens without using push notification bouncer.
        for endpoint, token, appid in no_bouncer_requests:
            result = self.client_delete(endpoint, {"token": token})
            self.assert_json_success(result)
            tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
            self.assert_length(tokens, 0)

        # Use push notification bouncer and test removing device tokens.
        # Tokens will be removed both locally and remotely.
        with activate_push_notification_service():
            for endpoint, token, appid in bouncer_requests:
                result = self.client_delete(endpoint, {"token": token})
                self.assert_json_success(result)
                tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
                remote_tokens = list(
                    RemotePushDeviceToken.objects.filter(user_uuid=user.uuid, token=token)
                )
                self.assert_length(tokens, 0)
                self.assert_length(remote_tokens, 0)

        # Verify that the above process indeed removed all the tokens we created.
        self.assertEqual(RemotePushDeviceToken.objects.all().count(), 0)
        self.assertEqual(PushDeviceToken.objects.all().count(), 0)


class GCMParseOptionsTest(ZulipTestCase):
    def test_invalid_option(self) -> None:
        with self.assertRaises(JsonableError):
            parse_fcm_options({"invalid": True}, {})

    def test_invalid_priority_value(self) -> None:
        with self.assertRaises(JsonableError):
            parse_fcm_options({"priority": "invalid"}, {})

    def test_default_priority(self) -> None:
        self.assertEqual("high", parse_fcm_options({}, {"event": "message"}))
        self.assertEqual("normal", parse_fcm_options({}, {"event": "remove"}))
        self.assertEqual("normal", parse_fcm_options({}, {}))

    def test_explicit_priority(self) -> None:
        self.assertEqual("normal", parse_fcm_options({"priority": "normal"}, {}))
        self.assertEqual("high", parse_fcm_options({"priority": "high"}, {}))


@mock.patch("zerver.lib.push_notifications.fcm_app")
@mock.patch("zerver.lib.push_notifications.firebase_messaging")
class FCMSendTest(PushNotificationTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.setup_fcm_tokens()

    def get_fcm_data(self, **kwargs: Any) -> dict[str, Any]:
        data = {
            "key 1": "Data 1",
            "key 2": "Data 2",
        }
        data.update(kwargs)
        return data

    def test_fcm_is_none(self, mock_fcm_messaging: mock.MagicMock, fcm_app: mock.MagicMock) -> None:
        fcm_app.__bool__.return_value = False
        with self.assertLogs("zerver.lib.push_notifications", level="DEBUG") as logger:
            send_android_push_notification_to_user(self.user_profile, {}, {})
            self.assertEqual(
                "DEBUG:zerver.lib.push_notifications:"
                "Skipping sending a FCM push notification since ZULIP_SERVICE_PUSH_NOTIFICATIONS "
                "and ANDROID_FCM_CREDENTIALS_PATH are both unset",
                logger.output[0],
            )

    def test_send_raises_error(
        self, mock_fcm_messaging: mock.MagicMock, fcm_app: mock.MagicMock
    ) -> None:
        mock_fcm_messaging.send_each.side_effect = firebase_exceptions.FirebaseError(
            firebase_exceptions.UNKNOWN, "error"
        )
        with self.assertLogs("zerver.lib.push_notifications", level="WARNING") as logger:
            send_android_push_notification_to_user(self.user_profile, {}, {})
            self.assertIn(
                "WARNING:zerver.lib.push_notifications:Error while pushing to FCM\nTraceback ",
                logger.output[0],
            )

    @mock.patch("zerver.lib.push_notifications.logger.warning")
    def test_success(
        self,
        mock_warning: mock.MagicMock,
        mock_fcm_messaging: mock.MagicMock,
        fcm_app: mock.MagicMock,
    ) -> None:
        res = {}
        res["success"] = {token: ind for ind, token in enumerate(self.fcm_tokens)}
        response = self.make_fcm_success_response(self.fcm_tokens)
        mock_fcm_messaging.send_each.return_value = response

        data = self.get_fcm_data()
        with self.assertLogs("zerver.lib.push_notifications", level="INFO") as logger:
            send_android_push_notification_to_user(self.user_profile, data, {})
        self.assert_length(logger.output, 3)
        log_msg1 = f"INFO:zerver.lib.push_notifications:FCM: Sending notification for local user <id:{self.user_profile.id}> to 2 devices"
        log_msg2 = f"INFO:zerver.lib.push_notifications:FCM: Sent message with ID: {response.responses[0].message_id} to {self.fcm_tokens[0]}"
        log_msg3 = f"INFO:zerver.lib.push_notifications:FCM: Sent message with ID: {response.responses[1].message_id} to {self.fcm_tokens[1]}"

        self.assertEqual([log_msg1, log_msg2, log_msg3], logger.output)
        mock_warning.assert_not_called()

    def test_not_registered(
        self, mock_fcm_messaging: mock.MagicMock, fcm_app: mock.MagicMock
    ) -> None:
        token = "1111"
        response = self.make_fcm_error_response(
            token, firebase_messaging.UnregisteredError("Requested entity was not found.")
        )
        mock_fcm_messaging.send_each.return_value = response

        def get_count(token: str) -> int:
            return PushDeviceToken.objects.filter(token=token, kind=PushDeviceToken.FCM).count()

        self.assertEqual(get_count("1111"), 1)

        data = self.get_fcm_data()
        with self.assertLogs("zerver.lib.push_notifications", level="INFO") as logger:
            send_android_push_notification_to_user(self.user_profile, data, {})
            self.assertEqual(
                f"INFO:zerver.lib.push_notifications:FCM: Sending notification for local user <id:{self.user_profile.id}> to 2 devices",
                logger.output[0],
            )
            self.assertEqual(
                f"INFO:zerver.lib.push_notifications:FCM: Removing {token} due to NOT_FOUND",
                logger.output[1],
            )
        self.assertEqual(get_count("1111"), 0)

    def test_failure(self, mock_fcm_messaging: mock.MagicMock, fcm_app: mock.MagicMock) -> None:
        token = "1111"
        response = self.make_fcm_error_response(token, firebase_exceptions.UnknownError("Failed"))
        mock_fcm_messaging.send_each.return_value = response

        data = self.get_fcm_data()
        with self.assertLogs("zerver.lib.push_notifications", level="WARNING") as logger:
            send_android_push_notification_to_user(self.user_profile, data, {})
            msg = f"WARNING:zerver.lib.push_notifications:FCM: Delivery failed for {token}: <class 'firebase_admin.exceptions.UnknownError'>:Failed"

            self.assertEqual(msg, logger.output[0])


class TestClearOnRead(ZulipTestCase):
    def test_mark_stream_as_read(self) -> None:
        n_msgs = 3

        hamlet = self.example_user("hamlet")
        hamlet.enable_stream_push_notifications = True
        hamlet.save()
        stream = self.subscribe(hamlet, "Denmark")

        message_ids = [
            self.send_stream_message(self.example_user("iago"), stream.name, f"yo {i}")
            for i in range(n_msgs)
        ]
        UserMessage.objects.filter(
            user_profile_id=hamlet.id,
            message_id__in=message_ids,
        ).update(flags=F("flags").bitor(UserMessage.flags.active_mobile_push_notification))

        with mock_queue_publish("zerver.actions.message_flags.queue_event_on_commit") as m:
            assert stream.recipient_id is not None
            do_mark_stream_messages_as_read(hamlet, stream.recipient_id)
            queue_items = [c[0][1] for c in m.call_args_list]
            groups = [item["message_ids"] for item in queue_items]

        self.assert_length(groups, 1)
        self.assertEqual(sum(len(g) for g in groups), len(message_ids))
        self.assertEqual({id for g in groups for id in g}, set(message_ids))


class TestPushNotificationsContent(ZulipTestCase):
    def test_fixtures(self) -> None:
        fixtures = orjson.loads(self.fixture_data("markdown_test_cases.json"))
        tests = fixtures["regular_tests"]
        for test in tests:
            if "text_content" in test:
                with self.subTest(markdown_test_case=test["name"]):
                    output = get_mobile_push_content(test["expected_output"])
                    self.assertEqual(output, test["text_content"])

    def test_backend_only_fixtures(self) -> None:
        realm = get_realm("zulip")
        cordelia = self.example_user("cordelia")
        stream = get_stream("Verona", realm)

        fixtures = [
            {
                "name": "realm_emoji",
                "rendered_content": f'<p>Testing <img alt=":green_tick:" class="emoji" src="/user_avatars/{realm.id}/emoji/green_tick.png" title="green tick"> realm emoji.</p>',
                "expected_output": "Testing :green_tick: realm emoji.",
            },
            {
                "name": "mentions",
                "rendered_content": f'<p>Mentioning <span class="user-mention" data-user-id="{cordelia.id}">@Cordelia, Lear\'s daughter</span>.</p>',
                "expected_output": "Mentioning @Cordelia, Lear's daughter.",
            },
            {
                "name": "stream_names",
                "rendered_content": f'<p>Testing stream names <a class="stream" data-stream-id="{stream.id}" href="/#narrow/channel/Verona">#Verona</a>.</p>',
                "expected_output": "Testing stream names #Verona.",
            },
        ]

        for test in fixtures:
            actual_output = get_mobile_push_content(test["rendered_content"])
            self.assertEqual(actual_output, test["expected_output"])


@skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
class PushBouncerSignupTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()

        # Set up a DNS lookup mock for all the tests, so that they don't have to
        # worry about it failing, unless they intentionally want to set it up
        # to happen.
        self.dns_resolver_patcher = mock.patch(
            "zilencer.views.dns_resolver.Resolver.resolve", return_value=["whee"]
        )
        self.dns_resolver_mock = self.dns_resolver_patcher.start()

    @override
    def tearDown(self) -> None:
        self.dns_resolver_patcher.stop()

    def test_deactivate_remote_server(self) -> None:
        zulip_org_id = str(uuid.uuid4())
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
            contact_email="server-admin@zulip.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)
        server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
        self.assertEqual(server.hostname, "example.com")
        self.assertEqual(server.contact_email, "server-admin@zulip.com")

        result = self.uuid_post(zulip_org_id, "/api/v1/remotes/server/deactivate", subdomain="")
        self.assert_json_success(result)

        server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
        remote_realm_audit_log = RemoteZulipServerAuditLog.objects.filter(
            event_type=AuditLogEventType.REMOTE_SERVER_DEACTIVATED
        ).last()
        assert remote_realm_audit_log is not None
        self.assertTrue(server.deactivated)

        # Now test that trying to deactivate again reports the right error.
        result = self.uuid_post(
            zulip_org_id, "/api/v1/remotes/server/deactivate", request, subdomain=""
        )
        self.assert_json_error(
            result,
            "The mobile push notification service registration for your server has been deactivated",
            status_code=401,
        )

        # Now try to do a request to server/register again. Normally, this updates
        # the server's registration details. But the server is deactivated, so it
        # should return the corresponding error.
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(
            result,
            "The mobile push notification service registration for your server has been deactivated",
            status_code=401,
        )

    def test_push_signup_invalid_host(self) -> None:
        zulip_org_id = str(uuid.uuid4())
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="invalid-host",
            contact_email="server-admin@zulip.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(result, "invalid-host is not a valid hostname")

        request["hostname"] = "example.com/path"
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(
            result, "example.com/path contains invalid components (e.g., path, query, fragment)."
        )

    def test_push_signup_invalid_zulip_org_id(self) -> None:
        zulip_org_id = "x" * RemoteZulipServer.UUID_LENGTH
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
            contact_email="server-admin@zulip.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(result, "Invalid UUID")

        # This looks mostly like a proper UUID, but isn't actually a valid UUIDv4,
        # which makes it slip past a basic validation via initializing uuid.UUID with it.
        # Thus we should test this scenario separately.
        zulip_org_id = "18cedb98-5222-5f34-50a9-fc418e1ba972"
        request["zulip_org_id"] = zulip_org_id
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(result, "Invalid UUID")

        # check if zulip org id is of allowed length
        zulip_org_id = "18cedb98"
        request["zulip_org_id"] = zulip_org_id
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(result, "zulip_org_id is not length 36")

    def test_push_signup_invalid_zulip_org_key(self) -> None:
        zulip_org_id = str(uuid.uuid4())
        zulip_org_key = get_random_string(63)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="invalid-host",
            contact_email="server-admin@zulip.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(result, "zulip_org_key is not length 64")

    def test_push_signup_success(self) -> None:
        zulip_org_id = str(uuid.uuid4())
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
            contact_email="server-admin@zulip.com",
        )

        time_sent = now()

        with time_machine.travel(time_sent, tick=False):
            result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)
        server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
        self.assertEqual(server.hostname, "example.com")
        self.assertEqual(server.contact_email, "server-admin@zulip.com")
        self.assertEqual(server.last_request_datetime, time_sent)

        # Update our hostname
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="zulip.example.com",
            contact_email="server-admin@zulip.com",
        )

        with time_machine.travel(time_sent + timedelta(minutes=1), tick=False):
            result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)
        server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
        self.assertEqual(server.hostname, "zulip.example.com")
        self.assertEqual(server.contact_email, "server-admin@zulip.com")
        self.assertEqual(server.last_request_datetime, time_sent + timedelta(minutes=1))

        # Now test rotating our key
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
            contact_email="server-admin@zulip.com",
            new_org_key=get_random_string(64),
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)
        server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
        self.assertEqual(server.hostname, "example.com")
        self.assertEqual(server.contact_email, "server-admin@zulip.com")
        zulip_org_key = request["new_org_key"]
        self.assertEqual(server.api_key, zulip_org_key)

        # Update contact_email
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="zulip.example.com",
            contact_email="new-server-admin@zulip.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)
        server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
        self.assertEqual(server.hostname, "zulip.example.com")
        self.assertEqual(server.contact_email, "new-server-admin@zulip.com")

        # Now test trying to double-create with a new random key fails
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=get_random_string(64),
            hostname="example.com",
            contact_email="server-admin@zulip.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(
            result, f"Zulip server auth failure: key does not match role {zulip_org_id}"
        )

    def test_register_duplicate_hostname(self) -> None:
        zulip_org_id = str(uuid.uuid4())
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
            contact_email="server-admin@zulip.com",
        )

        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)
        server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
        self.assertEqual(server.hostname, "example.com")

        new_zulip_org_id = str(uuid.uuid4())
        new_zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=new_zulip_org_id,
            zulip_org_key=new_zulip_org_key,
            hostname="example.com",
            contact_email="server-admin@zulip.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(result, "A server with hostname example.com already exists")
        self.assertEqual(result.json()["code"], "HOSTNAME_ALREADY_IN_USE_BOUNCER_ERROR")

    def test_register_contact_email_validation_rules(self) -> None:
        zulip_org_id = str(uuid.uuid4())
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
        )

        request["contact_email"] = "server-admin"
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(result, "Enter a valid email address.")

        request["contact_email"] = "admin@example.com"
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(result, "Invalid email address.")

        # An example disposable domain.
        request["contact_email"] = "admin@mailnator.com"
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(result, "Please use your real email address.")

        request["contact_email"] = "admin@zulip.com"
        with mock.patch("zilencer.views.dns_resolver.Resolver") as resolver:
            resolver.return_value.resolve.side_effect = DNSNoAnswer
            resolver.return_value.resolve_name.return_value = ["whee"]
            result = self.client_post("/api/v1/remotes/server/register", request)
            self.assert_json_error(
                result, "zulip.com is invalid because it does not have any MX records"
            )

        with mock.patch("zilencer.views.dns_resolver.Resolver") as resolver:
            resolver.return_value.resolve.side_effect = DNSNoAnswer
            resolver.return_value.resolve_name.side_effect = DNSNoAnswer
            result = self.client_post("/api/v1/remotes/server/register", request)
            self.assert_json_error(result, "zulip.com does not exist")

        with mock.patch("zilencer.views.dns_resolver.Resolver") as resolver:
            resolver.return_value.resolve.return_value = ["whee"]
            result = self.client_post("/api/v1/remotes/server/register", request)
            self.assert_json_success(result)


@skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
class RegistrationTakeoverFlowTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()

        self.zulip_org_id = str(uuid.uuid4())
        self.zulip_org_key = get_random_string(64)
        self.hostname = "example.com"
        request = dict(
            zulip_org_id=self.zulip_org_id,
            zulip_org_key=self.zulip_org_key,
            hostname=self.hostname,
            contact_email="server-admin@zulip.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)

    @responses.activate
    def test_flow_end_to_end(self) -> None:
        server = RemoteZulipServer.objects.get(uuid=self.zulip_org_id)

        result = self.client_post(
            "/api/v1/remotes/server/register/transfer", {"hostname": self.hostname}
        )
        self.assert_json_success(result)
        data = result.json()
        verification_secret = data["verification_secret"]

        access_token = prepare_for_registration_transfer_challenge(verification_secret)
        # First we query the host's endpoint for serving the verification_secret.
        result = self.client_post(f"/api/v1/zulip-services/verify/{access_token}/")
        self.assert_json_success(result)
        data = result.json()
        served_verification_secret = data["verification_secret"]
        self.assertEqual(served_verification_secret, verification_secret)

        # Now we return to testing the push bouncer and we send it the request that the hosts's
        # admin will once the host is ready to serve the verification_secret.
        responses.add(
            responses.GET,
            f"https://example.com/api/v1/zulip-services/verify/{access_token}/",
            json={"verification_secret": verification_secret},
            status=200,
        )
        with self.assertLogs("zilencer.views", level="INFO") as mock_log:
            result = self.client_post(
                "/api/v1/remotes/server/register/verify_challenge",
                {"hostname": self.hostname, "access_token": access_token},
            )
        self.assert_json_success(result)
        new_uuid = result.json()["zulip_org_id"]
        new_key = result.json()["zulip_org_key"]
        # The uuid of the registration is preserved and delivered in this final response,
        # but the secret key is rotated.
        self.assertEqual(new_uuid, self.zulip_org_id)
        self.assertNotEqual(new_key, self.zulip_org_key)
        self.assertEqual(
            mock_log.output,
            ["INFO:zilencer.views:verify_registration_transfer:host:example.com|success"],
        )

        # Verify the registration got updated accordingly.
        server.refresh_from_db()
        self.assertEqual(str(server.uuid), new_uuid)
        self.assertEqual(server.api_key, new_key)

        audit_log = RemoteZulipServerAuditLog.objects.filter(server=server).latest("id")
        self.assertEqual(
            audit_log.event_type, AuditLogEventType.REMOTE_SERVER_REGISTRATION_TRANSFERRED
        )

    @override_settings(
        RATE_LIMITING=True,
        ABSOLUTE_USAGE_LIMITS_BY_ENDPOINT={
            "verify_registration_transfer_challenge_ack_endpoint": [(10, 2)]
        },
    )
    @responses.activate
    def test_rate_limiting(self) -> None:
        responses.get(
            "https://example.com/api/v1/zulip-services/verify/sometoken/",
            json={"verification_secret": "foo"},
            status=200,
        )

        result = self.client_post(
            "/api/v1/remotes/server/register/verify_challenge",
            {"hostname": self.hostname, "access_token": "sometoken"},
        )
        self.assert_json_error(result, "The verification secret is malformed")
        result = self.client_post(
            "/api/v1/remotes/server/register/verify_challenge",
            {"hostname": self.hostname, "access_token": "sometoken"},
        )
        self.assert_json_error(result, "The verification secret is malformed")

        # Now the rate limit is hit.
        with self.assertLogs("zilencer.views", level="WARNING") as mock_log:
            result = self.client_post(
                "/api/v1/remotes/server/register/verify_challenge",
                {"hostname": self.hostname, "access_token": "sometoken"},
            )
        self.assert_json_error(
            result,
            f"The global limits on recent usage of this endpoint have been reached. Please try again later or reach out to {FromAddress.SUPPORT} for assistance.",
            status_code=429,
        )
        self.assertEqual(
            mock_log.output,
            [
                "WARNING:zilencer.views:Rate limit exceeded for verify_registration_transfer_challenge_ack_endpoint"
            ],
        )

    @responses.activate
    def test_ack_endpoint_errors(self) -> None:
        time_now = now()

        result = self.client_post(
            "/api/v1/remotes/server/register/verify_challenge",
            {"hostname": "unregistered.example.com", "access_token": "sometoken"},
        )
        self.assert_json_error(result, "Registration not found for this hostname")

        responses.get(
            "https://example.com/api/v1/zulip-services/verify/sometoken/",
            json={"verification_secret": "foo"},
            status=200,
        )

        result = self.client_post(
            "/api/v1/remotes/server/register/verify_challenge",
            {"hostname": self.hostname, "access_token": "sometoken"},
        )
        self.assert_json_error(result, "The verification secret is malformed")

        with time_machine.travel(time_now, tick=False):
            verification_secret = generate_registration_transfer_verification_secret(self.hostname)
        responses.get(
            "https://example.com/api/v1/zulip-services/verify/sometoken/",
            json={"verification_secret": verification_secret},
            status=200,
        )
        with time_machine.travel(
            time_now + timedelta(seconds=REMOTE_SERVER_TAKEOVER_TOKEN_VALIDITY_SECONDS + 1),
            tick=False,
        ):
            result = self.client_post(
                "/api/v1/remotes/server/register/verify_challenge",
                {"hostname": self.hostname, "access_token": "sometoken"},
            )
            self.assert_json_error(result, "The verification secret has expired")

        with (
            time_machine.travel(time_now, tick=False),
            mock.patch("zilencer.auth.REMOTE_SERVER_TAKEOVER_TOKEN_SALT", "foo"),
        ):
            verification_secret = generate_registration_transfer_verification_secret(self.hostname)
        responses.get(
            "https://example.com/api/v1/zulip-services/verify/sometoken/",
            json={"verification_secret": verification_secret},
            status=200,
        )
        result = self.client_post(
            "/api/v1/remotes/server/register/verify_challenge",
            {"hostname": self.hostname, "access_token": "sometoken"},
        )
        self.assert_json_error(result, "The verification secret is invalid")

        # Make sure a valid verification secret for one hostname does not work for another.
        with time_machine.travel(time_now, tick=False):
            verification_secret = generate_registration_transfer_verification_secret(
                "different.example.com"
            )
            responses.get(
                "https://example.com/api/v1/zulip-services/verify/sometoken/",
                json={"verification_secret": verification_secret},
                status=200,
            )
            result = self.client_post(
                "/api/v1/remotes/server/register/verify_challenge",
                {"hostname": self.hostname, "access_token": "sometoken"},
            )
        self.assert_json_error(result, "The verification secret is for a different hostname")

    @responses.activate
    def test_outgoing_verification_request_errors(self) -> None:
        access_token = "sometoken"
        base_url = f"https://{self.hostname}/api/v1/zulip-services/verify/{access_token}/"

        responses.add(
            method=responses.GET,
            url=base_url,
            json={"code": "REMOTE_SERVER_VERIFICATION_SECRET_NOT_PREPARED"},
            status=400,
        )
        with self.assertLogs("zilencer.views", level="INFO") as mock_log:
            result = self.client_post(
                "/api/v1/remotes/server/register/verify_challenge",
                {"hostname": self.hostname, "access_token": access_token},
            )
        self.assert_json_error(result, "The host reported it has no verification secret.")
        self.assertEqual(
            mock_log.output,
            [
                "INFO:zilencer.views:verify_registration_transfer:host:example.com|secret_not_prepared"
            ],
        )

        # HttpError:
        responses.add(
            method=responses.GET,
            url=base_url,
            status=403,
        )
        with self.assertLogs("zilencer.views", level="INFO") as mock_log:
            result = self.client_post(
                "/api/v1/remotes/server/register/verify_challenge",
                {"hostname": self.hostname, "access_token": access_token},
            )
        self.assert_json_error(result, "Error response received from the host: 403")
        self.assertIn(
            "verify_registration_transfer:host:example.com|exception:", mock_log.output[0]
        )

        # SSLError:
        responses.add(
            method=responses.GET,
            url=base_url,
            body=requests.exceptions.SSLError("certificate verification failed"),
        )
        with self.assertLogs("zilencer.views", level="INFO") as mock_log:
            result = self.client_post(
                "/api/v1/remotes/server/register/verify_challenge",
                {"hostname": self.hostname, "access_token": access_token},
            )
        self.assert_json_error(result, "SSL error occurred while communicating with the host.")
        self.assertIn(
            "verify_registration_transfer:host:example.com|exception:", mock_log.output[0]
        )

        # ConnectionError:
        responses.add(
            method=responses.GET,
            url=base_url,
            body=requests.exceptions.ConnectionError("Fake connection error"),
        )
        with self.assertLogs("zilencer.views", level="INFO") as mock_log:
            result = self.client_post(
                "/api/v1/remotes/server/register/verify_challenge",
                {"hostname": self.hostname, "access_token": access_token},
            )
        self.assert_json_error(
            result, "Connection error occurred while communicating with the host."
        )
        self.assertIn(
            "verify_registration_transfer:host:example.com|exception:", mock_log.output[0]
        )

        # Timeout:
        responses.add(
            method=responses.GET,
            url=base_url,
            body=requests.exceptions.Timeout("The request timed out"),
        )
        with self.assertLogs("zilencer.views", level="INFO") as mock_log:
            result = self.client_post(
                "/api/v1/remotes/server/register/verify_challenge",
                {"hostname": self.hostname, "access_token": access_token},
            )
        self.assert_json_error(result, "The request timed out while communicating with the host.")
        self.assertIn(
            "verify_registration_transfer:host:example.com|exception:", mock_log.output[0]
        )

        # Generic RequestException:
        responses.add(
            method=responses.GET,
            url=base_url,
            body=requests.exceptions.RequestException("Something else went wrong"),
        )
        with self.assertLogs("zilencer.views", level="INFO") as mock_log:
            result = self.client_post(
                "/api/v1/remotes/server/register/verify_challenge",
                {"hostname": self.hostname, "access_token": access_token},
            )
        self.assert_json_error(result, "An error occurred while communicating with the host.")
        self.assertIn(
            "verify_registration_transfer:host:example.com|exception:", mock_log.output[0]
        )

    def test_initiate_flow_for_unregistered_domain(self) -> None:
        result = self.client_post(
            "/api/v1/remotes/server/register/transfer",
            {"hostname": "unregistered.example.com"},
        )
        self.assert_json_error(result, "unregistered.example.com not yet registered")

    def test_serve_verification_secret_endpoint(self) -> None:
        result = self.client_get(
            "/api/v1/zulip-services/verify/sometoken/",
        )
        self.assert_json_error(result, "Verification secret not prepared")

        valid_access_token = prepare_for_registration_transfer_challenge(verification_secret="foo")
        result = self.client_get(
            f"/api/v1/zulip-services/verify/{valid_access_token}/",
        )
        self.assert_json_success(result)
        self.assertEqual(result.json()["verification_secret"], "foo")

        # Trying to access the verification secret with the wrong access_token should fail
        # in a way indistinguishable from the case where the host is not prepared to serve
        # a verification secret at all.
        result = self.client_get(
            "/api/v1/zulip-services/verify/wrongtoken/",
        )
        self.assert_json_error(result, "Verification secret not prepared")


class TestUserPushIdentityCompat(ZulipTestCase):
    def test_filter_q(self) -> None:
        user_identity_id = UserPushIdentityCompat(user_id=1)
        user_identity_uuid = UserPushIdentityCompat(user_uuid="aaaa")
        user_identity_both = UserPushIdentityCompat(user_id=1, user_uuid="aaaa")

        self.assertEqual(user_identity_id.filter_q(), Q(user_id=1))
        self.assertEqual(user_identity_uuid.filter_q(), Q(user_uuid="aaaa"))
        self.assertEqual(user_identity_both.filter_q(), Q(user_uuid="aaaa") | Q(user_id=1))

    def test_eq(self) -> None:
        user_identity_a = UserPushIdentityCompat(user_id=1)
        user_identity_b = UserPushIdentityCompat(user_id=1)
        user_identity_c = UserPushIdentityCompat(user_id=2)
        self.assertEqual(user_identity_a, user_identity_b)
        self.assertNotEqual(user_identity_a, user_identity_c)

        # An integer can't be equal to an instance of the class.
        self.assertNotEqual(user_identity_a, 1)
