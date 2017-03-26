from __future__ import absolute_import
from __future__ import print_function
from optparse import make_option

from typing import Any, Dict, Text

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandParser
from zerver.lib.actions import Realm, do_create_realm, set_default_streams
from zerver.models import RealmAlias, can_add_alias, get_realm

import re
import sys

class Command(BaseCommand):
    help = """Create a realm.

Usage: ./manage.py create_realm --string_id=acme --name='Acme'"""

    def add_arguments(self, parser):
        # type: (CommandParser) -> None
        parser.add_argument('-s', '--string_id',
                            dest='string_id',
                            type=str,
                            help="A short name for the realm. If this "
                                 "installation uses subdomains, this will be "
                                 "used as the realm's subdomain.")

        parser.add_argument('-n', '--name',
                            dest='name',
                            type=str,
                            help='The user-visible name for the realm.')

        parser.add_argument('--corporate',
                            dest='org_type',
                            action="store_const",
                            const=Realm.CORPORATE,
                            help='Is a corporate org_type')

        parser.add_argument('--community',
                            dest='org_type',
                            action="store_const",
                            const=Realm.COMMUNITY,
                            default=None,
                            help='Is a community org_type. Is the default.')

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        string_id = options["string_id"]
        name = options["name"]

        if not name or not string_id:
            print("\033[1;31mPlease provide a name and string_id.\033[0m\n", file=sys.stderr)
            self.print_help("./manage.py", "create_realm")
            exit(1)

        if get_realm(string_id) is not None:
            raise ValueError("string_id taken. Please choose another one.")

        realm, created = do_create_realm(string_id, name, org_type=options["org_type"])
        if created:
            print(string_id, "created.")
            stream_dict = {
                "social": {"description": "For socializing", "invite_only": False},
                "engineering": {"description": "For engineering", "invite_only": False}
            } # type: Dict[Text, Dict[Text, Any]]
            set_default_streams(realm, stream_dict)

            print("\033[1;36mDefault streams set to social,engineering,zulip!\033[0m")
        else:
            print(string_id, "already exists.")
