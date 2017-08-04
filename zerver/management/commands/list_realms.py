from __future__ import absolute_import
from __future__ import print_function

from typing import Any
from argparse import ArgumentParser

from zerver.models import Realm
from zerver.lib.management import ZulipBaseCommand

class Command(ZulipBaseCommand):
    help = """List realms in the server and it's configuration settings(optional).

Usage examples:

./manage.py list_realms
./manage.py list_realms --all"""

    def add_arguments(self, parser):
        # type: (ArgumentParser) -> None
        parser.add_argument("--all",
                            dest="all",
                            action="store_true",
                            default=False,
                            help="Print all the configuration settings of the realms.")

    def handle(self, *args, **options):
        # type: (*Any, **Any) -> None
        realms = Realm.objects.all()

        outer_format = "%-5s %-40s %-40s"
        inner_format = "%-40s %s"
        deactivated = False

        if not options["all"]:
            print(outer_format % ("id", "string_id", "name"))
            print(outer_format % ("--", "---------", "----"))

            for realm in realms:
                if realm.deactivated:
                    print(self.style.ERROR(outer_format % (realm.id, realm.string_id, realm.name)))
                    deactivated = True
                else:
                    print(outer_format % (realm.id, realm.string_id, realm.name))
            if deactivated:
                print(self.style.WARNING("\nRed row represents deactivated realm."))
            exit(0)

        identifier_attributes = ["id", "name", "string_id"]
        for realm in realms:
            realm_dict = realm.__dict__

            for key in identifier_attributes:
                if realm.deactivated:
                    print(self.style.ERROR(inner_format % (key, realm_dict[key])))
                    deactivated = True
                else:
                    print(inner_format % (key, realm_dict[key]))

            for key, value in realm_dict.iteritems():
                if key not in identifier_attributes:
                    if realm.deactivated:
                        print(self.style.ERROR(inner_format % (key, value)))
                    else:
                        print(inner_format % (key, value))
            print("-" * 80)

        if deactivated:
            print(self.style.WARNING("\nRed color represents deactivated realm."))
