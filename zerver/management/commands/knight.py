from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError

from zerver.lib.actions import do_change_is_api_super_user, do_change_user_role
from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile


class Command(ZulipBaseCommand):
    help = """Give an existing user administrative permissions over their (own) Realm.

ONLY perform this on customer request from an authorized person.
"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('-f', '--for-real',
                            dest='ack',
                            action="store_true",
                            help='Acknowledgement that this is done according to policy.')
        parser.add_argument('--revoke',
                            dest='grant',
                            action="store_false",
                            help='Remove an administrator\'s rights.')
        parser.add_argument('--permission',
                            default='administer',
                            choices=['administer', 'api_super_user'],
                            help='Permission to grant/remove.')
        parser.add_argument('email', metavar='<email>',
                            help="email of user to knight")
        self.add_realm_args(parser, True)

    def handle(self, *args: Any, **options: Any) -> None:
        email = options['email']
        realm = self.get_realm(options)

        user = self.get_user(email, realm)

        if options['grant']:
            if (user.is_realm_admin and options['permission'] == "administer" or
                    user.is_api_super_user and options['permission'] == "api_super_user"):
                raise CommandError("User already has permission for this realm.")
            else:
                if options['ack']:
                    if options['permission'] == "api_super_user":
                        do_change_is_api_super_user(user, True)
                    elif options['permission'] == "administer":
                        do_change_user_role(user, UserProfile.ROLE_REALM_ADMINISTRATOR, acting_user=None)
                    print("Done!")
                else:
                    print("Would have granted {} {} rights for {}".format(
                          email, options['permission'], user.realm.string_id))
        else:
            if (user.is_realm_admin and options['permission'] == "administer" or
                    user.is_api_super_user and options['permission'] == "api_super_user"):
                if options['ack']:
                    if options['permission'] == "api_super_user":
                        do_change_is_api_super_user(user, False)
                    elif options['permission'] == "administer":
                        do_change_user_role(user, UserProfile.ROLE_MEMBER, acting_user=None)
                    print("Done!")
                else:
                    print("Would have removed {}'s {} rights on {}".format(email, options['permission'],
                                                                           user.realm.string_id))
            else:
                raise CommandError("User did not have permission for this realm!")
