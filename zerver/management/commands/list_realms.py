
import sys
from argparse import ArgumentParser
from typing import Any

from zerver.lib.management import ZulipBaseCommand
from zerver.models import Realm

class Command(ZulipBaseCommand):
    help = """List realms in the server and it's configuration settings(optional).

Usage examples:

./manage.py list_realms
./manage.py list_realms --all"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--all",
                            dest="all",
                            action="store_true",
                            default=False,
                            help="Print all the configuration settings of the realms.")

    def handle(self, *args: Any, **options: Any) -> None:
        realms = Realm.objects.all()

        outer_format = "%-5s %-20s %-30s %-50s"
        inner_format = "%-40s %s"
        deactivated = False

        if not options["all"]:
            print(outer_format % ("id", "string_id", "name", "domain"))
            print(outer_format % ("--", "---------", "----", "------"))

            for realm in realms:
                display_string_id = realm.string_id if realm.string_id != '' else "''"
                if realm.deactivated:
                    print(self.style.ERROR(outer_format % (
                        realm.id,
                        display_string_id,
                        realm.name,
                        realm.uri)))
                    deactivated = True
                else:
                    print(outer_format % (realm.id, display_string_id, realm.name, realm.uri))
            if deactivated:
                print(self.style.WARNING("\nRed rows represent deactivated realms."))
            sys.exit(0)

        # The remaining code path is the --all case.
        identifier_attributes = ["id", "name", "string_id"]
        for realm in realms:
            # Start with just all the fields on the object, which is
            # hacky but doesn't require any work to maintain.
            realm_dict = realm.__dict__
            # Remove a field that is confusingly useless
            del realm_dict['_state']
            # Fix the one bitfield to display useful data
            realm_dict['authentication_methods'] = str(realm.authentication_methods_dict())

            for key in identifier_attributes:
                if realm.deactivated:
                    print(self.style.ERROR(inner_format % (key, realm_dict[key])))
                    deactivated = True
                else:
                    print(inner_format % (key, realm_dict[key]))

            for key, value in sorted(realm_dict.items()):
                if key not in identifier_attributes:
                    if realm.deactivated:
                        print(self.style.ERROR(inner_format % (key, value)))
                    else:
                        print(inner_format % (key, value))
            print("-" * 80)

        if deactivated:
            print(self.style.WARNING("\nRed is used to highlight deactivated realms."))
