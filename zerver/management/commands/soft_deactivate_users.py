
import sys
from argparse import ArgumentParser
from typing import Any, Dict

from django.conf import settings

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.soft_deactivation import do_soft_activate_users, \
    do_soft_deactivate_users, get_users_for_soft_deactivation, logger
from zerver.models import Realm, UserProfile

class Command(ZulipBaseCommand):
    help = """Soft activate/deactivate users. Users are recognised by there emails here."""

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
        user_emails = options['users']
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

            users_to_activate = UserProfile.objects.filter(
                email__in=user_emails,
                **filter_kwargs
            )
            users_to_activate = list(users_to_activate)

            if len(users_to_activate) != len(user_emails):
                user_emails_found = [user.email for user in users_to_activate]
                for user in user_emails:
                    if user not in user_emails_found:
                        raise Exception('User with email %s was not found. '
                                        'Check if the email is correct.' % (user))

            users_activated = do_soft_activate_users(users_to_activate)
            logger.info('Soft Reactivated %d user(s)' % (len(users_activated)))
        elif deactivate:
            if user_emails:
                users_to_deactivate = UserProfile.objects.filter(
                    email__in=user_emails,
                    **filter_kwargs
                )
                users_to_deactivate = list(users_to_deactivate)

                if len(users_to_deactivate) != len(user_emails):
                    user_emails_found = [user.email for user in users_to_deactivate]
                    for user in user_emails:
                        if user not in user_emails_found:
                            raise Exception('User with email %s was not found. '
                                            'Check if the email is correct.' % (user,))
                print('Soft deactivating forcefully...')
            else:
                if realm is not None:
                    filter_kwargs = dict(user_profile__realm=realm)
                users_to_deactivate = get_users_for_soft_deactivation(int(options['inactive_for']),
                                                                      filter_kwargs)

            if users_to_deactivate:
                users_deactivated = do_soft_deactivate_users(users_to_deactivate)
                logger.info('Soft Deactivated %d user(s)' % (len(users_deactivated)))
        else:
            self.print_help("./manage.py", "soft_deactivate_users")
            sys.exit(1)
