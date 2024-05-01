import asyncio
import base64
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple, Union
from unittest import mock, skipUnless

import aioapns
import DNS
import orjson
import responses
import time_machine
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.http.response import ResponseHeaders
from django.test import override_settings
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from requests.exceptions import ConnectionError
from requests.models import PreparedRequest
from typing_extensions import override

from analytics.lib.counts import CountStat, LoggingCountStat
from analytics.models import InstallationCount, RealmCount, UserCount
from corporate.lib.stripe import RemoteRealmBillingSession
from corporate.models import CustomerPlan
from version import ZULIP_VERSION
from zerver.actions.create_realm import do_create_realm
from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_flags import do_mark_stream_messages_as_read, do_update_message_flags
from zerver.actions.realm_settings import (
    do_change_realm_org_type,
    do_deactivate_realm,
    do_set_realm_authentication_methods,
)
from zerver.actions.user_groups import add_subgroups_to_user_group, check_add_user_group
from zerver.actions.user_settings import do_change_user_setting, do_regenerate_api_key
from zerver.actions.user_topics import do_set_user_topic_visibility_policy
from zerver.lib import redis_utils
from zerver.lib.avatar import absolute_avatar_url, get_avatar_for_inaccessible_user
from zerver.lib.exceptions import JsonableError
from zerver.lib.push_notifications import (
    APNsContext,
    DeviceToken,
    InvalidRemotePushDeviceTokenError,
    UserPushIdentityCompat,
    b64_to_hex,
    get_apns_badge_count,
    get_apns_badge_count_future,
    get_apns_context,
    get_base_payload,
    get_message_payload_apns,
    get_message_payload_gcm,
    get_mobile_push_content,
    handle_push_notification,
    handle_remove_push_notification,
    hex_to_b64,
    modernize_apns_payload,
    parse_gcm_options,
    send_android_push_notification_to_user,
    send_apple_push_notification,
    send_notifications_to_bouncer,
)
from zerver.lib.remote_server import (
    PUSH_NOTIFICATIONS_RECENTLY_WORKING_REDIS_KEY,
    AnalyticsRequest,
    PushNotificationBouncerError,
    PushNotificationBouncerRetryLaterError,
    PushNotificationBouncerServerError,
    build_analytics_data,
    get_realms_info_for_push_bouncer,
    record_push_notifications_recently_working,
    redis_client,
    send_server_data_to_push_bouncer,
    send_to_push_bouncer,
)
from zerver.lib.response import json_response_from_error
from zerver.lib.test_classes import BouncerTestCase, ZulipTestCase
from zerver.lib.test_helpers import (
    mock_queue_publish,
    reset_email_visibility_to_everyone_in_zulip_realm,
)
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.user_counts import realm_user_count_by_role
from zerver.models import (
    Message,
    PushDeviceToken,
    Realm,
    RealmAuditLog,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    UserProfile,
    UserTopic,
)
from zerver.models.clients import get_client
from zerver.models.realms import get_realm
from zerver.models.scheduled_jobs import NotificationTriggers
from zerver.models.streams import get_stream
from zilencer.lib.remote_counts import MissingDataError
from zilencer.models import RemoteZulipServerAuditLog
from zilencer.views import DevicesToCleanUpDict

if settings.ZILENCER_ENABLED:
    from zilencer.models import (
        RemoteInstallationCount,
        RemotePushDeviceToken,
        RemoteRealm,
        RemoteRealmAuditLog,
        RemoteRealmCount,
        RemoteZulipServer,
    )
    from zilencer.views import update_remote_realm_data_for_server


class SendTestPushNotificationEndpointTest(BouncerTestCase):
    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
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
            "token_kind": PushDeviceToken.GCM,
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
        token_kind = PushDeviceToken.GCM
        # We create a PushDeviceToken object, but no RemotePushDeviceToken object, to simulate
        # a missing registration on the bouncer.
        PushDeviceToken.objects.create(user=user, token=token, kind=token_kind)

        # As verified above, this is the response the server receives from the bouncer in this kind of case.
        # We have to simulate it with a response mock.
        error_response = json_response_from_error(InvalidRemotePushDeviceTokenError())
        responses.add(
            responses.POST,
            f"{settings.PUSH_NOTIFICATION_BOUNCER_URL}/api/v1/remotes/push/test_notification",
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
        android_token_kind = PushDeviceToken.GCM
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

        with mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification"
        ) as mock_send_android_push_notification, time_machine.travel(time_now, tick=False):
            result = self.api_post(user, endpoint, {"token": android_token}, subdomain="zulip")

        expected_android_payload = {
            "server": "testserver",
            "realm_id": user.realm_id,
            "realm_name": "Zulip Dev",
            "realm_uri": "http://zulip.testserver",
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

        with mock.patch(
            "zerver.lib.push_notifications.send_apple_push_notification"
        ) as mock_send_apple_push_notification, time_machine.travel(time_now, tick=False):
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
        with mock.patch(
            "zerver.lib.push_notifications.send_apple_push_notification"
        ) as mock_send_apple_push_notification, mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification"
        ) as mock_send_android_push_notification, time_machine.travel(time_now, tick=False):
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

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
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
        token_kind = PushDeviceToken.GCM
        PushDeviceToken.objects.create(user=user, token=token, kind=token_kind)
        remote_device = RemotePushDeviceToken.objects.create(
            server=server, user_uuid=str(user.uuid), token=token, kind=token_kind
        )

        endpoint = "/api/v1/mobile_push/test_notification"
        time_now = now()
        with mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification"
        ) as mock_send_android_push_notification, time_machine.travel(time_now, tick=False):
            result = self.api_post(user, endpoint, {"token": token}, subdomain="zulip")
        expected_payload = {
            "server": "testserver",
            "realm_id": user.realm_id,
            "realm_name": "Zulip Dev",
            "realm_uri": "http://zulip.testserver",
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
        token_kind = PushDeviceToken.GCM

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
        token_kind = PushDeviceToken.GCM

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
            {**args, "token_kind": PushDeviceToken.GCM},
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
        token_kind = PushDeviceToken.GCM

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
            kind=RemotePushDeviceToken.GCM,
            token=hex_to_b64("aaaa"),
            user_uuid=hamlet.uuid,
            server=server,
        )
        apple_token = RemotePushDeviceToken.objects.create(
            kind=RemotePushDeviceToken.APNS,
            token=hex_to_b64("bbbb"),
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
        with mock.patch(
            "zilencer.views.send_android_push_notification", return_value=1
        ), mock.patch("zilencer.views.send_apple_push_notification", return_value=1), mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
            return_value=10,
        ), self.assertLogs("zilencer.views", level="INFO"):
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
                    kind=RemotePushDeviceToken.GCM,
                    token=hex_to_b64(token + i),
                    user_id=hamlet.id,
                    server=server,
                )
            )

            # Create a duplicate, newer uuid-based registration for the same user to verify
            # the bouncer will handle that correctly, without triggering a duplicate notification,
            # and will delete the old, legacy registration.
            uuid_android_tokens.append(
                RemotePushDeviceToken.objects.create(
                    kind=RemotePushDeviceToken.GCM,
                    token=hex_to_b64(token + i),
                    user_uuid=str(hamlet.uuid),
                    server=server,
                )
            )

        apple_token = RemotePushDeviceToken.objects.create(
            kind=RemotePushDeviceToken.APNS,
            token=hex_to_b64(token),
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
        with mock.patch(
            "zilencer.views.send_android_push_notification", return_value=2
        ) as android_push, mock.patch(
            "zilencer.views.send_apple_push_notification", return_value=1
        ) as apple_push, mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
            return_value=10,
        ), time_machine.travel(time_sent, tick=False), self.assertLogs(
            "zilencer.views", level="INFO"
        ) as logger:
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
            list(reversed(uuid_android_tokens)),
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
            kind=RemotePushDeviceToken.GCM,
            token=hex_to_b64("aaaaaa"),
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
                    "realm_uri": hamlet.realm.uri,
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
            "realm_uri": hamlet.realm.uri,
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
            event_type=RealmAuditLog.USER_CREATED,
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
            event_type=RealmAuditLog.USER_DEACTIVATED,
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
            kind=RemotePushDeviceToken.GCM,
            token=hex_to_b64("aaaaaa"),
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
        with time_machine.travel(time_received, tick=False), mock.patch(
            "zilencer.views.send_android_push_notification", return_value=1
        ), mock.patch("zilencer.views.send_apple_push_notification", return_value=1), mock.patch(
            "corporate.lib.stripe.RemoteServerBillingSession.current_count_for_billed_licenses",
            return_value=10,
        ), self.assertLogs("zilencer.views", level="INFO") as logger:
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
        endpoints = [
            ("/api/v1/remotes/push/register", "apple-token"),
        ]

        for endpoint, method in endpoints:
            payload = {
                "user_id": 10,
                "token": "xyz uses non-hex characters",
                "token_kind": PushDeviceToken.APNS,
            }
            result = self.uuid_post(self.server_uuid, endpoint, payload)
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

        with mock.patch(
            "zerver.lib.push_notifications.push_notifications_configured", return_value=False
        ), self.assertLogs("zerver.lib.push_notifications", level="WARNING") as warn_log:
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

        with mock.patch(
            "zerver.lib.push_notifications.uses_notification_bouncer", return_value=True
        ):
            with mock.patch("zerver.lib.remote_server.send_to_push_bouncer") as m:
                post_response = {
                    "realms": {realm.uuid: {"can_push": True, "expected_end_timestamp": None}}
                }
                get_response = {
                    "last_realm_count_id": 0,
                    "last_installation_count_id": 0,
                    "last_realmauditlog_id": 0,
                }

                def mock_send_to_push_bouncer_response(method: str, *args: Any) -> Dict[str, Any]:
                    if method == "POST":
                        return post_response
                    return get_response

                m.side_effect = mock_send_to_push_bouncer_response

                initialize_push_notifications()

                realm = get_realm("zulip")
                self.assertTrue(realm.push_notifications_enabled)
                self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
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
        token = "apple-tokenaz"
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

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_push_bouncer_api(self) -> None:
        """This is a variant of the below test_push_api, but using the full
        push notification bouncer flow
        """
        self.add_mock_response()
        user = self.example_user("cordelia")
        self.login_user(user)
        server = self.server

        endpoints: List[Tuple[str, str, int, Mapping[str, str]]] = [
            (
                "/json/users/me/apns_device_token",
                "apple-tokenaz",
                RemotePushDeviceToken.APNS,
                {"appid": "org.zulip.Zulip"},
            ),
            ("/json/users/me/android_gcm_reg_id", "android-token", RemotePushDeviceToken.GCM, {}),
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

            assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
            URL = settings.PUSH_NOTIFICATION_BOUNCER_URL + "/api/v1/remotes/push/register"
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
                f"unknown realm {user.realm.uuid!s}, server {server.id}, "
                f"user {user.uuid!s}",
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
        time_sent = time_sent + timedelta(minutes=1)
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
        with mock.patch(
            "zerver.worker.deferred_work.clear_push_device_tokens",
            side_effect=PushNotificationBouncerRetryLaterError("test"),
        ), mock.patch("zerver.worker.deferred_work.retry_event") as mock_retry:
            do_regenerate_api_key(user, user)
            mock_retry.assert_called()

            # We didn't manage to communicate with the bouncer, to the tokens are still there:
            tokens = list(RemotePushDeviceToken.objects.filter(user_uuid=user.uuid, server=server))
            self.assert_length(tokens, 2)

        # Now we successfully remove them:
        time_sent = time_sent + timedelta(minutes=1)
        with time_machine.travel(time_sent, tick=False):
            do_regenerate_api_key(user, user)
        tokens = list(RemotePushDeviceToken.objects.filter(user_uuid=user.uuid, server=server))
        self.assert_length(tokens, 0)

        remote_realm.refresh_from_db()
        self.assertEqual(remote_realm.last_request_datetime, time_sent)


class AnalyticsBouncerTest(BouncerTestCase):
    TIME_ZERO = datetime(1988, 3, 14, tzinfo=timezone.utc)

    def assertPushNotificationsAre(self, should_be: bool) -> None:
        self.assertEqual(
            {should_be},
            set(
                Realm.objects.all().distinct().values_list("push_notifications_enabled", flat=True)
            ),
        )

    @override
    def setUp(self) -> None:
        redis_client.delete(PUSH_NOTIFICATIONS_RECENTLY_WORKING_REDIS_KEY)

        return super().setUp()

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_analytics_failure_api(self) -> None:
        assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
        ANALYTICS_URL = settings.PUSH_NOTIFICATION_BOUNCER_URL + "/api/v1/remotes/server/analytics"
        ANALYTICS_STATUS_URL = ANALYTICS_URL + "/status"

        with responses.RequestsMock() as resp, self.assertLogs(
            "zulip.analytics", level="WARNING"
        ) as mock_warning:
            resp.add(responses.GET, ANALYTICS_STATUS_URL, body=ConnectionError())
            Realm.objects.all().update(push_notifications_enabled=True)
            send_server_data_to_push_bouncer()
            self.assertEqual(
                "WARNING:zulip.analytics:ConnectionError while trying to connect to push notification bouncer",
                mock_warning.output[0],
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 1))
            self.assertPushNotificationsAre(False)

        # Simulate ConnectionError again, but this time with a redis record indicating
        # that push notifications have recently worked fine.
        with responses.RequestsMock() as resp, self.assertLogs(
            "zulip.analytics", level="WARNING"
        ) as mock_warning:
            resp.add(responses.GET, ANALYTICS_STATUS_URL, body=ConnectionError())
            Realm.objects.all().update(push_notifications_enabled=True)
            record_push_notifications_recently_working()

            send_server_data_to_push_bouncer()
            self.assertEqual(
                "WARNING:zulip.analytics:ConnectionError while trying to connect to push notification bouncer",
                mock_warning.output[0],
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 1))
            # push_notifications_enabled shouldn't get set to False, because this is treated
            # as a transient error.
            self.assertPushNotificationsAre(True)

            # However after an hour has passed without seeing push notifications
            # working, we take the error seriously.
            with time_machine.travel(now() + timedelta(minutes=61), tick=False):
                send_server_data_to_push_bouncer()
                self.assertEqual(
                    "WARNING:zulip.analytics:ConnectionError while trying to connect to push notification bouncer",
                    mock_warning.output[1],
                )
                self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 2))
                self.assertPushNotificationsAre(False)

            redis_client.delete(
                redis_utils.REDIS_KEY_PREFIX + PUSH_NOTIFICATIONS_RECENTLY_WORKING_REDIS_KEY
            )

        with responses.RequestsMock() as resp, self.assertLogs(
            "zulip.analytics", level="WARNING"
        ) as mock_warning:
            resp.add(responses.GET, ANALYTICS_STATUS_URL, body="This is not JSON")
            Realm.objects.all().update(push_notifications_enabled=True)
            send_server_data_to_push_bouncer()
            self.assertTrue(
                mock_warning.output[0].startswith(
                    f"ERROR:zulip.analytics:Exception communicating with {settings.PUSH_NOTIFICATION_BOUNCER_URL}\nTraceback",
                )
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 1))
            self.assertPushNotificationsAre(False)

        with responses.RequestsMock() as resp, self.assertLogs("", level="WARNING") as mock_warning:
            resp.add(responses.GET, ANALYTICS_STATUS_URL, body="Server error", status=502)
            Realm.objects.all().update(push_notifications_enabled=True)
            send_server_data_to_push_bouncer()
            self.assertEqual(
                "WARNING:root:Received 502 from push notification bouncer",
                mock_warning.output[0],
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 1))
            self.assertPushNotificationsAre(True)

        with responses.RequestsMock() as resp, self.assertLogs(
            "zulip.analytics", level="WARNING"
        ) as mock_warning:
            Realm.objects.all().update(push_notifications_enabled=True)
            resp.add(
                responses.GET,
                ANALYTICS_STATUS_URL,
                status=401,
                json={"CODE": "UNAUTHORIZED", "msg": "Some problem", "result": "error"},
            )
            send_server_data_to_push_bouncer()
            self.assertIn(
                "WARNING:zulip.analytics:Some problem",
                mock_warning.output[0],
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 1))
            self.assertPushNotificationsAre(False)

        with responses.RequestsMock() as resp, self.assertLogs(
            "zulip.analytics", level="WARNING"
        ) as mock_warning:
            Realm.objects.all().update(push_notifications_enabled=True)
            resp.add(
                responses.GET,
                ANALYTICS_STATUS_URL,
                json={
                    "last_realm_count_id": 0,
                    "last_installation_count_id": 0,
                    "last_realmauditlog_id": 0,
                },
            )
            resp.add(
                responses.POST,
                ANALYTICS_URL,
                status=401,
                json={"CODE": "UNAUTHORIZED", "msg": "Some problem", "result": "error"},
            )
            send_server_data_to_push_bouncer()
            self.assertIn(
                "WARNING:zulip.analytics:Some problem",
                mock_warning.output[0],
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_URL, 1))
            self.assertPushNotificationsAre(False)

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_analytics_api(self) -> None:
        """This is a variant of the below test_push_api, but using the full
        push notification bouncer flow
        """
        assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
        ANALYTICS_URL = settings.PUSH_NOTIFICATION_BOUNCER_URL + "/api/v1/remotes/server/analytics"
        ANALYTICS_STATUS_URL = ANALYTICS_URL + "/status"
        user = self.example_user("hamlet")
        end_time = self.TIME_ZERO

        self.add_mock_response()
        # Send any existing data over, so that we can start the test with a "clean" slate
        remote_server = self.server
        assert remote_server is not None
        assert remote_server.last_version is None

        send_server_data_to_push_bouncer()
        self.assertTrue(responses.assert_call_count(ANALYTICS_STATUS_URL, 1))

        audit_log = RealmAuditLog.objects.all().order_by("id").last()
        assert audit_log is not None
        audit_log_max_id = audit_log.id

        remote_server.refresh_from_db()
        assert remote_server.last_version == ZULIP_VERSION

        remote_audit_log_count = RemoteRealmAuditLog.objects.count()

        self.assertEqual(RemoteRealmCount.objects.count(), 0)
        self.assertEqual(RemoteInstallationCount.objects.count(), 0)

        def check_counts(
            analytics_status_mock_request_call_count: int,
            analytics_mock_request_call_count: int,
            remote_realm_count: int,
            remote_installation_count: int,
            remote_realm_audit_log: int,
        ) -> None:
            self.assertTrue(
                responses.assert_call_count(
                    ANALYTICS_STATUS_URL, analytics_status_mock_request_call_count
                )
            )
            self.assertTrue(
                responses.assert_call_count(ANALYTICS_URL, analytics_mock_request_call_count)
            )
            self.assertEqual(RemoteRealmCount.objects.count(), remote_realm_count)
            self.assertEqual(RemoteInstallationCount.objects.count(), remote_installation_count)
            self.assertEqual(
                RemoteRealmAuditLog.objects.count(), remote_audit_log_count + remote_realm_audit_log
            )

        # Create some rows we'll send to remote server
        # LoggingCountStat that should be included;
        # i.e. not in LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER
        messages_read_logging_stat = LoggingCountStat(
            "messages_read::hour", UserCount, CountStat.HOUR
        )
        RealmCount.objects.create(
            realm=user.realm,
            property=messages_read_logging_stat.property,
            end_time=end_time,
            value=5,
        )
        InstallationCount.objects.create(
            property=messages_read_logging_stat.property,
            end_time=end_time,
            value=5,
        )
        # LoggingCountStat that should not be included;
        # i.e. in LOGGING_COUNT_STAT_PROPERTIES_NOT_SENT_TO_BOUNCER
        invites_sent_logging_stat = LoggingCountStat("invites_sent::day", RealmCount, CountStat.DAY)
        RealmCount.objects.create(
            realm=user.realm,
            property=invites_sent_logging_stat.property,
            end_time=end_time,
            value=5,
        )
        InstallationCount.objects.create(
            property=invites_sent_logging_stat.property,
            end_time=end_time,
            value=5,
        )
        # Event type in SYNCED_BILLING_EVENTS -- should be included
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.USER_CREATED,
            event_time=end_time,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user.realm),
                }
            ).decode(),
        )
        # Event type not in SYNCED_BILLING_EVENTS -- should not be included
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.REALM_LOGO_CHANGED,
            event_time=end_time,
            extra_data=orjson.dumps({"foo": "bar"}).decode(),
        )
        self.assertEqual(RealmCount.objects.count(), 2)
        self.assertEqual(InstallationCount.objects.count(), 2)
        self.assertEqual(RealmAuditLog.objects.filter(id__gt=audit_log_max_id).count(), 2)

        with self.settings(SUBMIT_USAGE_STATISTICS=False):
            # With this setting off, we don't send RealmCounts and InstallationCounts.
            send_server_data_to_push_bouncer()
        check_counts(2, 2, 0, 0, 1)

        with self.settings(SUBMIT_USAGE_STATISTICS=True):
            # With 'SUBMIT_USAGE_STATISTICS=True' but 'consider_usage_statistics=False',
            # we don't send RealmCount and InstallationCounts.
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        check_counts(3, 3, 0, 0, 1)

        send_server_data_to_push_bouncer()
        check_counts(4, 4, 1, 1, 1)

        self.assertEqual(
            list(
                RemoteRealm.objects.order_by("id").values(
                    "server_id",
                    "uuid",
                    "uuid_owner_secret",
                    "host",
                    "name",
                    "org_type",
                    "authentication_methods",
                    "realm_date_created",
                    "registration_deactivated",
                    "realm_deactivated",
                    "plan_type",
                    "is_system_bot_realm",
                )
            ),
            [
                {
                    "server_id": self.server.id,
                    "uuid": realm.uuid,
                    "uuid_owner_secret": realm.uuid_owner_secret,
                    "host": realm.host,
                    "name": realm.name,
                    "org_type": realm.org_type,
                    "authentication_methods": realm.authentication_methods_dict(),
                    "realm_date_created": realm.date_created,
                    "registration_deactivated": False,
                    "realm_deactivated": False,
                    "plan_type": RemoteRealm.PLAN_TYPE_SELF_MANAGED,
                    "is_system_bot_realm": realm.string_id == "zulipinternal",
                }
                for realm in Realm.objects.order_by("id")
            ],
        )

        # Modify a realm and verify the remote realm data that should get updated, get updated.
        zephyr_realm = get_realm("zephyr")
        zephyr_original_host = zephyr_realm.host
        zephyr_realm.string_id = "zephyr2"

        zephyr_original_name = zephyr_realm.name
        zephyr_realm.name = "Zephyr2"

        zephyr_original_org_type = zephyr_realm.org_type
        self.assertEqual(zephyr_realm.org_type, Realm.ORG_TYPES["business"]["id"])
        do_change_realm_org_type(
            zephyr_realm, Realm.ORG_TYPES["government"]["id"], acting_user=user
        )

        # date_created can't be updated.
        original_date_created = zephyr_realm.date_created
        zephyr_realm.date_created = now()
        zephyr_realm.save()

        zephyr_original_authentication_methods = zephyr_realm.authentication_methods_dict()
        # Sanity check to make sure the set up is how we think.
        self.assertEqual(zephyr_original_authentication_methods["Email"], True)

        new_auth_method_dict = {
            "Google": False,
            "Email": False,
            "GitHub": False,
            "Apple": False,
            "Dev": True,
            "SAML": True,
            "GitLab": False,
            "OpenID Connect": False,
        }
        do_set_realm_authentication_methods(zephyr_realm, new_auth_method_dict, acting_user=user)

        # Deactivation is synced.
        do_deactivate_realm(zephyr_realm, acting_user=None)

        send_server_data_to_push_bouncer()
        check_counts(5, 5, 1, 1, 7)

        zephyr_remote_realm = RemoteRealm.objects.get(uuid=zephyr_realm.uuid)
        self.assertEqual(zephyr_remote_realm.host, zephyr_realm.host)
        self.assertEqual(zephyr_remote_realm.realm_date_created, original_date_created)
        self.assertEqual(zephyr_remote_realm.realm_deactivated, True)
        self.assertEqual(zephyr_remote_realm.name, zephyr_realm.name)
        self.assertEqual(zephyr_remote_realm.authentication_methods, new_auth_method_dict)
        self.assertEqual(zephyr_remote_realm.org_type, Realm.ORG_TYPES["government"]["id"])

        # Verify the RemoteRealmAuditLog entries created.
        remote_audit_logs = (
            RemoteRealmAuditLog.objects.filter(
                event_type=RemoteRealmAuditLog.REMOTE_REALM_VALUE_UPDATED
            )
            .exclude(realm_id=get_realm("zulipinternal").id)
            .order_by("id")
            .values("event_type", "remote_id", "realm_id", "extra_data")
        )

        self.assertEqual(
            list(remote_audit_logs),
            [
                dict(
                    event_type=RemoteRealmAuditLog.REMOTE_REALM_VALUE_UPDATED,
                    remote_id=None,
                    realm_id=zephyr_realm.id,
                    extra_data={
                        "attr_name": "host",
                        "old_value": zephyr_original_host,
                        "new_value": zephyr_realm.host,
                    },
                ),
                dict(
                    event_type=RemoteRealmAuditLog.REMOTE_REALM_VALUE_UPDATED,
                    remote_id=None,
                    realm_id=zephyr_realm.id,
                    extra_data={
                        "attr_name": "org_type",
                        "old_value": zephyr_original_org_type,
                        "new_value": zephyr_realm.org_type,
                    },
                ),
                dict(
                    event_type=RemoteRealmAuditLog.REMOTE_REALM_VALUE_UPDATED,
                    remote_id=None,
                    realm_id=zephyr_realm.id,
                    extra_data={
                        "attr_name": "name",
                        "old_value": zephyr_original_name,
                        "new_value": zephyr_realm.name,
                    },
                ),
                dict(
                    event_type=RemoteRealmAuditLog.REMOTE_REALM_VALUE_UPDATED,
                    remote_id=None,
                    realm_id=zephyr_realm.id,
                    extra_data={
                        "attr_name": "authentication_methods",
                        "old_value": zephyr_original_authentication_methods,
                        "new_value": new_auth_method_dict,
                    },
                ),
                dict(
                    event_type=RemoteRealmAuditLog.REMOTE_REALM_VALUE_UPDATED,
                    remote_id=None,
                    realm_id=zephyr_realm.id,
                    extra_data={
                        "attr_name": "realm_deactivated",
                        "old_value": False,
                        "new_value": True,
                    },
                ),
            ],
        )

        # Test having no new rows
        send_server_data_to_push_bouncer()
        check_counts(6, 6, 1, 1, 7)

        # Test only having new RealmCount rows
        RealmCount.objects.create(
            realm=user.realm,
            property=messages_read_logging_stat.property,
            end_time=end_time + timedelta(days=1),
            value=6,
        )
        RealmCount.objects.create(
            realm=user.realm,
            property=messages_read_logging_stat.property,
            end_time=end_time + timedelta(days=2),
            value=9,
        )
        send_server_data_to_push_bouncer()
        check_counts(7, 7, 3, 1, 7)

        # Test only having new InstallationCount rows
        InstallationCount.objects.create(
            property=messages_read_logging_stat.property,
            end_time=end_time + timedelta(days=1),
            value=6,
        )
        send_server_data_to_push_bouncer()
        check_counts(8, 8, 3, 2, 7)

        # Test only having new RealmAuditLog rows
        # Non-synced event
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.REALM_LOGO_CHANGED,
            event_time=end_time,
            extra_data={"data": "foo"},
        )
        send_server_data_to_push_bouncer()
        check_counts(9, 9, 3, 2, 7)
        # Synced event
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.USER_REACTIVATED,
            event_time=end_time,
            extra_data={
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user.realm),
            },
        )
        send_server_data_to_push_bouncer()
        check_counts(10, 10, 3, 2, 8)

        # Now create an InstallationCount with a property that's not supposed
        # to be tracked by the remote server - since the bouncer itself tracks
        # the RemoteInstallationCount with this property. We want to verify
        # that the remote server will fail at sending analytics to the bouncer
        # with such an InstallationCount - since syncing it should not be allowed.
        forbidden_installation_count = InstallationCount.objects.create(
            property="mobile_pushes_received::day",
            end_time=end_time,
            value=5,
        )
        with self.assertLogs("zulip.analytics", level="WARNING") as warn_log:
            send_server_data_to_push_bouncer()
        self.assertEqual(
            warn_log.output,
            ["WARNING:zulip.analytics:Invalid property mobile_pushes_received::day"],
        )
        # The analytics endpoint call counts increase by 1, but the actual RemoteCounts remain unchanged,
        # since syncing the data failed.
        check_counts(11, 11, 3, 2, 8)
        forbidden_installation_count.delete()

        (realm_count_data, installation_count_data, realmauditlog_data) = build_analytics_data(
            RealmCount.objects.all(), InstallationCount.objects.all(), RealmAuditLog.objects.all()
        )
        request = AnalyticsRequest.model_construct(
            realm_counts=realm_count_data,
            installation_counts=installation_count_data,
            realmauditlog_rows=realmauditlog_data,
            realms=[],
            version=None,
            api_feature_level=None,
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/server/analytics",
            request.model_dump(round_trip=True, exclude={"realms", "version", "api_feature_level"}),
            subdomain="",
        )
        self.assert_json_error(result, "Data is out of order.")

        # Adjust the id of all existing rows so that they get re-sent.
        # This is equivalent to running `./manage.py clear_analytics_tables`
        RealmCount.objects.all().update(id=F("id") + RealmCount.objects.latest("id").id)
        InstallationCount.objects.all().update(
            id=F("id") + InstallationCount.objects.latest("id").id
        )
        with self.assertLogs(level="WARNING") as warn_log:
            send_server_data_to_push_bouncer()
        self.assertEqual(
            warn_log.output,
            [
                f"WARNING:root:Dropped 3 duplicated rows while saving 3 rows of zilencer_remoterealmcount for server demo.example.com/{self.server_uuid}",
                f"WARNING:root:Dropped 2 duplicated rows while saving 2 rows of zilencer_remoteinstallationcount for server demo.example.com/{self.server_uuid}",
            ],
        )
        # Only the request counts go up -- all of the other rows' duplicates are dropped
        check_counts(12, 12, 3, 2, 8)

        # Test that only valid org_type values are accepted - integers defined in OrgTypeEnum.
        realms_data = get_realms_info_for_push_bouncer()
        # Not a valid org_type value:
        realms_data[0].org_type = 11

        request = AnalyticsRequest.model_construct(
            realm_counts=[],
            installation_counts=[],
            realmauditlog_rows=[],
            realms=realms_data,
            version=None,
            api_feature_level=None,
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/server/analytics",
            request.model_dump(round_trip=True, exclude={"version", "api_feature_level"}),
            subdomain="",
        )
        self.assert_json_error(
            result, 'Invalid realms[0]["org_type"]: Value error, Not a valid org_type value'
        )

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_analytics_api_foreign_keys_to_remote_realm(self) -> None:
        self.add_mock_response()

        user = self.example_user("hamlet")
        end_time = self.TIME_ZERO

        # Create some rows we'll send to remote server
        messages_read_logging_stat = LoggingCountStat(
            "messages_read::hour", UserCount, CountStat.HOUR
        )
        realm_count = RealmCount.objects.create(
            realm=user.realm,
            property=messages_read_logging_stat.property,
            end_time=end_time,
            value=5,
        )
        installation_count = InstallationCount.objects.create(
            property=messages_read_logging_stat.property,
            end_time=end_time,
            value=5,
        )
        realm_audit_log = RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.USER_CREATED,
            event_time=end_time,
            extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user.realm),
                }
            ).decode(),
        )
        realm_count_data, installation_count_data, realmauditlog_data = build_analytics_data(
            RealmCount.objects.all(), InstallationCount.objects.all(), RealmAuditLog.objects.all()
        )

        # This first post should fail because of excessive audit log event types.
        request = AnalyticsRequest.model_construct(
            realm_counts=realm_count_data,
            installation_counts=installation_count_data,
            realmauditlog_rows=realmauditlog_data,
            realms=[],
            version=None,
            api_feature_level=None,
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/server/analytics",
            request.model_dump(round_trip=True, exclude={"version", "api_feature_level"}),
            subdomain="",
        )
        self.assert_json_error(result, "Invalid event type.")

        # Start again only using synced billing events.
        realm_count_data, installation_count_data, realmauditlog_data = build_analytics_data(
            RealmCount.objects.all(),
            InstallationCount.objects.all(),
            RealmAuditLog.objects.filter(event_type__in=RemoteRealmAuditLog.SYNCED_BILLING_EVENTS),
        )

        # Send the data to the bouncer without any realms data. This should lead
        # to successful saving of the data, but with the remote_realm foreign key
        # set to NULL.
        request = AnalyticsRequest.model_construct(
            realm_counts=realm_count_data,
            installation_counts=installation_count_data,
            realmauditlog_rows=realmauditlog_data,
            realms=[],
            version=None,
            api_feature_level=None,
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/server/analytics",
            request.model_dump(round_trip=True, exclude={"version", "api_feature_level"}),
            subdomain="",
        )
        self.assert_json_success(result)
        remote_realm_count = RemoteRealmCount.objects.latest("id")
        remote_installation_count = RemoteInstallationCount.objects.latest("id")
        remote_realm_audit_log = RemoteRealmAuditLog.objects.latest("id")

        self.assertEqual(remote_realm_count.remote_id, realm_count.id)
        self.assertEqual(remote_realm_count.remote_realm, None)
        self.assertEqual(remote_installation_count.remote_id, installation_count.id)
        # InstallationCont/RemoteInstallationCount don't have realm/remote_realm foreign
        # keys, because they're aggregated over all realms.

        self.assertEqual(remote_realm_audit_log.remote_id, realm_audit_log.id)
        self.assertEqual(remote_realm_audit_log.remote_realm, None)

        send_server_data_to_push_bouncer()

        remote_realm_count.refresh_from_db()
        remote_installation_count.refresh_from_db()
        remote_realm_audit_log.refresh_from_db()

        remote_realm = RemoteRealm.objects.get(uuid=user.realm.uuid)

        self.assertEqual(remote_realm_count.remote_realm, remote_realm)
        self.assertEqual(remote_realm_audit_log.remote_realm, remote_realm)

        current_remote_realm_count_amount = RemoteRealmCount.objects.count()
        current_remote_realm_audit_log_amount = RemoteRealmAuditLog.objects.count()

        # Now create and send new data (including realm info) and verify it has .remote_realm
        # set as it should.
        RealmCount.objects.create(
            realm=user.realm,
            property=messages_read_logging_stat.property,
            end_time=end_time + timedelta(days=1),
            value=6,
        )
        InstallationCount.objects.create(
            property=messages_read_logging_stat.property,
            end_time=end_time + timedelta(days=1),
            value=6,
        )
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.USER_CREATED,
            event_time=end_time,
            extra_data={
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user.realm),
            },
        )
        send_server_data_to_push_bouncer()

        # Make sure new data was created, so that we're actually testing what we think.
        self.assertEqual(RemoteRealmCount.objects.count(), current_remote_realm_count_amount + 1)
        self.assertEqual(
            RemoteRealmAuditLog.objects.count(), current_remote_realm_audit_log_amount + 1
        )

        for remote_realm_count in RemoteRealmCount.objects.filter(realm_id=user.realm.id):
            self.assertEqual(remote_realm_count.remote_realm, remote_realm)
        for remote_realm_audit_log in RemoteRealmAuditLog.objects.filter(realm_id=user.realm.id):
            self.assertEqual(remote_realm_audit_log.remote_realm, remote_realm)

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_analytics_api_invalid(self) -> None:
        """This is a variant of the below test_push_api, but using the full
        push notification bouncer flow
        """
        self.add_mock_response()
        user = self.example_user("hamlet")
        end_time = self.TIME_ZERO

        realm_stat = LoggingCountStat("invalid count stat", RealmCount, CountStat.DAY)
        RealmCount.objects.create(
            realm=user.realm, property=realm_stat.property, end_time=end_time, value=5
        )

        self.assertEqual(RealmCount.objects.count(), 1)

        self.assertEqual(RemoteRealmCount.objects.count(), 0)
        with self.assertLogs("zulip.analytics", level="WARNING") as m:
            send_server_data_to_push_bouncer()
        self.assertEqual(m.output, ["WARNING:zulip.analytics:Invalid property invalid count stat"])
        self.assertEqual(RemoteRealmCount.objects.count(), 0)

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_remote_realm_duplicate_uuid(self) -> None:
        """
        Tests for a case where a RemoteRealm with a certain uuid is already registered for one server,
        and then another server tries to register the same uuid. This generally shouldn't happen,
        because export->import of a realm should re-generate the uuid, but we should have error
        handling for this edge case nonetheless.
        """

        # Start by deleting existing registration, to have a clean slate.
        RemoteRealm.objects.all().delete()

        second_server = RemoteZulipServer.objects.create(
            uuid=uuid.uuid4(),
            api_key="magic_secret_api_key2",
            hostname="demo2.example.com",
            last_updated=now(),
        )

        self.add_mock_response()
        user = self.example_user("hamlet")
        realm = user.realm

        RemoteRealm.objects.create(
            server=second_server,
            uuid=realm.uuid,
            uuid_owner_secret=realm.uuid_owner_secret,
            host=realm.host,
            realm_date_created=realm.date_created,
            registration_deactivated=False,
            realm_deactivated=False,
            plan_type=RemoteRealm.PLAN_TYPE_SELF_MANAGED,
        )

        with transaction.atomic(), self.assertLogs("zulip.analytics", level="WARNING") as m:
            # The usual atomic() wrapper to avoid IntegrityError breaking the test's
            # transaction.
            send_server_data_to_push_bouncer()
        self.assertEqual(m.output, ["WARNING:zulip.analytics:Duplicate registration detected."])

    # Servers on Zulip 2.0.6 and earlier only send realm_counts and installation_counts data,
    # and don't send realmauditlog_rows. Make sure that continues to work.
    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_old_two_table_format(self) -> None:
        self.add_mock_response()
        # Send fixture generated with Zulip 2.0 code
        send_to_push_bouncer(
            "POST",
            "server/analytics",
            {
                "realm_counts": '[{"id":1,"property":"invites_sent::day","subgroup":null,"end_time":574300800.0,"value":5,"realm":2}]',
                "installation_counts": "[]",
                "version": '"2.0.6+git"',
            },
        )
        assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
        ANALYTICS_URL = settings.PUSH_NOTIFICATION_BOUNCER_URL + "/api/v1/remotes/server/analytics"
        self.assertTrue(responses.assert_call_count(ANALYTICS_URL, 1))
        self.assertEqual(RemoteRealmCount.objects.count(), 1)
        self.assertEqual(RemoteInstallationCount.objects.count(), 0)
        self.assertEqual(RemoteRealmAuditLog.objects.count(), 0)

    # Make sure we aren't sending data we don't mean to, even if we don't store it.
    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_only_sending_intended_realmauditlog_data(self) -> None:
        self.add_mock_response()
        user = self.example_user("hamlet")
        # Event type in SYNCED_BILLING_EVENTS -- should be included
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.USER_REACTIVATED,
            event_time=self.TIME_ZERO,
            extra_data={
                RealmAuditLog.ROLE_COUNT: realm_user_count_by_role(user.realm),
            },
        )
        # Event type not in SYNCED_BILLING_EVENTS -- should not be included
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.REALM_LOGO_CHANGED,
            event_time=self.TIME_ZERO,
            extra_data=orjson.dumps({"foo": "bar"}).decode(),
        )

        # send_server_data_to_push_bouncer calls send_to_push_bouncer twice.
        # We need to distinguish the first and second calls.
        first_call = True

        def check_for_unwanted_data(*args: Any) -> Any:
            nonlocal first_call
            if first_call:
                first_call = False
            else:
                # Test that we're respecting SYNCED_BILLING_EVENTS
                self.assertIn(f'"event_type":{RealmAuditLog.USER_REACTIVATED}', str(args))
                self.assertNotIn(f'"event_type":{RealmAuditLog.REALM_LOGO_CHANGED}', str(args))
                # Test that we're respecting REALMAUDITLOG_PUSHED_FIELDS
                self.assertIn("backfilled", str(args))
                self.assertNotIn("modified_user", str(args))
            return send_to_push_bouncer(*args)

        with mock.patch(
            "zerver.lib.remote_server.send_to_push_bouncer", side_effect=check_for_unwanted_data
        ):
            send_server_data_to_push_bouncer()

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_realmauditlog_data_mapping(self) -> None:
        self.add_mock_response()
        user = self.example_user("hamlet")
        user_count = realm_user_count_by_role(user.realm)
        log_entry = RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            backfilled=True,
            event_type=RealmAuditLog.USER_REACTIVATED,
            event_time=self.TIME_ZERO,
            extra_data=orjson.dumps({RealmAuditLog.ROLE_COUNT: user_count}).decode(),
        )
        send_server_data_to_push_bouncer()
        remote_log_entry = RemoteRealmAuditLog.objects.order_by("id").last()
        assert remote_log_entry is not None
        self.assertEqual(str(remote_log_entry.server.uuid), self.server_uuid)
        self.assertEqual(remote_log_entry.remote_id, log_entry.id)
        self.assertEqual(remote_log_entry.event_time, self.TIME_ZERO)
        self.assertEqual(remote_log_entry.backfilled, True)
        assert remote_log_entry.extra_data is not None
        self.assertEqual(remote_log_entry.extra_data, {RealmAuditLog.ROLE_COUNT: user_count})
        self.assertEqual(remote_log_entry.event_type, RealmAuditLog.USER_REACTIVATED)

    # This verifies that the bouncer is backwards-compatible with remote servers using
    # TextField to store extra_data.
    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_realmauditlog_string_extra_data(self) -> None:
        self.add_mock_response()

        def verify_request_with_overridden_extra_data(
            request_extra_data: object,
            *,
            expected_extra_data: object = None,
            skip_audit_log_check: bool = False,
        ) -> None:
            user = self.example_user("hamlet")
            log_entry = RealmAuditLog.objects.create(
                realm=user.realm,
                modified_user=user,
                event_type=RealmAuditLog.USER_REACTIVATED,
                event_time=self.TIME_ZERO,
                extra_data=orjson.dumps(
                    {
                        RealmAuditLog.ROLE_COUNT: {
                            RealmAuditLog.ROLE_COUNT_HUMANS: {},
                        }
                    }
                ).decode(),
            )

            # We use this to patch send_to_push_bouncer so that extra_data in the
            # legacy format gets sent to the bouncer.
            def transform_realmauditlog_extra_data(
                method: str,
                endpoint: str,
                post_data: Union[bytes, Mapping[str, Union[str, int, None, bytes]]],
                extra_headers: Mapping[str, str] = {},
            ) -> Dict[str, Any]:
                if endpoint == "server/analytics":
                    assert isinstance(post_data, dict)
                    assert isinstance(post_data["realmauditlog_rows"], str)
                    original_data = orjson.loads(post_data["realmauditlog_rows"])
                    # We replace the extra_data with another fake example to verify that
                    # the bouncer actually gets requested with extra_data being string
                    new_data = [{**row, "extra_data": request_extra_data} for row in original_data]
                    post_data["realmauditlog_rows"] = orjson.dumps(new_data).decode()
                return send_to_push_bouncer(method, endpoint, post_data, extra_headers)

            with mock.patch(
                "zerver.lib.remote_server.send_to_push_bouncer",
                side_effect=transform_realmauditlog_extra_data,
            ):
                send_server_data_to_push_bouncer()

            if skip_audit_log_check:
                return

            remote_log_entry = RemoteRealmAuditLog.objects.order_by("id").last()
            assert remote_log_entry is not None
            self.assertEqual(str(remote_log_entry.server.uuid), self.server_uuid)
            self.assertEqual(remote_log_entry.remote_id, log_entry.id)
            self.assertEqual(remote_log_entry.event_time, self.TIME_ZERO)
            self.assertEqual(remote_log_entry.extra_data, expected_extra_data)

        # Pre-migration extra_data
        verify_request_with_overridden_extra_data(
            request_extra_data=orjson.dumps(
                {
                    RealmAuditLog.ROLE_COUNT: {
                        RealmAuditLog.ROLE_COUNT_HUMANS: {},
                    }
                }
            ).decode(),
            expected_extra_data={
                RealmAuditLog.ROLE_COUNT: {
                    RealmAuditLog.ROLE_COUNT_HUMANS: {},
                }
            },
        )
        verify_request_with_overridden_extra_data(request_extra_data=None, expected_extra_data={})
        # Post-migration extra_data
        verify_request_with_overridden_extra_data(
            request_extra_data={
                RealmAuditLog.ROLE_COUNT: {
                    RealmAuditLog.ROLE_COUNT_HUMANS: {},
                }
            },
            expected_extra_data={
                RealmAuditLog.ROLE_COUNT: {
                    RealmAuditLog.ROLE_COUNT_HUMANS: {},
                }
            },
        )
        verify_request_with_overridden_extra_data(
            request_extra_data={},
            expected_extra_data={},
        )
        # Invalid extra_data
        with self.assertLogs("zulip.analytics", level="WARNING") as m:
            verify_request_with_overridden_extra_data(
                request_extra_data="{malformedjson:",
                skip_audit_log_check=True,
            )
        self.assertIn("Malformed audit log data", m.output[0])

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_realm_properties_after_send_analytics(self) -> None:
        self.add_mock_response()

        with mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.get_customer", return_value=None
        ) as m:
            with mock.patch(
                "corporate.lib.stripe.RemoteServerBillingSession.current_count_for_billed_licenses",
                return_value=10,
            ):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)
                m.assert_called()
                realms = Realm.objects.all()
                for realm in realms:
                    self.assertEqual(realm.push_notifications_enabled, True)
                    self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

        with mock.patch(
            "zilencer.views.RemoteRealmBillingSession.get_customer", return_value=None
        ) as m:
            with mock.patch(
                "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                return_value=11,
            ):
                send_server_data_to_push_bouncer(consider_usage_statistics=False)
                m.assert_called()
                realms = Realm.objects.all()
                for realm in realms:
                    self.assertEqual(realm.push_notifications_enabled, False)
                    self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

        dummy_customer = mock.MagicMock()
        with mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
            return_value=dummy_customer,
        ):
            with mock.patch(
                "corporate.lib.stripe.get_current_plan_by_customer", return_value=None
            ) as m:
                send_server_data_to_push_bouncer(consider_usage_statistics=False)
                m.assert_called()
                realms = Realm.objects.all()
                for realm in realms:
                    self.assertEqual(realm.push_notifications_enabled, True)
                    self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

        dummy_customer = mock.MagicMock()
        with mock.patch(
            "zilencer.views.RemoteRealmBillingSession.get_customer", return_value=dummy_customer
        ):
            with mock.patch(
                "corporate.lib.stripe.get_current_plan_by_customer", return_value=None
            ) as m:
                with mock.patch(
                    "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                    return_value=11,
                ):
                    send_server_data_to_push_bouncer(consider_usage_statistics=False)
                    m.assert_called()
                    realms = Realm.objects.all()
                    for realm in realms:
                        self.assertEqual(realm.push_notifications_enabled, False)
                        self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

        RemoteRealm.objects.filter(server=self.server).update(
            plan_type=RemoteRealm.PLAN_TYPE_COMMUNITY
        )

        with mock.patch(
            "zilencer.views.RemoteRealmBillingSession.get_customer", return_value=dummy_customer
        ):
            with mock.patch("corporate.lib.stripe.get_current_plan_by_customer", return_value=None):
                with mock.patch(
                    "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses"
                ) as m:
                    send_server_data_to_push_bouncer(consider_usage_statistics=False)
                    m.assert_not_called()
                    realms = Realm.objects.all()
                    for realm in realms:
                        self.assertEqual(realm.push_notifications_enabled, True)
                        self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

        # Reset the plan type to test remaining cases.
        RemoteRealm.objects.filter(server=self.server).update(
            plan_type=RemoteRealm.PLAN_TYPE_SELF_MANAGED
        )

        dummy_customer_plan = mock.MagicMock()
        dummy_customer_plan.status = CustomerPlan.DOWNGRADE_AT_END_OF_CYCLE
        dummy_date = datetime(year=2023, month=12, day=3, tzinfo=timezone.utc)
        with mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
            return_value=dummy_customer,
        ):
            with mock.patch(
                "corporate.lib.stripe.get_current_plan_by_customer",
                return_value=dummy_customer_plan,
            ):
                with mock.patch(
                    "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                    return_value=11,
                ):
                    with mock.patch(
                        "corporate.lib.stripe.RemoteRealmBillingSession.get_next_billing_cycle",
                        return_value=dummy_date,
                    ) as m, self.assertLogs("zulip.analytics", level="INFO") as info_log:
                        send_server_data_to_push_bouncer(consider_usage_statistics=False)
                        m.assert_called()
                        realms = Realm.objects.all()
                        for realm in realms:
                            self.assertEqual(realm.push_notifications_enabled, True)
                            self.assertEqual(
                                realm.push_notifications_enabled_end_timestamp,
                                dummy_date,
                            )
                        self.assertIn(
                            "INFO:zulip.analytics:Reported 0 records",
                            info_log.output[0],
                        )

        with mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
            return_value=dummy_customer,
        ):
            with mock.patch(
                "corporate.lib.stripe.get_current_plan_by_customer",
                return_value=dummy_customer_plan,
            ):
                with mock.patch(
                    "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                    side_effect=MissingDataError,
                ):
                    with mock.patch(
                        "corporate.lib.stripe.RemoteRealmBillingSession.get_next_billing_cycle",
                        return_value=dummy_date,
                    ) as m, self.assertLogs("zulip.analytics", level="INFO") as info_log:
                        send_server_data_to_push_bouncer(consider_usage_statistics=False)
                        m.assert_called()
                        realms = Realm.objects.all()
                        for realm in realms:
                            self.assertEqual(realm.push_notifications_enabled, True)
                            self.assertEqual(
                                realm.push_notifications_enabled_end_timestamp,
                                dummy_date,
                            )
                        self.assertIn(
                            "INFO:zulip.analytics:Reported 0 records",
                            info_log.output[0],
                        )

        with mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
            return_value=dummy_customer,
        ):
            with mock.patch(
                "corporate.lib.stripe.get_current_plan_by_customer",
                return_value=dummy_customer_plan,
            ):
                with mock.patch(
                    "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
                    return_value=10,
                ):
                    send_server_data_to_push_bouncer(consider_usage_statistics=False)
                    m.assert_called()
                    realms = Realm.objects.all()
                    for realm in realms:
                        self.assertEqual(realm.push_notifications_enabled, True)
                        self.assertEqual(
                            realm.push_notifications_enabled_end_timestamp,
                            None,
                        )

        dummy_customer_plan = mock.MagicMock()
        dummy_customer_plan.status = CustomerPlan.ACTIVE
        with mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
            return_value=dummy_customer,
        ):
            with mock.patch(
                "corporate.lib.stripe.get_current_plan_by_customer",
                return_value=dummy_customer_plan,
            ):
                with self.assertLogs("zulip.analytics", level="INFO") as info_log:
                    send_server_data_to_push_bouncer(consider_usage_statistics=False)
                    m.assert_called()
                    realms = Realm.objects.all()
                    for realm in realms:
                        self.assertEqual(realm.push_notifications_enabled, True)
                        self.assertEqual(
                            realm.push_notifications_enabled_end_timestamp,
                            None,
                        )
                    self.assertIn(
                        "INFO:zulip.analytics:Reported 0 records",
                        info_log.output[0],
                    )

        # Remote realm is on an inactive plan. Remote server on active plan.
        # ACTIVE plan takes precedence.
        dummy_remote_realm_customer = mock.MagicMock()
        dummy_remote_server_customer = mock.MagicMock()
        dummy_remote_server_customer_plan = mock.MagicMock()
        dummy_remote_server_customer_plan.status = CustomerPlan.ACTIVE

        def get_current_plan_by_customer(customer: mock.MagicMock) -> Optional[mock.MagicMock]:
            assert customer in [dummy_remote_realm_customer, dummy_remote_server_customer]
            if customer == dummy_remote_server_customer:
                return dummy_remote_server_customer_plan
            return None

        with mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.get_customer",
            return_value=dummy_remote_realm_customer,
        ), mock.patch(
            "corporate.lib.stripe.RemoteServerBillingSession.get_customer",
            return_value=dummy_remote_server_customer,
        ), mock.patch(
            "zilencer.views.RemoteServerBillingSession.sync_license_ledger_if_needed"
        ), mock.patch(
            "corporate.lib.stripe.get_current_plan_by_customer",
            side_effect=get_current_plan_by_customer,
        ) as m:
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, True)
                self.assertEqual(
                    realm.push_notifications_enabled_end_timestamp,
                    None,
                )

        with mock.patch("zerver.lib.remote_server.send_to_push_bouncer") as m, self.assertLogs(
            "zulip.analytics", level="WARNING"
        ) as exception_log:
            get_response = {
                "last_realm_count_id": 0,
                "last_installation_count_id": 0,
                "last_realmauditlog_id": 0,
            }

            def mock_send_to_push_bouncer_response(method: str, *args: Any) -> Dict[str, int]:
                if method == "POST":
                    raise PushNotificationBouncerRetryLaterError("Some problem")
                return get_response

            m.side_effect = mock_send_to_push_bouncer_response

            send_server_data_to_push_bouncer(consider_usage_statistics=False)

            realms = Realm.objects.all()
            for realm in realms:
                self.assertFalse(realm.push_notifications_enabled)
        self.assertEqual(
            exception_log.output,
            ["WARNING:zulip.analytics:Some problem"],
        )

        send_server_data_to_push_bouncer(consider_usage_statistics=False)

        self.assertEqual(
            list(
                RemoteRealm.objects.order_by("id").values(
                    "server_id",
                    "uuid",
                    "uuid_owner_secret",
                    "host",
                    "realm_date_created",
                    "registration_deactivated",
                    "realm_deactivated",
                    "plan_type",
                )
            ),
            [
                {
                    "server_id": self.server.id,
                    "uuid": realm.uuid,
                    "uuid_owner_secret": realm.uuid_owner_secret,
                    "host": realm.host,
                    "realm_date_created": realm.date_created,
                    "registration_deactivated": False,
                    "realm_deactivated": False,
                    "plan_type": RemoteRealm.PLAN_TYPE_SELF_MANAGED,
                }
                for realm in Realm.objects.order_by("id")
            ],
        )

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_deleted_realm(self) -> None:
        self.add_mock_response()
        logger = logging.getLogger("zulip.analytics")

        realm_info = get_realms_info_for_push_bouncer()

        # Hard-delete a realm to test the non existent realm uuid case.
        zephyr_realm = get_realm("zephyr")
        assert zephyr_realm is not None
        deleted_realm_uuid = zephyr_realm.uuid
        zephyr_realm.delete()

        # This mock causes us to still send data to the bouncer as if the realm existed,
        # causing the bouncer to include its corresponding info in the response. Through
        # that, we're testing our graceful handling of seeing a non-existent realm uuid
        # in that response.
        with mock.patch(
            "zerver.lib.remote_server.get_realms_info_for_push_bouncer", return_value=realm_info
        ) as m, self.assertLogs(logger, level="WARNING") as analytics_logger:
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
            m.assert_called()
            realms = Realm.objects.all()
            for realm in realms:
                self.assertEqual(realm.push_notifications_enabled, True)
                self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

        self.assertEqual(
            analytics_logger.output,
            [
                "WARNING:zulip.analytics:"
                f"Received unexpected realm UUID from bouncer {deleted_realm_uuid}"
            ],
        )

        # Now we want to test the other side of this - bouncer's handling
        # of a deleted realm.
        with self.assertLogs(logger, level="WARNING") as analytics_logger, mock.patch(
            "zilencer.views.RemoteRealmBillingSession.on_paid_plan", return_value=True
        ):
            # This time the logger shouldn't get triggered - because the bouncer doesn't
            # include .realm_locally_deleted realms in its response.
            # Note: This is hacky, because until Python 3.10 we don't have access to
            # assertNoLogs - and regular assertLogs demands that the logger gets triggered.
            # So we do a dummy warning ourselves here, to satisfy it.
            # TODO: Replace this with assertNoLogs once we fully upgrade to Python 3.10.
            logger.warning("Dummy warning")
            send_server_data_to_push_bouncer(consider_usage_statistics=False)
        remote_realm_for_deleted_realm = RemoteRealm.objects.get(uuid=deleted_realm_uuid)

        self.assertEqual(remote_realm_for_deleted_realm.registration_deactivated, False)
        self.assertEqual(remote_realm_for_deleted_realm.realm_locally_deleted, True)
        self.assertEqual(analytics_logger.output, ["WARNING:zulip.analytics:Dummy warning"])

        audit_log = RemoteRealmAuditLog.objects.latest("id")
        self.assertEqual(audit_log.event_type, RemoteRealmAuditLog.REMOTE_REALM_LOCALLY_DELETED)
        self.assertEqual(audit_log.remote_realm, remote_realm_for_deleted_realm)

        from django.core.mail import outbox

        email = outbox[-1]
        self.assert_length(email.to, 1)
        self.assertEqual(email.to[0], "sales@zulip.com")

        billing_session = RemoteRealmBillingSession(remote_realm=remote_realm_for_deleted_realm)
        self.assertIn(
            f"Support URL: {billing_session.support_url()}",
            email.body,
        )
        self.assertIn(
            f"Internal billing notice for {billing_session.billing_entity_display_name}.",
            email.body,
        )
        self.assertIn(
            "Investigate why remote realm is marked as locally deleted when it's on a paid plan.",
            email.body,
        )
        self.assertEqual(
            f"{billing_session.billing_entity_display_name} on paid plan marked as locally deleted",
            email.subject,
        )

        # Restore the deleted realm to verify that the bouncer correctly handles that
        # by togglin off .realm_locally_deleted.
        restored_zephyr_realm = do_create_realm("zephyr", "Zephyr")
        restored_zephyr_realm.uuid = deleted_realm_uuid
        restored_zephyr_realm.save()

        send_server_data_to_push_bouncer(consider_usage_statistics=False)
        remote_realm_for_deleted_realm.refresh_from_db()
        self.assertEqual(remote_realm_for_deleted_realm.realm_locally_deleted, False)

        audit_log = RemoteRealmAuditLog.objects.latest("id")
        self.assertEqual(
            audit_log.event_type, RemoteRealmAuditLog.REMOTE_REALM_LOCALLY_DELETED_RESTORED
        )
        self.assertEqual(audit_log.remote_realm, remote_realm_for_deleted_realm)


class PushNotificationTest(BouncerTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user("hamlet")
        self.sending_client = get_client("test")
        self.sender = self.example_user("hamlet")
        self.personal_recipient_user = self.example_user("othello")

    def get_message(self, type: int, type_id: int, realm_id: int) -> Message:
        recipient, _ = Recipient.objects.get_or_create(
            type_id=type_id,
            type=type,
        )

        message = Message(
            sender=self.sender,
            recipient=recipient,
            realm_id=realm_id,
            content="This is test content",
            rendered_content="This is test content",
            date_sent=now(),
            sending_client=self.sending_client,
        )
        message.set_topic_name("Test topic")
        message.save()

        return message

    @contextmanager
    def mock_apns(self) -> Iterator[Tuple[APNsContext, mock.AsyncMock]]:
        apns = mock.Mock(spec=aioapns.APNs)
        apns.send_notification = mock.AsyncMock()
        apns_context = APNsContext(
            apns=apns,
            loop=asyncio.new_event_loop(),
        )
        try:
            with mock.patch("zerver.lib.push_notifications.get_apns_context") as mock_get:
                mock_get.return_value = apns_context
                yield apns_context, apns.send_notification
        finally:
            apns_context.loop.close()

    def setup_apns_tokens(self) -> None:
        self.tokens = [("aaaa", "org.zulip.Zulip"), ("bbbb", "com.zulip.flutter")]
        for token, appid in self.tokens:
            PushDeviceToken.objects.create(
                kind=PushDeviceToken.APNS,
                token=hex_to_b64(token),
                user=self.user_profile,
                ios_app_id=appid,
            )

        self.remote_tokens = [
            ("cccc", "dddd", "org.zulip.Zulip"),
            ("eeee", "ffff", "com.zulip.flutter"),
        ]
        for id_token, uuid_token, appid in self.remote_tokens:
            # We want to set up both types of RemotePushDeviceToken here:
            # the legacy one with user_id and the new with user_uuid.
            # This allows tests to work with either, without needing to
            # do their own setup.
            RemotePushDeviceToken.objects.create(
                kind=RemotePushDeviceToken.APNS,
                token=hex_to_b64(id_token),
                ios_app_id=appid,
                user_id=self.user_profile.id,
                server=self.server,
            )
            RemotePushDeviceToken.objects.create(
                kind=RemotePushDeviceToken.APNS,
                token=hex_to_b64(uuid_token),
                ios_app_id=appid,
                user_uuid=self.user_profile.uuid,
                server=self.server,
            )

    def setup_gcm_tokens(self) -> None:
        self.gcm_tokens = ["1111", "2222"]
        for token in self.gcm_tokens:
            PushDeviceToken.objects.create(
                kind=PushDeviceToken.GCM,
                token=hex_to_b64(token),
                user=self.user_profile,
                ios_app_id=None,
            )

        self.remote_gcm_tokens = [("dddd", "eeee")]
        for id_token, uuid_token in self.remote_gcm_tokens:
            RemotePushDeviceToken.objects.create(
                kind=RemotePushDeviceToken.GCM,
                token=hex_to_b64(id_token),
                user_id=self.user_profile.id,
                server=self.server,
            )
            RemotePushDeviceToken.objects.create(
                kind=RemotePushDeviceToken.GCM,
                token=hex_to_b64(uuid_token),
                user_uuid=self.user_profile.uuid,
                server=self.server,
            )


class HandlePushNotificationTest(PushNotificationTest):
    DEFAULT_SUBDOMAIN = ""

    def soft_deactivate_main_user(self) -> None:
        self.user_profile = self.example_user("hamlet")
        self.soft_deactivate_user(self.user_profile)

    @override
    def request_callback(self, request: PreparedRequest) -> Tuple[int, ResponseHeaders, bytes]:
        assert request.url is not None  # allow mypy to infer url is present.
        assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
        local_url = request.url.replace(settings.PUSH_NOTIFICATION_BOUNCER_URL, "")
        assert isinstance(request.body, bytes)
        result = self.uuid_post(
            self.server_uuid, local_url, request.body, content_type="application/json"
        )
        return (result.status_code, result.headers, result.content)

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_end_to_end(self) -> None:
        self.add_mock_response()
        self.setup_apns_tokens()
        self.setup_gcm_tokens()

        time_sent = now().replace(microsecond=0)
        with time_machine.travel(time_sent, tick=False):
            message = self.get_message(
                Recipient.PERSONAL,
                type_id=self.personal_recipient_user.id,
                realm_id=self.personal_recipient_user.realm_id,
            )
            UserMessage.objects.create(
                user_profile=self.user_profile,
                message=message,
            )

        time_received = time_sent + timedelta(seconds=1, milliseconds=234)
        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        with time_machine.travel(time_received, tick=False), mock.patch(
            "zerver.lib.push_notifications.gcm_client"
        ) as mock_gcm, self.mock_apns() as (apns_context, send_notification), mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
            return_value=10,
        ), self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as pn_logger, self.assertLogs("zilencer.views", level="INFO") as views_logger:
            apns_devices = [
                (b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS)
            ]
            gcm_devices = [
                (b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.GCM)
            ]
            mock_gcm.json_request.return_value = {
                "success": {device[2]: message.id for device in gcm_devices}
            }
            send_notification.return_value.is_successful = True
            handle_push_notification(self.user_profile.id, missed_message)
            self.assertEqual(
                {
                    (args[0][0].device_token, args[0][0].apns_topic)
                    for args in send_notification.call_args_list
                },
                {
                    (device.token, device.ios_app_id)
                    for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS)
                },
            )
            self.assertEqual(
                views_logger.output,
                [
                    "INFO:zilencer.views:"
                    f"Remote queuing latency for 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{self.user_profile.id}><uuid:{self.user_profile.uuid}> "
                    "is 1 seconds",
                    "INFO:zilencer.views:"
                    f"Sending mobile push notifications for remote user 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{self.user_profile.id}><uuid:{self.user_profile.uuid}>: "
                    f"{len(gcm_devices)} via FCM devices, {len(apns_devices)} via APNs devices",
                ],
            )
            for _, _, token in apns_devices:
                self.assertIn(
                    "INFO:zerver.lib.push_notifications:"
                    f"APNs: Success sending for user <id:{self.user_profile.id}><uuid:{self.user_profile.uuid}> to device {token}",
                    pn_logger.output,
                )
            for _, _, token in gcm_devices:
                self.assertIn(
                    f"INFO:zerver.lib.push_notifications:GCM: Sent {token} as {message.id}",
                    pn_logger.output,
                )

            remote_realm_count = RealmCount.objects.values("property", "subgroup", "value").last()
            self.assertEqual(
                remote_realm_count,
                dict(
                    property="mobile_pushes_sent::day",
                    subgroup=None,
                    value=len(gcm_devices) + len(apns_devices),
                ),
            )

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_end_to_end_failure_due_to_no_plan(self) -> None:
        self.add_mock_response()

        self.setup_apns_tokens()
        self.setup_gcm_tokens()

        self.server.last_api_feature_level = 237
        self.server.save()

        realm = self.user_profile.realm
        realm.push_notifications_enabled = True
        realm.save()

        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
        )

        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        with mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
            return_value=100,
        ) as mock_current_count, self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as pn_logger, self.assertLogs("zilencer.views", level="INFO"):
            handle_push_notification(self.user_profile.id, missed_message)

            self.assertEqual(
                pn_logger.output,
                [
                    f"INFO:zerver.lib.push_notifications:Sending push notifications to mobile clients for user {self.user_profile.id}",
                    "WARNING:zerver.lib.push_notifications:Bouncer refused to send push notification: Your plan doesn't allow sending push notifications. Reason provided by the server: Push notifications access with 10+ users requires signing up for a plan. https://zulip.com/plans/",
                ],
            )
            realm.refresh_from_db()
            self.assertEqual(realm.push_notifications_enabled, False)
            self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

            # Now verify the flag will correctly get flipped back if the server stops
            # rejecting our notification.

            # This will put us within the allowed number of users to use push notifications
            # for free, so the server will accept our next request.
            mock_current_count.return_value = 5

            new_message_id = self.send_personal_message(
                self.example_user("othello"), self.user_profile
            )
            new_missed_message = {
                "message_id": new_message_id,
                "trigger": NotificationTriggers.DIRECT_MESSAGE,
            }

            handle_push_notification(self.user_profile.id, new_missed_message)
            self.assertIn(
                f"Sent mobile push notifications for user {self.user_profile.id}",
                pn_logger.output[-1],
            )
            realm.refresh_from_db()
            self.assertEqual(realm.push_notifications_enabled, True)
            self.assertEqual(realm.push_notifications_enabled_end_timestamp, None)

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_unregistered_client(self) -> None:
        self.add_mock_response()
        self.setup_apns_tokens()
        self.setup_gcm_tokens()

        time_sent = now().replace(microsecond=0)
        with time_machine.travel(time_sent, tick=False):
            message = self.get_message(
                Recipient.PERSONAL,
                type_id=self.personal_recipient_user.id,
                realm_id=self.personal_recipient_user.realm_id,
            )
            UserMessage.objects.create(
                user_profile=self.user_profile,
                message=message,
            )

        time_received = time_sent + timedelta(seconds=1, milliseconds=234)
        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        with time_machine.travel(time_received, tick=False), mock.patch(
            "zerver.lib.push_notifications.gcm_client"
        ) as mock_gcm, self.mock_apns() as (apns_context, send_notification), mock.patch(
            "corporate.lib.stripe.RemoteRealmBillingSession.current_count_for_billed_licenses",
            return_value=10,
        ), self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as pn_logger, self.assertLogs("zilencer.views", level="INFO") as views_logger:
            apns_devices = [
                (b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS)
            ]
            gcm_devices = [
                (b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.GCM)
            ]

            # Reset the local registrations for the user to make them compatible
            # with the RemotePushDeviceToken entries.
            PushDeviceToken.objects.filter(kind=PushDeviceToken.APNS).delete()
            [
                PushDeviceToken.objects.create(
                    kind=PushDeviceToken.APNS,
                    token=device.token,
                    user=self.user_profile,
                    ios_app_id=device.ios_app_id,
                )
                for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS)
            ]
            PushDeviceToken.objects.filter(kind=PushDeviceToken.GCM).delete()
            [
                PushDeviceToken.objects.create(
                    kind=PushDeviceToken.GCM,
                    token=device.token,
                    user=self.user_profile,
                    ios_app_id=device.ios_app_id,
                )
                for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.GCM)
            ]

            mock_gcm.json_request.return_value = {"success": {gcm_devices[0][2]: message.id}}
            send_notification.return_value.is_successful = False
            send_notification.return_value.description = "Unregistered"

            # Ensure the setup is as expected:
            self.assertNotEqual(
                PushDeviceToken.objects.filter(kind=PushDeviceToken.APNS).count(), 0
            )
            handle_push_notification(self.user_profile.id, missed_message)
            self.assertEqual(
                views_logger.output,
                [
                    "INFO:zilencer.views:"
                    f"Remote queuing latency for 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{self.user_profile.id}><uuid:{self.user_profile.uuid}> "
                    "is 1 seconds",
                    "INFO:zilencer.views:"
                    f"Sending mobile push notifications for remote user 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{self.user_profile.id}><uuid:{self.user_profile.uuid}>: "
                    f"{len(gcm_devices)} via FCM devices, {len(apns_devices)} via APNs devices",
                ],
            )
            for _, _, token in apns_devices:
                self.assertIn(
                    "INFO:zerver.lib.push_notifications:"
                    f"APNs: Removing invalid/expired token {token} (Unregistered)",
                    pn_logger.output,
                )
            self.assertIn(
                "INFO:zerver.lib.push_notifications:Deleting push tokens based on response from bouncer: "
                f"Android: [], Apple: {sorted([token for _, _, token in apns_devices])}",
                pn_logger.output,
            )
            self.assertEqual(
                RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS).count(), 0
            )
            # Local registrations have also been deleted:
            self.assertEqual(PushDeviceToken.objects.filter(kind=PushDeviceToken.APNS).count(), 0)

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_connection_error(self) -> None:
        self.setup_apns_tokens()
        self.setup_gcm_tokens()

        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
        )

        missed_message = {
            "user_profile_id": self.user_profile.id,
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
        URL = settings.PUSH_NOTIFICATION_BOUNCER_URL + "/api/v1/remotes/push/notify"
        responses.add(responses.POST, URL, body=ConnectionError())
        with mock.patch("zerver.lib.push_notifications.gcm_client") as mock_gcm:
            gcm_devices = [
                (b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.GCM)
            ]
            mock_gcm.json_request.return_value = {"success": {gcm_devices[0][2]: message.id}}
            with self.assertRaises(PushNotificationBouncerRetryLaterError):
                handle_push_notification(self.user_profile.id, missed_message)

    @mock.patch("zerver.lib.push_notifications.push_notifications_configured", return_value=True)
    def test_read_message(self, mock_push_notifications: mock.MagicMock) -> None:
        user_profile = self.example_user("hamlet")
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )

        usermessage = UserMessage.objects.create(
            user_profile=user_profile,
            message=message,
        )

        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }

        # If the message is unread, we should send push notifications.
        with mock.patch(
            "zerver.lib.push_notifications.send_apple_push_notification", return_value=1
        ) as mock_send_apple, mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification", return_value=1
        ) as mock_send_android:
            handle_push_notification(user_profile.id, missed_message)
        mock_send_apple.assert_called_once()
        mock_send_android.assert_called_once()

        # If the message has been read, don't send push notifications.
        usermessage.flags.read = True
        usermessage.save()
        with mock.patch(
            "zerver.lib.push_notifications.send_apple_push_notification", return_value=1
        ) as mock_send_apple, mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification", return_value=1
        ) as mock_send_android:
            handle_push_notification(user_profile.id, missed_message)
        mock_send_apple.assert_not_called()
        mock_send_android.assert_not_called()

    def test_deleted_message(self) -> None:
        """Simulates the race where message is deleted before handling push notifications"""
        user_profile = self.example_user("hamlet")
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.read,
            message=message,
        )
        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        # Now, delete the message the normal way
        do_delete_messages(user_profile.realm, [message])

        # This mock.patch() should be assertNoLogs once that feature
        # is added to Python.
        with mock.patch(
            "zerver.lib.push_notifications.uses_notification_bouncer"
        ) as mock_check, mock.patch("logging.error") as mock_logging_error, mock.patch(
            "zerver.lib.push_notifications.push_notifications_configured", return_value=True
        ) as mock_push_notifications:
            handle_push_notification(user_profile.id, missed_message)
            mock_push_notifications.assert_called_once()
            # Check we didn't proceed through and didn't log anything.
            mock_check.assert_not_called()
            mock_logging_error.assert_not_called()

    def test_missing_message(self) -> None:
        """Simulates the race where message is missing when handling push notifications"""
        user_profile = self.example_user("hamlet")
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.read,
            message=message,
        )
        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        # Now delete the message forcefully, so it just doesn't exist.
        message.delete()

        # This should log an error
        with mock.patch(
            "zerver.lib.push_notifications.uses_notification_bouncer"
        ) as mock_check, self.assertLogs(level="INFO") as mock_logging_info, mock.patch(
            "zerver.lib.push_notifications.push_notifications_configured", return_value=True
        ) as mock_push_notifications:
            handle_push_notification(user_profile.id, missed_message)
            mock_push_notifications.assert_called_once()
            # Check we didn't proceed through.
            mock_check.assert_not_called()
            self.assertEqual(
                mock_logging_info.output,
                [
                    f"INFO:root:Unexpected message access failure handling push notifications: {user_profile.id} {missed_message['message_id']}"
                ],
            )

    def test_send_notifications_to_bouncer(self) -> None:
        self.setup_apns_tokens()
        self.setup_gcm_tokens()

        user_profile = self.user_profile
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=user_profile,
            message=message,
        )

        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=True), mock.patch(
            "zerver.lib.push_notifications.get_message_payload_apns", return_value={"apns": True}
        ), mock.patch(
            "zerver.lib.push_notifications.get_message_payload_gcm",
            return_value=({"gcm": True}, {}),
        ), mock.patch(
            "zerver.lib.push_notifications.send_json_to_push_bouncer",
            return_value=dict(
                total_android_devices=3,
                total_apple_devices=5,
                deleted_devices=DevicesToCleanUpDict(android_devices=[], apple_devices=[]),
                realm=None,
            ),
        ) as mock_send, self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as mock_logging_info:
            handle_push_notification(user_profile.id, missed_message)
            mock_send.assert_called_with(
                "POST",
                "push/notify",
                {
                    "user_uuid": str(user_profile.uuid),
                    "user_id": user_profile.id,
                    "realm_uuid": str(user_profile.realm.uuid),
                    "apns_payload": {"apns": True},
                    "gcm_payload": {"gcm": True},
                    "gcm_options": {},
                    "android_devices": list(
                        PushDeviceToken.objects.filter(user=user_profile, kind=PushDeviceToken.GCM)
                        .order_by("id")
                        .values_list("token", flat=True)
                    ),
                    "apple_devices": list(
                        PushDeviceToken.objects.filter(user=user_profile, kind=PushDeviceToken.APNS)
                        .order_by("id")
                        .values_list("token", flat=True)
                    ),
                },
            )

            self.assertEqual(
                mock_logging_info.output,
                [
                    f"INFO:zerver.lib.push_notifications:Sending push notifications to mobile clients for user {user_profile.id}",
                    f"INFO:zerver.lib.push_notifications:Sent mobile push notifications for user {user_profile.id} through bouncer: 3 via FCM devices, 5 via APNs devices",
                ],
            )

    def test_non_bouncer_push(self) -> None:
        self.setup_apns_tokens()
        self.setup_gcm_tokens()
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
        )

        android_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.GCM)
        )

        apple_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.APNS)
        )

        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        with mock.patch(
            "zerver.lib.push_notifications.get_message_payload_apns", return_value={"apns": True}
        ), mock.patch(
            "zerver.lib.push_notifications.get_message_payload_gcm",
            return_value=({"gcm": True}, {}),
        ), mock.patch(
            # Simulate the send...push_notification functions returning a number of successes
            # lesser than the number of devices, so that we can verify correct CountStat counting.
            "zerver.lib.push_notifications.send_apple_push_notification",
            return_value=len(apple_devices) - 1,
        ) as mock_send_apple, mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification",
            return_value=len(android_devices) - 1,
        ) as mock_send_android, mock.patch(
            "zerver.lib.push_notifications.push_notifications_configured", return_value=True
        ) as mock_push_notifications:
            handle_push_notification(self.user_profile.id, missed_message)
            user_identity = UserPushIdentityCompat(user_id=self.user_profile.id)
            mock_send_apple.assert_called_with(user_identity, apple_devices, {"apns": True})
            mock_send_android.assert_called_with(user_identity, android_devices, {"gcm": True}, {})
            mock_push_notifications.assert_called_once()

        remote_realm_count = RealmCount.objects.values("property", "subgroup", "value").last()
        self.assertEqual(
            remote_realm_count,
            dict(
                property="mobile_pushes_sent::day",
                subgroup=None,
                value=len(android_devices) + len(apple_devices) - 2,
            ),
        )

    def test_send_remove_notifications_to_bouncer(self) -> None:
        self.setup_apns_tokens()
        self.setup_gcm_tokens()

        user_profile = self.user_profile
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=user_profile,
            message=message,
            flags=UserMessage.flags.active_mobile_push_notification,
        )

        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=True), mock.patch(
            "zerver.lib.push_notifications.send_notifications_to_bouncer"
        ) as mock_send:
            handle_remove_push_notification(user_profile.id, [message.id])
            mock_send.assert_called_with(
                user_profile,
                {
                    "badge": 0,
                    "custom": {
                        "zulip": {
                            "server": "testserver",
                            "realm_id": self.sender.realm.id,
                            "realm_name": self.sender.realm.name,
                            "realm_uri": "http://zulip.testserver",
                            "user_id": self.user_profile.id,
                            "event": "remove",
                            "zulip_message_ids": str(message.id),
                        },
                    },
                },
                {
                    "server": "testserver",
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": "http://zulip.testserver",
                    "user_id": self.user_profile.id,
                    "event": "remove",
                    "zulip_message_ids": str(message.id),
                    "zulip_message_id": message.id,
                },
                {"priority": "normal"},
                list(
                    PushDeviceToken.objects.filter(
                        user=user_profile, kind=PushDeviceToken.GCM
                    ).order_by("id")
                ),
                list(
                    PushDeviceToken.objects.filter(
                        user=user_profile, kind=PushDeviceToken.APNS
                    ).order_by("id")
                ),
            )
            user_message = UserMessage.objects.get(user_profile=self.user_profile, message=message)
            self.assertEqual(user_message.flags.active_mobile_push_notification, False)

    def test_non_bouncer_push_remove(self) -> None:
        self.setup_apns_tokens()
        self.setup_gcm_tokens()
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
            flags=UserMessage.flags.active_mobile_push_notification,
        )

        android_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.GCM)
        )

        apple_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.APNS)
        )

        with mock.patch(
            "zerver.lib.push_notifications.push_notifications_configured", return_value=True
        ) as mock_push_notifications, mock.patch(
            # Simulate the send...push_notification functions returning a number of successes
            # lesser than the number of devices, so that we can verify correct CountStat counting.
            "zerver.lib.push_notifications.send_android_push_notification",
            return_value=len(apple_devices) - 1,
        ) as mock_send_android, mock.patch(
            "zerver.lib.push_notifications.send_apple_push_notification",
            return_value=len(apple_devices) - 1,
        ) as mock_send_apple:
            handle_remove_push_notification(self.user_profile.id, [message.id])
            mock_push_notifications.assert_called_once()
            user_identity = UserPushIdentityCompat(user_id=self.user_profile.id)
            mock_send_android.assert_called_with(
                user_identity,
                android_devices,
                {
                    "server": "testserver",
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": "http://zulip.testserver",
                    "user_id": self.user_profile.id,
                    "event": "remove",
                    "zulip_message_ids": str(message.id),
                    "zulip_message_id": message.id,
                },
                {"priority": "normal"},
            )
            mock_send_apple.assert_called_with(
                user_identity,
                apple_devices,
                {
                    "badge": 0,
                    "custom": {
                        "zulip": {
                            "server": "testserver",
                            "realm_id": self.sender.realm.id,
                            "realm_name": self.sender.realm.name,
                            "realm_uri": "http://zulip.testserver",
                            "user_id": self.user_profile.id,
                            "event": "remove",
                            "zulip_message_ids": str(message.id),
                        }
                    },
                },
            )
            user_message = UserMessage.objects.get(user_profile=self.user_profile, message=message)
            self.assertEqual(user_message.flags.active_mobile_push_notification, False)

            remote_realm_count = RealmCount.objects.values("property", "subgroup", "value").last()
            self.assertEqual(
                remote_realm_count,
                dict(
                    property="mobile_pushes_sent::day",
                    subgroup=None,
                    value=len(android_devices) + len(apple_devices) - 2,
                ),
            )

    def test_user_message_does_not_exist(self) -> None:
        """This simulates a condition that should only be an error if the user is
        not long-term idle; we fake it, though, in the sense that the user should
        not have received the message in the first place"""
        self.make_stream("public_stream")
        sender = self.example_user("iago")
        self.subscribe(sender, "public_stream")
        message_id = self.send_stream_message(sender, "public_stream", "test")
        missed_message = {"message_id": message_id}
        with self.assertLogs("zerver.lib.push_notifications", level="ERROR") as logger, mock.patch(
            "zerver.lib.push_notifications.push_notifications_configured", return_value=True
        ) as mock_push_notifications:
            handle_push_notification(self.user_profile.id, missed_message)
            self.assertEqual(
                "ERROR:zerver.lib.push_notifications:"
                f"Could not find UserMessage with message_id {message_id} and user_id {self.user_profile.id}"
                "\nNoneType: None",  # This is an effect of using `exc_info=True` in the actual logger.
                logger.output[0],
            )
            mock_push_notifications.assert_called_once()

    def test_user_message_does_not_exist_remove(self) -> None:
        """This simulates a condition that should only be an error if the user is
        not long-term idle; we fake it, though, in the sense that the user should
        not have received the message in the first place"""
        self.setup_apns_tokens()
        self.setup_gcm_tokens()
        self.make_stream("public_stream")
        sender = self.example_user("iago")
        self.subscribe(sender, "public_stream")
        message_id = self.send_stream_message(sender, "public_stream", "test")
        with mock.patch(
            "zerver.lib.push_notifications.push_notifications_configured", return_value=True
        ) as mock_push_notifications, mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification", return_value=1
        ) as mock_send_android, mock.patch(
            "zerver.lib.push_notifications.send_apple_push_notification", return_value=1
        ) as mock_send_apple:
            handle_remove_push_notification(self.user_profile.id, [message_id])
            mock_push_notifications.assert_called_once()
            mock_send_android.assert_called_once()
            mock_send_apple.assert_called_once()

    def test_user_message_soft_deactivated(self) -> None:
        """This simulates a condition that should only be an error if the user is
        not long-term idle; we fake it, though, in the sense that the user should
        not have received the message in the first place"""
        self.setup_apns_tokens()
        self.setup_gcm_tokens()
        self.make_stream("public_stream")
        sender = self.example_user("iago")
        self.subscribe(self.user_profile, "public_stream")
        self.subscribe(sender, "public_stream")
        logger_string = "zulip.soft_deactivation"
        with self.assertLogs(logger_string, level="INFO") as info_logs:
            self.soft_deactivate_main_user()

        self.assertEqual(
            info_logs.output,
            [
                f"INFO:{logger_string}:Soft deactivated user {self.user_profile.id}",
                f"INFO:{logger_string}:Soft-deactivated batch of 1 users; 0 remain to process",
            ],
        )
        message_id = self.send_stream_message(sender, "public_stream", "test")
        missed_message = {
            "message_id": message_id,
            "trigger": NotificationTriggers.STREAM_PUSH,
        }

        android_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.GCM)
        )

        apple_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.APNS)
        )

        with mock.patch(
            "zerver.lib.push_notifications.get_message_payload_apns", return_value={"apns": True}
        ), mock.patch(
            "zerver.lib.push_notifications.get_message_payload_gcm",
            return_value=({"gcm": True}, {}),
        ), mock.patch(
            "zerver.lib.push_notifications.send_apple_push_notification", return_value=1
        ) as mock_send_apple, mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification", return_value=1
        ) as mock_send_android, mock.patch(
            "zerver.lib.push_notifications.logger.error"
        ) as mock_logger, mock.patch(
            "zerver.lib.push_notifications.push_notifications_configured", return_value=True
        ) as mock_push_notifications:
            handle_push_notification(self.user_profile.id, missed_message)
            mock_logger.assert_not_called()
            user_identity = UserPushIdentityCompat(user_id=self.user_profile.id)
            mock_send_apple.assert_called_with(user_identity, apple_devices, {"apns": True})
            mock_send_android.assert_called_with(user_identity, android_devices, {"gcm": True}, {})
            mock_push_notifications.assert_called_once()

    @override_settings(MAX_GROUP_SIZE_FOR_MENTION_REACTIVATION=2)
    @mock.patch("zerver.lib.push_notifications.push_notifications_configured", return_value=True)
    def test_user_push_soft_reactivate_soft_deactivated_user(
        self, mock_push_notifications: mock.MagicMock
    ) -> None:
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")
        zulip_realm = get_realm("zulip")

        # user groups having upto 'MAX_GROUP_SIZE_FOR_MENTION_REACTIVATION'
        # members are small user groups.
        small_user_group = check_add_user_group(
            zulip_realm,
            "small_user_group",
            [self.user_profile, othello],
            acting_user=None,
        )

        large_user_group = check_add_user_group(
            zulip_realm, "large_user_group", [self.user_profile], acting_user=None
        )
        subgroup = check_add_user_group(
            zulip_realm, "subgroup", [othello, cordelia], acting_user=None
        )
        add_subgroups_to_user_group(large_user_group, [subgroup], acting_user=None)

        # Personal mention in a stream message should soft reactivate the user
        def mention_in_stream() -> None:
            mention = f"@**{self.user_profile.full_name}**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": stream_mentioned_message_id,
                    "trigger": NotificationTriggers.MENTION,
                },
            )

        self.soft_deactivate_main_user()
        self.expect_soft_reactivation(self.user_profile, mention_in_stream)

        # Direct message should soft reactivate the user
        def direct_message() -> None:
            # Soft reactivate the user by sending a personal message
            personal_message_id = self.send_personal_message(othello, self.user_profile, "Message")
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": personal_message_id,
                    "trigger": NotificationTriggers.DIRECT_MESSAGE,
                },
            )

        self.soft_deactivate_main_user()
        self.expect_soft_reactivation(self.user_profile, direct_message)

        # User FOLLOWS the topic.
        # 'wildcard_mentions_notify' is disabled to verify the corner case when only
        # 'enable_followed_topic_wildcard_mentions_notify' is enabled (True by default).
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "test",
            visibility_policy=UserTopic.VisibilityPolicy.FOLLOWED,
        )
        do_change_user_setting(
            self.user_profile, "wildcard_mentions_notify", False, acting_user=None
        )

        # Topic wildcard mention in followed topic should soft reactivate the user
        # user should be a topic participant
        self.send_stream_message(self.user_profile, "Denmark", "topic participant")

        def send_topic_wildcard_mention() -> None:
            mention = "@**topic**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": stream_mentioned_message_id,
                    "trigger": NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
                },
            )

        self.soft_deactivate_main_user()
        self.expect_soft_reactivation(self.user_profile, send_topic_wildcard_mention)

        # Stream wildcard mention in followed topic should NOT soft reactivate the user
        def send_stream_wildcard_mention() -> None:
            mention = "@**all**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": stream_mentioned_message_id,
                    "trigger": NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
                },
            )

        self.soft_deactivate_main_user()
        self.expect_to_stay_long_term_idle(self.user_profile, send_stream_wildcard_mention)

        # Reset
        do_set_user_topic_visibility_policy(
            self.user_profile,
            get_stream("Denmark", self.user_profile.realm),
            "test",
            visibility_policy=UserTopic.VisibilityPolicy.INHERIT,
        )
        do_change_user_setting(
            self.user_profile, "wildcard_mentions_notify", True, acting_user=None
        )

        # Topic Wildcard mention should soft reactivate the user
        self.expect_soft_reactivation(self.user_profile, send_topic_wildcard_mention)

        # Stream Wildcard mention should NOT soft reactivate the user
        self.soft_deactivate_main_user()
        self.expect_to_stay_long_term_idle(self.user_profile, send_stream_wildcard_mention)

        # Small group mention should soft reactivate the user
        def send_small_group_mention() -> None:
            mention = "@*small_user_group*"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": stream_mentioned_message_id,
                    "trigger": NotificationTriggers.MENTION,
                    "mentioned_user_group_id": small_user_group.id,
                },
            )

        self.soft_deactivate_main_user()
        self.expect_soft_reactivation(self.user_profile, send_small_group_mention)

        # Large group mention should NOT soft reactivate the user
        def send_large_group_mention() -> None:
            mention = "@*large_user_group*"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": stream_mentioned_message_id,
                    "trigger": NotificationTriggers.MENTION,
                    "mentioned_user_group_id": large_user_group.id,
                },
            )

        self.soft_deactivate_main_user()
        self.expect_to_stay_long_term_idle(self.user_profile, send_large_group_mention)

    @mock.patch("zerver.lib.push_notifications.logger.info")
    @mock.patch("zerver.lib.push_notifications.push_notifications_configured", return_value=True)
    def test_user_push_notification_already_active(
        self, mock_push_notifications: mock.MagicMock, mock_info: mock.MagicMock
    ) -> None:
        user_profile = self.example_user("hamlet")
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.active_mobile_push_notification,
            message=message,
        )

        missed_message = {
            "message_id": message.id,
            "trigger": NotificationTriggers.DIRECT_MESSAGE,
        }
        handle_push_notification(user_profile.id, missed_message)
        mock_push_notifications.assert_called_once()
        # Check we didn't proceed ahead and function returned.
        mock_info.assert_not_called()


class TestAPNs(PushNotificationTest):
    def devices(self) -> List[DeviceToken]:
        return list(
            PushDeviceToken.objects.filter(user=self.user_profile, kind=PushDeviceToken.APNS)
        )

    def send(
        self,
        devices: Optional[List[Union[PushDeviceToken, RemotePushDeviceToken]]] = None,
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
            with self.settings(APNS_CERT_FILE="/foo.pem"), mock.patch(
                "ssl.SSLContext.load_cert_chain"
            ) as mock_load_cert_chain:
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
        with mock.patch(
            "zerver.lib.push_notifications.get_apns_context"
        ) as mock_get, self.assertLogs("zerver.lib.push_notifications", level="DEBUG") as logger:
            mock_get.return_value = None
            self.send()
            notification_drop_log = (
                "DEBUG:zerver.lib.push_notifications:"
                "APNs: Dropping a notification because nothing configured.  "
                "Set PUSH_NOTIFICATION_BOUNCER_URL (or APNS_CERT_FILE)."
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
        with self.mock_apns() as (apns_context, send_notification), self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as logger:
            send_notification.return_value.is_successful = True
            self.send()
            for device in self.devices():
                self.assertIn(
                    f"INFO:zerver.lib.push_notifications:APNs: Success sending for user <id:{self.user_profile.id}> to device {device.token}",
                    logger.output,
                )

    def test_http_retry_eventually_fails(self) -> None:
        self.setup_apns_tokens()
        with self.mock_apns() as (apns_context, send_notification), self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as logger:
            send_notification.side_effect = aioapns.exceptions.ConnectionError()
            self.send(devices=self.devices()[0:1])
            self.assertIn(
                f"ERROR:zerver.lib.push_notifications:APNs: ConnectionError sending for user <id:{self.user_profile.id}> to device {self.devices()[0].token}; check certificate expiration",
                logger.output,
            )

    def test_other_exception(self) -> None:
        self.setup_apns_tokens()
        with self.mock_apns() as (apns_context, send_notification), self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as logger:
            send_notification.side_effect = IOError
            self.send(devices=self.devices()[0:1])
            self.assertIn(
                f"ERROR:zerver.lib.push_notifications:APNs: Error sending for user <id:{self.user_profile.id}> to device {self.devices()[0].token}",
                logger.output[1],
            )

    def test_internal_server_error(self) -> None:
        self.setup_apns_tokens()
        with self.mock_apns() as (apns_context, send_notification), self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as logger:
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
        with self.mock_apns() as (apns_context, send_notification), self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as logger:
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
            do_update_message_flags(user_profile, "add", "read", [message_id])
            self.assertEqual(get_apns_badge_count(user_profile), 0)
            self.assertEqual(get_apns_badge_count_future(user_profile), num_messages - i - 1)

        mock_push_notifications.assert_called()


class TestGetAPNsPayload(PushNotificationTest):
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
                    "realm_uri": self.sender.realm.uri,
                    "user_id": user_profile.id,
                    "time": datetime_to_timestamp(message.date_sent),
                },
            },
        }
        self.assertDictEqual(payload, expected)

    @mock.patch("zerver.lib.push_notifications.push_notifications_configured", return_value=True)
    def test_get_message_payload_apns_huddle_message(
        self, mock_push_notifications: mock.MagicMock
    ) -> None:
        user_profile = self.example_user("othello")
        message_id = self.send_huddle_message(
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
                    "realm_uri": self.sender.realm.uri,
                    "user_id": user_profile.id,
                    "time": datetime_to_timestamp(message.date_sent),
                },
            },
        }
        self.assertDictEqual(payload, expected)
        mock_push_notifications.assert_called()

    def _test_get_message_payload_apns_stream_message(self, trigger: str) -> None:
        stream = Stream.objects.filter(name="Verona").get()
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)
        payload = get_message_payload_apns(self.sender, message, trigger)
        expected = {
            "alert": {
                "title": "#Verona > Test topic",
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
                    "topic": message.topic_name(),
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_name": self.sender.realm.name,
                    "realm_uri": self.sender.realm.uri,
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
                    "realm_uri": self.sender.realm.uri,
                    "user_id": user_profile.id,
                    "time": datetime_to_timestamp(message.date_sent),
                },
            },
        }
        self.assertDictEqual(payload, expected)

    def test_get_message_payload_apns_user_group_mention(self) -> None:
        user_profile = self.example_user("othello")
        user_group = check_add_user_group(
            get_realm("zulip"), "test_user_group", [user_profile], acting_user=None
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
                    "realm_uri": self.sender.realm.uri,
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
                    "realm_uri": self.sender.realm.uri,
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
        message_id = self.send_huddle_message(
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
                    "realm_uri": self.sender.realm.uri,
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
                    "realm_uri": hamlet.realm.uri,
                    "user_id": polonius.id,
                    "time": datetime_to_timestamp(message.date_sent),
                }
            },
        }
        self.assertDictEqual(payload, expected)


class TestGetGCMPayload(PushNotificationTest):
    def _test_get_message_payload_gcm_stream_message(
        self,
        truncate_content: bool = False,
        mentioned_user_group_id: Optional[int] = None,
        mentioned_user_group_name: Optional[str] = None,
    ) -> None:
        stream = Stream.objects.filter(name="Verona").get()
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)
        content = message.content
        if truncate_content:
            message.content = "a" * 210
            message.rendered_content = "a" * 210
            message.save()
            content = "a" * 200 + "…"

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
            "realm_uri": hamlet.realm.uri,
            "sender_id": hamlet.id,
            "sender_email": hamlet.email,
            "sender_full_name": "King Hamlet",
            "sender_avatar_url": absolute_avatar_url(message.sender),
            "recipient_type": "stream",
            "stream": stream.name,
            "stream_id": stream.id,
            "topic": message.topic_name(),
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
                "realm_uri": hamlet.realm.uri,
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
                "realm_uri": hamlet.realm.uri,
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
                "realm_uri": hamlet.realm.uri,
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


class TestSendNotificationsToBouncer(PushNotificationTest):
    def test_send_notifications_to_bouncer_when_no_devices(self) -> None:
        user = self.example_user("hamlet")

        with mock.patch(
            "zerver.lib.remote_server.send_to_push_bouncer"
        ) as mock_send, self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as mock_logging_info:
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
        self.setup_gcm_tokens()

        android_devices = PushDeviceToken.objects.filter(kind=PushDeviceToken.GCM)
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
        self.assertEqual(PushDeviceToken.objects.filter(kind=PushDeviceToken.GCM).count(), 0)

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


@override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
class TestSendToPushBouncer(ZulipTestCase):
    def add_mock_response(
        self, body: bytes = orjson.dumps({"msg": "error"}), status: int = 200
    ) -> None:
        assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
        URL = settings.PUSH_NOTIFICATION_BOUNCER_URL + "/api/v1/remotes/register"
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


class TestPushApi(BouncerTestCase):
    @responses.activate
    def test_push_api_error_handling(self) -> None:
        user = self.example_user("cordelia")
        self.login_user(user)

        endpoints: List[Tuple[str, str, Mapping[str, str]]] = [
            ("/json/users/me/apns_device_token", "apple-tokenaz", {"appid": "org.zulip.Zulip"}),
            ("/json/users/me/android_gcm_reg_id", "android-token", {}),
        ]

        # Test error handling
        for endpoint, label, appid in endpoints:
            # Try adding/removing tokens that are too big...
            broken_token = "a" * 5000  # too big
            result = self.client_post(endpoint, {"token": broken_token, **appid})
            self.assert_json_error(result, "Empty or invalid length token")

            if label == "apple-tokenaz":
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
            with self.settings(
                PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com"
            ), responses.RequestsMock() as resp:
                assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
                URL = settings.PUSH_NOTIFICATION_BOUNCER_URL + "/api/v1/remotes/push/unregister"
                resp.add_callback(responses.POST, URL, callback=self.request_callback)
                result = self.client_delete(endpoint, {"token": "abcd1234"})
                self.assert_json_error(result, "Token does not exist")
                self.assertTrue(resp.assert_call_count(URL, 1))

    @responses.activate
    def test_push_api_add_and_remove_device_tokens(self) -> None:
        user = self.example_user("cordelia")
        self.login_user(user)

        no_bouncer_requests: List[Tuple[str, str, Mapping[str, str]]] = [
            ("/json/users/me/apns_device_token", "apple-tokenaa", {"appid": "org.zulip.Zulip"}),
            ("/json/users/me/android_gcm_reg_id", "android-token-1", {}),
        ]

        bouncer_requests: List[Tuple[str, str, Mapping[str, str]]] = [
            ("/json/users/me/apns_device_token", "apple-tokenbb", {"appid": "org.zulip.Zulip"}),
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

        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com"):
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
            token_values, ["apple-tokenaa", "android-token-1", "apple-tokenbb", "android-token-2"]
        )

        # RemotePushDeviceToken will only include tokens of
        # the devices using push notification bouncer.
        remote_token_values = list(RemotePushDeviceToken.objects.values_list("token", flat=True))
        self.assertEqual(sorted(remote_token_values), ["android-token-2", "apple-tokenbb"])

        # Test removing tokens without using push notification bouncer.
        for endpoint, token, appid in no_bouncer_requests:
            result = self.client_delete(endpoint, {"token": token})
            self.assert_json_success(result)
            tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
            self.assert_length(tokens, 0)

        # Use push notification bouncer and test removing device tokens.
        # Tokens will be removed both locally and remotely.
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com"):
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
            parse_gcm_options({"invalid": True}, {})

    def test_invalid_priority_value(self) -> None:
        with self.assertRaises(JsonableError):
            parse_gcm_options({"priority": "invalid"}, {})

    def test_default_priority(self) -> None:
        self.assertEqual("high", parse_gcm_options({}, {"event": "message"}))
        self.assertEqual("normal", parse_gcm_options({}, {"event": "remove"}))
        self.assertEqual("normal", parse_gcm_options({}, {}))

    def test_explicit_priority(self) -> None:
        self.assertEqual("normal", parse_gcm_options({"priority": "normal"}, {}))
        self.assertEqual("high", parse_gcm_options({"priority": "high"}, {}))


@mock.patch("zerver.lib.push_notifications.gcm_client")
class GCMSendTest(PushNotificationTest):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.setup_gcm_tokens()

    def get_gcm_data(self, **kwargs: Any) -> Dict[str, Any]:
        data = {
            "key 1": "Data 1",
            "key 2": "Data 2",
        }
        data.update(kwargs)
        return data

    def test_gcm_is_none(self, mock_gcm: mock.MagicMock) -> None:
        mock_gcm.__bool__.return_value = False
        with self.assertLogs("zerver.lib.push_notifications", level="DEBUG") as logger:
            send_android_push_notification_to_user(self.user_profile, {}, {})
            self.assertEqual(
                "DEBUG:zerver.lib.push_notifications:"
                "Skipping sending a GCM push notification since PUSH_NOTIFICATION_BOUNCER_URL "
                "and ANDROID_GCM_API_KEY are both unset",
                logger.output[0],
            )

    def test_json_request_raises_ioerror(self, mock_gcm: mock.MagicMock) -> None:
        mock_gcm.json_request.side_effect = OSError("error")
        with self.assertLogs("zerver.lib.push_notifications", level="WARNING") as logger:
            send_android_push_notification_to_user(self.user_profile, {}, {})
            self.assertIn(
                "WARNING:zerver.lib.push_notifications:Error while pushing to GCM\nTraceback ",
                logger.output[0],
            )

    @mock.patch("zerver.lib.push_notifications.logger.warning")
    def test_success(self, mock_warning: mock.MagicMock, mock_gcm: mock.MagicMock) -> None:
        res = {}
        res["success"] = {token: ind for ind, token in enumerate(self.gcm_tokens)}
        mock_gcm.json_request.return_value = res

        data = self.get_gcm_data()
        with self.assertLogs("zerver.lib.push_notifications", level="INFO") as logger:
            send_android_push_notification_to_user(self.user_profile, data, {})
        self.assert_length(logger.output, 3)
        log_msg1 = f"INFO:zerver.lib.push_notifications:GCM: Sending notification for local user <id:{self.user_profile.id}> to 2 devices"
        log_msg2 = f"INFO:zerver.lib.push_notifications:GCM: Sent {1111} as {0}"
        log_msg3 = f"INFO:zerver.lib.push_notifications:GCM: Sent {2222} as {1}"
        self.assertEqual([log_msg1, log_msg2, log_msg3], logger.output)
        mock_warning.assert_not_called()

    def test_canonical_equal(self, mock_gcm: mock.MagicMock) -> None:
        res = {}
        res["canonical"] = {1: 1}
        mock_gcm.json_request.return_value = res

        data = self.get_gcm_data()
        with self.assertLogs("zerver.lib.push_notifications", level="WARNING") as logger:
            send_android_push_notification_to_user(self.user_profile, data, {})
        self.assertEqual(
            f"WARNING:zerver.lib.push_notifications:GCM: Got canonical ref but it already matches our ID {1}!",
            logger.output[0],
        )

    def test_canonical_pushdevice_not_present(self, mock_gcm: mock.MagicMock) -> None:
        res = {}
        t1 = hex_to_b64("1111")
        t2 = hex_to_b64("3333")
        res["canonical"] = {t1: t2}
        mock_gcm.json_request.return_value = res

        def get_count(hex_token: str) -> int:
            token = hex_to_b64(hex_token)
            return PushDeviceToken.objects.filter(token=token, kind=PushDeviceToken.GCM).count()

        self.assertEqual(get_count("1111"), 1)
        self.assertEqual(get_count("3333"), 0)

        data = self.get_gcm_data()
        with self.assertLogs("zerver.lib.push_notifications", level="WARNING") as logger:
            send_android_push_notification_to_user(self.user_profile, data, {})
            msg = f"WARNING:zerver.lib.push_notifications:GCM: Got canonical ref {t2} replacing {t1} but new ID not registered! Updating."
            self.assertEqual(msg, logger.output[0])

        self.assertEqual(get_count("1111"), 0)
        self.assertEqual(get_count("3333"), 1)

    def test_canonical_pushdevice_different(self, mock_gcm: mock.MagicMock) -> None:
        res = {}
        old_token = hex_to_b64("1111")
        new_token = hex_to_b64("2222")
        res["canonical"] = {old_token: new_token}
        mock_gcm.json_request.return_value = res

        def get_count(hex_token: str) -> int:
            token = hex_to_b64(hex_token)
            return PushDeviceToken.objects.filter(token=token, kind=PushDeviceToken.GCM).count()

        self.assertEqual(get_count("1111"), 1)
        self.assertEqual(get_count("2222"), 1)

        data = self.get_gcm_data()
        with self.assertLogs("zerver.lib.push_notifications", level="INFO") as logger:
            send_android_push_notification_to_user(self.user_profile, data, {})
            self.assertEqual(
                f"INFO:zerver.lib.push_notifications:GCM: Sending notification for local user <id:{self.user_profile.id}> to 2 devices",
                logger.output[0],
            )
            self.assertEqual(
                f"INFO:zerver.lib.push_notifications:GCM: Got canonical ref {new_token}, dropping {old_token}",
                logger.output[1],
            )

        self.assertEqual(get_count("1111"), 0)
        self.assertEqual(get_count("2222"), 1)

    def test_not_registered(self, mock_gcm: mock.MagicMock) -> None:
        res = {}
        token = hex_to_b64("1111")
        res["errors"] = {"NotRegistered": [token]}
        mock_gcm.json_request.return_value = res

        def get_count(hex_token: str) -> int:
            token = hex_to_b64(hex_token)
            return PushDeviceToken.objects.filter(token=token, kind=PushDeviceToken.GCM).count()

        self.assertEqual(get_count("1111"), 1)

        data = self.get_gcm_data()
        with self.assertLogs("zerver.lib.push_notifications", level="INFO") as logger:
            send_android_push_notification_to_user(self.user_profile, data, {})
            self.assertEqual(
                f"INFO:zerver.lib.push_notifications:GCM: Sending notification for local user <id:{self.user_profile.id}> to 2 devices",
                logger.output[0],
            )
            self.assertEqual(
                f"INFO:zerver.lib.push_notifications:GCM: Removing {token}",
                logger.output[1],
            )
        self.assertEqual(get_count("1111"), 0)

    def test_failure(self, mock_gcm: mock.MagicMock) -> None:
        res = {}
        token = hex_to_b64("1111")
        res["errors"] = {"Failed": [token]}
        mock_gcm.json_request.return_value = res

        data = self.get_gcm_data()
        with self.assertLogs("zerver.lib.push_notifications", level="WARNING") as logger:
            send_android_push_notification_to_user(self.user_profile, data, {})
            msg = f"WARNING:zerver.lib.push_notifications:GCM: Delivery to {token} failed: Failed"
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

        with mock_queue_publish("zerver.actions.message_flags.queue_json_publish") as mock_publish:
            assert stream.recipient_id is not None
            do_mark_stream_messages_as_read(hamlet, stream.recipient_id)
            queue_items = [c[0][1] for c in mock_publish.call_args_list]
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
                "rendered_content": f'<p>Testing stream names <a class="stream" data-stream-id="{stream.id}" href="/#narrow/stream/Verona">#Verona</a>.</p>',
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

        # Set up a MX lookup mock for all the tests, so that they don't have to
        # worry about it failing, unless they intentionally want to set it up
        # to happen.
        self.mxlookup_patcher = mock.patch("DNS.mxlookup", return_value=[(0, "")])
        self.mxlookup_mock = self.mxlookup_patcher.start()

    @override
    def tearDown(self) -> None:
        self.mxlookup_patcher.stop()

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
            event_type=RealmAuditLog.REMOTE_SERVER_DEACTIVATED
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
        self.assert_json_error(result, "Invalid address.")

        # An example disposable domain.
        request["contact_email"] = "admin@mailnator.com"
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(result, "Please use your real email address.")

        request["contact_email"] = "admin@zulip.com"
        with mock.patch("DNS.mxlookup", side_effect=DNS.Base.ServerError("test", 1)):
            result = self.client_post("/api/v1/remotes/server/register", request)
            self.assert_json_error(
                result, "zulip.com does not exist or is not configured to accept email."
            )

        with mock.patch("DNS.mxlookup", return_value=[]):
            result = self.client_post("/api/v1/remotes/server/register", request)
            self.assert_json_error(
                result, "zulip.com does not exist or is not configured to accept email."
            )


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
