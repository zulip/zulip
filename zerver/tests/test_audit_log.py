
from django.utils import timezone

from zerver.lib.actions import do_create_user, do_deactivate_user, \
    do_activate_user, do_reactivate_user
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import RealmAuditLog, get_realm

from datetime import timedelta

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
