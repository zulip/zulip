from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError

from zerver.lib.actions import do_change_is_admin
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """Give an existing user administrative permissions over their (own) Realm.

ONLY perform this on customer request from an authorized person.
"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('-f', '--for-real',
                            dest='ack',
                            action="store_true",
                            default=False,
                            help='Acknowledgement that this is done according to policy.')
        parser.add_argument('--revoke',
                            dest='grant',
                            action="store_false",
                            default=True,
                            help='Remove an administrator\'s rights.')
        parser.add_argument('--permission',
                            dest='permission',
                            action="store",
                            default='administer',
                            choices=['administer', 'api_super_user', ],
                            help='Permission to grant/remove.')
        parser.add_argument('email', metavar='<email>', type=str,
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
                    do_change_is_admin(user, True, permission=options['permission'])
                    print("Done!")
                else:
                    print("Would have granted %s %s rights for %s" % (
                          email, options['permission'], user.realm.string_id))
        else:
            if (user.is_realm_admin and options['permission'] == "administer" or
                    user.is_api_super_user and options['permission'] == "api_super_user"):
                if options['ack']:
                    do_change_is_admin(user, False, permission=options['permission'])
                    print("Done!")
                else:
                    print("Would have removed %s's %s rights on %s" % (email, options['permission'],
                                                                       user.realm.string_id))
            else:
                raise CommandError("User did not have permission for this realm!")
