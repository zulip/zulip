import base64
import datetime
import itertools
import os
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Iterator, List, Optional
from unittest import mock, skipUnless
from unittest.mock import call

import orjson
import requests
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.http import HttpResponse
from django.test import override_settings
from django.utils.crypto import get_random_string
from django.utils.timezone import now

from analytics.lib.counts import CountStat, LoggingCountStat
from analytics.models import InstallationCount, RealmCount
from zerver.lib.actions import (
    do_delete_messages,
    do_mark_stream_messages_as_read,
    do_regenerate_api_key,
    do_update_message_flags,
)
from zerver.lib.push_notifications import (
    DeviceToken,
    absolute_avatar_url,
    b64_to_hex,
    datetime_to_timestamp,
    get_apns_badge_count,
    get_apns_badge_count_future,
    get_apns_client,
    get_display_recipient,
    get_message_payload_apns,
    get_message_payload_gcm,
    get_mobile_push_content,
    handle_push_notification,
    handle_remove_push_notification,
    hex_to_b64,
    modernize_apns_payload,
    num_push_devices_for_user,
    parse_gcm_options,
    send_android_push_notification_to_user,
    send_apple_push_notification,
    send_notifications_to_bouncer,
    send_to_push_bouncer,
)
from zerver.lib.remote_server import (
    PushNotificationBouncerException,
    PushNotificationBouncerRetryLaterError,
    build_analytics_data,
    send_analytics_to_remote_server,
)
from zerver.lib.request import JsonableError
from zerver.lib.soft_deactivation import do_soft_deactivate_users
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import mock_queue_publish
from zerver.models import (
    Message,
    PushDeviceToken,
    RealmAuditLog,
    Recipient,
    Stream,
    Subscription,
    UserMessage,
    get_client,
    get_realm,
    get_stream,
    receives_offline_email_notifications,
    receives_offline_push_notifications,
    receives_online_notifications,
    receives_stream_notifications,
)

if settings.ZILENCER_ENABLED:
    from zilencer.models import (
        RemoteInstallationCount,
        RemotePushDeviceToken,
        RemoteRealmAuditLog,
        RemoteRealmCount,
        RemoteZulipServer,
    )

ZERVER_DIR = os.path.dirname(os.path.dirname(__file__))

@skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
class BouncerTestCase(ZulipTestCase):
    def setUp(self) -> None:
        self.server_uuid = "1234-abcd"
        server = RemoteZulipServer(uuid=self.server_uuid,
                                   api_key="magic_secret_api_key",
                                   hostname="demo.example.com",
                                   last_updated=now())
        server.save()
        super().setUp()

    def tearDown(self) -> None:
        RemoteZulipServer.objects.filter(uuid=self.server_uuid).delete()
        super().tearDown()

    def bounce_request(self, *args: Any, **kwargs: Any) -> HttpResponse:
        """This method is used to carry out the push notification bouncer
        requests using the Django test browser, rather than python-requests.
        """
        # args[0] is method, args[1] is URL.
        local_url = args[1].replace(settings.PUSH_NOTIFICATION_BOUNCER_URL, "")
        if args[0] == "POST":
            result = self.uuid_post(
                self.server_uuid,
                local_url,
                kwargs['data'],
                subdomain='')

        elif args[0] == "GET":
            result = self.uuid_get(
                self.server_uuid,
                local_url,
                kwargs['data'],
                subdomain='')
        else:
            raise AssertionError("Unsupported method for bounce_request")
        return result

    def get_generic_payload(self, method: str='register') -> Dict[str, Any]:
        user_id = 10
        token = "111222"
        token_kind = PushDeviceToken.GCM

        return {'user_id': user_id,
                'token': token,
                'token_kind': token_kind}

class PushBouncerNotificationTest(BouncerTestCase):
    DEFAULT_SUBDOMAIN = ""

    def test_unregister_remote_push_user_params(self) -> None:
        token = "111222"
        token_kind = PushDeviceToken.GCM

        endpoint = '/api/v1/remotes/push/unregister'
        result = self.uuid_post(self.server_uuid, endpoint, {'token_kind': token_kind})
        self.assert_json_error(result, "Missing 'token' argument")
        result = self.uuid_post(self.server_uuid, endpoint, {'token': token})
        self.assert_json_error(result, "Missing 'token_kind' argument")

        # We need the root ('') subdomain to be in use for this next
        # test, since the push bouncer API is only available there:
        hamlet = self.example_user('hamlet')
        realm = get_realm("zulip")
        realm.string_id = ""
        realm.save()

        result = self.api_post(
            hamlet,
            endpoint,
            dict(user_id=15, token=token, token_kind=token_kind),
            subdomain='',
        )
        self.assert_json_error(result, "Must validate with valid Zulip server API key")

    def test_register_remote_push_user_paramas(self) -> None:
        token = "111222"
        user_id = 11
        token_kind = PushDeviceToken.GCM

        endpoint = '/api/v1/remotes/push/register'

        result = self.uuid_post(self.server_uuid, endpoint, {'user_id': user_id, 'token_kind': token_kind})
        self.assert_json_error(result, "Missing 'token' argument")
        result = self.uuid_post(self.server_uuid, endpoint, {'user_id': user_id, 'token': token})
        self.assert_json_error(result, "Missing 'token_kind' argument")
        result = self.uuid_post(self.server_uuid, endpoint, {'token': token, 'token_kind': token_kind})
        self.assert_json_error(result, "Missing 'user_id' argument")
        result = self.uuid_post(self.server_uuid, endpoint, {'user_id': user_id, 'token': token, 'token_kind': 17})
        self.assert_json_error(result, "Invalid token type")

        hamlet = self.example_user('hamlet')

        with self.assertLogs(level='WARNING') as warn_log:
            result = self.api_post(
                hamlet,
                endpoint,
                dict(user_id=user_id, token_kin=token_kind, token=token),
            )
        self.assertEqual(warn_log.output, [
            'WARNING:root:User hamlet@zulip.com (zulip) attempted to access API on wrong subdomain ()'
        ])
        self.assert_json_error(result, "Account is not associated with this subdomain",
                               status_code=401)

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
            subdomain="zulip")
        self.assert_json_error(result, "Invalid subdomain for push notifications bouncer",
                               status_code=401)

        # We do a bit of hackery here to the API_KEYS cache just to
        # make the code simple for sending an incorrect API key.
        self.API_KEYS[self.server_uuid] = 'invalid'
        result = self.uuid_post(
            self.server_uuid,
            endpoint,
            dict(user_id=user_id, token_kind=token_kind, token=token))
        self.assert_json_error(result, "Zulip server auth failure: key does not match role 1234-abcd",
                               status_code=401)

        del self.API_KEYS[self.server_uuid]

        credentials = "{}:{}".format("5678-efgh", 'invalid')
        api_auth = 'Basic ' + base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        result = self.client_post(endpoint, {'user_id': user_id,
                                             'token_kind': token_kind,
                                             'token': token},
                                  HTTP_AUTHORIZATION = api_auth)
        self.assert_json_error(result, "Zulip server auth failure: 5678-efgh is not registered",
                               status_code=401)

    def test_remote_push_user_endpoints(self) -> None:
        endpoints = [
            ('/api/v1/remotes/push/register', 'register'),
            ('/api/v1/remotes/push/unregister', 'unregister'),
        ]

        for endpoint, method in endpoints:
            payload = self.get_generic_payload(method)

            # Verify correct results are success
            result = self.uuid_post(self.server_uuid, endpoint, payload)
            self.assert_json_success(result)

            remote_tokens = RemotePushDeviceToken.objects.filter(token=payload['token'])
            token_count = 1 if method == 'register' else 0
            self.assertEqual(len(remote_tokens), token_count)

            # Try adding/removing tokens that are too big...
            broken_token = "x" * 5000  # too big
            payload['token'] = broken_token
            result = self.uuid_post(self.server_uuid, endpoint, payload)
            self.assert_json_error(result, 'Empty or invalid length token')

    def test_remote_push_unregister_all(self) -> None:
        payload = self.get_generic_payload('register')

        # Verify correct results are success
        result = self.uuid_post(self.server_uuid,
                                '/api/v1/remotes/push/register', payload)
        self.assert_json_success(result)

        remote_tokens = RemotePushDeviceToken.objects.filter(token=payload['token'])
        self.assertEqual(len(remote_tokens), 1)
        result = self.uuid_post(self.server_uuid,
                                '/api/v1/remotes/push/unregister/all',
                                dict(user_id=10))
        self.assert_json_success(result)

        remote_tokens = RemotePushDeviceToken.objects.filter(token=payload['token'])
        self.assertEqual(len(remote_tokens), 0)

    def test_invalid_apns_token(self) -> None:
        endpoints = [
            ('/api/v1/remotes/push/register', 'apple-token'),
        ]

        for endpoint, method in endpoints:
            payload = {
                'user_id': 10,
                'token': 'xyz uses non-hex characters',
                'token_kind': PushDeviceToken.APNS,
            }
            result = self.uuid_post(self.server_uuid, endpoint, payload)
            self.assert_json_error(result, 'Invalid APNS token')

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL='https://push.zulip.org.example.com')
    @mock.patch('zerver.lib.remote_server.requests.request')
    def test_push_bouncer_api(self, mock_request: Any) -> None:
        """This is a variant of the below test_push_api, but using the full
        push notification bouncer flow
        """
        mock_request.side_effect = self.bounce_request
        user = self.example_user('cordelia')
        self.login_user(user)
        server = RemoteZulipServer.objects.get(uuid=self.server_uuid)

        endpoints = [
            ('/json/users/me/apns_device_token', 'apple-tokenaz', RemotePushDeviceToken.APNS),
            ('/json/users/me/android_gcm_reg_id', 'android-token', RemotePushDeviceToken.GCM),
        ]

        # Test error handling
        for endpoint, token, kind in endpoints:
            # Try adding/removing tokens that are too big...
            broken_token = "a" * 5000  # too big
            result = self.client_post(endpoint, {'token': broken_token,
                                                 'token_kind': kind},
                                      subdomain="zulip")
            self.assert_json_error(result, 'Empty or invalid length token')

            result = self.client_delete(endpoint, {'token': broken_token,
                                                   'token_kind': kind},
                                        subdomain="zulip")
            self.assert_json_error(result, 'Empty or invalid length token')

            # Try to remove a non-existent token...
            result = self.client_delete(endpoint, {'token': 'abcd1234',
                                                   'token_kind': kind},
                                        subdomain="zulip")
            self.assert_json_error(result, 'Token does not exist')

            with mock.patch('zerver.lib.remote_server.requests.request',
                            side_effect=requests.ConnectionError), self.assertLogs(level="ERROR") as error_log:
                result = self.client_post(endpoint, {'token': token},
                                          subdomain="zulip")
                self.assert_json_error(
                    result, "ConnectionError while trying to connect to push notification bouncer", 502)
                self.assertEqual(error_log.output, [
                    f'ERROR:django.request:Bad Gateway: {endpoint}',
                ])

            with mock.patch('zerver.lib.remote_server.requests.request',
                            return_value=Result(status=500)), self.assertLogs(level="WARNING") as warn_log:
                result = self.client_post(endpoint, {'token': token},
                                          subdomain="zulip")
                self.assert_json_error(result, "Received 500 from push notification bouncer", 502)
                self.assertEqual(warn_log.output, [
                    'WARNING:root:Received 500 from push notification bouncer',
                    f'ERROR:django.request:Bad Gateway: {endpoint}',
                ])

        # Add tokens
        for endpoint, token, kind in endpoints:
            # Test that we can push twice
            result = self.client_post(endpoint, {'token': token},
                                      subdomain="zulip")
            self.assert_json_success(result)

            result = self.client_post(endpoint, {'token': token},
                                      subdomain="zulip")
            self.assert_json_success(result)

            tokens = list(RemotePushDeviceToken.objects.filter(user_id=user.id, token=token,
                                                               server=server))
            self.assertEqual(len(tokens), 1)
            self.assertEqual(tokens[0].token, token)

        # User should have tokens for both devices now.
        tokens = list(RemotePushDeviceToken.objects.filter(user_id=user.id,
                                                           server=server))
        self.assertEqual(len(tokens), 2)

        # Remove tokens
        for endpoint, token, kind in endpoints:
            result = self.client_delete(endpoint, {'token': token,
                                                   'token_kind': kind},
                                        subdomain="zulip")
            self.assert_json_success(result)
            tokens = list(RemotePushDeviceToken.objects.filter(user_id=user.id, token=token,
                                                               server=server))
            self.assertEqual(len(tokens), 0)

        # Re-add copies of those tokens
        for endpoint, token, kind in endpoints:
            result = self.client_post(endpoint, {'token': token},
                                      subdomain="zulip")
            self.assert_json_success(result)
        tokens = list(RemotePushDeviceToken.objects.filter(user_id=user.id,
                                                           server=server))
        self.assertEqual(len(tokens), 2)

        # Now we want to remove them using the bouncer after an API key change.
        # First we test error handling in case of issues with the bouncer:
        with mock.patch('zerver.worker.queue_processors.clear_push_device_tokens',
                        side_effect=PushNotificationBouncerRetryLaterError("test")), \
                mock.patch('zerver.worker.queue_processors.retry_event') as mock_retry:
            do_regenerate_api_key(user, user)
            mock_retry.assert_called()

            # We didn't manage to communicate with the bouncer, to the tokens are still there:
            tokens = list(RemotePushDeviceToken.objects.filter(user_id=user.id,
                                                               server=server))
            self.assertEqual(len(tokens), 2)

        # Now we successfully remove them:
        do_regenerate_api_key(user, user)
        tokens = list(RemotePushDeviceToken.objects.filter(user_id=user.id,
                                                           server=server))
        self.assertEqual(len(tokens), 0)

class AnalyticsBouncerTest(BouncerTestCase):
    TIME_ZERO = datetime.datetime(1988, 3, 14, tzinfo=datetime.timezone.utc)

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL='https://push.zulip.org.example.com')
    @mock.patch('zerver.lib.remote_server.requests.request')
    def test_analytics_api(self, mock_request: Any) -> None:
        """This is a variant of the below test_push_api, but using the full
        push notification bouncer flow
        """
        mock_request.side_effect = self.bounce_request
        user = self.example_user('hamlet')
        end_time = self.TIME_ZERO

        with mock.patch('zerver.lib.remote_server.requests.request',
                        side_effect=requests.ConnectionError), \
                mock.patch('zerver.lib.remote_server.logging.warning') as mock_warning:
            send_analytics_to_remote_server()
            mock_warning.assert_called_once_with(
                "ConnectionError while trying to connect to push notification bouncer")

        # Send any existing data over, so that we can start the test with a "clean" slate
        audit_log_max_id = RealmAuditLog.objects.all().order_by('id').last().id
        send_analytics_to_remote_server()
        self.assertEqual(mock_request.call_count, 2)
        remote_audit_log_count = RemoteRealmAuditLog.objects.count()
        self.assertEqual(RemoteRealmCount.objects.count(), 0)
        self.assertEqual(RemoteInstallationCount.objects.count(), 0)

        def check_counts(mock_request_call_count: int, remote_realm_count: int,
                         remote_installation_count: int, remote_realm_audit_log: int) -> None:
            self.assertEqual(mock_request.call_count, mock_request_call_count)
            self.assertEqual(RemoteRealmCount.objects.count(), remote_realm_count)
            self.assertEqual(RemoteInstallationCount.objects.count(), remote_installation_count)
            self.assertEqual(RemoteRealmAuditLog.objects.count(),
                             remote_audit_log_count + remote_realm_audit_log)

        # Create some rows we'll send to remote server
        realm_stat = LoggingCountStat('invites_sent::day', RealmCount, CountStat.DAY)
        RealmCount.objects.create(
            realm=user.realm, property=realm_stat.property, end_time=end_time, value=5)
        InstallationCount.objects.create(
            property=realm_stat.property, end_time=end_time, value=5,
            # We set a subgroup here to work around:
            # https://github.com/zulip/zulip/issues/12362
            subgroup="test_subgroup")
        # Event type in SYNCED_BILLING_EVENTS -- should be included
        RealmAuditLog.objects.create(
            realm=user.realm, modified_user=user, event_type=RealmAuditLog.USER_CREATED,
            event_time=end_time, extra_data='data')
        # Event type not in SYNCED_BILLING_EVENTS -- should not be included
        RealmAuditLog.objects.create(
            realm=user.realm, modified_user=user, event_type=RealmAuditLog.REALM_LOGO_CHANGED,
            event_time=end_time, extra_data='data')
        self.assertEqual(RealmCount.objects.count(), 1)
        self.assertEqual(InstallationCount.objects.count(), 1)
        self.assertEqual(RealmAuditLog.objects.filter(id__gt=audit_log_max_id).count(), 2)

        send_analytics_to_remote_server()
        check_counts(4, 1, 1, 1)

        # Test having no new rows
        send_analytics_to_remote_server()
        check_counts(5, 1, 1, 1)

        # Test only having new RealmCount rows
        RealmCount.objects.create(
            realm=user.realm, property=realm_stat.property, end_time=end_time + datetime.timedelta(days=1), value=6)
        RealmCount.objects.create(
            realm=user.realm, property=realm_stat.property, end_time=end_time + datetime.timedelta(days=2), value=9)
        send_analytics_to_remote_server()
        check_counts(7, 3, 1, 1)

        # Test only having new InstallationCount rows
        InstallationCount.objects.create(
            property=realm_stat.property, end_time=end_time + datetime.timedelta(days=1), value=6)
        send_analytics_to_remote_server()
        check_counts(9, 3, 2, 1)

        # Test only having new RealmAuditLog rows
        # Non-synced event
        RealmAuditLog.objects.create(
            realm=user.realm, modified_user=user, event_type=RealmAuditLog.REALM_LOGO_CHANGED,
            event_time=end_time, extra_data='data')
        send_analytics_to_remote_server()
        check_counts(10, 3, 2, 1)
        # Synced event
        RealmAuditLog.objects.create(
            realm=user.realm, modified_user=user, event_type=RealmAuditLog.USER_REACTIVATED,
            event_time=end_time, extra_data='data')
        send_analytics_to_remote_server()
        check_counts(12, 3, 2, 2)

        (realm_count_data,
         installation_count_data,
         realmauditlog_data) = build_analytics_data(RealmCount.objects.all(),
                                                    InstallationCount.objects.all(),
                                                    RealmAuditLog.objects.all())
        result = self.uuid_post(
            self.server_uuid,
            '/api/v1/remotes/server/analytics',
            {'realm_counts': orjson.dumps(realm_count_data).decode(),
             'installation_counts': orjson.dumps(installation_count_data).decode(),
             'realmauditlog_rows': orjson.dumps(realmauditlog_data).decode()},
            subdomain="")
        self.assert_json_error(result, "Data is out of order.")

        with mock.patch("zilencer.views.validate_incoming_table_data"), self.assertLogs(level='WARNING') as warn_log:
            # We need to wrap a transaction here to avoid the
            # IntegrityError that will be thrown in here from breaking
            # the unittest transaction.
            with transaction.atomic():
                result = self.uuid_post(
                    self.server_uuid,
                    '/api/v1/remotes/server/analytics',
                    {'realm_counts': orjson.dumps(realm_count_data).decode(),
                     'installation_counts': orjson.dumps(installation_count_data).decode(),
                     'realmauditlog_rows': orjson.dumps(realmauditlog_data).decode()},
                    subdomain="")
            self.assert_json_error(result, "Invalid data.")
            self.assertEqual(warn_log.output, [
                'WARNING:root:Invalid data saving zilencer_remoteinstallationcount for server demo.example.com/1234-abcd'
            ])

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL='https://push.zulip.org.example.com')
    @mock.patch('zerver.lib.remote_server.requests.request')
    def test_analytics_api_invalid(self, mock_request: Any) -> None:
        """This is a variant of the below test_push_api, but using the full
        push notification bouncer flow
        """
        mock_request.side_effect = self.bounce_request
        user = self.example_user('hamlet')
        end_time = self.TIME_ZERO

        realm_stat = LoggingCountStat('invalid count stat', RealmCount, CountStat.DAY)
        RealmCount.objects.create(
            realm=user.realm, property=realm_stat.property, end_time=end_time, value=5)

        self.assertEqual(RealmCount.objects.count(), 1)

        self.assertEqual(RemoteRealmCount.objects.count(), 0)
        with self.assertLogs(level="WARNING") as m:
            send_analytics_to_remote_server()
        self.assertEqual(m.output, ["WARNING:root:Invalid property invalid count stat"])
        self.assertEqual(RemoteRealmCount.objects.count(), 0)

    # Servers on Zulip 2.0.6 and earlier only send realm_counts and installation_counts data,
    # and don't send realmauditlog_rows. Make sure that continues to work.
    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL='https://push.zulip.org.example.com')
    @mock.patch('zerver.lib.remote_server.requests.request')
    def test_old_two_table_format(self, mock_request: Any) -> None:
        mock_request.side_effect = self.bounce_request
        # Send fixture generated with Zulip 2.0 code
        send_to_push_bouncer('POST', 'server/analytics', {
            'realm_counts': '[{"id":1,"property":"invites_sent::day","subgroup":null,"end_time":574300800.0,"value":5,"realm":2}]',
            'installation_counts': '[]',
            'version': '"2.0.6+git"'})
        self.assertEqual(mock_request.call_count, 1)
        self.assertEqual(RemoteRealmCount.objects.count(), 1)
        self.assertEqual(RemoteInstallationCount.objects.count(), 0)
        self.assertEqual(RemoteRealmAuditLog.objects.count(), 0)

    # Make sure we aren't sending data we don't mean to, even if we don't store it.
    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL='https://push.zulip.org.example.com')
    @mock.patch('zerver.lib.remote_server.requests.request')
    def test_only_sending_intended_realmauditlog_data(self, mock_request: Any) -> None:
        mock_request.side_effect = self.bounce_request
        user = self.example_user('hamlet')
        # Event type in SYNCED_BILLING_EVENTS -- should be included
        RealmAuditLog.objects.create(
            realm=user.realm, modified_user=user, event_type=RealmAuditLog.USER_REACTIVATED,
            event_time=self.TIME_ZERO, extra_data='data')
        # Event type not in SYNCED_BILLING_EVENTS -- should not be included
        RealmAuditLog.objects.create(
            realm=user.realm, modified_user=user, event_type=RealmAuditLog.REALM_LOGO_CHANGED,
            event_time=self.TIME_ZERO, extra_data='data')

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
                self.assertIn('backfilled', str(args))
                self.assertNotIn('modified_user', str(args))
            return send_to_push_bouncer(*args)

        with mock.patch('zerver.lib.remote_server.send_to_push_bouncer',
                        side_effect=check_for_unwanted_data):
            send_analytics_to_remote_server()

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL='https://push.zulip.org.example.com')
    @mock.patch('zerver.lib.remote_server.requests.request')
    def test_realmauditlog_data_mapping(self, mock_request: Any) -> None:
        mock_request.side_effect = self.bounce_request
        user = self.example_user('hamlet')
        log_entry = RealmAuditLog.objects.create(
            realm=user.realm, modified_user=user, backfilled=True,
            event_type=RealmAuditLog.USER_REACTIVATED, event_time=self.TIME_ZERO, extra_data='data')
        send_analytics_to_remote_server()
        remote_log_entry = RemoteRealmAuditLog.objects.order_by('id').last()
        self.assertEqual(remote_log_entry.server.uuid, self.server_uuid)
        self.assertEqual(remote_log_entry.remote_id, log_entry.id)
        self.assertEqual(remote_log_entry.event_time, self.TIME_ZERO)
        self.assertEqual(remote_log_entry.backfilled, True)
        self.assertEqual(remote_log_entry.extra_data, 'data')
        self.assertEqual(remote_log_entry.event_type, RealmAuditLog.USER_REACTIVATED)

class PushNotificationTest(BouncerTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user_profile = self.example_user('hamlet')
        self.sending_client = get_client('test')
        self.sender = self.example_user('hamlet')

    def get_message(self, type: int, type_id: int=100) -> Message:
        recipient, _ = Recipient.objects.get_or_create(
            type_id=type_id,
            type=type,
        )

        message = Message(
            sender=self.sender,
            recipient=recipient,
            content='This is test content',
            rendered_content='This is test content',
            date_sent=now(),
            sending_client=self.sending_client,
        )
        message.set_topic_name('Test Topic')
        message.save()

        return message

    @contextmanager
    def mock_apns(self) -> Iterator[mock.MagicMock]:
        mock_apns = mock.Mock()
        with mock.patch('zerver.lib.push_notifications.get_apns_client') as mock_get:
            mock_get.return_value = mock_apns
            yield mock_apns

    def setup_apns_tokens(self) -> None:
        self.tokens = ['aaaa', 'bbbb']
        for token in self.tokens:
            PushDeviceToken.objects.create(
                kind=PushDeviceToken.APNS,
                token=hex_to_b64(token),
                user=self.user_profile,
                ios_app_id=settings.ZULIP_IOS_APP_ID)

        self.remote_tokens = ['cccc']
        for token in self.remote_tokens:
            RemotePushDeviceToken.objects.create(
                kind=RemotePushDeviceToken.APNS,
                token=hex_to_b64(token),
                user_id=self.user_profile.id,
                server=RemoteZulipServer.objects.get(uuid=self.server_uuid),
            )

    def setup_gcm_tokens(self) -> None:
        self.gcm_tokens = ['1111', '2222']
        for token in self.gcm_tokens:
            PushDeviceToken.objects.create(
                kind=PushDeviceToken.GCM,
                token=hex_to_b64(token),
                user=self.user_profile,
                ios_app_id=None)

        self.remote_gcm_tokens = ['dddd']
        for token in self.remote_gcm_tokens:
            RemotePushDeviceToken.objects.create(
                kind=RemotePushDeviceToken.GCM,
                token=hex_to_b64(token),
                user_id=self.user_profile.id,
                server=RemoteZulipServer.objects.get(uuid=self.server_uuid),
            )

class HandlePushNotificationTest(PushNotificationTest):
    DEFAULT_SUBDOMAIN = ""

    def bounce_request(self, *args: Any, **kwargs: Any) -> HttpResponse:
        """This method is used to carry out the push notification bouncer
        requests using the Django test browser, rather than python-requests.
        """
        # args[0] is method, args[1] is URL.
        local_url = args[1].replace(settings.PUSH_NOTIFICATION_BOUNCER_URL, "")
        if args[0] == "POST":
            result = self.uuid_post(
                self.server_uuid,
                local_url,
                kwargs['data'],
                content_type="application/json")
        else:
            raise AssertionError("Unsupported method for bounce_request")
        return result

    def test_end_to_end(self) -> None:
        self.setup_apns_tokens()
        self.setup_gcm_tokens()

        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
        )

        missed_message = {
            'message_id': message.id,
            'trigger': 'private_message',
        }
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=''), \
                mock.patch('zerver.lib.remote_server.requests.request',
                           side_effect=self.bounce_request), \
                mock.patch('zerver.lib.push_notifications.gcm_client') as mock_gcm, \
                self.mock_apns() as mock_apns, \
                mock.patch('zerver.lib.push_notifications.logger.info') as mock_info, \
                mock.patch('zerver.lib.push_notifications.logger.warning'):
            apns_devices = [
                (b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(
                    kind=PushDeviceToken.APNS)
            ]
            gcm_devices = [
                (b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(
                    kind=PushDeviceToken.GCM)
            ]
            mock_gcm.json_request.return_value = {
                'success': {gcm_devices[0][2]: message.id}}
            mock_apns.get_notification_result.return_value = 'Success'
            handle_push_notification(self.user_profile.id, missed_message)
            for _, _, token in apns_devices:
                mock_info.assert_any_call(
                    "APNs: Success sending for user %d to device %s",
                    self.user_profile.id, token)
            for _, _, token in gcm_devices:
                mock_info.assert_any_call(
                    "GCM: Sent %s as %s", token, message.id,
                )

    def test_unregistered_client(self) -> None:
        self.setup_apns_tokens()
        self.setup_gcm_tokens()

        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
        )

        missed_message = {
            'message_id': message.id,
            'trigger': 'private_message',
        }
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=''), \
                mock.patch('zerver.lib.remote_server.requests.request',
                           side_effect=self.bounce_request), \
                mock.patch('zerver.lib.push_notifications.gcm_client') as mock_gcm, \
                self.mock_apns() as mock_apns, \
                mock.patch('zerver.lib.push_notifications.logger.info') as mock_info, \
                mock.patch('zerver.lib.push_notifications.logger.warning'):
            apns_devices = [
                (b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(
                    kind=PushDeviceToken.APNS)
            ]
            gcm_devices = [
                (b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(
                    kind=PushDeviceToken.GCM)
            ]
            mock_gcm.json_request.return_value = {
                'success': {gcm_devices[0][2]: message.id}}

            mock_apns.get_notification_result.return_value = ('Unregistered', 1234567)
            handle_push_notification(self.user_profile.id, missed_message)
            for _, _, token in apns_devices:
                mock_info.assert_any_call(
                    "APNs: Removing invalid/expired token %s (%s)",
                    token, "Unregistered",
                )
            self.assertEqual(RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS).count(), 0)

    def test_connection_error(self) -> None:
        self.setup_apns_tokens()
        self.setup_gcm_tokens()

        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
        )

        missed_message = {
            'user_profile_id': self.user_profile.id,
            'message_id': message.id,
            'trigger': 'private_message',
        }
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=''), \
                mock.patch('zerver.lib.remote_server.requests.request',
                           side_effect=self.bounce_request), \
                mock.patch('zerver.lib.push_notifications.gcm_client') as mock_gcm, \
                mock.patch('zerver.lib.remote_server.requests.request',
                           side_effect=requests.ConnectionError):
            gcm_devices = [
                (b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(
                    kind=PushDeviceToken.GCM)
            ]
            mock_gcm.json_request.return_value = {
                'success': {gcm_devices[0][2]: message.id}}
            with self.assertRaises(PushNotificationBouncerRetryLaterError):
                handle_push_notification(self.user_profile.id, missed_message)

    @mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True)
    def test_disabled_notifications(self, mock_push_notifications: mock.MagicMock) -> None:
        user_profile = self.example_user('hamlet')
        user_profile.enable_online_email_notifications = False
        user_profile.enable_online_push_notifications = False
        user_profile.enable_offline_email_notifications = False
        user_profile.enable_offline_push_notifications = False
        user_profile.enable_stream_push_notifications = False
        user_profile.save()
        handle_push_notification(user_profile.id, {})
        mock_push_notifications.assert_called()

    @mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True)
    def test_read_message(self, mock_push_notifications: mock.MagicMock) -> None:
        user_profile = self.example_user('hamlet')
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.read,
            message=message,
        )

        missed_message = {
            'message_id': message.id,
            'trigger': 'private_message',
        }
        handle_push_notification(user_profile.id, missed_message)
        mock_push_notifications.assert_called_once()

    def test_deleted_message(self) -> None:
        """Simulates the race where message is deleted before handlingx push notifications"""
        user_profile = self.example_user('hamlet')
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.read,
            message=message,
        )
        missed_message = {
            'message_id': message.id,
            'trigger': 'private_message',
        }
        # Now, delete the message the normal way
        do_delete_messages(user_profile.realm, [message])

        with mock.patch('zerver.lib.push_notifications.uses_notification_bouncer') as mock_check, \
                mock.patch('logging.error') as mock_logging_error, \
                mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True) as mock_push_notifications:
            handle_push_notification(user_profile.id, missed_message)
            mock_push_notifications.assert_called_once()
            # Check we didn't proceed through and didn't log anything.
            mock_check.assert_not_called()
            mock_logging_error.assert_not_called()

    def test_missing_message(self) -> None:
        """Simulates the race where message is missing when handling push notifications"""
        user_profile = self.example_user('hamlet')
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.read,
            message=message,
        )
        missed_message = {
            'message_id': message.id,
            'trigger': 'private_message',
        }
        # Now delete the message forcefully, so it just doesn't exist.
        message.delete()

        # This should log an error
        with mock.patch('zerver.lib.push_notifications.uses_notification_bouncer') as mock_check, \
                self.assertLogs(level="INFO") as mock_logging_info, \
                mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True) as mock_push_notifications:
            handle_push_notification(user_profile.id, missed_message)
            mock_push_notifications.assert_called_once()
            # Check we didn't proceed through.
            mock_check.assert_not_called()
            self.assertEqual(mock_logging_info.output, [f"INFO:root:Unexpected message access failure handling push notifications: {user_profile.id} {missed_message['message_id']}"])

    def test_send_notifications_to_bouncer(self) -> None:
        user_profile = self.example_user('hamlet')
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=user_profile,
            message=message,
        )

        missed_message = {
            'message_id': message.id,
            'trigger': 'private_message',
        }
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=True), \
                mock.patch('zerver.lib.push_notifications.get_message_payload_apns',
                           return_value={'apns': True}), \
                mock.patch('zerver.lib.push_notifications.get_message_payload_gcm',
                           return_value=({'gcm': True}, {})), \
                mock.patch('zerver.lib.push_notifications'
                           '.send_notifications_to_bouncer') as mock_send:
            handle_push_notification(user_profile.id, missed_message)
            mock_send.assert_called_with(user_profile.id,
                                         {'apns': True},
                                         {'gcm': True},
                                         {},
                                         )

    def test_non_bouncer_push(self) -> None:
        self.setup_apns_tokens()
        self.setup_gcm_tokens()
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
        )

        android_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile,
                                           kind=PushDeviceToken.GCM))

        apple_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile,
                                           kind=PushDeviceToken.APNS))

        missed_message = {
            'message_id': message.id,
            'trigger': 'private_message',
        }
        with mock.patch('zerver.lib.push_notifications.get_message_payload_apns',
                        return_value={'apns': True}), \
                mock.patch('zerver.lib.push_notifications.get_message_payload_gcm',
                           return_value=({'gcm': True}, {})), \
                mock.patch('zerver.lib.push_notifications'
                           '.send_apple_push_notification') as mock_send_apple, \
                mock.patch('zerver.lib.push_notifications'
                           '.send_android_push_notification') as mock_send_android, \
                mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True) as mock_push_notifications:

            handle_push_notification(self.user_profile.id, missed_message)
            mock_send_apple.assert_called_with(self.user_profile.id,
                                               apple_devices,
                                               {'apns': True})
            mock_send_android.assert_called_with(android_devices, {'gcm': True}, {})
            mock_push_notifications.assert_called_once()

    def test_send_remove_notifications_to_bouncer(self) -> None:
        user_profile = self.example_user('hamlet')
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=user_profile,
            message=message,
            flags=UserMessage.flags.active_mobile_push_notification,
        )

        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=True), \
                mock.patch('zerver.lib.push_notifications'
                           '.send_notifications_to_bouncer') as mock_send:
            handle_remove_push_notification(user_profile.id, [message.id])
            mock_send.assert_called_with(
                user_profile.id,
                {
                    'badge': 0,
                    'custom': {
                        'zulip': {
                            'server': 'testserver',
                            'realm_id': self.sender.realm.id,
                            'realm_uri': 'http://zulip.testserver',
                            'user_id': self.user_profile.id,
                            'event': 'remove',
                            'zulip_message_ids': str(message.id),
                        },
                    },
                },
                {
                    'server': 'testserver',
                    'realm_id': self.sender.realm.id,
                    'realm_uri': 'http://zulip.testserver',
                    'user_id': self.user_profile.id,
                    'event': 'remove',
                    'zulip_message_ids': str(message.id),
                    'zulip_message_id': message.id,
                },
                {'priority': 'normal'})
            user_message = UserMessage.objects.get(user_profile=self.user_profile,
                                                   message=message)
            self.assertEqual(user_message.flags.active_mobile_push_notification, False)

    def test_non_bouncer_push_remove(self) -> None:
        self.setup_apns_tokens()
        self.setup_gcm_tokens()
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message,
            flags=UserMessage.flags.active_mobile_push_notification,
        )

        android_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile,
                                           kind=PushDeviceToken.GCM))

        apple_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile,
                                           kind=PushDeviceToken.APNS))

        with mock.patch('zerver.lib.push_notifications'
                        '.send_android_push_notification') as mock_send_android, \
                mock.patch('zerver.lib.push_notifications'
                           '.send_apple_push_notification') as mock_send_apple:
            handle_remove_push_notification(self.user_profile.id, [message.id])
            mock_send_android.assert_called_with(
                android_devices,
                {
                    'server': 'testserver',
                    'realm_id': self.sender.realm.id,
                    'realm_uri': 'http://zulip.testserver',
                    'user_id': self.user_profile.id,
                    'event': 'remove',
                    'zulip_message_ids': str(message.id),
                    'zulip_message_id': message.id,
                },
                {'priority': 'normal'})
            mock_send_apple.assert_called_with(
                self.user_profile.id,
                apple_devices,
                {'badge': 0,
                 'custom': {
                     'zulip': {
                         'server': 'testserver',
                         'realm_id': self.sender.realm.id,
                         'realm_uri': 'http://zulip.testserver',
                         'user_id': self.user_profile.id,
                         'event': 'remove',
                         'zulip_message_ids': str(message.id),
                     }
                 }})
            user_message = UserMessage.objects.get(user_profile=self.user_profile,
                                                   message=message)
            self.assertEqual(user_message.flags.active_mobile_push_notification, False)

    def test_user_message_does_not_exist(self) -> None:
        """This simulates a condition that should only be an error if the user is
        not long-term idle; we fake it, though, in the sense that the user should
        not have received the message in the first place"""
        self.make_stream('public_stream')
        sender = self.example_user('iago')
        message_id = self.send_stream_message(sender, "public_stream", "test")
        missed_message = {'message_id': message_id}
        with mock.patch('zerver.lib.push_notifications.logger.error') as mock_logger, \
                mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True) as mock_push_notifications:
            handle_push_notification(self.user_profile.id, missed_message)
            mock_logger.assert_called_with(
                "Could not find UserMessage with message_id %s and user_id %s",
                message_id, self.user_profile.id,
            )
            mock_push_notifications.assert_called_once()

    def test_user_message_soft_deactivated(self) -> None:
        """This simulates a condition that should only be an error if the user is
        not long-term idle; we fake it, though, in the sense that the user should
        not have received the message in the first place"""
        self.setup_apns_tokens()
        self.setup_gcm_tokens()
        self.make_stream('public_stream')
        self.subscribe(self.user_profile, 'public_stream')
        logger_string = "zulip.soft_deactivation"
        with self.assertLogs(logger_string, level='INFO') as info_logs:
            do_soft_deactivate_users([self.user_profile])
        self.assertEqual(info_logs.output, [
            f"INFO:{logger_string}:Soft Deactivated user {self.user_profile.id}",
            f"INFO:{logger_string}:Soft-deactivated batch of 1 users; 0 remain to process"
        ])
        sender = self.example_user('iago')
        message_id = self.send_stream_message(sender, "public_stream", "test")
        missed_message = {
            'message_id': message_id,
            'trigger': 'stream_push_notify',
        }

        android_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile,
                                           kind=PushDeviceToken.GCM))

        apple_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile,
                                           kind=PushDeviceToken.APNS))

        with mock.patch('zerver.lib.push_notifications.get_message_payload_apns',
                        return_value={'apns': True}), \
                mock.patch('zerver.lib.push_notifications.get_message_payload_gcm',
                           return_value=({'gcm': True}, {})), \
                mock.patch('zerver.lib.push_notifications'
                           '.send_apple_push_notification') as mock_send_apple, \
                mock.patch('zerver.lib.push_notifications'
                           '.send_android_push_notification') as mock_send_android, \
                mock.patch('zerver.lib.push_notifications.logger.error') as mock_logger, \
                mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True) as mock_push_notifications:
            handle_push_notification(self.user_profile.id, missed_message)
            mock_logger.assert_not_called()
            mock_send_apple.assert_called_with(self.user_profile.id,
                                               apple_devices,
                                               {'apns': True})
            mock_send_android.assert_called_with(android_devices, {'gcm': True}, {})
            mock_push_notifications.assert_called_once()

    @mock.patch('zerver.lib.push_notifications.logger.info')
    @mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True)
    def test_user_push_notification_already_active(self, mock_push_notifications: mock.MagicMock, mock_info: mock.MagicMock) -> None:
        user_profile = self.example_user('hamlet')
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.active_mobile_push_notification,
            message=message,
        )

        missed_message = {
            'message_id': message.id,
            'trigger': 'private_message',
        }
        handle_push_notification(user_profile.id, missed_message)
        mock_push_notifications.assert_called_once()
        # Check we didn't proceed ahead and function returned.
        mock_info.assert_not_called()

class TestAPNs(PushNotificationTest):
    def devices(self) -> List[DeviceToken]:
        return list(PushDeviceToken.objects.filter(
            user=self.user_profile, kind=PushDeviceToken.APNS))

    def send(self, devices: Optional[List[PushDeviceToken]]=None,
             payload_data: Dict[str, Any]={}) -> None:
        if devices is None:
            devices = self.devices()
        send_apple_push_notification(
            self.user_profile.id, devices, payload_data)

    def test_get_apns_client(self) -> None:
        """This test is pretty hacky, and needs to carefully reset the state
        it modifies in order to avoid leaking state that can lead to
        nondeterministic results for other tests.
        """
        import zerver.lib.push_notifications
        zerver.lib.push_notifications._apns_client_initialized = False
        try:
            with self.settings(APNS_CERT_FILE='/foo.pem'), \
                    mock.patch('apns2.client.APNsClient') as mock_client:
                client = get_apns_client()
                self.assertEqual(mock_client.return_value, client)
        finally:
            # Reset the values set by `get_apns_client` so that we don't
            # leak changes to the rest of the world.
            zerver.lib.push_notifications._apns_client_initialized = False
            zerver.lib.push_notifications._apns_client = None

    def test_not_configured(self) -> None:
        self.setup_apns_tokens()
        with mock.patch('zerver.lib.push_notifications.get_apns_client') as mock_get, \
                mock.patch('zerver.lib.push_notifications.logger') as mock_logging:
            mock_get.return_value = None
            self.send()
            mock_logging.debug.assert_called_once_with(
                "APNs: Dropping a notification because nothing configured.  "
                "Set PUSH_NOTIFICATION_BOUNCER_URL (or APNS_CERT_FILE).")
            mock_logging.warning.assert_not_called()
            from zerver.lib.push_notifications import initialize_push_notifications
            initialize_push_notifications()
            mock_logging.warning.assert_called_once_with(
                "Mobile push notifications are not configured.\n  "
                "See https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html")

    def test_success(self) -> None:
        self.setup_apns_tokens()
        with self.mock_apns() as mock_apns, \
                mock.patch('zerver.lib.push_notifications.logger') as mock_logging:
            mock_apns.get_notification_result.return_value = 'Success'
            self.send()
            mock_logging.warning.assert_not_called()
            for device in self.devices():
                mock_logging.info.assert_any_call(
                    "APNs: Success sending for user %d to device %s",
                    self.user_profile.id, device.token)

    def test_http_retry(self) -> None:
        import hyper
        self.setup_apns_tokens()
        with self.mock_apns() as mock_apns, \
                mock.patch('zerver.lib.push_notifications.logger') as mock_logging:
            mock_apns.get_notification_result.side_effect = itertools.chain(
                [hyper.http20.exceptions.StreamResetError()],
                itertools.repeat('Success'))
            self.send()
            mock_logging.warning.assert_called_once_with(
                "APNs: HTTP error sending for user %d to device %s: %s",
                self.user_profile.id, self.devices()[0].token, "StreamResetError")
            for device in self.devices():
                mock_logging.info.assert_any_call(
                    "APNs: Success sending for user %d to device %s",
                    self.user_profile.id, device.token)

    def test_http_retry_pipefail(self) -> None:
        self.setup_apns_tokens()
        with self.mock_apns() as mock_apns, \
                mock.patch('zerver.lib.push_notifications.logger') as mock_logging:
            mock_apns.get_notification_result.side_effect = itertools.chain(
                [BrokenPipeError()],
                itertools.repeat('Success'))
            self.send()
            mock_logging.warning.assert_called_once_with(
                "APNs: BrokenPipeError sending for user %d to device %s: %s",
                self.user_profile.id, self.devices()[0].token, "BrokenPipeError")
            for device in self.devices():
                mock_logging.info.assert_any_call(
                    "APNs: Success sending for user %d to device %s",
                    self.user_profile.id, device.token)

    def test_http_retry_eventually_fails(self) -> None:
        import hyper
        self.setup_apns_tokens()
        with self.mock_apns() as mock_apns, \
                mock.patch('zerver.lib.push_notifications.logger') as mock_logging:
            mock_apns.get_notification_result.side_effect = itertools.chain(
                [hyper.http20.exceptions.StreamResetError()],
                [hyper.http20.exceptions.StreamResetError()],
                [hyper.http20.exceptions.StreamResetError()],
                [hyper.http20.exceptions.StreamResetError()],
                [hyper.http20.exceptions.StreamResetError()],
            )

            self.send(devices=self.devices()[0:1])
            self.assertEqual(mock_logging.warning.call_count, 5)
            mock_logging.warning.assert_called_with(
                'APNs: Failed to send for user %d to device %s: %s',
                self.user_profile.id, self.devices()[0].token, 'HTTP error, retries exhausted')
            self.assertEqual(mock_logging.info.call_count, 1)

    def test_modernize_apns_payload(self) -> None:
        payload = {'alert': 'Message from Hamlet',
                   'badge': 0,
                   'custom': {'zulip': {'message_ids': [3]}}}
        self.assertEqual(
            modernize_apns_payload(
                {'alert': 'Message from Hamlet',
                 'message_ids': [3],
                 'badge': 0}),
            payload)
        self.assertEqual(
            modernize_apns_payload(payload),
            payload)

    @mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True)
    def test_apns_badge_count(self, mock_push_notifications: mock.MagicMock) -> None:

        user_profile = self.example_user('othello')
        # Test APNs badge count for personal messages.
        message_ids = [self.send_personal_message(self.sender,
                                                  user_profile,
                                                  'Content of message')
                       for i in range(3)]
        self.assertEqual(get_apns_badge_count(user_profile), 0)
        self.assertEqual(get_apns_badge_count_future(user_profile), 3)
        # Similarly, test APNs badge count for stream mention.
        stream = self.subscribe(user_profile, "Denmark")
        message_ids += [self.send_stream_message(self.sender,
                                                 stream.name,
                                                 'Hi, @**Othello, the Moor of Venice**')
                        for i in range(2)]
        self.assertEqual(get_apns_badge_count(user_profile), 0)
        self.assertEqual(get_apns_badge_count_future(user_profile), 5)

        num_messages = len(message_ids)
        # Mark the messages as read and test whether
        # the count decreases correctly.
        for i, message_id in enumerate(message_ids):
            do_update_message_flags(user_profile, get_client("website"), 'add', 'read', [message_id])
            self.assertEqual(get_apns_badge_count(user_profile), 0)
            self.assertEqual(get_apns_badge_count_future(user_profile), num_messages - i - 1)

        mock_push_notifications.assert_called()

class TestGetAPNsPayload(PushNotificationTest):
    def test_get_message_payload_apns_personal_message(self) -> None:
        user_profile = self.example_user("othello")
        message_id = self.send_personal_message(
            self.sender,
            user_profile,
            'Content of personal message',
        )
        message = Message.objects.get(id=message_id)
        message.trigger = 'private_message'
        payload = get_message_payload_apns(user_profile, message)
        expected = {
            'alert': {
                'title': 'King Hamlet',
                'subtitle': '',
                'body': message.content,
            },
            'badge': 0,
            'sound': 'default',
            'custom': {
                'zulip': {
                    'message_ids': [message.id],
                    'recipient_type': 'private',
                    'sender_email': self.sender.email,
                    'sender_id': self.sender.id,
                    'server': settings.EXTERNAL_HOST,
                    'realm_id': self.sender.realm.id,
                    'realm_uri': self.sender.realm.uri,
                    "user_id": user_profile.id,
                },
            },
        }
        self.assertDictEqual(payload, expected)

    @mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True)
    def test_get_message_payload_apns_huddle_message(self, mock_push_notifications: mock.MagicMock) -> None:
        user_profile = self.example_user("othello")
        message_id = self.send_huddle_message(
            self.sender,
            [self.example_user('othello'), self.example_user('cordelia')])
        message = Message.objects.get(id=message_id)
        message.trigger = 'private_message'
        payload = get_message_payload_apns(user_profile, message)
        expected = {
            'alert': {
                'title': 'Cordelia Lear, King Hamlet, Othello, the Moor of Venice',
                'subtitle': 'King Hamlet:',
                'body': message.content,
            },
            'sound': 'default',
            'badge': 0,
            'custom': {
                'zulip': {
                    'message_ids': [message.id],
                    'recipient_type': 'private',
                    'pm_users': ','.join(
                        str(s.user_profile_id)
                        for s in Subscription.objects.filter(
                            recipient=message.recipient)),
                    'sender_email': self.sender.email,
                    'sender_id': self.sender.id,
                    'server': settings.EXTERNAL_HOST,
                    'realm_id': self.sender.realm.id,
                    'realm_uri': self.sender.realm.uri,
                    "user_id": user_profile.id,
                },
            },
        }
        self.assertDictEqual(payload, expected)
        mock_push_notifications.assert_called()

    def test_get_message_payload_apns_stream_message(self) -> None:
        stream = Stream.objects.filter(name='Verona').get()
        message = self.get_message(Recipient.STREAM, stream.id)
        message.trigger = 'push_stream_notify'
        message.stream_name = 'Verona'
        payload = get_message_payload_apns(self.sender, message)
        expected = {
            'alert': {
                'title': '#Verona > Test Topic',
                'subtitle': 'King Hamlet:',
                'body': message.content,
            },
            'sound': 'default',
            'badge': 0,
            'custom': {
                'zulip': {
                    'message_ids': [message.id],
                    'recipient_type': 'stream',
                    'sender_email': self.sender.email,
                    'sender_id': self.sender.id,
                    "stream": get_display_recipient(message.recipient),
                    "topic": message.topic_name(),
                    'server': settings.EXTERNAL_HOST,
                    'realm_id': self.sender.realm.id,
                    'realm_uri': self.sender.realm.uri,
                    "user_id": self.sender.id,
                },
            },
        }
        self.assertDictEqual(payload, expected)

    def test_get_message_payload_apns_stream_mention(self) -> None:
        user_profile = self.example_user("othello")
        stream = Stream.objects.filter(name='Verona').get()
        message = self.get_message(Recipient.STREAM, stream.id)
        message.trigger = 'mentioned'
        message.stream_name = 'Verona'
        payload = get_message_payload_apns(user_profile, message)
        expected = {
            'alert': {
                'title': '#Verona > Test Topic',
                'subtitle': 'King Hamlet mentioned you:',
                'body': message.content,
            },
            'sound': 'default',
            'badge': 0,
            'custom': {
                'zulip': {
                    'message_ids': [message.id],
                    'recipient_type': 'stream',
                    'sender_email': self.sender.email,
                    'sender_id': self.sender.id,
                    "stream": get_display_recipient(message.recipient),
                    "topic": message.topic_name(),
                    'server': settings.EXTERNAL_HOST,
                    'realm_id': self.sender.realm.id,
                    'realm_uri': self.sender.realm.uri,
                    "user_id": user_profile.id,
                },
            },
        }
        self.assertDictEqual(payload, expected)

    def test_get_message_payload_apns_stream_wildcard_mention(self) -> None:
        user_profile = self.example_user("othello")
        stream = Stream.objects.filter(name='Verona').get()
        message = self.get_message(Recipient.STREAM, stream.id)
        message.trigger = 'wildcard_mentioned'
        message.stream_name = 'Verona'
        payload = get_message_payload_apns(user_profile, message)
        expected = {
            'alert': {
                'title': '#Verona > Test Topic',
                'subtitle': 'King Hamlet mentioned everyone:',
                'body': message.content,
            },
            'sound': 'default',
            'badge': 0,
            'custom': {
                'zulip': {
                    'message_ids': [message.id],
                    'recipient_type': 'stream',
                    'sender_email': self.sender.email,
                    'sender_id': self.sender.id,
                    "stream": get_display_recipient(message.recipient),
                    "topic": message.topic_name(),
                    'server': settings.EXTERNAL_HOST,
                    'realm_id': self.sender.realm.id,
                    'realm_uri': self.sender.realm.uri,
                    "user_id": user_profile.id,
                },
            },
        }
        self.assertDictEqual(payload, expected)

    @override_settings(PUSH_NOTIFICATION_REDACT_CONTENT = True)
    def test_get_message_payload_apns_redacted_content(self) -> None:
        user_profile = self.example_user("othello")
        message_id = self.send_huddle_message(
            self.sender,
            [self.example_user('othello'), self.example_user('cordelia')])
        message = Message.objects.get(id=message_id)
        message.trigger = 'private_message'
        payload = get_message_payload_apns(user_profile, message)
        expected = {
            'alert': {
                'title': 'Cordelia Lear, King Hamlet, Othello, the Moor of Venice',
                'subtitle': "King Hamlet:",
                'body': "***REDACTED***",
            },
            'sound': 'default',
            'badge': 0,
            'custom': {
                'zulip': {
                    'message_ids': [message.id],
                    'recipient_type': 'private',
                    'pm_users': ','.join(
                        str(s.user_profile_id)
                        for s in Subscription.objects.filter(
                            recipient=message.recipient)),
                    'sender_email': self.sender.email,
                    'sender_id': self.sender.id,
                    'server': settings.EXTERNAL_HOST,
                    'realm_id': self.sender.realm.id,
                    'realm_uri': self.sender.realm.uri,
                    "user_id": user_profile.id,
                },
            },
        }
        self.assertDictEqual(payload, expected)

class TestGetGCMPayload(PushNotificationTest):
    def test_get_message_payload_gcm(self) -> None:
        stream = Stream.objects.filter(name='Verona').get()
        message = self.get_message(Recipient.STREAM, stream.id)
        message.content = 'a' * 210
        message.rendered_content = 'a' * 210
        message.save()
        message.trigger = 'mentioned'

        hamlet = self.example_user('hamlet')
        payload, gcm_options = get_message_payload_gcm(hamlet, message)
        self.assertDictEqual(payload, {
            "user_id": hamlet.id,
            "event": "message",
            "alert": "New mention from King Hamlet",
            "zulip_message_id": message.id,
            "time": datetime_to_timestamp(message.date_sent),
            "content": 'a' * 200 + '…',
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
            "topic": message.topic_name(),
        })
        self.assertDictEqual(gcm_options, {
            "priority": "high",
        })

    def test_get_message_payload_gcm_personal(self) -> None:
        message = self.get_message(Recipient.PERSONAL, 1)
        message.trigger = 'private_message'
        hamlet = self.example_user('hamlet')
        payload, gcm_options = get_message_payload_gcm(hamlet, message)
        self.assertDictEqual(payload, {
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
        })
        self.assertDictEqual(gcm_options, {
            "priority": "high",
        })

    def test_get_message_payload_gcm_stream_notifications(self) -> None:
        message = self.get_message(Recipient.STREAM, 1)
        message.trigger = 'stream_push_notify'
        message.stream_name = 'Denmark'
        hamlet = self.example_user('hamlet')
        payload, gcm_options = get_message_payload_gcm(hamlet, message)
        self.assertDictEqual(payload, {
            "user_id": hamlet.id,
            "event": "message",
            "alert": "New stream message from King Hamlet in Denmark",
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
            "topic": "Test Topic",
            "stream": "Denmark",
        })
        self.assertDictEqual(gcm_options, {
            "priority": "high",
        })

    @override_settings(PUSH_NOTIFICATION_REDACT_CONTENT = True)
    def test_get_message_payload_gcm_redacted_content(self) -> None:
        message = self.get_message(Recipient.STREAM, 1)
        message.trigger = 'stream_push_notify'
        message.stream_name = 'Denmark'
        hamlet = self.example_user('hamlet')
        payload, gcm_options = get_message_payload_gcm(hamlet, message)
        self.assertDictEqual(payload, {
            "user_id": hamlet.id,
            "event": "message",
            "alert": "New stream message from King Hamlet in Denmark",
            "zulip_message_id": message.id,
            "time": datetime_to_timestamp(message.date_sent),
            "content": "***REDACTED***",
            "content_truncated": False,
            "server": settings.EXTERNAL_HOST,
            "realm_id": hamlet.realm.id,
            "realm_uri": hamlet.realm.uri,
            "sender_id": hamlet.id,
            "sender_email": hamlet.email,
            "sender_full_name": "King Hamlet",
            "sender_avatar_url": absolute_avatar_url(message.sender),
            "recipient_type": "stream",
            "topic": "Test Topic",
            "stream": "Denmark",
        })
        self.assertDictEqual(gcm_options, {
            "priority": "high",
        })


class TestSendNotificationsToBouncer(ZulipTestCase):
    @mock.patch('zerver.lib.remote_server.send_to_push_bouncer')
    def test_send_notifications_to_bouncer(self, mock_send: mock.MagicMock) -> None:
        send_notifications_to_bouncer(1, {'apns': True}, {'gcm': True}, {})
        post_data = {
            'user_id': 1,
            'apns_payload': {'apns': True},
            'gcm_payload': {'gcm': True},
            'gcm_options': {},
        }
        mock_send.assert_called_with('POST',
                                     'push/notify',
                                     orjson.dumps(post_data),
                                     extra_headers={'Content-type':
                                                    'application/json'})

class Result:
    def __init__(self, status: int=200, content: bytes=orjson.dumps({'msg': 'error'})) -> None:
        self.status_code = status
        self.content = content

class TestSendToPushBouncer(ZulipTestCase):
    @mock.patch('requests.request', return_value=Result(status=500))
    @mock.patch('logging.warning')
    def test_500_error(self, mock_request: mock.MagicMock, mock_warning: mock.MagicMock) -> None:
        with self.assertRaises(PushNotificationBouncerRetryLaterError):
            result, failed = send_to_push_bouncer('register', 'register', {'data': 'true'})
        mock_warning.assert_called_once()

    @mock.patch('requests.request', return_value=Result(status=400))
    def test_400_error(self, mock_request: mock.MagicMock) -> None:
        with self.assertRaises(JsonableError) as exc:
            send_to_push_bouncer('register', 'register', {'msg': 'true'})
        self.assertEqual(exc.exception.msg, 'error')

    def test_400_error_invalid_server_key(self) -> None:
        from zerver.decorator import InvalidZulipServerError

        # This is the exception our decorator uses for an invalid Zulip server
        error_obj = InvalidZulipServerError("testRole")
        with mock.patch('requests.request',
                        return_value=Result(status=400,
                                            content=orjson.dumps(error_obj.to_json()))):
            with self.assertRaises(PushNotificationBouncerException) as exc:
                send_to_push_bouncer('register', 'register', {'msg': 'true'})
        self.assertEqual(str(exc.exception),
                         'Push notifications bouncer error: '
                         'Zulip server auth failure: testRole is not registered')

    @mock.patch('requests.request', return_value=Result(status=400, content=b'/'))
    def test_400_error_when_content_is_not_serializable(self, mock_request: mock.MagicMock) -> None:
        with self.assertRaises(orjson.JSONDecodeError):
            send_to_push_bouncer('register', 'register', {'msg': 'true'})

    @mock.patch('requests.request', return_value=Result(status=300, content=b'/'))
    def test_300_error(self, mock_request: mock.MagicMock) -> None:
        with self.assertRaises(PushNotificationBouncerException) as exc:
            send_to_push_bouncer('register', 'register', {'msg': 'true'})
        self.assertEqual(str(exc.exception),
                         'Push notification bouncer returned unexpected status code 300')

class TestNumPushDevicesForUser(PushNotificationTest):
    def test_when_kind_is_none(self) -> None:
        self.setup_apns_tokens()
        self.assertEqual(num_push_devices_for_user(self.user_profile), 2)

    def test_when_kind_is_not_none(self) -> None:
        self.setup_apns_tokens()
        count = num_push_devices_for_user(self.user_profile,
                                          kind=PushDeviceToken.APNS)
        self.assertEqual(count, 2)

class TestPushApi(BouncerTestCase):
    def test_push_api_error_handling(self) -> None:
        user = self.example_user('cordelia')
        self.login_user(user)

        endpoints = [
            ('/json/users/me/apns_device_token', 'apple-tokenaz'),
            ('/json/users/me/android_gcm_reg_id', 'android-token'),
        ]

        # Test error handling
        for endpoint, label in endpoints:
            # Try adding/removing tokens that are too big...
            broken_token = "a" * 5000  # too big
            result = self.client_post(endpoint, {'token': broken_token})
            self.assert_json_error(result, 'Empty or invalid length token')

            if label == 'apple-tokenaz':
                result = self.client_post(endpoint, {'token': 'xyz has non-hex characters'})
                self.assert_json_error(result, 'Invalid APNS token')

            result = self.client_delete(endpoint, {'token': broken_token})
            self.assert_json_error(result, 'Empty or invalid length token')

            # Try to remove a non-existent token...
            result = self.client_delete(endpoint, {'token': 'abcd1234'})
            self.assert_json_error(result, 'Token does not exist')

            # Use push notification bouncer and try to remove non-existing tokens.
            with self.settings(PUSH_NOTIFICATION_BOUNCER_URL='https://push.zulip.org.example.com'), \
                mock.patch('zerver.lib.remote_server.requests.request',
                           side_effect=self.bounce_request) as remote_server_request:
                result = self.client_delete(endpoint, {'token': 'abcd1234'})
                self.assert_json_error(result, 'Token does not exist')
                remote_server_request.assert_called_once()

    def test_push_api_add_and_remove_device_tokens(self) -> None:
        user = self.example_user('cordelia')
        self.login_user(user)

        no_bouncer_requests = [
            ('/json/users/me/apns_device_token', 'apple-tokenaa'),
            ('/json/users/me/android_gcm_reg_id', 'android-token-1'),
        ]

        bouncer_requests = [
            ('/json/users/me/apns_device_token', 'apple-tokenbb'),
            ('/json/users/me/android_gcm_reg_id', 'android-token-2'),
        ]

        # Add tokens without using push notification bouncer.
        for endpoint, token in no_bouncer_requests:
            # Test that we can push twice.
            result = self.client_post(endpoint, {'token': token})
            self.assert_json_success(result)

            result = self.client_post(endpoint, {'token': token})
            self.assert_json_success(result)

            tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
            self.assertEqual(len(tokens), 1)
            self.assertEqual(tokens[0].token, token)

        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL='https://push.zulip.org.example.com'), \
            mock.patch('zerver.lib.remote_server.requests.request',
                       side_effect=self.bounce_request):
            # Enable push notification bouncer and add tokens.
            for endpoint, token in bouncer_requests:
                # Test that we can push twice.
                result = self.client_post(endpoint, {'token': token})
                self.assert_json_success(result)

                result = self.client_post(endpoint, {'token': token})
                self.assert_json_success(result)

                tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
                self.assertEqual(len(tokens), 1)
                self.assertEqual(tokens[0].token, token)

                tokens = list(RemotePushDeviceToken.objects.filter(user_id=user.id, token=token))
                self.assertEqual(len(tokens), 1)
                self.assertEqual(tokens[0].token, token)

        # PushDeviceToken will include all the device tokens.
        tokens = list(PushDeviceToken.objects.values_list('token', flat=True))
        self.assertEqual(tokens, ['apple-tokenaa', 'android-token-1', 'apple-tokenbb', 'android-token-2'])

        # RemotePushDeviceToken will only include tokens of
        # the devices using push notification bouncer.
        remote_tokens = list(RemotePushDeviceToken.objects.values_list('token', flat=True))
        self.assertEqual(remote_tokens, ['apple-tokenbb', 'android-token-2'])

        # Test removing tokens without using push notification bouncer.
        for endpoint, token in no_bouncer_requests:
            result = self.client_delete(endpoint, {'token': token})
            self.assert_json_success(result)
            tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
            self.assertEqual(len(tokens), 0)

        # Use push notification bouncer and test removing device tokens.
        # Tokens will be removed both locally and remotely.
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL='https://push.zulip.org.example.com'), \
            mock.patch('zerver.lib.remote_server.requests.request',
                       side_effect=self.bounce_request):
            for endpoint, token in bouncer_requests:
                result = self.client_delete(endpoint, {'token': token})
                self.assert_json_success(result)
                tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
                remote_tokens = list(RemotePushDeviceToken.objects.filter(user_id=user.id, token=token))
                self.assertEqual(len(tokens), 0)
                self.assertEqual(len(remote_tokens), 0)

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
        self.assertEqual(
            "high", parse_gcm_options({}, {"event": "message"}))
        self.assertEqual(
            "normal", parse_gcm_options({}, {"event": "remove"}))
        self.assertEqual(
            "normal", parse_gcm_options({}, {}))

    def test_explicit_priority(self) -> None:
        self.assertEqual(
            "normal", parse_gcm_options({"priority": "normal"}, {}))
        self.assertEqual(
            "high", parse_gcm_options({"priority": "high"}, {}))

@mock.patch('zerver.lib.push_notifications.gcm_client')
class GCMSendTest(PushNotificationTest):
    def setUp(self) -> None:
        super().setUp()
        self.setup_gcm_tokens()

    def get_gcm_data(self, **kwargs: Any) -> Dict[str, Any]:
        data = {
            'key 1': 'Data 1',
            'key 2': 'Data 2',
        }
        data.update(kwargs)
        return data

    @mock.patch('zerver.lib.push_notifications.logger.debug')
    def test_gcm_is_none(self, mock_debug: mock.MagicMock, mock_gcm: mock.MagicMock) -> None:
        mock_gcm.__bool__.return_value = False
        send_android_push_notification_to_user(self.user_profile, {}, {})
        mock_debug.assert_called_with(
            "Skipping sending a GCM push notification since PUSH_NOTIFICATION_BOUNCER_URL "
            "and ANDROID_GCM_API_KEY are both unset")

    @mock.patch('zerver.lib.push_notifications.logger.warning')
    def test_json_request_raises_ioerror(self, mock_warn: mock.MagicMock,
                                         mock_gcm: mock.MagicMock) -> None:
        mock_gcm.json_request.side_effect = IOError('error')
        send_android_push_notification_to_user(self.user_profile, {}, {})
        mock_warn.assert_called_with("Error while pushing to GCM", exc_info=True)

    @mock.patch('zerver.lib.push_notifications.logger.warning')
    @mock.patch('zerver.lib.push_notifications.logger.info')
    def test_success(self, mock_info: mock.MagicMock, mock_warning: mock.MagicMock,
                     mock_gcm: mock.MagicMock) -> None:
        res = {}
        res['success'] = {token: ind for ind, token in enumerate(self.gcm_tokens)}
        mock_gcm.json_request.return_value = res

        data = self.get_gcm_data()
        send_android_push_notification_to_user(self.user_profile, data, {})
        self.assertEqual(mock_info.call_count, 2)
        c1 = call("GCM: Sent %s as %s", "1111", 0)
        c2 = call("GCM: Sent %s as %s", "2222", 1)
        mock_info.assert_has_calls([c1, c2], any_order=True)
        mock_warning.assert_not_called()

    @mock.patch('zerver.lib.push_notifications.logger.warning')
    def test_canonical_equal(self, mock_warning: mock.MagicMock, mock_gcm: mock.MagicMock) -> None:
        res = {}
        res['canonical'] = {1: 1}
        mock_gcm.json_request.return_value = res

        data = self.get_gcm_data()
        send_android_push_notification_to_user(self.user_profile, data, {})
        mock_warning.assert_called_once_with(
            "GCM: Got canonical ref but it already matches our ID %s!", 1,
        )

    @mock.patch('zerver.lib.push_notifications.logger.warning')
    def test_canonical_pushdevice_not_present(self, mock_warning: mock.MagicMock,
                                              mock_gcm: mock.MagicMock) -> None:
        res = {}
        t1 = hex_to_b64('1111')
        t2 = hex_to_b64('3333')
        res['canonical'] = {t1: t2}
        mock_gcm.json_request.return_value = res

        def get_count(hex_token: str) -> int:
            token = hex_to_b64(hex_token)
            return PushDeviceToken.objects.filter(
                token=token, kind=PushDeviceToken.GCM).count()

        self.assertEqual(get_count('1111'), 1)
        self.assertEqual(get_count('3333'), 0)

        data = self.get_gcm_data()
        send_android_push_notification_to_user(self.user_profile, data, {})
        msg = ("GCM: Got canonical ref %s "
               "replacing %s but new ID not "
               "registered! Updating.")
        mock_warning.assert_called_once_with(msg, t2, t1)

        self.assertEqual(get_count('1111'), 0)
        self.assertEqual(get_count('3333'), 1)

    @mock.patch('zerver.lib.push_notifications.logger.info')
    def test_canonical_pushdevice_different(self, mock_info: mock.MagicMock,
                                            mock_gcm: mock.MagicMock) -> None:
        res = {}
        old_token = hex_to_b64('1111')
        new_token = hex_to_b64('2222')
        res['canonical'] = {old_token: new_token}
        mock_gcm.json_request.return_value = res

        def get_count(hex_token: str) -> int:
            token = hex_to_b64(hex_token)
            return PushDeviceToken.objects.filter(
                token=token, kind=PushDeviceToken.GCM).count()

        self.assertEqual(get_count('1111'), 1)
        self.assertEqual(get_count('2222'), 1)

        data = self.get_gcm_data()
        send_android_push_notification_to_user(self.user_profile, data, {})
        mock_info.assert_called_once_with(
            "GCM: Got canonical ref %s, dropping %s", new_token, old_token,
        )

        self.assertEqual(get_count('1111'), 0)
        self.assertEqual(get_count('2222'), 1)

    @mock.patch('zerver.lib.push_notifications.logger.info')
    def test_not_registered(self, mock_info: mock.MagicMock, mock_gcm: mock.MagicMock) -> None:
        res = {}
        token = hex_to_b64('1111')
        res['errors'] = {'NotRegistered': [token]}
        mock_gcm.json_request.return_value = res

        def get_count(hex_token: str) -> int:
            token = hex_to_b64(hex_token)
            return PushDeviceToken.objects.filter(
                token=token, kind=PushDeviceToken.GCM).count()

        self.assertEqual(get_count('1111'), 1)

        data = self.get_gcm_data()
        send_android_push_notification_to_user(self.user_profile, data, {})
        mock_info.assert_called_once_with("GCM: Removing %s", token)
        self.assertEqual(get_count('1111'), 0)

    @mock.patch('zerver.lib.push_notifications.logger.warning')
    def test_failure(self, mock_warn: mock.MagicMock, mock_gcm: mock.MagicMock) -> None:
        res = {}
        token = hex_to_b64('1111')
        res['errors'] = {'Failed': [token]}
        mock_gcm.json_request.return_value = res

        data = self.get_gcm_data()
        send_android_push_notification_to_user(self.user_profile, data, {})
        c1 = call("GCM: Delivery to %s failed: %s", token, "Failed")
        mock_warn.assert_has_calls([c1], any_order=True)

class TestClearOnRead(ZulipTestCase):
    def test_mark_stream_as_read(self) -> None:
        n_msgs = 3

        hamlet = self.example_user("hamlet")
        hamlet.enable_stream_push_notifications = True
        hamlet.save()
        stream = self.subscribe(hamlet, "Denmark")

        message_ids = [self.send_stream_message(self.example_user("iago"),
                                                stream.name,
                                                f"yo {i}")
                       for i in range(n_msgs)]
        UserMessage.objects.filter(
            user_profile_id=hamlet.id,
            message_id__in=message_ids,
        ).update(
            flags=F('flags').bitor(
                UserMessage.flags.active_mobile_push_notification))

        with mock_queue_publish("zerver.lib.actions.queue_json_publish") as mock_publish:
            do_mark_stream_messages_as_read(hamlet, stream.recipient_id)
            queue_items = [c[0][1] for c in mock_publish.call_args_list]
            groups = [item['message_ids'] for item in queue_items]

        self.assert_length(groups, 1)
        self.assertEqual(sum(len(g) for g in groups), len(message_ids))
        self.assertEqual({id for g in groups for id in g}, set(message_ids))

class TestReceivesNotificationsFunctions(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = self.example_user('cordelia')

    def test_receivers_online_notifications_when_user_is_a_bot(self) -> None:
        self.user.is_bot = True

        self.user.enable_online_push_notifications = True
        self.assertFalse(receives_online_notifications(self.user))

        self.user.enable_online_push_notifications = False
        self.assertFalse(receives_online_notifications(self.user))

    def test_receivers_online_notifications_when_user_is_not_a_bot(self) -> None:
        self.user.is_bot = False

        self.user.enable_online_push_notifications = True
        self.assertTrue(receives_online_notifications(self.user))

        self.user.enable_online_push_notifications = False
        self.assertFalse(receives_online_notifications(self.user))

    def test_receivers_offline_notifications_when_user_is_a_bot(self) -> None:
        self.user.is_bot = True

        self.user.enable_offline_email_notifications = True
        self.user.enable_offline_push_notifications = True
        self.assertFalse(receives_offline_push_notifications(self.user))
        self.assertFalse(receives_offline_email_notifications(self.user))

        self.user.enable_offline_email_notifications = False
        self.user.enable_offline_push_notifications = False
        self.assertFalse(receives_offline_push_notifications(self.user))
        self.assertFalse(receives_offline_email_notifications(self.user))

        self.user.enable_offline_email_notifications = True
        self.user.enable_offline_push_notifications = False
        self.assertFalse(receives_offline_push_notifications(self.user))
        self.assertFalse(receives_offline_email_notifications(self.user))

        self.user.enable_offline_email_notifications = False
        self.user.enable_offline_push_notifications = True
        self.assertFalse(receives_offline_push_notifications(self.user))
        self.assertFalse(receives_offline_email_notifications(self.user))

    def test_receivers_offline_notifications_when_user_is_not_a_bot(self) -> None:
        self.user.is_bot = False

        self.user.enable_offline_email_notifications = True
        self.user.enable_offline_push_notifications = True
        self.assertTrue(receives_offline_push_notifications(self.user))
        self.assertTrue(receives_offline_email_notifications(self.user))

        self.user.enable_offline_email_notifications = False
        self.user.enable_offline_push_notifications = False
        self.assertFalse(receives_offline_push_notifications(self.user))
        self.assertFalse(receives_offline_email_notifications(self.user))

        self.user.enable_offline_email_notifications = True
        self.user.enable_offline_push_notifications = False
        self.assertFalse(receives_offline_push_notifications(self.user))
        self.assertTrue(receives_offline_email_notifications(self.user))

        self.user.enable_offline_email_notifications = False
        self.user.enable_offline_push_notifications = True
        self.assertTrue(receives_offline_push_notifications(self.user))
        self.assertFalse(receives_offline_email_notifications(self.user))

    def test_receivers_stream_notifications_when_user_is_a_bot(self) -> None:
        self.user.is_bot = True

        self.user.enable_stream_push_notifications = True
        self.assertFalse(receives_stream_notifications(self.user))

        self.user.enable_stream_push_notifications = False
        self.assertFalse(receives_stream_notifications(self.user))

    def test_receivers_stream_notifications_when_user_is_not_a_bot(self) -> None:
        self.user.is_bot = False

        self.user.enable_stream_push_notifications = True
        self.assertTrue(receives_stream_notifications(self.user))

        self.user.enable_stream_push_notifications = False
        self.assertFalse(receives_stream_notifications(self.user))

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
                'name': 'realm_emoji',
                'rendered_content': f'<p>Testing <img alt=":green_tick:" class="emoji" src="/user_avatars/{realm.id}/emoji/green_tick.png" title="green tick"> realm emoji.</p>',
                'expected_output': 'Testing :green_tick: realm emoji.',
            },
            {
                'name': 'mentions',
                'rendered_content': f'<p>Mentioning <span class="user-mention" data-user-id="{cordelia.id}">@Cordelia Lear</span>.</p>',
                'expected_output': 'Mentioning @Cordelia Lear.',
            },
            {
                'name': 'stream_names',
                'rendered_content': f'<p>Testing stream names <a class="stream" data-stream-id="{stream.id}" href="/#narrow/stream/Verona">#Verona</a>.</p>',
                'expected_output': 'Testing stream names #Verona.',
            },
        ]

        for test in fixtures:
            actual_output = get_mobile_push_content(test["rendered_content"])
            self.assertEqual(actual_output, test["expected_output"])

@skipUnless(settings.ZILENCER_ENABLED, "requires zilencer")
class PushBouncerSignupTest(ZulipTestCase):
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
        self.assert_json_error(result, f"Zulip server auth failure: key does not match role {zulip_org_id}")
