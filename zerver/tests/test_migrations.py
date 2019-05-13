# These are tests for Zulip's database migrations.  System documented at:
#   https://zulip.readthedocs.io/en/latest/subsystems/schema-migrations.html
#
# You can also read
#   https://www.caktusgroup.com/blog/2016/02/02/writing-unit-tests-django-migrations/
# to get a tutorial on the framework that inspired this feature.

from zerver.lib.test_classes import MigrationsTestCase
from zerver.lib.test_helpers import use_db_models
from django.db.migrations.state import StateApps

from zerver.models import get_stream

# Important note: These tests are very expensive, and details of
# Django's database transaction model mean it does not super work to
# have a lot of migrations tested in this file at once; so we usually
# delete the old migration tests when adding a new one, so this file
# always has a single migration test in it as an example.
#
# The error you get with multiple similar tests doing migrations on
# the same table is this (table name may vary):
#
#   django.db.utils.OperationalError: cannot ALTER TABLE
#   "zerver_subscription" because it has pending trigger events
#
# As a result, we generally mark these tests as skipped once they have
# been tested for a migration being merged.

class SubsNotificationSettingsTestCase(MigrationsTestCase):  # nocoverage
    __unittest_skip__ = True

    migrate_from = '0220_subscription_notification_settings'
    migrate_to = '0221_subscription_notifications_data_migration'
    RECIPIENT_PERSONAL = 1
    RECIPIENT_STREAM = 2

    @use_db_models
    def setUpBeforeMigration(self, apps: StateApps) -> None:
        Recipient = apps.get_model('zerver', 'Recipient')
        Subscription = apps.get_model('zerver', 'Subscription')

        iago = self.example_user('iago')
        iago.enable_stream_desktop_notifications = True
        iago.enable_stream_audible_notifications = False
        iago.enable_desktop_notifications = True
        iago.enable_online_push_notifications = True
        iago.enable_sounds = False
        iago.save()

        stream_name = 'Denmark'
        denmark = get_stream(stream_name, iago.realm)
        denmark_recipient = Recipient.objects.get(type=self.RECIPIENT_STREAM, type_id=denmark.id)
        denmark_sub = Subscription.objects.get(user_profile=iago, recipient=denmark_recipient)
        denmark_sub.desktop_notifications = False
        denmark_sub.audible_notifications = False
        denmark_sub.save(update_fields=['desktop_notifications', 'audible_notifications'])

        iago_recipient = Recipient.objects.get(type=self.RECIPIENT_PERSONAL, type_id=iago.id)
        iago_sub = Subscription.objects.get(user_profile=iago, recipient=iago_recipient)
        iago_sub.desktop_notifications = False
        iago_sub.audible_notifications = False
        iago_sub.push_notifications = True
        iago_sub.save(update_fields=['desktop_notifications', 'audible_notifications', 'push_notifications'])

    def test_subs_migrated(self) -> None:
        UserProfile = self.apps.get_model('zerver', 'UserProfile')
        Recipient = self.apps.get_model('zerver', 'Recipient')
        Realm = self.apps.get_model('zerver', 'Realm')
        Subscription = self.apps.get_model('zerver', 'Subscription')
        Stream = self.apps.get_model('zerver', 'Stream')

        realm = Realm.objects.get(string_id='zulip')
        iago = UserProfile.objects.get(email='iago@zulip.com', realm=realm)
        stream_name = 'Denmark'
        denmark = Stream.objects.get(realm=iago.realm, name=stream_name)
        denmark_recipient = Recipient.objects.get(type=self.RECIPIENT_STREAM, type_id=denmark.id)
        denmark_sub = Subscription.objects.get(user_profile=iago, recipient=denmark_recipient)
        self.assertEqual(denmark_sub.desktop_notifications, False)
        self.assertIsNone(denmark_sub.audible_notifications)

        # Zulip ignores subscription's notification related settings for PMs so don't migrate them.
        iago_recipient = Recipient.objects.get(type=self.RECIPIENT_PERSONAL, type_id=iago.id)
        iago_sub = Subscription.objects.get(user_profile=iago, recipient=iago_recipient)
        self.assertEqual(iago_sub.desktop_notifications, False)
        self.assertEqual(iago_sub.audible_notifications, False)
        self.assertEqual(iago_sub.push_notifications, True)
