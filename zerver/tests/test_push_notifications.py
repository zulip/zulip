from __future__ import absolute_import
from __future__ import print_function

import itertools
import requests
import mock
from mock import call
import time
from typing import Any, Dict, List, Union, SupportsInt, Text

import gcm
import ujson

from django.test import TestCase, override_settings
from django.conf import settings
from django.http import HttpResponse

from zerver.models import (
    PushDeviceToken,
    UserProfile,
    Message,
    UserMessage,
    receives_offline_notifications,
    receives_online_notifications,
    receives_stream_notifications,
    get_client,
    get_realm,
    Recipient,
    Stream,
)
from zerver.lib import push_notifications as apn
from zerver.lib.push_notifications import DeviceToken
from zerver.lib.response import json_success
from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zilencer.models import RemoteZulipServer, RemotePushDeviceToken
from django.utils.timezone import now

class BouncerTestCase(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.server_uuid = "1234-abcd"
        server = RemoteZulipServer(uuid=self.server_uuid,
                                   api_key="magic_secret_api_key",
                                   hostname="demo.example.com",
                                   last_updated=now())
        server.save()
        super(BouncerTestCase, self).setUp()

    def tearDown(self):
        # type: () -> None
        RemoteZulipServer.objects.filter(uuid=self.server_uuid).delete()
        super(BouncerTestCase, self).tearDown()

    def bounce_request(self, *args, **kwargs):
        # type: (*Any, **Any) -> HttpResponse
        """This method is used to carry out the push notification bouncer
        requests using the Django test browser, rather than python-requests.
        """
        # args[0] is method, args[1] is URL.
        local_url = args[1].replace(settings.PUSH_NOTIFICATION_BOUNCER_URL, "")
        if args[0] == "POST":
            result = self.client_post(local_url,
                                      kwargs['data'],
                                      subdomain="",
                                      **self.get_auth())
        else:
            raise AssertionError("Unsupported method for bounce_request")
        return result

    def get_generic_payload(self, method='register'):
        # type: (Text) -> Dict[str, Any]
        user_id = 10
        token = "111222"
        token_kind = PushDeviceToken.GCM

        return {'user_id': user_id,
                'token': token,
                'token_kind': token_kind}

    def get_auth(self):
        # type: () -> Dict[str, Text]
        # Auth on this user
        return self.api_auth(self.server_uuid)

class PushBouncerNotificationTest(BouncerTestCase):
    DEFAULT_SUBDOMAIN = ""

    def test_unregister_remote_push_user_params(self):
        # type: () -> None
        token = "111222"
        token_kind = PushDeviceToken.GCM

        endpoint = '/api/v1/remotes/push/unregister'
        result = self.client_post(endpoint, {'token_kind': token_kind},
                                  **self.get_auth())
        self.assert_json_error(result, "Missing 'token' argument")
        result = self.client_post(endpoint, {'token': token},
                                  **self.get_auth())
        self.assert_json_error(result, "Missing 'token_kind' argument")

        # We need the root ('') subdomain to be in use for this next
        # test, since the push bouncer API is only available there:
        realm = get_realm("zulip")
        realm.string_id = ""
        realm.save()

        result = self.client_post(endpoint, {'token': token, 'token_kind': token_kind},
                                  **self.api_auth(self.example_email("hamlet")))
        self.assert_json_error(result, "Must validate with valid Zulip server API key")

    def test_register_remote_push_user_paramas(self):
        # type: () -> None
        token = "111222"
        user_id = 11
        token_kind = PushDeviceToken.GCM

        endpoint = '/api/v1/remotes/push/register'

        result = self.client_post(endpoint, {'user_id': user_id, 'token_kind': token_kind},
                                  **self.get_auth())
        self.assert_json_error(result, "Missing 'token' argument")
        result = self.client_post(endpoint, {'user_id': user_id, 'token': token},
                                  **self.get_auth())
        self.assert_json_error(result, "Missing 'token_kind' argument")
        result = self.client_post(endpoint, {'token': token, 'token_kind': token_kind},
                                  **self.get_auth())
        self.assert_json_error(result, "Missing 'user_id' argument")
        result = self.client_post(endpoint, {'user_id': user_id, 'token': token,
                                             'token_kind': 17},
                                  **self.get_auth())
        self.assert_json_error(result, "Invalid token type")

        with self.settings(REALMS_HAVE_SUBDOMAINS=True):
            result = self.client_post(endpoint, {'user_id': user_id, 'token_kind': token_kind,
                                                 'token': token},
                                      **self.api_auth(self.example_email("hamlet")))
        self.assert_json_error(result, "Account is not associated with this subdomain",
                               status_code=401)

        # We need the root ('') subdomain to be in use for this next
        # test, since the push bouncer API is only available there:
        realm = get_realm("zulip")
        realm.string_id = ""
        realm.save()

        result = self.client_post(endpoint, {'user_id': user_id, 'token_kind': token_kind,
                                             'token': token},
                                  **self.api_auth(self.example_email("hamlet")))
        self.assert_json_error(result, "Must validate with valid Zulip server API key")

    def test_remote_push_user_endpoints(self):
        # type: () -> None
        endpoints = [
            ('/api/v1/remotes/push/register', 'register'),
            ('/api/v1/remotes/push/unregister', 'unregister'),
        ]

        for endpoint, method in endpoints:
            payload = self.get_generic_payload(method)

            # Verify correct results are success
            result = self.client_post(endpoint, payload, **self.get_auth())
            self.assert_json_success(result)

            remote_tokens = RemotePushDeviceToken.objects.filter(token=payload['token'])
            token_count = 1 if method == 'register' else 0
            self.assertEqual(len(remote_tokens), token_count)

            # Try adding/removing tokens that are too big...
            broken_token = "x" * 5000  # too big
            payload['token'] = broken_token
            result = self.client_post(endpoint, payload, **self.get_auth())
            self.assert_json_error(result, 'Empty or invalid length token')

    def test_invalid_apns_token(self):
        # type: () -> None
        endpoints = [
            ('/api/v1/remotes/push/register', 'apple-token'),
        ]

        for endpoint, method in endpoints:
            payload = {
                'user_id': 10,
                'token': 'xyz uses non-hex characters',
                'token_kind': PushDeviceToken.APNS,
            }
            result = self.client_post(endpoint, payload,
                                      **self.get_auth())
            self.assert_json_error(result, 'Invalid APNS token')

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL='https://push.zulip.org.example.com')
    @mock.patch('zerver.lib.push_notifications.requests.request')
    def test_push_bouncer_api(self, mock):
        # type: (Any) -> None
        """This is a variant of the below test_push_api, but using the full
        push notification bouncer flow
        """
        mock.side_effect = self.bounce_request
        user = self.example_user('cordelia')
        email = user.email
        self.login(email)
        server = RemoteZulipServer.objects.get(uuid=self.server_uuid)

        endpoints = [
            ('/json/users/me/apns_device_token', 'apple-tokenaz', RemotePushDeviceToken.APNS),
            ('/json/users/me/android_gcm_reg_id', 'android-token', RemotePushDeviceToken.GCM),
        ]

        # Test error handling
        for endpoint, _, kind in endpoints:
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

class PushNotificationTest(BouncerTestCase):
    def setUp(self):
        # type: () -> None
        super(PushNotificationTest, self).setUp()
        self.user_profile = self.example_user('hamlet')
        self.tokens = [u'aaaa', u'bbbb']
        for token in self.tokens:
            PushDeviceToken.objects.create(
                kind=PushDeviceToken.APNS,
                token=apn.hex_to_b64(token),
                user=self.user_profile,
                ios_app_id=settings.ZULIP_IOS_APP_ID)

        self.remote_tokens = [u'cccc']
        for token in self.remote_tokens:
            RemotePushDeviceToken.objects.create(
                kind=RemotePushDeviceToken.APNS,
                token=apn.hex_to_b64(token),
                user_id=self.user_profile.id,
                server=RemoteZulipServer.objects.get(uuid=self.server_uuid),
            )

        self.sending_client = get_client('test')
        self.sender = self.example_user('hamlet')

    def get_message(self, type, type_id=100):
        # type: (int, int) -> Message
        recipient, _ = Recipient.objects.get_or_create(
            type_id=type_id,
            type=type,
        )

        return Message.objects.create(
            sender=self.sender,
            recipient=recipient,
            subject='Test Message',
            content='This is test content',
            pub_date=now(),
            sending_client=self.sending_client,
        )

class HandlePushNotificationTest(PushNotificationTest):
    DEFAULT_SUBDOMAIN = ""

    def bounce_request(self, *args, **kwargs):
        # type: (*Any, **Any) -> HttpResponse
        """This method is used to carry out the push notification bouncer
        requests using the Django test browser, rather than python-requests.
        """
        # args[0] is method, args[1] is URL.
        local_url = args[1].replace(settings.PUSH_NOTIFICATION_BOUNCER_URL, "")
        if args[0] == "POST":
            result = self.client_post(local_url,
                                      kwargs['data'],
                                      content_type="application/json",
                                      **self.get_auth())
        else:
            raise AssertionError("Unsupported method for bounce_request")
        return result

    def test_end_to_end(self):
        # type: () -> None
        remote_gcm_tokens = [u'dddd']
        for token in remote_gcm_tokens:
            RemotePushDeviceToken.objects.create(
                kind=RemotePushDeviceToken.GCM,
                token=apn.hex_to_b64(token),
                user_id=self.user_profile.id,
                server=RemoteZulipServer.objects.get(uuid=self.server_uuid),
            )

        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message
        )

        missed_message = {
            'message_id': message.id,
            'triggers': {
                'private_message': True,
                'mentioned': False,
                'stream_push_notify': False,
            },
        }
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=''), \
                mock.patch('zerver.lib.push_notifications.requests.request',
                           side_effect=self.bounce_request), \
                mock.patch('zerver.lib.push_notifications.gcm') as mock_gcm, \
                mock.patch('zerver.lib.push_notifications._apns_client') as mock_apns, \
                mock.patch('logging.info') as mock_info, \
                mock.patch('logging.warn'):
            apns_devices = [
                (apn.b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(
                    kind=PushDeviceToken.APNS)
            ]
            gcm_devices = [
                (apn.b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(
                    kind=PushDeviceToken.GCM)
            ]
            mock_gcm.json_request.return_value = {
                'success': {gcm_devices[0][2]: message.id}}
            mock_apns.get_notification_result.return_value = 'Success'
            apn.handle_push_notification(self.user_profile.id, missed_message)
            for _, _, token in apns_devices:
                mock_info.assert_any_call(
                    "APNs: Success sending for user %d to device %s",
                    self.user_profile.id, token)
            for _, _, token in gcm_devices:
                mock_info.assert_any_call(
                    "GCM: Sent %s as %s" % (token, message.id))

    def test_end_to_end_connection_error(self):
        # type: () -> None
        remote_gcm_tokens = [u'dddd']
        for token in remote_gcm_tokens:
            RemotePushDeviceToken.objects.create(
                kind=RemotePushDeviceToken.GCM,
                token=apn.hex_to_b64(token),
                user_id=self.user_profile.id,
                server=RemoteZulipServer.objects.get(uuid=self.server_uuid),
            )

        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message
        )

        def retry(queue_name, event, processor):
            # type: (Any, Any, Any) -> None
            apn.handle_push_notification(event['user_profile_id'], event)

        missed_message = {
            'user_profile_id': self.user_profile.id,
            'message_id': message.id,
            'triggers': {
                'private_message': True,
                'mentioned': False,
                'stream_push_notify': False,
            },
        }
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=''), \
                mock.patch('zerver.lib.push_notifications.requests.request',
                           side_effect=self.bounce_request), \
                mock.patch('zerver.lib.push_notifications.gcm') as mock_gcm, \
                mock.patch('zerver.lib.push_notifications.send_notifications_to_bouncer',
                           side_effect=requests.ConnectionError), \
                mock.patch('zerver.lib.queue.queue_json_publish',
                           side_effect=retry) as mock_retry, \
                mock.patch('logging.warning') as mock_warn:
            gcm_devices = [
                (apn.b64_to_hex(device.token), device.ios_app_id, device.token)
                for device in RemotePushDeviceToken.objects.filter(
                    kind=PushDeviceToken.GCM)
            ]
            mock_gcm.json_request.return_value = {
                'success': {gcm_devices[0][2]: message.id}}
            apn.handle_push_notification(self.user_profile.id, missed_message)
            self.assertEqual(mock_retry.call_count, 3)
            mock_warn.assert_called_with("Maximum retries exceeded for "
                                         "trigger:%s event:"
                                         "push_notification" % (self.user_profile.id,))

    def test_disabled_notifications(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        user_profile.enable_online_email_notifications = False
        user_profile.enable_online_push_notifications = False
        user_profile.enable_offline_email_notifications = False
        user_profile.enable_offline_push_notifications = False
        user_profile.enable_stream_push_notifications = False
        user_profile.save()
        apn.handle_push_notification(user_profile.id, {})

    def test_read_message(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.read,
            message=message
        )

        missed_message = {
            'message_id': message.id,
            'triggers': {
                'private_message': True,
                'mentioned': False,
                'stream_push_notify': False,
            },
        }
        apn.handle_push_notification(user_profile.id, missed_message)

    def test_send_notifications_to_bouncer(self):
        # type: () -> None
        user_profile = self.example_user('hamlet')
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=user_profile,
            message=message
        )

        missed_message = {
            'message_id': message.id,
            'triggers': {
                'private_message': True,
                'mentioned': False,
                'stream_push_notify': False,
            },
        }
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=True), \
                mock.patch('zerver.lib.push_notifications.get_apns_payload',
                           return_value={'apns': True}), \
                mock.patch('zerver.lib.push_notifications.get_gcm_payload',
                           return_value={'gcm': True}), \
                mock.patch('zerver.lib.push_notifications'
                           '.send_notifications_to_bouncer') as mock_send:
            apn.handle_push_notification(user_profile.id, missed_message)
            mock_send.assert_called_with(user_profile.id,
                                         {'apns': True},
                                         {'gcm': True},
                                         )

    def test_non_bouncer_push(self):
        # type: () -> None
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=self.user_profile,
            message=message
        )

        for token in [u'dddd']:
            PushDeviceToken.objects.create(
                kind=PushDeviceToken.GCM,
                token=apn.hex_to_b64(token),
                user=self.user_profile)

        android_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile,
                                           kind=PushDeviceToken.GCM))

        apple_devices = list(
            PushDeviceToken.objects.filter(user=self.user_profile,
                                           kind=PushDeviceToken.APNS))

        missed_message = {
            'message_id': message.id,
            'triggers': {
                'private_message': True,
                'mentioned': False,
                'stream_push_notify': False,
            },
        }
        with mock.patch('zerver.lib.push_notifications.get_apns_payload',
                        return_value={'apns': True}), \
                mock.patch('zerver.lib.push_notifications.get_gcm_payload',
                           return_value={'gcm': True}), \
                mock.patch('zerver.lib.push_notifications'
                           '.send_apple_push_notification') as mock_send_apple, \
                mock.patch('zerver.lib.push_notifications'
                           '.send_android_push_notification') as mock_send_android:

            apn.handle_push_notification(self.user_profile.id, missed_message)
            mock_send_apple.assert_called_with(self.user_profile.id,
                                               apple_devices,
                                               {'apns': True})
            mock_send_android.assert_called_with(android_devices,
                                                 {'gcm': True})

    def test_user_message_does_not_exist(self):
        # type: () -> None
        missed_message = {'message_id': 100}
        with mock.patch('logging.error') as mock_logger:
            apn.handle_push_notification(self.user_profile.id, missed_message)
            mock_logger.assert_called_with("Could not find UserMessage with "
                                           "message_id 100")

class TestAPNs(PushNotificationTest):
    def devices(self):
        # type: () -> List[DeviceToken]
        return list(PushDeviceToken.objects.filter(
            user=self.user_profile, kind=PushDeviceToken.APNS))

    def send(self, payload_data={}):
        # type: (Dict[str, Any]) -> None
        apn.send_apple_push_notification(
            self.user_profile.id, self.devices(), payload_data)

    def test_success(self):
        # type: () -> None
        with mock.patch('zerver.lib.push_notifications._apns_client') as mock_apns, \
                mock.patch('zerver.lib.push_notifications.logging') as mock_logging:
            mock_apns.get_notification_result.return_value = 'Success'
            self.send()
            mock_logging.warn.assert_not_called()
            for device in self.devices():
                mock_logging.info.assert_any_call(
                    "APNs: Success sending for user %d to device %s",
                    self.user_profile.id, device.token)

    def test_http_retry(self):
        # type: () -> None
        import hyper
        with mock.patch('zerver.lib.push_notifications._apns_client') as mock_apns, \
                mock.patch('zerver.lib.push_notifications.logging') as mock_logging:
            mock_apns.get_notification_result.side_effect = itertools.chain(
                [hyper.http20.exceptions.StreamResetError()],
                itertools.repeat('Success'))
            self.send()
            mock_logging.warn.assert_called_once_with(
                "APNs: HTTP error sending for user %d to device %s: %s",
                self.user_profile.id, self.devices()[0].token, "StreamResetError")
            for device in self.devices():
                mock_logging.info.assert_any_call(
                    "APNs: Success sending for user %d to device %s",
                    self.user_profile.id, device.token)

class TestGetAlertFromMessage(PushNotificationTest):
    def test_get_alert_from_private_group_message(self):
        # type: () -> None
        message = self.get_message(Recipient.HUDDLE)
        message.triggers = {
            'private_message': True,
            'mentioned': False,
            'stream_push_notify': False,
        }
        alert = apn.get_alert_from_message(message)
        self.assertEqual(alert, "New private group message from King Hamlet")

    def test_get_alert_from_private_message(self):
        # type: () -> None
        message = self.get_message(Recipient.PERSONAL)
        message.triggers = {
            'private_message': True,
            'mentioned': False,
            'stream_push_notify': False,
        }
        alert = apn.get_alert_from_message(message)
        self.assertEqual(alert, "New private message from King Hamlet")

    def test_get_alert_from_mention(self):
        # type: () -> None
        message = self.get_message(Recipient.STREAM)
        message.triggers = {
            'private_message': False,
            'mentioned': True,
            'stream_push_notify': False,
        }
        alert = apn.get_alert_from_message(message)
        self.assertEqual(alert, "New mention from King Hamlet")

    def test_get_alert_from_stream_message(self):
        # type: () -> None
        message = self.get_message(Recipient.STREAM)
        message.triggers = {
            'private_message': False,
            'mentioned': False,
            'stream_push_notify': True,
        }
        message.stream_name = 'Denmark'
        alert = apn.get_alert_from_message(message)
        self.assertEqual(alert, "New stream message from King Hamlet in Denmark")

    def test_get_alert_from_other_message(self):
        # type: () -> None
        message = self.get_message(0)
        message.triggers = {
            'private_message': False,
            'mentioned': False,
            'stream_push_notify': False,
        }
        alert = apn.get_alert_from_message(message)
        alert = apn.get_alert_from_message(self.get_message(0))
        self.assertEqual(alert,
                         "New Zulip mentions and private messages from King "
                         "Hamlet")

class TestGetAPNsPayload(PushNotificationTest):
    def test_get_apns_payload(self):
        # type: () -> None
        message = self.get_message(Recipient.HUDDLE)
        message.triggers = {
            'private_message': True,
            'mentioned': False,
            'stream_push_notify': False,
        }
        payload = apn.get_apns_payload(message)
        expected = {
            'alert': {
                'title': "New private group message from King Hamlet",
                'body': message.content,
            },
            'badge': 1,
            'custom': {
                'zulip': {
                    'message_ids': [message.id],
                }
            }
        }
        self.assertDictEqual(payload, expected)

class TestGetGCMPayload(PushNotificationTest):
    def test_get_gcm_payload(self):
        # type: () -> None
        stream = Stream.objects.filter(name='Verona').get()
        message = self.get_message(Recipient.STREAM, stream.id)
        message.content = 'a' * 210
        message.save()
        message.triggers = {
            'private_message': False,
            'mentioned': True,
            'stream_push_notify': False,
        }

        user_profile = self.example_user('hamlet')
        payload = apn.get_gcm_payload(user_profile, message)
        expected = {
            "user": user_profile.email,
            "event": "message",
            "alert": "New mention from King Hamlet",
            "zulip_message_id": message.id,
            "time": apn.datetime_to_timestamp(message.pub_date),
            "content": 'a' * 200 + '...',
            "content_truncated": True,
            "sender_email": self.example_email("hamlet"),
            "sender_full_name": "King Hamlet",
            "sender_avatar_url": apn.absolute_avatar_url(message.sender),
            "recipient_type": "stream",
            "stream": apn.get_display_recipient(message.recipient),
            "topic": message.subject,
        }
        self.assertDictEqual(payload, expected)

    def test_get_gcm_payload_personal(self):
        # type: () -> None
        message = self.get_message(Recipient.PERSONAL, 1)
        message.triggers = {
            'private_message': True,
            'mentioned': False,
            'stream_push_notify': False,
        }
        user_profile = self.example_user('hamlet')
        payload = apn.get_gcm_payload(user_profile, message)
        expected = {
            "user": user_profile.email,
            "event": "message",
            "alert": "New private message from King Hamlet",
            "zulip_message_id": message.id,
            "time": apn.datetime_to_timestamp(message.pub_date),
            "content": message.content,
            "content_truncated": False,
            "sender_email": self.example_email("hamlet"),
            "sender_full_name": "King Hamlet",
            "sender_avatar_url": apn.absolute_avatar_url(message.sender),
            "recipient_type": "private",
        }
        self.assertDictEqual(payload, expected)

    def test_get_gcm_payload_stream_notifications(self):
        # type: () -> None
        message = self.get_message(Recipient.STREAM, 1)
        message.triggers = {
            'private_message': False,
            'mentioned': False,
            'stream_push_notify': True,
        }
        message.stream_name = 'Denmark'
        user_profile = self.example_user('hamlet')
        payload = apn.get_gcm_payload(user_profile, message)
        expected = {
            "user": user_profile.email,
            "event": "message",
            "alert": "New stream message from King Hamlet in Denmark",
            "zulip_message_id": message.id,
            "time": apn.datetime_to_timestamp(message.pub_date),
            "content": message.content,
            "content_truncated": False,
            "sender_email": self.example_email("hamlet"),
            "sender_full_name": "King Hamlet",
            "sender_avatar_url": apn.absolute_avatar_url(message.sender),
            "recipient_type": "stream",
            "topic": "Test Message",
            "stream": "Denmark"
        }
        self.assertDictEqual(payload, expected)

class TestSendNotificationsToBouncer(ZulipTestCase):
    @mock.patch('zerver.lib.push_notifications.send_to_push_bouncer')
    def test_send_notifications_to_bouncer(self, mock_send):
        # type: (mock.MagicMock) -> None
        apn.send_notifications_to_bouncer(1, {'apns': True}, {'gcm': True})
        post_data = {
            'user_id': 1,
            'apns_payload': {'apns': True},
            'gcm_payload': {'gcm': True},
        }
        mock_send.assert_called_with('POST',
                                     'notify',
                                     ujson.dumps(post_data),
                                     extra_headers={'Content-type':
                                                    'application/json'})

class TestSendToPushBouncer(PushNotificationTest):
    class Result(object):
        def __init__(self, status=200, content=ujson.dumps({'msg': 'error'})):
            # type: (int, str) -> None
            self.status_code = status
            self.content = content

    @mock.patch('requests.request', return_value=Result(status=500))
    def test_500_error(self, mock_request):
        # type: (mock.MagicMock) -> None
        with self.assertRaises(apn.JsonableError) as exc:
            apn.send_to_push_bouncer('register', 'register', {'data': True})
        self.assertEqual(exc.exception.msg,
                         'Error received from push notification bouncer')

    @mock.patch('requests.request', return_value=Result(status=400))
    def test_400_error(self, mock_request):
        # type: (mock.MagicMock) -> None
        with self.assertRaises(apn.JsonableError) as exc:
            apn.send_to_push_bouncer('register', 'register', {'msg': True})
        self.assertEqual(exc.exception.msg, 'error')

    @mock.patch('requests.request', return_value=Result(status=400, content='/'))
    def test_400_error_when_content_is_not_serializable(self, mock_request):
        # type: (mock.MagicMock) -> None
        with self.assertRaises(apn.JsonableError) as exc:
            apn.send_to_push_bouncer('register', 'register', {'msg': True})
        self.assertEqual(exc.exception.msg,
                         'Error received from push notification bouncer')

    @mock.patch('requests.request', return_value=Result(status=300, content='/'))
    def test_300_error(self, mock_request):
        # type: (mock.MagicMock) -> None
        with self.assertRaises(apn.JsonableError) as exc:
            apn.send_to_push_bouncer('register', 'register', {'msg': True})
        self.assertEqual(exc.exception.msg,
                         'Error received from push notification bouncer')

class TestNumPushDevicesForUser(PushNotificationTest):
    def test_when_kind_is_none(self):
        # type: () -> None
        self.assertEqual(apn.num_push_devices_for_user(self.user_profile), 2)

    def test_when_kind_is_not_none(self):
        # type: () -> None
        count = apn.num_push_devices_for_user(self.user_profile,
                                              kind=PushDeviceToken.APNS)
        self.assertEqual(count, 2)

class TestPushApi(ZulipTestCase):
    def test_push_api(self):
        # type: () -> None
        user = self.example_user('cordelia')
        email = user.email
        self.login(email)

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

        # Add tokens
        for endpoint, token in endpoints:
            # Test that we can push twice
            result = self.client_post(endpoint, {'token': token})
            self.assert_json_success(result)

            result = self.client_post(endpoint, {'token': token})
            self.assert_json_success(result)

            tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
            self.assertEqual(len(tokens), 1)
            self.assertEqual(tokens[0].token, token)

        # User should have tokens for both devices now.
        tokens = list(PushDeviceToken.objects.filter(user=user))
        self.assertEqual(len(tokens), 2)

        # Remove tokens
        for endpoint, token in endpoints:
            result = self.client_delete(endpoint, {'token': token})
            self.assert_json_success(result)
            tokens = list(PushDeviceToken.objects.filter(user=user, token=token))
            self.assertEqual(len(tokens), 0)

class GCMTest(PushNotificationTest):
    def setUp(self):
        # type: () -> None
        super(GCMTest, self).setUp()
        apn.gcm = gcm.GCM('fake key')
        self.gcm_tokens = [u'1111', u'2222']
        for token in self.gcm_tokens:
            PushDeviceToken.objects.create(
                kind=PushDeviceToken.GCM,
                token=apn.hex_to_b64(token),
                user=self.user_profile,
                ios_app_id=None)

    def get_gcm_data(self, **kwargs):
        # type: (**Any) -> Dict[str, Any]
        data = {
            'key 1': 'Data 1',
            'key 2': 'Data 2',
        }
        data.update(kwargs)
        return data

class GCMNotSetTest(GCMTest):
    @mock.patch('logging.warning')
    def test_gcm_is_none(self, mock_warning):
        # type: (mock.MagicMock) -> None
        apn.gcm = None
        apn.send_android_push_notification_to_user(self.user_profile, {})
        mock_warning.assert_called_with("Attempting to send a GCM push "
                                        "notification, but no API key was "
                                        "configured")

class GCMIOErrorTest(GCMTest):
    @mock.patch('zerver.lib.push_notifications.gcm.json_request')
    @mock.patch('logging.warning')
    def test_json_request_raises_ioerror(self, mock_warn, mock_json_request):
        # type: (mock.MagicMock, mock.MagicMock) -> None
        mock_json_request.side_effect = IOError('error')
        apn.send_android_push_notification_to_user(self.user_profile, {})
        mock_warn.assert_called_with('error')

class GCMSuccessTest(GCMTest):
    @mock.patch('logging.warning')
    @mock.patch('logging.info')
    @mock.patch('gcm.GCM.json_request')
    def test_success(self, mock_send, mock_info, mock_warning):
        # type: (mock.MagicMock, mock.MagicMock, mock.MagicMock) -> None
        res = {}
        res['success'] = {token: ind for ind, token in enumerate(self.gcm_tokens)}
        mock_send.return_value = res

        data = self.get_gcm_data()
        apn.send_android_push_notification_to_user(self.user_profile, data)
        self.assertEqual(mock_info.call_count, 2)
        c1 = call("GCM: Sent 1111 as 0")
        c2 = call("GCM: Sent 2222 as 1")
        mock_info.assert_has_calls([c1, c2], any_order=True)
        mock_warning.assert_not_called()

class GCMCanonicalTest(GCMTest):
    @mock.patch('logging.warning')
    @mock.patch('gcm.GCM.json_request')
    def test_equal(self, mock_send, mock_warning):
        # type: (mock.MagicMock, mock.MagicMock) -> None
        res = {}
        res['canonical'] = {1: 1}
        mock_send.return_value = res

        data = self.get_gcm_data()
        apn.send_android_push_notification_to_user(self.user_profile, data)
        mock_warning.assert_called_once_with("GCM: Got canonical ref but it "
                                             "already matches our ID 1!")

    @mock.patch('logging.warning')
    @mock.patch('gcm.GCM.json_request')
    def test_pushdevice_not_present(self, mock_send, mock_warning):
        # type: (mock.MagicMock, mock.MagicMock) -> None
        res = {}
        t1 = apn.hex_to_b64(u'1111')
        t2 = apn.hex_to_b64(u'3333')
        res['canonical'] = {t1: t2}
        mock_send.return_value = res

        def get_count(hex_token):
            # type: (Text) -> int
            token = apn.hex_to_b64(hex_token)
            return PushDeviceToken.objects.filter(
                token=token, kind=PushDeviceToken.GCM).count()

        self.assertEqual(get_count(u'1111'), 1)
        self.assertEqual(get_count(u'3333'), 0)

        data = self.get_gcm_data()
        apn.send_android_push_notification_to_user(self.user_profile, data)
        msg = ("GCM: Got canonical ref %s "
               "replacing %s but new ID not "
               "registered! Updating.")
        mock_warning.assert_called_once_with(msg % (t2, t1))

        self.assertEqual(get_count(u'1111'), 0)
        self.assertEqual(get_count(u'3333'), 1)

    @mock.patch('logging.info')
    @mock.patch('gcm.GCM.json_request')
    def test_pushdevice_different(self, mock_send, mock_info):
        # type: (mock.MagicMock, mock.MagicMock) -> None
        res = {}
        old_token = apn.hex_to_b64(u'1111')
        new_token = apn.hex_to_b64(u'2222')
        res['canonical'] = {old_token: new_token}
        mock_send.return_value = res

        def get_count(hex_token):
            # type: (Text) -> int
            token = apn.hex_to_b64(hex_token)
            return PushDeviceToken.objects.filter(
                token=token, kind=PushDeviceToken.GCM).count()

        self.assertEqual(get_count(u'1111'), 1)
        self.assertEqual(get_count(u'2222'), 1)

        data = self.get_gcm_data()
        apn.send_android_push_notification_to_user(self.user_profile, data)
        mock_info.assert_called_once_with(
            "GCM: Got canonical ref %s, dropping %s" % (new_token, old_token))

        self.assertEqual(get_count(u'1111'), 0)
        self.assertEqual(get_count(u'2222'), 1)

class GCMNotRegisteredTest(GCMTest):
    @mock.patch('logging.info')
    @mock.patch('gcm.GCM.json_request')
    def test_not_registered(self, mock_send, mock_info):
        # type: (mock.MagicMock, mock.MagicMock) -> None
        res = {}
        token = apn.hex_to_b64(u'1111')
        res['errors'] = {'NotRegistered': [token]}
        mock_send.return_value = res

        def get_count(hex_token):
            # type: (Text) -> int
            token = apn.hex_to_b64(hex_token)
            return PushDeviceToken.objects.filter(
                token=token, kind=PushDeviceToken.GCM).count()

        self.assertEqual(get_count(u'1111'), 1)

        data = self.get_gcm_data()
        apn.send_android_push_notification_to_user(self.user_profile, data)
        mock_info.assert_called_once_with("GCM: Removing %s" % (token,))
        self.assertEqual(get_count(u'1111'), 0)

class GCMFailureTest(GCMTest):
    @mock.patch('logging.warning')
    @mock.patch('gcm.GCM.json_request')
    def test_failure(self, mock_send, mock_warn):
        # type: (mock.MagicMock, mock.MagicMock) -> None
        res = {}
        token = apn.hex_to_b64(u'1111')
        res['errors'] = {'Failed': [token]}
        mock_send.return_value = res

        data = self.get_gcm_data()
        apn.send_android_push_notification_to_user(self.user_profile, data)
        c1 = call("GCM: Delivery to %s failed: Failed" % (token,))
        mock_warn.assert_has_calls([c1], any_order=True)

class TestReceivesNotificationsFunctions(ZulipTestCase):
    def setUp(self):
        # type: () -> None
        self.user = self.example_user('cordelia')

    def test_receivers_online_notifications_when_user_is_a_bot(self):
        # type: () -> None
        self.user.is_bot = True

        self.user.enable_online_push_notifications = True
        self.assertFalse(receives_online_notifications(self.user))

        self.user.enable_online_push_notifications = False
        self.assertFalse(receives_online_notifications(self.user))

    def test_receivers_online_notifications_when_user_is_not_a_bot(self):
        # type: () -> None
        self.user.is_bot = False

        self.user.enable_online_push_notifications = True
        self.assertTrue(receives_online_notifications(self.user))

        self.user.enable_online_push_notifications = False
        self.assertFalse(receives_online_notifications(self.user))

    def test_receivers_offline_notifications_when_user_is_a_bot(self):
        # type: () -> None
        self.user.is_bot = True

        self.user.enable_offline_email_notifications = True
        self.user.enable_offline_push_notifications = True
        self.assertFalse(receives_offline_notifications(self.user))

        self.user.enable_offline_email_notifications = False
        self.user.enable_offline_push_notifications = False
        self.assertFalse(receives_offline_notifications(self.user))

        self.user.enable_offline_email_notifications = True
        self.user.enable_offline_push_notifications = False
        self.assertFalse(receives_offline_notifications(self.user))

        self.user.enable_offline_email_notifications = False
        self.user.enable_offline_push_notifications = True
        self.assertFalse(receives_offline_notifications(self.user))

    def test_receivers_offline_notifications_when_user_is_not_a_bot(self):
        # type: () -> None
        self.user.is_bot = False

        self.user.enable_offline_email_notifications = True
        self.user.enable_offline_push_notifications = True
        self.assertTrue(receives_offline_notifications(self.user))

        self.user.enable_offline_email_notifications = False
        self.user.enable_offline_push_notifications = False
        self.assertFalse(receives_offline_notifications(self.user))

        self.user.enable_offline_email_notifications = True
        self.user.enable_offline_push_notifications = False
        self.assertTrue(receives_offline_notifications(self.user))

        self.user.enable_offline_email_notifications = False
        self.user.enable_offline_push_notifications = True
        self.assertTrue(receives_offline_notifications(self.user))

    def test_receivers_stream_notifications_when_user_is_a_bot(self):
        # type: () -> None
        self.user.is_bot = True

        self.user.enable_stream_push_notifications = True
        self.assertFalse(receives_stream_notifications(self.user))

        self.user.enable_stream_push_notifications = False
        self.assertFalse(receives_stream_notifications(self.user))

    def test_receivers_stream_notifications_when_user_is_not_a_bot(self):
        # type: () -> None
        self.user.is_bot = False

        self.user.enable_stream_push_notifications = True
        self.assertTrue(receives_stream_notifications(self.user))

        self.user.enable_stream_push_notifications = False
        self.assertFalse(receives_stream_notifications(self.user))
