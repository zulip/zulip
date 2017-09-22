
from django.utils.timezone import now as timezone_now

from zerver.lib.actions import do_create_user, do_deactivate_user, \
    do_activate_user, do_reactivate_user, do_change_password, \
    do_change_user_email, do_change_avatar_fields, do_change_bot_owner, \
    do_regenerate_api_key, do_change_full_name, do_change_tos_version, \
    bulk_add_subscriptions, bulk_remove_subscriptions
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import RealmAuditLog, get_realm

from datetime import timedelta
from django.contrib.auth.password_validation import validate_password

import ujson

class TestRealmAuditLog(ZulipTestCase):
    def test_user_activation(self):
        # type: () -> None
        realm = get_realm('zulip')
        now = timezone_now()
        user = do_create_user('email', 'password', realm, 'full_name', 'short_name')
        do_deactivate_user(user)
        do_activate_user(user)
        do_deactivate_user(user)
        do_reactivate_user(user)
        self.assertEqual(RealmAuditLog.objects.filter(event_time__gte=now).count(), 5)
        event_types = list(RealmAuditLog.objects.filter(
            realm=realm, acting_user=None, modified_user=user, modified_stream=None,
            event_time__gte=now, event_time__lte=now+timedelta(minutes=60))
            .order_by('event_time').values_list('event_type', flat=True))
        self.assertEqual(event_types, ['user_created', 'user_deactivated', 'user_activated',
                                       'user_deactivated', 'user_reactivated'])

    def test_change_password(self):
        # type: () -> None
        now = timezone_now()
        user = self.example_user('hamlet')
        password = 'test1'
        do_change_password(user, password)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='user_change_password',
                                                      event_time__gte=now).count(), 1)
        self.assertIsNone(validate_password(password, user))

    def test_change_email(self):
        # type: () -> None
        now = timezone_now()
        user = self.example_user('hamlet')
        email = 'test@example.com'
        do_change_user_email(user, email)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='user_email_changed',
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(email, user.email)

        # Test the RealmAuditLog stringification
        audit_entry = RealmAuditLog.objects.get(event_type='user_email_changed', event_time__gte=now)
        self.assertTrue(str(audit_entry).startswith("<RealmAuditLog: <UserProfile: test@example.com <Realm: zulip 1>> user_email_changed "))

    def test_change_avatar_source(self):
        # type: () -> None
        now = timezone_now()
        user = self.example_user('hamlet')
        avatar_source = u'G'
        do_change_avatar_fields(user, avatar_source)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='user_change_avatar_source',
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(avatar_source, user.avatar_source)

    def test_change_full_name(self):
        # type: () -> None
        start = timezone_now()
        new_name = 'George Hamletovich'
        self.login(self.example_email("iago"))
        req = dict(full_name=ujson.dumps(new_name))
        result = self.client_patch('/json/users/hamlet@zulip.com', req)
        self.assertTrue(result.status_code == 200)
        query = RealmAuditLog.objects.filter(event_type='user_full_name_changed',
                                             event_time__gte=start)
        self.assertEqual(query.count(), 1)

    def test_change_tos_version(self):
        # type: () -> None
        now = timezone_now()
        user = self.example_user("hamlet")
        tos_version = 'android'
        do_change_tos_version(user, tos_version)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='user_tos_version_changed',
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(tos_version, user.tos_version)

    def test_change_bot_owner(self):
        # type: () -> None
        now = timezone_now()
        admin = self.example_user('iago')
        bot = self.notification_bot()
        bot_owner = self.example_user('hamlet')
        do_change_bot_owner(bot, bot_owner, admin)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='bot_owner_changed',
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(bot_owner, bot.bot_owner)

    def test_regenerate_api_key(self):
        # type: () -> None
        now = timezone_now()
        user = self.example_user('hamlet')
        do_regenerate_api_key(user, user)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='user_api_key_changed',
                                                      event_time__gte=now).count(), 1)
        self.assertTrue(user.api_key)

    def test_subscriptions(self):
        # type: () -> None
        now = timezone_now()
        user = [self.example_user('hamlet')]
        stream = [self.make_stream('test_stream')]

        bulk_add_subscriptions(stream, user)
        subscription_creation_logs = RealmAuditLog.objects.filter(event_type='subscription_created',
                                                                  event_time__gte=now)
        self.assertEqual(subscription_creation_logs.count(), 1)
        self.assertEqual(subscription_creation_logs[0].modified_stream, stream[0])
        self.assertEqual(subscription_creation_logs[0].modified_user, user[0])

        bulk_remove_subscriptions(user, stream)
        subscription_deactivation_logs = RealmAuditLog.objects.filter(event_type='subscription_deactivated',
                                                                      event_time__gte=now)
        self.assertEqual(subscription_deactivation_logs.count(), 1)
        self.assertEqual(subscription_deactivation_logs[0].modified_stream, stream[0])
        self.assertEqual(subscription_deactivation_logs[0].modified_user, user[0])
