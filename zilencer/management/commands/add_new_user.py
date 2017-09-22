from django.core.management.base import BaseCommand, CommandParser
from zerver.lib.actions import do_create_user
from zerver.lib.management import ZulipBaseCommand
from zerver.lib.onboarding import send_initial_pms
from zerver.models import Realm, UserProfile

from typing import Any

class Command(ZulipBaseCommand):
    help = """Add a new user for manual testing of the onboarding process.
If realm is unspecified, will try to use a realm created by add_new_realm,
and will otherwise fall back to the zulip realm."""

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        self.add_realm_args(parser)

    def handle(self, **options):
        # type: (**Any) -> None
        realm = self.get_realm(options)
        if realm is None:
            realm = Realm.objects.filter(string_id__startswith='realm') \
                                 .order_by('-string_id').first()
        if realm is None:
            print('Warning: Using default zulip realm, which has an unusual configuration.\n'
                  'Try running `python manage.py add_new_realm`, and then running this again.')
            realm = Realm.objects.get(string_id='zulip')
            domain = 'zulip.com'
        else:
            domain = realm.string_id + '.zulip.com'

        name = '%02d-user' % (UserProfile.objects.filter(email__contains='user@').count(),)
        user = do_create_user('%s@%s' % (name, domain),
                              'password', realm, name, name)
        send_initial_pms(user)
