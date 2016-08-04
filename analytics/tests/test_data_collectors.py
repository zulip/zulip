from django.test import TestCase
from django.utils import timezone

from zerver.models import Realm, UserProfile, Message
from analytics.lib.data_collectors import process_count, process_aggregate_count, \
    get_human_count_by_realm, get_bot_count_by_realm, get_messages_sent_count_by_user
from analytics.lib.interval import TimeInterval

from datetime import timedelta


class TestDataCollectors(TestCase):
    def assertRealmValueEqual(self, rows, value, realm_id = None):
        if realm_id is None:
            realm_id = self.realm_id
        for row in rows:
            if row['realm_id'] == realm_id:
                self.assertEqual(row['value'], value)
                return
        self.assertIn(realm_id, [])

    def setUp(self):
        end = timezone.now() + timedelta(seconds = 1200) # 20 minutes
        self.gauge_interval = TimeInterval('gauge', end)
        self.hour_interval = TimeInterval('hour', end)
        self.day_interval = TimeInterval('day', end)
        self.realm = Realm(domain='analytics.test', name='Realm Test')
        self.realm.save()

    def test_human_and_bot_count_by_realm(self):
        # create a human and bot, and check that is_bot, is_active, and some
        # basic time_interval constraints are being upheld
        human = UserProfile(email = 'email1', realm = self.realm, date_joined = self.end - timedelta(seconds = 7200))
        human.save()
        self.assertRealmValueEqual(get_human_count_by_realm(self.day_interval), 1)
        self.assertRealmValueEqual(get_human_count_by_realm(self.hour_interval), 0)
        self.assertRealmValueEqual(get_bot_count_by_realm(self.day_interval), 0)
        bot = UserProfile(email = 'email2', realm = realm, is_bot = True)
        human.is_active = False
        human.save()
        self.assertRealmValueEqual(get_human_count_by_realm(self.day_interval), 0)
        self.assertRealmValueEqual(get_bot_count_by_realm(self.hour_interval), 1)
        bot.is_active = False
        bot.save()
        self.assertRealmValueEqual(get_bot_count_by_realm(self.hour_interval), 0)

    def test_messages_sent_count_by_user(self):
        user = UserProfile(email = 'email1', realm = self.realm, is_bot=True)
        user.save()
