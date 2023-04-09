import asyncio
import base64
import datetime
import re
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple, Union
from unittest import mock, skipUnless
from urllib import parse

import aioapns
import orjson
import responses
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.http.response import ResponseHeaders
from django.test import override_settings
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from requests.exceptions import ConnectionError
from requests.models import PreparedRequest

from analytics.lib.counts import CountStat, LoggingCountStat
from analytics.models import InstallationCount, RealmCount
from zerver.actions.message_delete import do_delete_messages
from zerver.actions.message_flags import do_mark_stream_messages_as_read, do_update_message_flags
from zerver.actions.user_settings import do_regenerate_api_key
from zerver.lib.avatar import absolute_avatar_url
from zerver.lib.exceptions import JsonableError
from zerver.lib.push_notifications import (
    APNsContext,
    DeviceToken,
    UserPushIdentityCompat,
    b64_to_hex,
    get_apns_badge_count,
    get_apns_badge_count_future,
    get_apns_context,
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
    PushNotificationBouncerError,
    PushNotificationBouncerRetryLaterError,
    build_analytics_data,
    send_analytics_to_remote_server,
    send_to_push_bouncer,
)
from zerver.lib.response import json_response_from_error
from zerver.lib.soft_deactivation import do_soft_deactivate_users
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import mock_queue_publish
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.user_groups import create_user_group
from zerver.models import (
    Message,
    NotificationTriggers,
    PushDeviceToken,
    RealmAuditLog,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    get_client,
    get_display_recipient,
    get_realm,
    get_stream,
    get_user_profile_by_id,
)
from zilencer.models import RemoteZulipServerAuditLog

if settings.ZILENCER_ENABLED:
    from zilencer.models import (
        RemoteInstallationCount,
        RemotePushDeviceToken,
        RemoteRealmAuditLog,
        RemoteRealmCount,
        RemoteZulipServer,
    )


@skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
class BouncerTestCase(ZulipTestCase):
    def setUp(self) -> None:
        self.server_uuid = "6cde5f7a-1f7e-4978-9716-49f69ebfc9fe"
        self.server = RemoteZulipServer(
            uuid=self.server_uuid,
            api_key="magic_secret_api_key",
            hostname="demo.example.com",
            last_updated=now(),
        )
        self.server.save()
        super().setUp()

    def tearDown(self) -> None:
        RemoteZulipServer.objects.filter(uuid=self.server_uuid).delete()
        super().tearDown()

    def request_callback(self, request: PreparedRequest) -> Tuple[int, ResponseHeaders, bytes]:
        assert isinstance(request.body, str) or request.body is None
        params: Dict[str, List[str]] = parse.parse_qs(request.body)
        # In Python 3, the values of the dict from `parse_qs` are
        # in a list, because there might be multiple values.
        # But since we are sending values with no same keys, hence
        # we can safely pick the first value.
        data = {k: v[0] for k, v in params.items()}
        assert request.url is not None  # allow mypy to infer url is present.
        assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
        local_url = request.url.replace(settings.PUSH_NOTIFICATION_BOUNCER_URL, "")
        if request.method == "POST":
            result = self.uuid_post(self.server_uuid, local_url, data, subdomain="")
        elif request.method == "GET":
            result = self.uuid_get(self.server_uuid, local_url, data, subdomain="")
        return (result.status_code, result.headers, result.content)

    def add_mock_response(self) -> None:
        # Match any endpoint with the PUSH_NOTIFICATION_BOUNCER_URL.
        assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
        COMPILED_URL = re.compile(settings.PUSH_NOTIFICATION_BOUNCER_URL + ".*")
        responses.add_callback(responses.POST, COMPILED_URL, callback=self.request_callback)
        responses.add_callback(responses.GET, COMPILED_URL, callback=self.request_callback)

    def get_generic_payload(self, method: str = "register") -> Dict[str, Any]:
        user_id = 10
        token = "111222"
        token_kind = PushDeviceToken.GCM

        return {"user_id": user_id, "token": token, "token_kind": token_kind}


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

    def test_send_notification_endpoint(self) -> None:
        hamlet = self.example_user("hamlet")
        server = RemoteZulipServer.objects.get(uuid=self.server_uuid)
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
            "gcm_payload": {"event": "remove", "zulip_message_ids": many_ids},
            "apns_payload": {
                "badge": 0,
                "custom": {"zulip": {"event": "remove", "zulip_message_ids": many_ids}},
            },
            "gcm_options": {},
        }
        with mock.patch(
            "zilencer.views.send_android_push_notification"
        ) as android_push, mock.patch(
            "zilencer.views.send_apple_push_notification"
        ) as apple_push, self.assertLogs(
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
            {"result": "success", "msg": "", "total_android_devices": 2, "total_apple_devices": 1},
            data,
        )
        self.assertEqual(
            logger.output,
            [
                "INFO:zilencer.views:"
                f"Deduplicating push registrations for server id:{server.id} user id:{hamlet.id} uuid:{str(hamlet.uuid)} and tokens:{sorted([t.token for t in android_tokens[:]])}",
                "INFO:zilencer.views:"
                f"Sending mobile push notifications for remote user 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{hamlet.id}><uuid:{str(hamlet.uuid)}>: "
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

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_push_bouncer_api(self) -> None:
        """This is a variant of the below test_push_api, but using the full
        push notification bouncer flow
        """
        self.add_mock_response()
        user = self.example_user("cordelia")
        self.login_user(user)
        server = RemoteZulipServer.objects.get(uuid=self.server_uuid)

        endpoints = [
            ("/json/users/me/apns_device_token", "apple-tokenaz", RemotePushDeviceToken.APNS),
            ("/json/users/me/android_gcm_reg_id", "android-token", RemotePushDeviceToken.GCM),
        ]

        # Test error handling
        for endpoint, token, kind in endpoints:
            # Try adding/removing tokens that are too big...
            broken_token = "a" * 5000  # too big
            result = self.client_post(
                endpoint, {"token": broken_token, "token_kind": kind}, subdomain="zulip"
            )
            self.assert_json_error(result, "Empty or invalid length token")

            result = self.client_delete(
                endpoint, {"token": broken_token, "token_kind": kind}, subdomain="zulip"
            )
            self.assert_json_error(result, "Empty or invalid length token")

            # Try to remove a non-existent token...
            result = self.client_delete(
                endpoint, {"token": "abcd1234", "token_kind": kind}, subdomain="zulip"
            )
            self.assert_json_error(result, "Token does not exist")

            assert settings.PUSH_NOTIFICATION_BOUNCER_URL is not None
            URL = settings.PUSH_NOTIFICATION_BOUNCER_URL + "/api/v1/remotes/push/register"
            with responses.RequestsMock() as resp, self.assertLogs(level="ERROR") as error_log:
                resp.add(responses.POST, URL, body=ConnectionError(), status=502)
                result = self.client_post(endpoint, {"token": token}, subdomain="zulip")
                self.assert_json_error(
                    result,
                    "ConnectionError while trying to connect to push notification bouncer",
                    502,
                )
                self.assertIn(
                    f"ERROR:django.request:Bad Gateway: {endpoint}\nTraceback",
                    error_log.output[0],
                )

            with responses.RequestsMock() as resp, self.assertLogs(level="WARNING") as warn_log:
                resp.add(responses.POST, URL, body=orjson.dumps({"msg": "error"}), status=500)
                result = self.client_post(endpoint, {"token": token}, subdomain="zulip")
                self.assert_json_error(result, "Received 500 from push notification bouncer", 502)
                self.assertEqual(
                    warn_log.output[0],
                    "WARNING:root:Received 500 from push notification bouncer",
                )
                self.assertIn(
                    f"ERROR:django.request:Bad Gateway: {endpoint}\nTraceback", warn_log.output[1]
                )

        # Add tokens
        for endpoint, token, kind in endpoints:
            # Test that we can push twice
            result = self.client_post(endpoint, {"token": token}, subdomain="zulip")
            self.assert_json_success(result)

            result = self.client_post(endpoint, {"token": token}, subdomain="zulip")
            self.assert_json_success(result)

            tokens = list(
                RemotePushDeviceToken.objects.filter(
                    user_uuid=user.uuid, token=token, server=server
                )
            )
            self.assert_length(tokens, 1)
            self.assertEqual(tokens[0].token, token)

        # User should have tokens for both devices now.
        tokens = list(RemotePushDeviceToken.objects.filter(user_uuid=user.uuid, server=server))
        self.assert_length(tokens, 2)

        # Remove tokens
        for endpoint, token, kind in endpoints:
            result = self.client_delete(endpoint, {"token": token}, subdomain="zulip")
            self.assert_json_success(result)
            tokens = list(
                RemotePushDeviceToken.objects.filter(
                    user_uuid=user.uuid, token=token, server=server
                )
            )
            self.assert_length(tokens, 0)

        # Re-add copies of those tokens
        for endpoint, token, kind in endpoints:
            result = self.client_post(endpoint, {"token": token}, subdomain="zulip")
            self.assert_json_success(result)
        tokens = list(RemotePushDeviceToken.objects.filter(user_uuid=user.uuid, server=server))
        self.assert_length(tokens, 2)

        # Now we want to remove them using the bouncer after an API key change.
        # First we test error handling in case of issues with the bouncer:
        with mock.patch(
            "zerver.worker.queue_processors.clear_push_device_tokens",
            side_effect=PushNotificationBouncerRetryLaterError("test"),
        ), mock.patch("zerver.worker.queue_processors.retry_event") as mock_retry:
            do_regenerate_api_key(user, user)
            mock_retry.assert_called()

            # We didn't manage to communicate with the bouncer, to the tokens are still there:
            tokens = list(RemotePushDeviceToken.objects.filter(user_uuid=user.uuid, server=server))
            self.assert_length(tokens, 2)

        # Now we successfully remove them:
        do_regenerate_api_key(user, user)
        tokens = list(RemotePushDeviceToken.objects.filter(user_uuid=user.uuid, server=server))
        self.assert_length(tokens, 0)


class AnalyticsBouncerTest(BouncerTestCase):
    TIME_ZERO = datetime.datetime(1988, 3, 14, tzinfo=datetime.timezone.utc)

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

        with responses.RequestsMock() as resp, self.assertLogs(level="WARNING") as mock_warning:
            resp.add(responses.GET, ANALYTICS_STATUS_URL, body=ConnectionError())
            send_analytics_to_remote_server()
            self.assertIn(
                "WARNING:root:ConnectionError while trying to connect to push notification bouncer\nTraceback ",
                mock_warning.output[0],
            )
            self.assertTrue(resp.assert_call_count(ANALYTICS_STATUS_URL, 1))

        self.add_mock_response()
        # Send any existing data over, so that we can start the test with a "clean" slate
        audit_log = RealmAuditLog.objects.all().order_by("id").last()
        assert audit_log is not None
        audit_log_max_id = audit_log.id
        send_analytics_to_remote_server()
        self.assertTrue(responses.assert_call_count(ANALYTICS_STATUS_URL, 1))
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
        realm_stat = LoggingCountStat("invites_sent::day", RealmCount, CountStat.DAY)
        RealmCount.objects.create(
            realm=user.realm, property=realm_stat.property, end_time=end_time, value=5
        )
        InstallationCount.objects.create(
            property=realm_stat.property,
            end_time=end_time,
            value=5,
            # We set a subgroup here to work around:
            # https://github.com/zulip/zulip/issues/12362
            subgroup="test_subgroup",
        )
        # Event type in SYNCED_BILLING_EVENTS -- should be included
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.USER_CREATED,
            event_time=end_time,
            extra_data="data",
        )
        # Event type not in SYNCED_BILLING_EVENTS -- should not be included
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.REALM_LOGO_CHANGED,
            event_time=end_time,
            extra_data="data",
        )
        self.assertEqual(RealmCount.objects.count(), 1)
        self.assertEqual(InstallationCount.objects.count(), 1)
        self.assertEqual(RealmAuditLog.objects.filter(id__gt=audit_log_max_id).count(), 2)

        send_analytics_to_remote_server()
        check_counts(2, 2, 1, 1, 1)

        # Test having no new rows
        send_analytics_to_remote_server()
        check_counts(3, 2, 1, 1, 1)

        # Test only having new RealmCount rows
        RealmCount.objects.create(
            realm=user.realm,
            property=realm_stat.property,
            end_time=end_time + datetime.timedelta(days=1),
            value=6,
        )
        RealmCount.objects.create(
            realm=user.realm,
            property=realm_stat.property,
            end_time=end_time + datetime.timedelta(days=2),
            value=9,
        )
        send_analytics_to_remote_server()
        check_counts(4, 3, 3, 1, 1)

        # Test only having new InstallationCount rows
        InstallationCount.objects.create(
            property=realm_stat.property, end_time=end_time + datetime.timedelta(days=1), value=6
        )
        send_analytics_to_remote_server()
        check_counts(5, 4, 3, 2, 1)

        # Test only having new RealmAuditLog rows
        # Non-synced event
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.REALM_LOGO_CHANGED,
            event_time=end_time,
            extra_data="data",
        )
        send_analytics_to_remote_server()
        check_counts(6, 4, 3, 2, 1)
        # Synced event
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.USER_REACTIVATED,
            event_time=end_time,
            extra_data="data",
        )
        send_analytics_to_remote_server()
        check_counts(7, 5, 3, 2, 2)

        (realm_count_data, installation_count_data, realmauditlog_data) = build_analytics_data(
            RealmCount.objects.all(), InstallationCount.objects.all(), RealmAuditLog.objects.all()
        )
        result = self.uuid_post(
            self.server_uuid,
            "/api/v1/remotes/server/analytics",
            {
                "realm_counts": orjson.dumps(realm_count_data).decode(),
                "installation_counts": orjson.dumps(installation_count_data).decode(),
                "realmauditlog_rows": orjson.dumps(realmauditlog_data).decode(),
            },
            subdomain="",
        )
        self.assert_json_error(result, "Data is out of order.")

        with mock.patch("zilencer.views.validate_incoming_table_data"), self.assertLogs(
            level="WARNING"
        ) as warn_log:
            # We need to wrap a transaction here to avoid the
            # IntegrityError that will be thrown in here from breaking
            # the unittest transaction.
            with transaction.atomic():
                result = self.uuid_post(
                    self.server_uuid,
                    "/api/v1/remotes/server/analytics",
                    {
                        "realm_counts": orjson.dumps(realm_count_data).decode(),
                        "installation_counts": orjson.dumps(installation_count_data).decode(),
                        "realmauditlog_rows": orjson.dumps(realmauditlog_data).decode(),
                    },
                    subdomain="",
                )
            self.assert_json_error(result, "Invalid data.")
            self.assertEqual(
                warn_log.output,
                [
                    "WARNING:root:Invalid data saving zilencer_remoteinstallationcount for server demo.example.com/6cde5f7a-1f7e-4978-9716-49f69ebfc9fe"
                ],
            )

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
        with self.assertLogs(level="WARNING") as m:
            send_analytics_to_remote_server()
        self.assertEqual(m.output, ["WARNING:root:Invalid property invalid count stat"])
        self.assertEqual(RemoteRealmCount.objects.count(), 0)

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
            extra_data="data",
        )
        # Event type not in SYNCED_BILLING_EVENTS -- should not be included
        RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            event_type=RealmAuditLog.REALM_LOGO_CHANGED,
            event_time=self.TIME_ZERO,
            extra_data="data",
        )

        # send_analytics_to_remote_server calls send_to_push_bouncer twice.
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
            send_analytics_to_remote_server()

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_realmauditlog_data_mapping(self) -> None:
        self.add_mock_response()
        user = self.example_user("hamlet")
        log_entry = RealmAuditLog.objects.create(
            realm=user.realm,
            modified_user=user,
            backfilled=True,
            event_type=RealmAuditLog.USER_REACTIVATED,
            event_time=self.TIME_ZERO,
            extra_data="data",
        )
        send_analytics_to_remote_server()
        remote_log_entry = RemoteRealmAuditLog.objects.order_by("id").last()
        assert remote_log_entry is not None
        self.assertEqual(str(remote_log_entry.server.uuid), self.server_uuid)
        self.assertEqual(remote_log_entry.remote_id, log_entry.id)
        self.assertEqual(remote_log_entry.event_time, self.TIME_ZERO)
        self.assertEqual(remote_log_entry.backfilled, True)
        self.assertEqual(remote_log_entry.extra_data, "data")
        self.assertEqual(remote_log_entry.event_type, RealmAuditLog.USER_REACTIVATED)


class PushNotificationTest(BouncerTestCase):
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
    def mock_apns(self) -> Iterator[APNsContext]:
        apns_context = APNsContext(apns=mock.Mock(), loop=asyncio.new_event_loop())
        try:
            with mock.patch("zerver.lib.push_notifications.get_apns_context") as mock_get:
                mock_get.return_value = apns_context
                yield apns_context
        finally:
            apns_context.loop.close()

    def setup_apns_tokens(self) -> None:
        self.tokens = ["aaaa", "bbbb"]
        for token in self.tokens:
            PushDeviceToken.objects.create(
                kind=PushDeviceToken.APNS,
                token=hex_to_b64(token),
                user=self.user_profile,
                ios_app_id=settings.ZULIP_IOS_APP_ID,
            )

        self.remote_tokens = [("cccc", "ffff")]
        for id_token, uuid_token in self.remote_tokens:
            # We want to set up both types of RemotePushDeviceToken here:
            # the legacy one with user_id and the new with user_uuid.
            # This allows tests to work with either, without needing to
            # do their own setup.
            RemotePushDeviceToken.objects.create(
                kind=RemotePushDeviceToken.APNS,
                token=hex_to_b64(id_token),
                user_id=self.user_profile.id,
                server=RemoteZulipServer.objects.get(uuid=self.server_uuid),
            )
            RemotePushDeviceToken.objects.create(
                kind=RemotePushDeviceToken.APNS,
                token=hex_to_b64(uuid_token),
                user_uuid=self.user_profile.uuid,
                server=RemoteZulipServer.objects.get(uuid=self.server_uuid),
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
                server=RemoteZulipServer.objects.get(uuid=self.server_uuid),
            )
            RemotePushDeviceToken.objects.create(
                kind=RemotePushDeviceToken.GCM,
                token=hex_to_b64(uuid_token),
                user_uuid=self.user_profile.uuid,
                server=RemoteZulipServer.objects.get(uuid=self.server_uuid),
            )


class HandlePushNotificationTest(PushNotificationTest):
    DEFAULT_SUBDOMAIN = ""

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
            "trigger": "private_message",
        }
        with mock.patch(
            "zerver.lib.push_notifications.gcm_client"
        ) as mock_gcm, self.mock_apns() as apns_context, self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as pn_logger, self.assertLogs(
            "zilencer.views", level="INFO"
        ) as views_logger:
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
            apns_context.apns.send_notification = mock.AsyncMock()
            apns_context.apns.send_notification.return_value.is_successful = True
            handle_push_notification(self.user_profile.id, missed_message)
            self.assertEqual(
                views_logger.output,
                [
                    "INFO:zilencer.views:"
                    f"Sending mobile push notifications for remote user 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{str(self.user_profile.id)}><uuid:{str(self.user_profile.uuid)}>: "
                    f"{len(gcm_devices)} via FCM devices, {len(apns_devices)} via APNs devices"
                ],
            )
            for _, _, token in apns_devices:
                self.assertIn(
                    "INFO:zerver.lib.push_notifications:"
                    f"APNs: Success sending for user <id:{str(self.user_profile.id)}><uuid:{str(self.user_profile.uuid)}> to device {token}",
                    pn_logger.output,
                )
            for _, _, token in gcm_devices:
                self.assertIn(
                    "INFO:zerver.lib.push_notifications:" f"GCM: Sent {token} as {message.id}",
                    pn_logger.output,
                )

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com")
    @responses.activate
    def test_unregistered_client(self) -> None:
        self.add_mock_response()
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
            "message_id": message.id,
            "trigger": "private_message",
        }
        with mock.patch(
            "zerver.lib.push_notifications.gcm_client"
        ) as mock_gcm, self.mock_apns() as apns_context, self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as pn_logger, self.assertLogs(
            "zilencer.views", level="INFO"
        ) as views_logger:
            apns_devices = [
                (b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS)
            ]
            gcm_devices = [
                (b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.GCM)
            ]
            mock_gcm.json_request.return_value = {"success": {gcm_devices[0][2]: message.id}}
            apns_context.apns.send_notification = mock.AsyncMock()
            apns_context.apns.send_notification.return_value.is_successful = False
            apns_context.apns.send_notification.return_value.description = "Unregistered"
            handle_push_notification(self.user_profile.id, missed_message)
            self.assertEqual(
                views_logger.output,
                [
                    "INFO:zilencer.views:"
                    f"Sending mobile push notifications for remote user 6cde5f7a-1f7e-4978-9716-49f69ebfc9fe:<id:{str(self.user_profile.id)}><uuid:{str(self.user_profile.uuid)}>: "
                    f"{len(gcm_devices)} via FCM devices, {len(apns_devices)} via APNs devices"
                ],
            )
            for _, _, token in apns_devices:
                self.assertIn(
                    "INFO:zerver.lib.push_notifications:"
                    f"APNs: Removing invalid/expired token {token} (Unregistered)",
                    pn_logger.output,
                )
            self.assertEqual(
                RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS).count(), 0
            )

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
            "trigger": "private_message",
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

    @mock.patch("zerver.lib.push_notifications.push_notifications_enabled", return_value=True)
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
            "trigger": "private_message",
        }

        # If the message is unread, we should send push notifications.
        with mock.patch(
            "zerver.lib.push_notifications.send_apple_push_notification"
        ) as mock_send_apple, mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification"
        ) as mock_send_android:
            handle_push_notification(user_profile.id, missed_message)
        mock_send_apple.assert_called_once()
        mock_send_android.assert_called_once()

        # If the message has been read, don't send push notifications.
        usermessage.flags.read = True
        usermessage.save()
        with mock.patch(
            "zerver.lib.push_notifications.send_apple_push_notification"
        ) as mock_send_apple, mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification"
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
            "trigger": "private_message",
        }
        # Now, delete the message the normal way
        do_delete_messages(user_profile.realm, [message])

        # This mock.patch() should be assertNoLogs once that feature
        # is added to Python.
        with mock.patch(
            "zerver.lib.push_notifications.uses_notification_bouncer"
        ) as mock_check, mock.patch("logging.error") as mock_logging_error, mock.patch(
            "zerver.lib.push_notifications.push_notifications_enabled", return_value=True
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
            "trigger": "private_message",
        }
        # Now delete the message forcefully, so it just doesn't exist.
        message.delete()

        # This should log an error
        with mock.patch(
            "zerver.lib.push_notifications.uses_notification_bouncer"
        ) as mock_check, self.assertLogs(level="INFO") as mock_logging_info, mock.patch(
            "zerver.lib.push_notifications.push_notifications_enabled", return_value=True
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
        user_profile = self.example_user("hamlet")
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
            "trigger": "private_message",
        }
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=True), mock.patch(
            "zerver.lib.push_notifications.get_message_payload_apns", return_value={"apns": True}
        ), mock.patch(
            "zerver.lib.push_notifications.get_message_payload_gcm",
            return_value=({"gcm": True}, {}),
        ), mock.patch(
            "zerver.lib.push_notifications.send_notifications_to_bouncer", return_value=(3, 5)
        ) as mock_send, self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as mock_logging_info:
            handle_push_notification(user_profile.id, missed_message)
            mock_send.assert_called_with(
                user_profile.id,
                {"apns": True},
                {"gcm": True},
                {},
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
            "trigger": "private_message",
        }
        with mock.patch(
            "zerver.lib.push_notifications.get_message_payload_apns", return_value={"apns": True}
        ), mock.patch(
            "zerver.lib.push_notifications.get_message_payload_gcm",
            return_value=({"gcm": True}, {}),
        ), mock.patch(
            "zerver.lib.push_notifications.send_apple_push_notification"
        ) as mock_send_apple, mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification"
        ) as mock_send_android, mock.patch(
            "zerver.lib.push_notifications.push_notifications_enabled", return_value=True
        ) as mock_push_notifications:
            handle_push_notification(self.user_profile.id, missed_message)
            user_identity = UserPushIdentityCompat(user_id=self.user_profile.id)
            mock_send_apple.assert_called_with(user_identity, apple_devices, {"apns": True})
            mock_send_android.assert_called_with(user_identity, android_devices, {"gcm": True}, {})
            mock_push_notifications.assert_called_once()

    def test_send_remove_notifications_to_bouncer(self) -> None:
        user_profile = self.example_user("hamlet")
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
                user_profile.id,
                {
                    "badge": 0,
                    "custom": {
                        "zulip": {
                            "server": "testserver",
                            "realm_id": self.sender.realm.id,
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
                    "realm_uri": "http://zulip.testserver",
                    "user_id": self.user_profile.id,
                    "event": "remove",
                    "zulip_message_ids": str(message.id),
                    "zulip_message_id": message.id,
                },
                {"priority": "normal"},
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
            "zerver.lib.push_notifications.push_notifications_enabled", return_value=True
        ) as mock_push_notifications, mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification"
        ) as mock_send_android, mock.patch(
            "zerver.lib.push_notifications.send_apple_push_notification"
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
            "zerver.lib.push_notifications.push_notifications_enabled", return_value=True
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
            "zerver.lib.push_notifications.push_notifications_enabled", return_value=True
        ) as mock_push_notifications, mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification"
        ) as mock_send_android, mock.patch(
            "zerver.lib.push_notifications.send_apple_push_notification"
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
            do_soft_deactivate_users([self.user_profile])
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
            "trigger": "stream_push_notify",
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
            "zerver.lib.push_notifications.send_apple_push_notification"
        ) as mock_send_apple, mock.patch(
            "zerver.lib.push_notifications.send_android_push_notification"
        ) as mock_send_android, mock.patch(
            "zerver.lib.push_notifications.logger.error"
        ) as mock_logger, mock.patch(
            "zerver.lib.push_notifications.push_notifications_enabled", return_value=True
        ) as mock_push_notifications:
            handle_push_notification(self.user_profile.id, missed_message)
            mock_logger.assert_not_called()
            user_identity = UserPushIdentityCompat(user_id=self.user_profile.id)
            mock_send_apple.assert_called_with(user_identity, apple_devices, {"apns": True})
            mock_send_android.assert_called_with(user_identity, android_devices, {"gcm": True}, {})
            mock_push_notifications.assert_called_once()

    @mock.patch("zerver.lib.push_notifications.push_notifications_enabled", return_value=True)
    def test_user_push_soft_reactivate_soft_deactivated_user(
        self, mock_push_notifications: mock.MagicMock
    ) -> None:
        othello = self.example_user("othello")
        cordelia = self.example_user("cordelia")
        large_user_group = create_user_group(
            "large_user_group", [self.user_profile, othello, cordelia], get_realm("zulip")
        )

        # Personal mention in a stream message should soft reactivate the user
        with self.soft_deactivate_and_check_long_term_idle(self.user_profile, expected=False):
            mention = f"@**{self.user_profile.full_name}**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {"message_id": stream_mentioned_message_id, "trigger": "mentioned"},
            )

        # Private message should soft reactivate the user
        with self.soft_deactivate_and_check_long_term_idle(self.user_profile, expected=False):
            # Soft reactivate the user by sending a personal message
            personal_message_id = self.send_personal_message(othello, self.user_profile, "Message")
            handle_push_notification(
                self.user_profile.id,
                {"message_id": personal_message_id, "trigger": "private_message"},
            )

        # Wild card mention should NOT soft reactivate the user
        with self.soft_deactivate_and_check_long_term_idle(self.user_profile, expected=True):
            # Soft reactivate the user by sending a personal message
            mention = "@**all**"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {"message_id": stream_mentioned_message_id, "trigger": "wildcard_mentioned"},
            )

        # Group mention should NOT soft reactivate the user
        with self.soft_deactivate_and_check_long_term_idle(self.user_profile, expected=True):
            # Soft reactivate the user by sending a personal message
            mention = "@*large_user_group*"
            stream_mentioned_message_id = self.send_stream_message(othello, "Denmark", mention)
            handle_push_notification(
                self.user_profile.id,
                {
                    "message_id": stream_mentioned_message_id,
                    "trigger": "mentioned",
                    "mentioned_user_group_id": large_user_group.id,
                },
            )

    @mock.patch("zerver.lib.push_notifications.logger.info")
    @mock.patch("zerver.lib.push_notifications.push_notifications_enabled", return_value=True)
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
            "trigger": "private_message",
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
        with self.mock_apns() as apns_context, self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as logger:
            apns_context.apns.send_notification = mock.AsyncMock()
            apns_context.apns.send_notification.return_value.is_successful = True
            self.send()
            for device in self.devices():
                self.assertIn(
                    f"INFO:zerver.lib.push_notifications:APNs: Success sending for user <id:{self.user_profile.id}> to device {device.token}",
                    logger.output,
                )

    def test_http_retry_eventually_fails(self) -> None:
        self.setup_apns_tokens()
        with self.mock_apns() as apns_context, self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as logger:
            apns_context.apns.send_notification = mock.AsyncMock(
                side_effect=aioapns.exceptions.ConnectionError()
            )
            self.send(devices=self.devices()[0:1])
            self.assertIn(
                f"ERROR:zerver.lib.push_notifications:APNs: ConnectionError sending for user <id:{self.user_profile.id}> to device {self.devices()[0].token}; check certificate expiration",
                logger.output,
            )

    def test_internal_server_error(self) -> None:
        self.setup_apns_tokens()
        with self.mock_apns() as apns_context, self.assertLogs(
            "zerver.lib.push_notifications", level="INFO"
        ) as logger:
            apns_context.apns.send_notification = mock.AsyncMock()
            apns_context.apns.send_notification.return_value.is_successful = False
            apns_context.apns.send_notification.return_value.description = "InternalServerError"
            self.send(devices=self.devices()[0:1])
            self.assertIn(
                f"WARNING:zerver.lib.push_notifications:APNs: Failed to send for user <id:{self.user_profile.id}> to device {self.devices()[0].token}: InternalServerError",
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

    @mock.patch("zerver.lib.push_notifications.push_notifications_enabled", return_value=True)
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
            user_profile, message, NotificationTriggers.PRIVATE_MESSAGE
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
                    "realm_uri": self.sender.realm.uri,
                    "user_id": user_profile.id,
                },
            },
        }
        self.assertDictEqual(payload, expected)

    @mock.patch("zerver.lib.push_notifications.push_notifications_enabled", return_value=True)
    def test_get_message_payload_apns_huddle_message(
        self, mock_push_notifications: mock.MagicMock
    ) -> None:
        user_profile = self.example_user("othello")
        message_id = self.send_huddle_message(
            self.sender, [self.example_user("othello"), self.example_user("cordelia")]
        )
        message = Message.objects.get(id=message_id)
        payload = get_message_payload_apns(
            user_profile, message, NotificationTriggers.PRIVATE_MESSAGE
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
                    "realm_uri": self.sender.realm.uri,
                    "user_id": user_profile.id,
                },
            },
        }
        self.assertDictEqual(payload, expected)
        mock_push_notifications.assert_called()

    def test_get_message_payload_apns_stream_message(self) -> None:
        stream = Stream.objects.filter(name="Verona").get()
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)
        payload = get_message_payload_apns(self.sender, message, NotificationTriggers.STREAM_PUSH)
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
                    "stream": get_display_recipient(message.recipient),
                    "stream_id": stream.id,
                    "topic": message.topic_name(),
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_uri": self.sender.realm.uri,
                    "user_id": self.sender.id,
                },
            },
        }
        self.assertDictEqual(payload, expected)

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
                    "stream": get_display_recipient(message.recipient),
                    "stream_id": stream.id,
                    "topic": message.topic_name(),
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_uri": self.sender.realm.uri,
                    "user_id": user_profile.id,
                },
            },
        }
        self.assertDictEqual(payload, expected)

    def test_get_message_payload_apns_user_group_mention(self) -> None:
        user_profile = self.example_user("othello")
        user_group = create_user_group("test_user_group", [user_profile], get_realm("zulip"))
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
                    "stream": get_display_recipient(message.recipient),
                    "stream_id": stream.id,
                    "topic": message.topic_name(),
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_uri": self.sender.realm.uri,
                    "user_id": user_profile.id,
                    "mentioned_user_group_id": user_group.id,
                    "mentioned_user_group_name": user_group.name,
                }
            },
        }
        self.assertDictEqual(payload, expected)

    def test_get_message_payload_apns_stream_wildcard_mention(self) -> None:
        user_profile = self.example_user("othello")
        stream = Stream.objects.filter(name="Verona").get()
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)
        payload = get_message_payload_apns(
            user_profile, message, NotificationTriggers.WILDCARD_MENTION
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
                    "stream": get_display_recipient(message.recipient),
                    "stream_id": stream.id,
                    "topic": message.topic_name(),
                    "server": settings.EXTERNAL_HOST,
                    "realm_id": self.sender.realm.id,
                    "realm_uri": self.sender.realm.uri,
                    "user_id": user_profile.id,
                },
            },
        }
        self.assertDictEqual(payload, expected)

    @override_settings(PUSH_NOTIFICATION_REDACT_CONTENT=True)
    def test_get_message_payload_apns_redacted_content(self) -> None:
        user_profile = self.example_user("othello")
        message_id = self.send_huddle_message(
            self.sender, [self.example_user("othello"), self.example_user("cordelia")]
        )
        message = Message.objects.get(id=message_id)
        payload = get_message_payload_apns(
            user_profile, message, NotificationTriggers.PRIVATE_MESSAGE
        )
        expected = {
            "alert": {
                "title": "Cordelia, Lear's daughter, King Hamlet, Othello, the Moor of Venice",
                "subtitle": "King Hamlet:",
                "body": "*This organization has disabled including message content in mobile push notifications*",
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
                    "realm_uri": self.sender.realm.uri,
                    "user_id": user_profile.id,
                },
            },
        }
        self.assertDictEqual(payload, expected)


class TestGetGCMPayload(PushNotificationTest):
    def _test_get_message_payload_gcm_mentions(
        self,
        trigger: str,
        alert: str,
        *,
        mentioned_user_group_id: Optional[int] = None,
        mentioned_user_group_name: Optional[str] = None,
    ) -> None:
        stream = Stream.objects.filter(name="Verona").get()
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)
        message.content = "a" * 210
        message.rendered_content = "a" * 210
        message.save()

        hamlet = self.example_user("hamlet")
        payload, gcm_options = get_message_payload_gcm(
            hamlet, message, trigger, mentioned_user_group_id, mentioned_user_group_name
        )
        expected_payload = {
            "user_id": hamlet.id,
            "event": "message",
            "alert": alert,
            "zulip_message_id": message.id,
            "time": datetime_to_timestamp(message.date_sent),
            "content": "a" * 200 + "…",
            "content_truncated": True,
            "server": settings.EXTERNAL_HOST,
            "realm_id": hamlet.realm.id,
            "realm_uri": hamlet.realm.uri,
            "sender_id": hamlet.id,
            "sender_email": hamlet.email,
            "sender_full_name": "King Hamlet",
            "sender_avatar_url": absolute_avatar_url(message.sender),
            "recipient_type": "stream",
            "stream": get_display_recipient(message.recipient),
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

    def test_get_message_payload_gcm_personal_mention(self) -> None:
        self._test_get_message_payload_gcm_mentions(
            "mentioned", "King Hamlet mentioned you in #Verona"
        )

    def test_get_message_payload_gcm_user_group_mention(self) -> None:
        # Note that the @mobile_team user group doesn't actually
        # exist; this test is just verifying the formatting logic.
        self._test_get_message_payload_gcm_mentions(
            "mentioned",
            "King Hamlet mentioned @mobile_team in #Verona",
            mentioned_user_group_id=3,
            mentioned_user_group_name="mobile_team",
        )

    def test_get_message_payload_gcm_wildcard_mention(self) -> None:
        self._test_get_message_payload_gcm_mentions(
            "wildcard_mentioned", "King Hamlet mentioned everyone in #Verona"
        )

    def test_get_message_payload_gcm_private_message(self) -> None:
        message = self.get_message(
            Recipient.PERSONAL,
            type_id=self.personal_recipient_user.id,
            realm_id=self.personal_recipient_user.realm_id,
        )
        hamlet = self.example_user("hamlet")
        payload, gcm_options = get_message_payload_gcm(
            hamlet, message, NotificationTriggers.PRIVATE_MESSAGE
        )
        self.assertDictEqual(
            payload,
            {
                "user_id": hamlet.id,
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
            },
        )
        self.assertDictEqual(
            gcm_options,
            {
                "priority": "high",
            },
        )

    def test_get_message_payload_gcm_stream_notifications(self) -> None:
        stream = Stream.objects.get(name="Denmark")
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)
        hamlet = self.example_user("hamlet")
        payload, gcm_options = get_message_payload_gcm(
            hamlet, message, NotificationTriggers.STREAM_PUSH
        )
        self.assertDictEqual(
            payload,
            {
                "user_id": hamlet.id,
                "event": "message",
                "alert": "New stream message from King Hamlet in #Denmark",
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

    @override_settings(PUSH_NOTIFICATION_REDACT_CONTENT=True)
    def test_get_message_payload_gcm_redacted_content(self) -> None:
        stream = Stream.objects.get(name="Denmark")
        message = self.get_message(Recipient.STREAM, stream.id, stream.realm_id)
        hamlet = self.example_user("hamlet")
        payload, gcm_options = get_message_payload_gcm(
            hamlet, message, NotificationTriggers.STREAM_PUSH
        )
        self.assertDictEqual(
            payload,
            {
                "user_id": hamlet.id,
                "event": "message",
                "alert": "New stream message from King Hamlet in #Denmark",
                "zulip_message_id": message.id,
                "time": datetime_to_timestamp(message.date_sent),
                "content": "*This organization has disabled including message content in mobile push notifications*",
                "content_truncated": False,
                "server": settings.EXTERNAL_HOST,
                "realm_id": hamlet.realm.id,
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


class TestSendNotificationsToBouncer(ZulipTestCase):
    @mock.patch("zerver.lib.remote_server.send_to_push_bouncer")
    def test_send_notifications_to_bouncer(self, mock_send: mock.MagicMock) -> None:
        mock_send.return_value = {"total_android_devices": 1, "total_apple_devices": 3}
        total_android_devices, total_apple_devices = send_notifications_to_bouncer(
            1, {"apns": True}, {"gcm": True}, {}
        )
        post_data = {
            "user_uuid": get_user_profile_by_id(1).uuid,
            "user_id": 1,
            "apns_payload": {"apns": True},
            "gcm_payload": {"gcm": True},
            "gcm_options": {},
        }
        mock_send.assert_called_with(
            "POST",
            "push/notify",
            orjson.dumps(post_data),
            extra_headers={"Content-type": "application/json"},
        )
        self.assertEqual(total_android_devices, 1)
        self.assertEqual(total_apple_devices, 3)


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
            with self.assertRaises(PushNotificationBouncerRetryLaterError):
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

        endpoints = [
            ("/json/users/me/apns_device_token", "apple-tokenaz"),
            ("/json/users/me/android_gcm_reg_id", "android-token"),
        ]

        # Test error handling
        for endpoint, label in endpoints:
            # Try adding/removing tokens that are too big...
            broken_token = "a" * 5000  # too big
            result = self.client_post(endpoint, {"token": broken_token})
            self.assert_json_error(result, "Empty or invalid length token")

            if label == "apple-tokenaz":
                result = self.client_post(endpoint, {"token": "xyz has non-hex characters"})
                self.assert_json_error(result, "Invalid APNS token")

            result = self.client_delete(endpoint, {"token": broken_token})
            self.assert_json_error(result, "Empty or invalid length token")

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

        no_bouncer_requests = [
            ("/json/users/me/apns_device_token", "apple-tokenaa"),
            ("/json/users/me/android_gcm_reg_id", "android-token-1"),
        ]

        bouncer_requests = [
            ("/json/users/me/apns_device_token", "apple-tokenbb"),
            ("/json/users/me/android_gcm_reg_id", "android-token-2"),
        ]

        # Add tokens without using push notification bouncer.
        for endpoint, token in no_bouncer_requests:
            # Test that we can push twice.
            result = self.client_post(endpoint, {"token": token})
            self.assert_json_success(result)

            result = self.client_post(endpoint, {"token": token})
            self.assert_json_success(result)

            tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
            self.assert_length(tokens, 1)
            self.assertEqual(tokens[0].token, token)

        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com"):
            self.add_mock_response()
            # Enable push notification bouncer and add tokens.
            for endpoint, token in bouncer_requests:
                # Test that we can push twice.
                result = self.client_post(endpoint, {"token": token})
                self.assert_json_success(result)

                result = self.client_post(endpoint, {"token": token})
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
        self.assertEqual(remote_token_values, ["apple-tokenbb", "android-token-2"])

        # Test removing tokens without using push notification bouncer.
        for endpoint, token in no_bouncer_requests:
            result = self.client_delete(endpoint, {"token": token})
            self.assert_json_success(result)
            tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
            self.assert_length(tokens, 0)

        # Use push notification bouncer and test removing device tokens.
        # Tokens will be removed both locally and remotely.
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL="https://push.zulip.org.example.com"):
            for endpoint, token in bouncer_requests:
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
    def test_deactivate_remote_server(self) -> None:
        zulip_org_id = str(uuid.uuid4())
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
            contact_email="server-admin@example.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)
        server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
        self.assertEqual(server.hostname, "example.com")
        self.assertEqual(server.contact_email, "server-admin@example.com")

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

    def test_push_signup_invalid_host(self) -> None:
        zulip_org_id = str(uuid.uuid4())
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="invalid-host",
            contact_email="server-admin@example.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(result, "invalid-host is not a valid hostname")

    def test_push_signup_invalid_email(self) -> None:
        zulip_org_id = str(uuid.uuid4())
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
            contact_email="server-admin",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(result, "Enter a valid email address.")

    def test_push_signup_invalid_zulip_org_id(self) -> None:
        zulip_org_id = "x" * RemoteZulipServer.UUID_LENGTH
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
            contact_email="server-admin@example.com",
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

    def test_push_signup_success(self) -> None:
        zulip_org_id = str(uuid.uuid4())
        zulip_org_key = get_random_string(64)
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
            contact_email="server-admin@example.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)
        server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
        self.assertEqual(server.hostname, "example.com")
        self.assertEqual(server.contact_email, "server-admin@example.com")

        # Update our hostname
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="zulip.example.com",
            contact_email="server-admin@example.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)
        server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
        self.assertEqual(server.hostname, "zulip.example.com")
        self.assertEqual(server.contact_email, "server-admin@example.com")

        # Now test rotating our key
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="example.com",
            contact_email="server-admin@example.com",
            new_org_key=get_random_string(64),
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)
        server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
        self.assertEqual(server.hostname, "example.com")
        self.assertEqual(server.contact_email, "server-admin@example.com")
        zulip_org_key = request["new_org_key"]
        self.assertEqual(server.api_key, zulip_org_key)

        # Update our hostname
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=zulip_org_key,
            hostname="zulip.example.com",
            contact_email="new-server-admin@example.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_success(result)
        server = RemoteZulipServer.objects.get(uuid=zulip_org_id)
        self.assertEqual(server.hostname, "zulip.example.com")
        self.assertEqual(server.contact_email, "new-server-admin@example.com")

        # Now test trying to double-create with a new random key fails
        request = dict(
            zulip_org_id=zulip_org_id,
            zulip_org_key=get_random_string(64),
            hostname="example.com",
            contact_email="server-admin@example.com",
        )
        result = self.client_post("/api/v1/remotes/server/register", request)
        self.assert_json_error(
            result, f"Zulip server auth failure: key does not match role {zulip_org_id}"
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
