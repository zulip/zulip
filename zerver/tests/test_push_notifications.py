
from contextlib import contextmanager
import itertools
import requests
import mock
from mock import call
import time
from typing import Any, Dict, List, Optional, Union, SupportsInt

import base64
import gcm
import json
import os
import ujson
import uuid

from django.test import TestCase, override_settings
from django.conf import settings
from django.http import HttpResponse
from django.utils.crypto import get_random_string

from zerver.models import (
    PushDeviceToken,
    UserProfile,
    Message,
    UserMessage,
    receives_offline_email_notifications,
    receives_offline_push_notifications,
    receives_online_notifications,
    receives_stream_notifications,
    get_client,
    get_realm,
    Recipient,
    Stream,
    Subscription,
)
from zerver.lib.actions import do_delete_message
from zerver.lib.soft_deactivation import do_soft_deactivate_users
from zerver.lib import push_notifications as apn
from zerver.lib.push_notifications import get_mobile_push_content, \
    DeviceToken, PushNotificationBouncerException, get_apns_client
from zerver.lib.response import json_success
from zerver.lib.test_classes import (
    ZulipTestCase,
)

from zilencer.models import RemoteZulipServer, RemotePushDeviceToken
from django.utils.timezone import now

ZERVER_DIR = os.path.dirname(os.path.dirname(__file__))

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
            result = self.api_post(self.server_uuid,
                                   local_url,
                                   kwargs['data'],
                                   subdomain="")
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
        result = self.api_post(self.server_uuid, endpoint, {'token_kind': token_kind})
        self.assert_json_error(result, "Missing 'token' argument")
        result = self.api_post(self.server_uuid, endpoint, {'token': token})
        self.assert_json_error(result, "Missing 'token_kind' argument")

        # We need the root ('') subdomain to be in use for this next
        # test, since the push bouncer API is only available there:
        realm = get_realm("zulip")
        realm.string_id = ""
        realm.save()

        result = self.api_post(self.example_email("hamlet"), endpoint, {'token': token,
                                                                        'user_id': 15,
                                                                        'token_kind': token_kind},
                               realm="")
        self.assert_json_error(result, "Must validate with valid Zulip server API key")

    def test_register_remote_push_user_paramas(self) -> None:
        token = "111222"
        user_id = 11
        token_kind = PushDeviceToken.GCM

        endpoint = '/api/v1/remotes/push/register'

        result = self.api_post(self.server_uuid, endpoint, {'user_id': user_id, 'token_kind': token_kind})
        self.assert_json_error(result, "Missing 'token' argument")
        result = self.api_post(self.server_uuid, endpoint, {'user_id': user_id, 'token': token})
        self.assert_json_error(result, "Missing 'token_kind' argument")
        result = self.api_post(self.server_uuid, endpoint, {'token': token, 'token_kind': token_kind})
        self.assert_json_error(result, "Missing 'user_id' argument")
        result = self.api_post(self.server_uuid, endpoint, {'user_id': user_id, 'token': token, 'token_kind': 17})
        self.assert_json_error(result, "Invalid token type")

        result = self.api_post(self.example_email("hamlet"), endpoint, {'user_id': user_id,
                                                                        'token_kind': token_kind,
                                                                        'token': token})
        self.assert_json_error(result, "Account is not associated with this subdomain",
                               status_code=401)

        # We need the root ('') subdomain to be in use for this next
        # test, since the push bouncer API is only available there:
        realm = get_realm("zulip")
        realm.string_id = ""
        realm.save()

        result = self.api_post(self.example_email("hamlet"), endpoint, {'user_id': user_id,
                                                                        'token_kind': token_kind,
                                                                        'token': token})
        self.assert_json_error(result, "Must validate with valid Zulip server API key")

        result = self.api_post(self.server_uuid, endpoint, {'user_id': user_id,
                                                            'token_kind': token_kind,
                                                            'token': token},
                               subdomain="zulip")
        self.assert_json_error(result, "Invalid subdomain for push notifications bouncer",
                               status_code=401)

        # We do a bit of hackery here to the API_KEYS cache just to
        # make the code simple for sending an incorrect API key.
        from zerver.lib.test_classes import API_KEYS
        API_KEYS[self.server_uuid] = 'invalid'
        result = self.api_post(self.server_uuid, endpoint, {'user_id': user_id,
                                                            'token_kind': token_kind,
                                                            'token': token})
        self.assert_json_error(result, "Zulip server auth failure: key does not match role 1234-abcd",
                               status_code=401)

        del API_KEYS[self.server_uuid]

        credentials = "%s:%s" % ("5678-efgh", 'invalid')
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
            result = self.api_post(self.server_uuid, endpoint, payload)
            self.assert_json_success(result)

            remote_tokens = RemotePushDeviceToken.objects.filter(token=payload['token'])
            token_count = 1 if method == 'register' else 0
            self.assertEqual(len(remote_tokens), token_count)

            # Try adding/removing tokens that are too big...
            broken_token = "x" * 5000  # too big
            payload['token'] = broken_token
            result = self.api_post(self.server_uuid, endpoint, payload)
            self.assert_json_error(result, 'Empty or invalid length token')

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
            result = self.api_post(self.server_uuid, endpoint, payload)
            self.assert_json_error(result, 'Invalid APNS token')

    @override_settings(PUSH_NOTIFICATION_BOUNCER_URL='https://push.zulip.org.example.com')
    @mock.patch('zerver.lib.push_notifications.requests.request')
    def test_push_bouncer_api(self, mock: Any) -> None:
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
    def setUp(self) -> None:
        super().setUp()
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
            pub_date=now(),
            sending_client=self.sending_client,
        )
        message.set_topic_name('Test Topic')
        message.save()

        return message

    @contextmanager
    def mock_apns(self) -> mock.MagicMock:
        mock_apns = mock.Mock()
        with mock.patch('zerver.lib.push_notifications.get_apns_client') as mock_get:
            mock_get.return_value = mock_apns
            yield mock_apns

class HandlePushNotificationTest(PushNotificationTest):
    DEFAULT_SUBDOMAIN = ""

    def bounce_request(self, *args: Any, **kwargs: Any) -> HttpResponse:
        """This method is used to carry out the push notification bouncer
        requests using the Django test browser, rather than python-requests.
        """
        # args[0] is method, args[1] is URL.
        local_url = args[1].replace(settings.PUSH_NOTIFICATION_BOUNCER_URL, "")
        if args[0] == "POST":
            result = self.api_post(self.server_uuid,
                                   local_url,
                                   kwargs['data'],
                                   content_type="application/json")
        else:
            raise AssertionError("Unsupported method for bounce_request")
        return result

    def test_end_to_end(self) -> None:
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
            'trigger': 'private_message',
        }
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=''), \
                mock.patch('zerver.lib.push_notifications.requests.request',
                           side_effect=self.bounce_request), \
                mock.patch('zerver.lib.push_notifications.gcm') as mock_gcm, \
                self.mock_apns() as mock_apns, \
                mock.patch('zerver.lib.push_notifications.logger.info') as mock_info, \
                mock.patch('zerver.lib.push_notifications.logger.warning'):
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

            # Now test the unregistered case
            mock_apns.get_notification_result.return_value = ('Unregistered', 1234567)
            apn.handle_push_notification(self.user_profile.id, missed_message)
            for _, _, token in apns_devices:
                mock_info.assert_any_call(
                    "APNs: Removing invalid/expired token %s (%s)" %
                    (token, "Unregistered"))
            self.assertEqual(RemotePushDeviceToken.objects.filter(kind=PushDeviceToken.APNS).count(), 0)

    def test_end_to_end_connection_error(self) -> None:
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

        def retry(queue_name: Any, event: Any, processor: Any) -> None:
            apn.handle_push_notification(event['user_profile_id'], event)

        missed_message = {
            'user_profile_id': self.user_profile.id,
            'message_id': message.id,
            'trigger': 'private_message',
        }
        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=''), \
                mock.patch('zerver.lib.push_notifications.requests.request',
                           side_effect=self.bounce_request), \
                mock.patch('zerver.lib.push_notifications.gcm') as mock_gcm, \
                mock.patch('zerver.lib.push_notifications.send_notifications_to_bouncer',
                           side_effect=requests.ConnectionError), \
                mock.patch('zerver.lib.queue.queue_json_publish',
                           side_effect=retry) as mock_retry, \
                mock.patch('zerver.lib.push_notifications.logger.warning') as mock_warn:
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

    @mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True)
    def test_disabled_notifications(self, mock_push_notifications: mock.MagicMock) -> None:
        user_profile = self.example_user('hamlet')
        user_profile.enable_online_email_notifications = False
        user_profile.enable_online_push_notifications = False
        user_profile.enable_offline_email_notifications = False
        user_profile.enable_offline_push_notifications = False
        user_profile.enable_stream_push_notifications = False
        user_profile.save()
        apn.handle_push_notification(user_profile.id, {})
        mock_push_notifications.assert_called()

    @mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True)
    def test_read_message(self, mock_push_notifications: mock.MagicMock) -> None:
        user_profile = self.example_user('hamlet')
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.read,
            message=message
        )

        missed_message = {
            'message_id': message.id,
            'trigger': 'private_message',
        }
        apn.handle_push_notification(user_profile.id, missed_message)
        mock_push_notifications.assert_called_once()

    def test_deleted_message(self) -> None:
        """Simulates the race where message is deleted before handlingx push notifications"""
        user_profile = self.example_user('hamlet')
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=user_profile,
            flags=UserMessage.flags.read,
            message=message
        )
        missed_message = {
            'message_id': message.id,
            'trigger': 'private_message',
        }
        # Now, delete the message the normal way
        do_delete_message(user_profile, message)

        with mock.patch('zerver.lib.push_notifications.uses_notification_bouncer') as mock_check, \
                mock.patch('logging.error') as mock_logging_error, \
                mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True) as mock_push_notifications:
            apn.handle_push_notification(user_profile.id, missed_message)
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
            message=message
        )
        missed_message = {
            'message_id': message.id,
            'trigger': 'private_message',
        }
        # Now delete the message forcefully, so it just doesn't exist.
        message.delete()

        # This should log an error
        with mock.patch('zerver.lib.push_notifications.uses_notification_bouncer') as mock_check, \
                mock.patch('logging.error') as mock_logging_error, \
                mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True) as mock_push_notifications:
            apn.handle_push_notification(user_profile.id, missed_message)
            mock_push_notifications.assert_called_once()
            # Check we didn't proceed through.
            mock_check.assert_not_called()
            mock_logging_error.assert_called_once()

    def test_send_notifications_to_bouncer(self) -> None:
        user_profile = self.example_user('hamlet')
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=user_profile,
            message=message
        )

        missed_message = {
            'message_id': message.id,
            'trigger': 'private_message',
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

    def test_non_bouncer_push(self) -> None:
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
            'trigger': 'private_message',
        }
        with mock.patch('zerver.lib.push_notifications.get_apns_payload',
                        return_value={'apns': True}), \
                mock.patch('zerver.lib.push_notifications.get_gcm_payload',
                           return_value={'gcm': True}), \
                mock.patch('zerver.lib.push_notifications'
                           '.send_apple_push_notification') as mock_send_apple, \
                mock.patch('zerver.lib.push_notifications'
                           '.send_android_push_notification') as mock_send_android, \
                mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True) as mock_push_notifications:

            apn.handle_push_notification(self.user_profile.id, missed_message)
            mock_send_apple.assert_called_with(self.user_profile.id,
                                               apple_devices,
                                               {'apns': True})
            mock_send_android.assert_called_with(android_devices,
                                                 {'gcm': True})
            mock_push_notifications.assert_called_once()

    @override_settings(SEND_REMOVE_PUSH_NOTIFICATIONS=True)
    def test_send_remove_notifications_to_bouncer(self) -> None:
        user_profile = self.example_user('hamlet')
        message = self.get_message(Recipient.PERSONAL, type_id=1)
        UserMessage.objects.create(
            user_profile=user_profile,
            message=message
        )

        with self.settings(PUSH_NOTIFICATION_BOUNCER_URL=True), \
                mock.patch('zerver.lib.push_notifications'
                           '.send_notifications_to_bouncer') as mock_send_android, \
                mock.patch('zerver.lib.push_notifications.get_common_payload',
                           return_value={'gcm': True}):
            apn.handle_remove_push_notification(user_profile.id, message.id)
            mock_send_android.assert_called_with(user_profile.id, {},
                                                 {'gcm': True,
                                                  'event': 'remove',
                                                  'zulip_message_id': message.id})

    @override_settings(SEND_REMOVE_PUSH_NOTIFICATIONS=True)
    def test_non_bouncer_push_remove(self) -> None:
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

        with mock.patch('zerver.lib.push_notifications'
                        '.send_android_push_notification') as mock_send_android, \
                mock.patch('zerver.lib.push_notifications.get_common_payload',
                           return_value={'gcm': True}):
            apn.handle_remove_push_notification(self.user_profile.id, message.id)
            mock_send_android.assert_called_with(android_devices,
                                                 {'gcm': True,
                                                  'event': 'remove',
                                                  'zulip_message_id': message.id})

    def test_user_message_does_not_exist(self) -> None:
        """This simulates a condition that should only be an error if the user is
        not long-term idle; we fake it, though, in the sense that the user should
        not have received the message in the first place"""
        self.make_stream('public_stream')
        message_id = self.send_stream_message("iago@zulip.com", "public_stream", "test")
        missed_message = {'message_id': message_id}
        with mock.patch('zerver.lib.push_notifications.logger.error') as mock_logger, \
                mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True) as mock_push_notifications:
            apn.handle_push_notification(self.user_profile.id, missed_message)
            mock_logger.assert_called_with("Could not find UserMessage with "
                                           "message_id %s and user_id %s" %
                                           (message_id, self.user_profile.id,))
            mock_push_notifications.assert_called_once()

    def test_user_message_soft_deactivated(self) -> None:
        """This simulates a condition that should only be an error if the user is
        not long-term idle; we fake it, though, in the sense that the user should
        not have received the message in the first place"""
        self.make_stream('public_stream')
        self.subscribe(self.user_profile, 'public_stream')
        do_soft_deactivate_users([self.user_profile])

        message_id = self.send_stream_message("iago@zulip.com", "public_stream", "test")
        missed_message = {
            'message_id': message_id,
            'trigger': 'stream_push_notify',
        }

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

        with mock.patch('zerver.lib.push_notifications.get_apns_payload',
                        return_value={'apns': True}), \
                mock.patch('zerver.lib.push_notifications.get_gcm_payload',
                           return_value={'gcm': True}), \
                mock.patch('zerver.lib.push_notifications'
                           '.send_apple_push_notification') as mock_send_apple, \
                mock.patch('zerver.lib.push_notifications'
                           '.send_android_push_notification') as mock_send_android, \
                mock.patch('zerver.lib.push_notifications.logger.error') as mock_logger, \
                mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True) as mock_push_notifications:
            apn.handle_push_notification(self.user_profile.id, missed_message)
            mock_logger.assert_not_called()
            mock_send_apple.assert_called_with(self.user_profile.id,
                                               apple_devices,
                                               {'apns': True})
            mock_send_android.assert_called_with(android_devices,
                                                 {'gcm': True})
            mock_push_notifications.assert_called_once()

class TestAPNs(PushNotificationTest):
    def devices(self) -> List[DeviceToken]:
        return list(PushDeviceToken.objects.filter(
            user=self.user_profile, kind=PushDeviceToken.APNS))

    def send(self, devices: Optional[List[PushDeviceToken]]=None,
             payload_data: Dict[str, Any]={}) -> None:
        if devices is None:
            devices = self.devices()
        apn.send_apple_push_notification(
            self.user_profile.id, devices, payload_data)

    def test_get_apns_client(self) -> None:
        """This test is pretty hacky, and needs to carefully reset the state
        it modifies in order to avoid leaking state that can lead to
        nondeterministic results for other tests.
        """
        import zerver.lib.push_notifications
        zerver.lib.push_notifications._apns_client_initialized = False
        with self.settings(APNS_CERT_FILE='/foo.pem'), \
                mock.patch('apns2.client.APNsClient') as mock_client:
            client = get_apns_client()
            self.assertEqual(mock_client.return_value, client)
        # Reset the values set by `get_apns_client` so that we don't
        # leak changes to the rest of the world.
        zerver.lib.push_notifications._apns_client_initialized = False
        zerver.lib.push_notifications._apns_client = None

    def test_not_configured(self) -> None:
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
        import hyper
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
            apn.modernize_apns_payload(
                {'alert': 'Message from Hamlet',
                 'message_ids': [3]}),
            payload)
        self.assertEqual(
            apn.modernize_apns_payload(payload),
            payload)

class TestGetAPNsPayload(PushNotificationTest):
    def test_get_apns_payload_personal_message(self) -> None:
        user_profile = self.example_user("othello")
        message_id = self.send_personal_message(
            self.example_email('hamlet'),
            self.example_email('othello'),
            'Content of personal message',
        )
        message = Message.objects.get(id=message_id)
        message.trigger = 'private_message'
        payload = apn.get_apns_payload(user_profile, message)
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
                    'sender_email': 'hamlet@zulip.com',
                    'sender_id': 4,
                    'server': settings.EXTERNAL_HOST,
                    'realm_id': message.sender.realm.id,
                    'realm_uri': message.sender.realm.uri,
                }
            }
        }
        self.assertDictEqual(payload, expected)

    @mock.patch('zerver.lib.push_notifications.push_notifications_enabled', return_value = True)
    def test_get_apns_payload_huddle_message(self, mock_push_notifications: mock.MagicMock) -> None:
        user_profile = self.example_user("othello")
        message_id = self.send_huddle_message(
            self.sender.email,
            [self.example_email('othello'), self.example_email('cordelia')])
        message = Message.objects.get(id=message_id)
        message.trigger = 'private_message'
        payload = apn.get_apns_payload(user_profile, message)
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
                    'sender_email': 'hamlet@zulip.com',
                    'sender_id': 4,
                    'server': settings.EXTERNAL_HOST,
                    'realm_id': message.sender.realm.id,
                    'realm_uri': message.sender.realm.uri,
                }
            }
        }
        self.assertDictEqual(payload, expected)
        mock_push_notifications.assert_called()

    def test_get_apns_payload_stream_message(self):
        # type: () -> None
        user_profile = self.example_user("hamlet")
        stream = Stream.objects.filter(name='Verona').get()
        message = self.get_message(Recipient.STREAM, stream.id)
        message.trigger = 'push_stream_notify'
        message.stream_name = 'Verona'
        payload = apn.get_apns_payload(user_profile, message)
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
                    'sender_email': 'hamlet@zulip.com',
                    'sender_id': 4,
                    "stream": apn.get_display_recipient(message.recipient),
                    "topic": message.topic_name(),
                    'server': settings.EXTERNAL_HOST,
                    'realm_id': message.sender.realm.id,
                    'realm_uri': message.sender.realm.uri,
                }
            }
        }
        self.assertDictEqual(payload, expected)

    def test_get_apns_payload_stream_mention(self):
        # type: () -> None
        user_profile = self.example_user("othello")
        stream = Stream.objects.filter(name='Verona').get()
        message = self.get_message(Recipient.STREAM, stream.id)
        message.trigger = 'mentioned'
        message.stream_name = 'Verona'
        payload = apn.get_apns_payload(user_profile, message)
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
                    'sender_email': 'hamlet@zulip.com',
                    'sender_id': 4,
                    "stream": apn.get_display_recipient(message.recipient),
                    "topic": message.topic_name(),
                    'server': settings.EXTERNAL_HOST,
                    'realm_id': message.sender.realm.id,
                    'realm_uri': message.sender.realm.uri,
                }
            }
        }
        self.assertDictEqual(payload, expected)

    @override_settings(PUSH_NOTIFICATION_REDACT_CONTENT = True)
    def test_get_apns_payload_redacted_content(self) -> None:
        user_profile = self.example_user("othello")
        message_id = self.send_huddle_message(
            self.sender.email,
            [self.example_email('othello'), self.example_email('cordelia')])
        message = Message.objects.get(id=message_id)
        message.trigger = 'private_message'
        payload = apn.get_apns_payload(user_profile, message)
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
                    'sender_email': self.example_email("hamlet"),
                    'sender_id': 4,
                    'server': settings.EXTERNAL_HOST,
                    'realm_id': message.sender.realm.id,
                    'realm_uri': message.sender.realm.uri,
                }
            }
        }
        self.assertDictEqual(payload, expected)

class TestGetGCMPayload(PushNotificationTest):
    def test_get_gcm_payload(self) -> None:
        stream = Stream.objects.filter(name='Verona').get()
        message = self.get_message(Recipient.STREAM, stream.id)
        message.content = 'a' * 210
        message.rendered_content = 'a' * 210
        message.save()
        message.trigger = 'mentioned'

        user_profile = self.example_user('hamlet')
        payload = apn.get_gcm_payload(user_profile, message)
        expected = {
            "user": user_profile.email,
            "event": "message",
            "alert": "New mention from King Hamlet",
            "zulip_message_id": message.id,
            "time": apn.datetime_to_timestamp(message.pub_date),
            "content": 'a' * 200 + '…',
            "content_truncated": True,
            "server": settings.EXTERNAL_HOST,
            "realm_id": self.example_user("hamlet").realm.id,
            "realm_uri": self.example_user("hamlet").realm.uri,
            "sender_id": self.example_user("hamlet").id,
            "sender_email": self.example_email("hamlet"),
            "sender_full_name": "King Hamlet",
            "sender_avatar_url": apn.absolute_avatar_url(message.sender),
            "recipient_type": "stream",
            "stream": apn.get_display_recipient(message.recipient),
            "topic": message.topic_name(),
        }
        self.assertDictEqual(payload, expected)

    def test_get_gcm_payload_personal(self) -> None:
        message = self.get_message(Recipient.PERSONAL, 1)
        message.trigger = 'private_message'
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
            "server": settings.EXTERNAL_HOST,
            "realm_id": self.example_user("hamlet").realm.id,
            "realm_uri": self.example_user("hamlet").realm.uri,
            "sender_id": self.example_user("hamlet").id,
            "sender_email": self.example_email("hamlet"),
            "sender_full_name": "King Hamlet",
            "sender_avatar_url": apn.absolute_avatar_url(message.sender),
            "recipient_type": "private",
        }
        self.assertDictEqual(payload, expected)

    def test_get_gcm_payload_stream_notifications(self) -> None:
        message = self.get_message(Recipient.STREAM, 1)
        message.trigger = 'stream_push_notify'
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
            "server": settings.EXTERNAL_HOST,
            "realm_id": self.example_user("hamlet").realm.id,
            "realm_uri": self.example_user("hamlet").realm.uri,
            "sender_id": self.example_user("hamlet").id,
            "sender_email": self.example_email("hamlet"),
            "sender_full_name": "King Hamlet",
            "sender_avatar_url": apn.absolute_avatar_url(message.sender),
            "recipient_type": "stream",
            "topic": "Test Topic",
            "stream": "Denmark"
        }
        self.assertDictEqual(payload, expected)

    @override_settings(PUSH_NOTIFICATION_REDACT_CONTENT = True)
    def test_get_gcm_payload_redacted_content(self) -> None:
        message = self.get_message(Recipient.STREAM, 1)
        message.trigger = 'stream_push_notify'
        message.stream_name = 'Denmark'
        user_profile = self.example_user('hamlet')
        payload = apn.get_gcm_payload(user_profile, message)
        expected = {
            "user": user_profile.email,
            "event": "message",
            "alert": "New stream message from King Hamlet in Denmark",
            "zulip_message_id": message.id,
            "time": apn.datetime_to_timestamp(message.pub_date),
            "content": "***REDACTED***",
            "content_truncated": False,
            "server": settings.EXTERNAL_HOST,
            "realm_id": self.example_user("hamlet").realm.id,
            "realm_uri": self.example_user("hamlet").realm.uri,
            "sender_id": self.example_user("hamlet").id,
            "sender_email": self.example_email("hamlet"),
            "sender_full_name": "King Hamlet",
            "sender_avatar_url": apn.absolute_avatar_url(message.sender),
            "recipient_type": "stream",
            "topic": "Test Topic",
            "stream": "Denmark"
        }
        self.assertDictEqual(payload, expected)


class TestSendNotificationsToBouncer(ZulipTestCase):
    @mock.patch('zerver.lib.push_notifications.send_to_push_bouncer')
    def test_send_notifications_to_bouncer(self, mock_send: mock.MagicMock) -> None:
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

class Result:
    def __init__(self, status: int=200, content: str=ujson.dumps({'msg': 'error'})) -> None:
        self.status_code = status
        self.content = content

class TestSendToPushBouncer(PushNotificationTest):
    @mock.patch('requests.request', return_value=Result(status=500))
    def test_500_error(self, mock_request: mock.MagicMock) -> None:
        with self.assertRaises(PushNotificationBouncerException) as exc:
            apn.send_to_push_bouncer('register', 'register', {'data': True})
        self.assertEqual(str(exc.exception),
                         'Received 500 from push notification bouncer')

    @mock.patch('requests.request', return_value=Result(status=400))
    def test_400_error(self, mock_request: mock.MagicMock) -> None:
        with self.assertRaises(apn.JsonableError) as exc:
            apn.send_to_push_bouncer('register', 'register', {'msg': True})
        self.assertEqual(exc.exception.msg, 'error')

    def test_400_error_invalid_server_key(self) -> None:
        from zerver.decorator import InvalidZulipServerError
        # This is the exception our decorator uses for an invalid Zulip server
        error_obj = InvalidZulipServerError("testRole")
        with mock.patch('requests.request',
                        return_value=Result(status=400,
                                            content=ujson.dumps(error_obj.to_json()))):
            with self.assertRaises(PushNotificationBouncerException) as exc:
                apn.send_to_push_bouncer('register', 'register', {'msg': True})
        self.assertEqual(str(exc.exception),
                         'Push notifications bouncer error: '
                         'Zulip server auth failure: testRole is not registered')

    @mock.patch('requests.request', return_value=Result(status=400, content='/'))
    def test_400_error_when_content_is_not_serializable(self, mock_request: mock.MagicMock) -> None:
        with self.assertRaises(ValueError) as exc:
            apn.send_to_push_bouncer('register', 'register', {'msg': True})
        self.assertEqual(str(exc.exception),
                         'Expected object or value')

    @mock.patch('requests.request', return_value=Result(status=300, content='/'))
    def test_300_error(self, mock_request: mock.MagicMock) -> None:
        with self.assertRaises(PushNotificationBouncerException) as exc:
            apn.send_to_push_bouncer('register', 'register', {'msg': True})
        self.assertEqual(str(exc.exception),
                         'Push notification bouncer returned unexpected status code 300')

class TestNumPushDevicesForUser(PushNotificationTest):
    def test_when_kind_is_none(self) -> None:
        self.assertEqual(apn.num_push_devices_for_user(self.user_profile), 2)

    def test_when_kind_is_not_none(self) -> None:
        count = apn.num_push_devices_for_user(self.user_profile,
                                              kind=PushDeviceToken.APNS)
        self.assertEqual(count, 2)

class TestPushApi(ZulipTestCase):
    def test_push_api(self) -> None:
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
    def setUp(self) -> None:
        super().setUp()
        apn.gcm = gcm.GCM('fake key')
        self.gcm_tokens = [u'1111', u'2222']
        for token in self.gcm_tokens:
            PushDeviceToken.objects.create(
                kind=PushDeviceToken.GCM,
                token=apn.hex_to_b64(token),
                user=self.user_profile,
                ios_app_id=None)

    def get_gcm_data(self, **kwargs: Any) -> Dict[str, Any]:
        data = {
            'key 1': 'Data 1',
            'key 2': 'Data 2',
        }
        data.update(kwargs)
        return data

class GCMNotSetTest(GCMTest):
    @mock.patch('zerver.lib.push_notifications.logger.debug')
    def test_gcm_is_none(self, mock_debug: mock.MagicMock) -> None:
        apn.gcm = None
        apn.send_android_push_notification_to_user(self.user_profile, {})
        mock_debug.assert_called_with(
            "Skipping sending a GCM push notification since PUSH_NOTIFICATION_BOUNCER_URL "
            "and ANDROID_GCM_API_KEY are both unset")

class GCMIOErrorTest(GCMTest):
    @mock.patch('zerver.lib.push_notifications.gcm.json_request')
    @mock.patch('zerver.lib.push_notifications.logger.warning')
    def test_json_request_raises_ioerror(self, mock_warn: mock.MagicMock,
                                         mock_json_request: mock.MagicMock) -> None:
        mock_json_request.side_effect = IOError('error')
        apn.send_android_push_notification_to_user(self.user_profile, {})
        mock_warn.assert_called_with('error')

class GCMSuccessTest(GCMTest):
    @mock.patch('zerver.lib.push_notifications.logger.warning')
    @mock.patch('zerver.lib.push_notifications.logger.info')
    @mock.patch('gcm.GCM.json_request')
    def test_success(self, mock_send: mock.MagicMock, mock_info: mock.MagicMock,
                     mock_warning: mock.MagicMock) -> None:
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
    @mock.patch('zerver.lib.push_notifications.logger.warning')
    @mock.patch('gcm.GCM.json_request')
    def test_equal(self, mock_send: mock.MagicMock, mock_warning: mock.MagicMock) -> None:
        res = {}
        res['canonical'] = {1: 1}
        mock_send.return_value = res

        data = self.get_gcm_data()
        apn.send_android_push_notification_to_user(self.user_profile, data)
        mock_warning.assert_called_once_with("GCM: Got canonical ref but it "
                                             "already matches our ID 1!")

    @mock.patch('zerver.lib.push_notifications.logger.warning')
    @mock.patch('gcm.GCM.json_request')
    def test_pushdevice_not_present(self, mock_send: mock.MagicMock,
                                    mock_warning: mock.MagicMock) -> None:
        res = {}
        t1 = apn.hex_to_b64(u'1111')
        t2 = apn.hex_to_b64(u'3333')
        res['canonical'] = {t1: t2}
        mock_send.return_value = res

        def get_count(hex_token: str) -> int:
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

    @mock.patch('zerver.lib.push_notifications.logger.info')
    @mock.patch('gcm.GCM.json_request')
    def test_pushdevice_different(self, mock_send: mock.MagicMock,
                                  mock_info: mock.MagicMock) -> None:
        res = {}
        old_token = apn.hex_to_b64(u'1111')
        new_token = apn.hex_to_b64(u'2222')
        res['canonical'] = {old_token: new_token}
        mock_send.return_value = res

        def get_count(hex_token: str) -> int:
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
    @mock.patch('zerver.lib.push_notifications.logger.info')
    @mock.patch('gcm.GCM.json_request')
    def test_not_registered(self, mock_send: mock.MagicMock, mock_info: mock.MagicMock) -> None:
        res = {}
        token = apn.hex_to_b64(u'1111')
        res['errors'] = {'NotRegistered': [token]}
        mock_send.return_value = res

        def get_count(hex_token: str) -> int:
            token = apn.hex_to_b64(hex_token)
            return PushDeviceToken.objects.filter(
                token=token, kind=PushDeviceToken.GCM).count()

        self.assertEqual(get_count(u'1111'), 1)

        data = self.get_gcm_data()
        apn.send_android_push_notification_to_user(self.user_profile, data)
        mock_info.assert_called_once_with("GCM: Removing %s" % (token,))
        self.assertEqual(get_count(u'1111'), 0)

class GCMFailureTest(GCMTest):
    @mock.patch('zerver.lib.push_notifications.logger.warning')
    @mock.patch('gcm.GCM.json_request')
    def test_failure(self, mock_send: mock.MagicMock, mock_warn: mock.MagicMock) -> None:
        res = {}
        token = apn.hex_to_b64(u'1111')
        res['errors'] = {'Failed': [token]}
        mock_send.return_value = res

        data = self.get_gcm_data()
        apn.send_android_push_notification_to_user(self.user_profile, data)
        c1 = call("GCM: Delivery to %s failed: Failed" % (token,))
        mock_warn.assert_has_calls([c1], any_order=True)

class TestReceivesNotificationsFunctions(ZulipTestCase):
    def setUp(self) -> None:
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
        fixtures = ujson.loads(self.fixture_data("markdown_test_cases.json"))
        tests = fixtures["regular_tests"]
        for test in tests:
            if "text_content" in test:
                output = get_mobile_push_content(test["expected_output"])
                self.assertEqual(output, test["text_content"])

    def test_backend_only_fixtures(self) -> None:
        fixtures = [
            {
                'name': 'realm_emoji',
                'rendered_content': '<p>Testing <img alt=":green_tick:" class="emoji" src="/user_avatars/1/emoji/green_tick.png" title="green tick"> realm emoji.</p>',
                'expected_output': 'Testing :green_tick: realm emoji.',
            },
            {
                'name': 'mentions',
                'rendered_content': '<p>Mentioning <span class="user-mention" data-user-id="3">@Cordelia Lear</span>.</p>',
                'expected_output': 'Mentioning @Cordelia Lear.',
            },
            {
                'name': 'stream_names',
                'rendered_content': '<p>Testing stream names <a class="stream" data-stream-id="5" href="/#narrow/stream/Verona">#Verona</a>.</p>',
                'expected_output': 'Testing stream names #Verona.',
            },
        ]

        for test in fixtures:
            actual_output = get_mobile_push_content(test["rendered_content"])
            self.assertEqual(actual_output, test["expected_output"])

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
        self.assert_json_error(result, "Zulip server auth failure: key does not match role %s" %
                               (zulip_org_id,))
