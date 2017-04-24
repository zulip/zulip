
from django.utils.timezone import now as timezone_now

from zerver.lib.actions import do_create_user, do_deactivate_user, \
    do_activate_user, do_reactivate_user, do_change_password, \
    do_change_user_email, do_change_avatar_fields, do_change_bot_owner, \
    do_change_full_name, do_change_tos_version

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import RealmAuditLog, get_realm, get_user_profile_by_email

from datetime import timedelta
from django.contrib.auth.password_validation import validate_password

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
        user = get_user_profile_by_email("hamlet@zulip.com")
        password = 'test1'
        do_change_password(user, password)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='user_change_password',
                                                      event_time__gte=now).count(), 1)
        self.assertIsNone(validate_password(password, user))

    def test_change_email(self):
        # type: () -> None
        now = timezone_now()
        user = get_user_profile_by_email("hamlet@zulip.com")
        email = 'test@example.com'
        do_change_user_email(user, email)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='user_email_changed',
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(email, user.email)

    def test_change_avatar_source(self):
        # type: () -> None
        now = timezone_now()
        user = get_user_profile_by_email("hamlet@zulip.com")
        avatar_source = u'G'
        do_change_avatar_fields(user, avatar_source)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='user_avatar_source_changed',
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(avatar_source, user.avatar_source)

    def test_change_full_name(self):
        # type: () -> None
        now = timezone.now()
        user = get_user_profile_by_email("hamlet@zulip.com")
        full_name = 'George Hamletovich'
        do_change_full_name(user, full_name, user)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='user_full_name_changed',
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(full_name, user.full_name)

    def test_change_tos_version(self):
        # type: () -> None
        now = timezone.now()
        user = get_user_profile_by_email("hamlet@zulip.com")
        tos_version = 'android'
        do_change_tos_version(user, tos_version)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='user_tos_version_changed',
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(tos_version, user.tos_version)

    def test_change_bot_owner(self):
        # type: () -> None
        now = timezone_now()
        admin = get_user_profile_by_email('iago@zulip.com')
        bot = get_user_profile_by_email("notification-bot@zulip.com")
        bot_owner = get_user_profile_by_email("hamlet@zulip.com")
        do_change_bot_owner(bot, bot_owner, admin)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='bot_owner_changed',
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(bot_owner, bot.bot_owner)
