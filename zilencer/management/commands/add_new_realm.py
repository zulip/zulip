from typing import Any

from zerver.lib.actions import bulk_add_subscriptions, do_create_realm, do_create_user
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.onboarding import send_initial_realm_messages
from zerver.models import Realm, UserProfile


class Command(ZulipBaseCommand):
    help = """Add a new realm and initial user for manual testing of the onboarding process."""

    def handle(self, **options: Any) -> None:
        string_id = 'realm%02d' % (
            Realm.objects.filter(string_id__startswith='realm').count(),)
        realm = do_create_realm(string_id, string_id)

        name = '%02d-user' % (
            UserProfile.objects.filter(email__contains='user@').count(),)
        user = do_create_user(f'{name}@{string_id}.zulip.com',
                              'password', realm, name, name, role=UserProfile.ROLE_REALM_ADMINISTRATOR)
        bulk_add_subscriptions([realm.signup_notifications_stream], [user])

        send_initial_realm_messages(realm)
