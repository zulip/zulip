from __future__ import absolute_import
from __future__ import print_function

from django.db import connection
from django.utils.timezone import now as timezone_now

from typing import Any, List
from argparse import ArgumentParser
from six.moves import map
import sys

from zerver.models import UserProfile, UserMessage, Realm, RealmAuditLog
from zerver.lib.soft_deactivation import (
    do_soft_deactivate_users, do_soft_activate_users,
    get_users_for_soft_deactivation
)
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Soft activate/deactivate users. Users are recognised by there emails here."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        self.add_realm_args(parser, True)
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
                            help='Specify the number of days of user inactivity that user should be marked soft_deactviated')
        parser.add_argument('users', metavar='<users>', type=str, nargs='*', default=[],
                            help="This option can be used to specify a list of user emails to soft activate/deactivate.")

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        realm = self.get_realm(options)
        user_emails = options['users']
        activate = options['activate']
        deactivate = options['deactivate']
        if activate:
            if not user_emails:
                print('You need to specify at least one user to use the activate option.')
                self.print_help("./manage.py", "soft_activate_deactivate_users")
                sys.exit(1)
            users_to_activate = list(UserProfile.objects.filter(
                realm=realm,
                email__in=user_emails))
            do_soft_activate_users(users_to_activate)
        elif deactivate:
            if user_emails:
                print('Soft deactivating forcefully...')
                users_to_deactivate = list(UserProfile.objects.filter(
                    realm=realm,
                    email__in=user_emails))
            else:
                users_to_deactivate = get_users_for_soft_deactivation(realm, int(options['inactive_for']))

            if users_to_deactivate:
                do_soft_deactivate_users(users_to_deactivate)
        else:
            self.print_help("./manage.py", "soft_activate_deactivate_users")
            sys.exit(1)
