from typing import Any

from zerver.lib.actions import do_create_realm, do_create_user
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.onboarding import send_initial_realm_messages, \
    setup_initial_private_stream, setup_initial_streams
from zerver.models import Realm, UserProfile

class Command(ZulipBaseCommand):
    help = """Add a new realm and initial user for manual testing of the onboarding process."""

    def handle(self, **options):
        # type: (**Any) -> None
        string_id = 'realm%02d' % (
            Realm.objects.filter(string_id__startswith='realm').count(),)
        realm = do_create_realm(string_id, string_id)
        setup_initial_streams(realm)

        name = '%02d-user' % (
            UserProfile.objects.filter(email__contains='user@').count(),)
        user = do_create_user('%s@%s.zulip.com' % (name, string_id),
                              'password', realm, name, name, is_realm_admin=True)
        setup_initial_private_stream(user)

        send_initial_realm_messages(realm)
