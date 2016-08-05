import mock
from typing import Any

from django.test import TestCase
from django.conf import settings

from zerver.models import PushDeviceToken, UserProfile
from zerver.models import get_user_profile_by_email
from zerver.lib import push_notifications as apn

class MockRedis(object):
    data = {}  # type: Dict[str, Any]

    def hgetall(self, key):
        return self.data.get(key)

    def exists(self, key):
        return key in self.data

    def hmset(self, key, data):
        self.data[key] = data

    def delete(self, key):
        if self.exists(key):
            del self.data[key]

    def expire(self, *args, **kwargs):
        pass

class PushNotificationTest(TestCase):
    def setUp(self):
        email = 'hamlet@zulip.com'
        apn.connection = apn.get_connection('fake-cert', 'fake-key')
        self.redis_client = apn.redis_client = MockRedis()  # type: ignore
        apn.dbx_connection = apn.get_connection('fake-cert', 'fake-key')
        self.user_profile = get_user_profile_by_email(email)
        self.tokens = ['aaaa', 'bbbb']
        for token in self.tokens:
            PushDeviceToken.objects.create(
                kind=PushDeviceToken.APNS,
                token=apn.hex_to_b64(token),
                user=self.user_profile,
                ios_app_id=settings.ZULIP_IOS_APP_ID)

    def tearDown(self):
        for i in [100, 200]:
            self.redis_client.delete(apn.get_apns_key(i))

class APNsMessageTest(PushNotificationTest):
    @mock.patch('random.getrandbits', side_effect=[100, 200])
    def test_apns_message(self, mock_getrandbits):
        apn.APNsMessage(self.user_profile, self.tokens, alert="test")
        data = self.redis_client.hgetall(apn.get_apns_key(100))
        self.assertEqual(data['token'], 'aaaa')
        self.assertEqual(int(data['user_id']), self.user_profile.id)
        data = self.redis_client.hgetall(apn.get_apns_key(200))
        self.assertEqual(data['token'], 'bbbb')
        self.assertEqual(int(data['user_id']), self.user_profile.id)
