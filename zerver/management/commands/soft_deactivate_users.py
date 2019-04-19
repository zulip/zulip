import sys
from argparse import ArgumentParser
from typing import Any, Dict, List

from django.conf import settings
from django.core.management.base import CommandError

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.soft_deactivation import do_soft_activate_users, \
    do_soft_deactivate_users, do_auto_soft_deactivate_users, logger
from zerver.models import Realm, UserProfile

def get_users_from_emails(emails: Any,
                          filter_kwargs: Any) -> List[UserProfile]:
    users = UserProfile.objects.filter(
        email__in=emails,
        **filter_kwargs)

    if len(users) != len(emails):
        user_emails_found = {user.email for user in users}
        user_emails_not_found = '\n'.join(set(emails) - user_emails_found)
        raise CommandError('Users with the following emails were not found:\n\n%s\n\n'
                           'Check if they are correct.' % (user_emails_not_found,))
    return users

class Command(ZulipBaseCommand):
    help = """Soft activate/deactivate users. Users are recognised by their emails here."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser)
        parser.add_argument('-d', '--deactivate',
                            dest='deactivate',
                            action='store_true',
                            default=False,
                            help='Used to deactivate user/users.')
        parser.add_argument('-a', '--activate',
                            dest='activate',
                            action='store_true',
                            default=False,
                            help='Used to activate user/users.')
        parser.add_argument('--inactive-for',
                            type=int,
                            default=28,
                            help='Number of days of inactivity before soft-deactivation')
        parser.add_argument('users', metavar='<users>', type=str, nargs='*', default=[],
                            help="A list of user emails to soft activate/deactivate.")

    def handle(self, *args: Any, **options: str) -> None:
        if settings.STAGING:
            print('This is a Staging server. Suppressing management command.')
            sys.exit(0)

        realm = self.get_realm(options)
        user_emails = options['users']  # type: ignore  # mypy thinks this is a str, not List[str] #
        activate = options['activate']
        deactivate = options['deactivate']

        filter_kwargs = {}  # type: Dict[str, Realm]
        if realm is not None:
            filter_kwargs = dict(realm=realm)

        if activate:
            if not user_emails:
                print('You need to specify at least one user to use the activate option.')
                self.print_help("./manage.py", "soft_deactivate_users")
                sys.exit(1)

            users_to_activate = get_users_from_emails(user_emails, filter_kwargs)
            users_activated = do_soft_activate_users(users_to_activate)
            logger.info('Soft Reactivated %d user(s)' % (len(users_activated),))

        elif deactivate:
            if user_emails:
                users_to_deactivate = get_users_from_emails(user_emails, filter_kwargs)
                print('Soft deactivating forcefully...')
                users_deactivated = do_soft_deactivate_users(users_to_deactivate)
            else:
                users_deactivated = do_auto_soft_deactivate_users(int(options['inactive_for']),
                                                                  realm)
            logger.info('Soft Deactivated %d user(s)' % (len(users_deactivated),))

        else:
            self.print_help("./manage.py", "soft_deactivate_users")
            sys.exit(1)
