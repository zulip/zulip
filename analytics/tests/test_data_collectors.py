from django.test import TestCase
from django.utils import timezone

from zerver.models import Realm, UserProfile, Message
from analytics.lib.data_collectors import process_count, process_aggregate_count, \
    get_human_count_by_realm, get_bot_count_by_realm, get_messages_sent_count_by_user
from analytics.lib.interval import TimeInterval

from datetime import timedelta

class TestDataCollectors(TestCase):
    def create_user(self, email, **kwargs):
        defaults = {'realm' : self.realm,
                    'full_name' : 'full_name',
                    'short_name' : 'short_name',
                    'pointer' : -1,
                    'last_pointer_updater' : 'seems unused?',
                    'api_key' : '42'}
        for key, value in defaults.items():
            kwargs[key] = kwargs.get(key, value)
        user = UserProfile(email=email, **kwargs)
        user.save()
        return user

    def assertRealmValueEqual(self, rows, value, realm_id = None):
        if realm_id is None:
            realm_id = self.realm_id
        for row in rows:
            if row['realm_id'] == realm_id:
                self.assertEqual(row['value'], value)
                return
        self.assertEqual(0, value)

    def assertUserValueEqual(self, rows, value, user_id = None):
        if user_id is None:
            user_id = self.user_id
        for row in rows:
            if row['userprofile_id'] == user_id:
                self.assertEqual(row['value'], value)
                return
        self.assertIn(user_id, [])

    def setUp(self):
        # almost every test will need a time_interval, realm, and user
        end = timezone.now() + timedelta(seconds = 7200) # 2 hours
        self.day_interval = TimeInterval('day', end, 'hour')
        self.realm = Realm(domain='analytics.test', name='Realm Test')
        self.realm.save()
        # don't pull the realm object back from the database every time we need its id
        self.realm_id = self.realm.id
        self.user = self.create_user('email', date_joined = end - timedelta(seconds = 7200))
        self.user_id = self.user.id

    def test_human_and_bot_count_by_realm(self):
        def assert_user_counts(humans, bots):
            self.assertRealmValueEqual(get_human_count_by_realm(self.day_interval), humans)
            self.assertRealmValueEqual(get_bot_count_by_realm(self.day_interval), bots)
        def set_active_bot(is_active, is_bot):
            self.user.is_active = is_active
            self.user.is_bot = is_bot
            self.user.save(update_fields=['is_active', 'is_bot'])
        # (is_active, is_bot) starts as True, False
        assert_user_counts(1, 0)
        set_active_bot(True, True)
        assert_user_counts(0, 1)
        set_active_bot(False, True)
        assert_user_counts(0, 0)
        set_active_bot(False, False)
        assert_user_counts(0, 0)

    def test_messages_sent_count_by_user(self):
        pass

    def test_aggregate_user_to_realm(self):
        process_count(UserCount, [self.user_id]
