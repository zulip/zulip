
from django.utils import timezone

from zerver.lib.actions import do_create_user, do_deactivate_user, \
    do_activate_user, do_reactivate_user, do_change_password, \
    do_change_user_email
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import RealmAuditLog, get_realm

from datetime import timedelta
from django.contrib.auth.password_validation import validate_password

class TestUserActivation(ZulipTestCase):
    def test_user_activation(self):
        # type: () -> None
        realm = get_realm('zulip')
        now = timezone.now()
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

class TestChangePassword(ZulipTestCase):
    def test_change_password(self):
        # type: () -> None
        realm = get_realm('zulip')
        now = timezone.now()
        user = do_create_user('email', 'password', realm, 'full_name', 'short_name')
        password = 'test1'
        do_change_password(user, password)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='user_change_password',
                                                      event_time__gte=now).count(), 1)
        self.assertIsNone(validate_password(password, user))

class TestChangeEmail(ZulipTestCase):
    def test_change_email(self):
        # type: () -> None
        realm = get_realm('zulip')
        now = timezone.now()
        user = do_create_user('email', 'password', realm, 'full_name', 'short_name')
        email = 'test@example.com'
        do_change_user_email(user, email)
        self.assertEqual(RealmAuditLog.objects.filter(event_type='user_email_changed',
                                                      event_time__gte=now).count(), 1)
        self.assertEqual(email, user.email)
