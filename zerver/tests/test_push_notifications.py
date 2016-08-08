import mock
import time
from typing import Any, Union, SupportsInt

from django.test import TestCase
from django.conf import settings

from zerver.models import PushDeviceToken, UserProfile, Message
from zerver.models import get_user_profile_by_email
from zerver.lib import push_notifications as apn

class MockRedis(object):
    data = {}  # type: Dict[str, Any]

    def hgetall(self, key):
        # type: (str) -> Any
        return self.data.get(key)

    def exists(self, key):
        # type: (str) -> bool
        return key in self.data

    def hmset(self, key, data):
        # type: (str, Dict[Any, Any]) -> None
        self.data[key] = data

    def delete(self, key):
        # type: (str) -> None
        if self.exists(key):
            del self.data[key]

    def expire(self, *args, **kwargs):
        # type: (Any, Any) -> None
        pass

class PushNotificationTest(TestCase):
    def setUp(self):
        # type: () -> None
        email = 'hamlet@zulip.com'
        apn.connection = apn.get_connection('fake-cert', 'fake-key')
        self.redis_client = apn.redis_client = MockRedis()  # type: ignore
        apn.dbx_connection = apn.get_connection('fake-cert', 'fake-key')
        self.user_profile = get_user_profile_by_email(email)
        self.tokens = [u'aaaa', u'bbbb']
        for token in self.tokens:
            PushDeviceToken.objects.create(
                kind=PushDeviceToken.APNS,
                token=apn.hex_to_b64(token),
                user=self.user_profile,
                ios_app_id=settings.ZULIP_IOS_APP_ID)

    def tearDown(self):
        # type: () -> None
        for i in [100, 200]:
            self.redis_client.delete(apn.get_apns_key(i))

class APNsMessageTest(PushNotificationTest):
    @mock.patch('random.getrandbits', side_effect=[100, 200])
    def test_apns_message(self, mock_getrandbits):
        # type: (mock.MagicMock) -> None
        apn.APNsMessage(self.user_profile, self.tokens, alert="test")
        data = self.redis_client.hgetall(apn.get_apns_key(100))
        self.assertEqual(data['token'], 'aaaa')
        self.assertEqual(int(data['user_id']), self.user_profile.id)
        data = self.redis_client.hgetall(apn.get_apns_key(200))
        self.assertEqual(data['token'], 'bbbb')
        self.assertEqual(int(data['user_id']), self.user_profile.id)

class ResponseListenerTest(PushNotificationTest):
    def get_error_response(self, **kwargs):
        # type: (Any) -> Dict[str, SupportsInt]
        er = {'identifier': 0, 'status': 0}  # type: Dict[str, SupportsInt]
        er.update({k: v for k, v in kwargs.items() if k in er})
        return er

    def get_cache_value(self):
        # type: () -> Dict[str, Union[str, int]]
        return {'token': 'aaaa', 'user_id': self.user_profile.id}

    @mock.patch('logging.warn')
    def test_cache_does_not_exist(self, mock_warn):
        # type: (mock.MagicMock) -> None
        err_rsp = self.get_error_response(identifier=100, status=1)
        apn.response_listener(err_rsp)
        msg = "APNs key, apns:100, doesn't not exist."
        mock_warn.assert_called_once_with(msg)

    @mock.patch('logging.warn')
    def test_cache_exists(self, mock_warn):
        # type: (mock.MagicMock) -> None
        self.redis_client.hmset(apn.get_apns_key(100), self.get_cache_value())
        err_rsp = self.get_error_response(identifier=100, status=1)
        apn.response_listener(err_rsp)
        b64_token = apn.hex_to_b64('aaaa')
        errmsg = apn.ERROR_CODES[int(err_rsp['status'])]
        msg = ("APNS: Failed to deliver APNS notification to %s, "
               "reason: %s" % (b64_token, errmsg))
        mock_warn.assert_called_once_with(msg)

    @mock.patch('logging.warn')
    def test_error_code_eight(self, mock_warn):
        # type: (mock.MagicMock) -> None
        self.redis_client.hmset(apn.get_apns_key(100), self.get_cache_value())
        err_rsp = self.get_error_response(identifier=100, status=8)
        b64_token = apn.hex_to_b64('aaaa')
        self.assertEqual(PushDeviceToken.objects.filter(
            user=self.user_profile, token=b64_token).count(), 1)
        apn.response_listener(err_rsp)
        self.assertEqual(mock_warn.call_count, 2)
        self.assertEqual(PushDeviceToken.objects.filter(
            user=self.user_profile, token=b64_token).count(), 0)

class SendNotificationTest(PushNotificationTest):
    @mock.patch('zerver.lib.push_notifications._do_push_to_apns_service')
    def test_send_apple_push_notifiction(self, mock_send):
        # type: (mock.MagicMock) -> None
        def test_send(user, message, alert):
            # type: (UserProfile, Message, str) -> None
            self.assertEqual(user.id, self.user_profile.id)
            self.assertEqual(set(message.tokens), set(self.tokens))

        mock_send.side_effect = test_send
        apn.send_apple_push_notification(self.user_profile, "test alert")
        self.assertEqual(mock_send.call_count, 1)

    @mock.patch('apns.GatewayConnection.send_notification_multiple')
    def test_do_push_to_apns_service(self, mock_push):
        # type: (mock.MagicMock) -> None
        msg = apn.APNsMessage(self.user_profile, self.tokens, alert="test")
        def test_push(message):
            # type: (Message) -> None
            self.assertIs(message, msg.get_frame())

        mock_push.side_effect = test_push
        apn._do_push_to_apns_service(self.user_profile, msg, apn.connection)

    @mock.patch('apns.GatewayConnection.send_notification_multiple')
    def test_connection_single_none(self, mock_push):
        # type: (mock.MagicMock) -> None
        apn.connection = None
        apn.send_apple_push_notification(self.user_profile, "test alert")

    @mock.patch('apns.GatewayConnection.send_notification_multiple')
    def test_connection_both_none(self, mock_push):
        # type: (mock.MagicMock) -> None
        apn.connection = None
        apn.dbx_connection = None
        apn.send_apple_push_notification(self.user_profile, "test alert")

class APNsFeedbackTest(PushNotificationTest):
    @mock.patch('apns.FeedbackConnection.items')
    def test_feedback(self, mock_items):
        # type: (mock.MagicMock) -> None
        update_time = apn.timestamp_to_datetime(int(time.time()) - 10000)
        PushDeviceToken.objects.all().update(last_updated=update_time)
        mock_items.return_value = [
            ('aaaa', int(time.time())),
        ]
        self.assertEqual(PushDeviceToken.objects.all().count(), 2)
        apn.check_apns_feedback()
        self.assertEqual(PushDeviceToken.objects.all().count(), 1)
