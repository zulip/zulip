from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from zerver.lib.actions import do_change_is_admin

from zerver.models import UserProfile

class Command(BaseCommand):
    help = """Give an existing user administrative permissions over their (own) Realm.

ONLY perform this on customer request from an authorized person.
"""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
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
                            help='Permission to grant/remove.')
        parser.add_argument('email', metavar='<email>', type=str,
                            help="email of user to knight")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        email = options['email']
        try:
            profile = UserProfile.objects.get(email=email)
        except ValidationError:
            raise CommandError("No such user.")

        if options['grant']:
            if profile.has_perm(options['permission'], profile.realm):
                raise CommandError("User already has permission for this realm.")
            else:
                if options['ack']:
                    do_change_is_admin(profile, True, permission=options['permission'])
                    print("Done!")
                else:
                    print("Would have granted %s %s rights for %s" % (
                          email, options['permission'], profile.realm.domain))
        else:
            if profile.has_perm(options['permission'], profile.realm):
                if options['ack']:
                    do_change_is_admin(profile, False, permission=options['permission'])
                    print("Done!")
                else:
                    print("Would have removed %s's %s rights on %s" % (email, options['permission'],
                            profile.realm.domain))
            else:
                raise CommandError("User did not have permission for this realm!")
