from __future__ import absolute_import
from __future__ import print_function

from typing import Any

from argparse import ArgumentParser
from django.core.management.base import BaseCommand

from zerver.lib.actions import do_change_full_name
from zerver.models import UserProfile, get_realm, get_user_for_mgmt

class Command(BaseCommand):
    help = """Change the names for many users."""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument(
            '-r', '--realm', nargs='?', default=None,
            dest='string_id',
            type=str,
            help='The name of the realm in which you are bulk changing user names.')

        parser.add_argument('data_file', metavar='<data file>', type=str,
                            help="file containing rows of the form <email>,<desired name>")

    def handle(self, *args, **options):
        # type: (*Any, **str) -> None
        data_file = options['data_file']
        realm = get_realm(options["string_id"])
        with open(data_file, "r") as f:
            for line in f:
                email, new_name = line.strip().split(",", 1)

                try:
                    user_profile = get_user_for_mgmt(email, realm)
                    old_name = user_profile.full_name
                    print("%s: %s -> %s" % (email, old_name, new_name))
                    do_change_full_name(user_profile, new_name)
                except UserProfile.DoesNotExist:
                    print("* E-mail %s doesn't exist in the system, skipping." % (email,))
