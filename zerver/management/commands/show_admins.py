from argparse import ArgumentParser
from typing import Any

from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Show the admins in a realm."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, required=True)

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        assert realm is not None  # True because of required=True above
        users = realm.get_admin_users()

        if users:
            print('Admins:\n')
            for user in users:
                print('  %s (%s)' % (user.email, user.full_name))
        else:
            print('There are no admins for this realm!')

        print('\nYou can use the "knight" management command to make more users admins.')
        print('\nOr with the --revoke argument, remove admin status from users.')
