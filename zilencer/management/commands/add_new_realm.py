from django.core.management.base import BaseCommand
from zerver.lib.actions import do_create_user, do_create_realm
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.onboarding import send_initial_pms, setup_initial_streams, \
    setup_initial_private_stream, send_initial_realm_messages
from zerver.models import Realm, UserProfile

from typing import Any

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
        send_initial_pms(user)
        setup_initial_private_stream(user)

        send_initial_realm_messages(realm)
