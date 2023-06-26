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
        parser.add_argument(
            "--all", action="store_true", help="Print all the configuration settings of the realms."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        realms = Realm.objects.all()

        outer_format = "{:<5} {:<20} {!s:<30} {:<50}"
        inner_format = "{:<40} {}"
        deactivated = False

        if not options["all"]:
            print(outer_format.format("id", "string_id", "name", "domain"))
            print(outer_format.format("--", "---------", "----", "------"))

            for realm in realms:
                display_string_id = realm.string_id if realm.string_id != "" else "''"
                if realm.deactivated:
                    print(
                        self.style.ERROR(
                            outer_format.format(realm.id, display_string_id, realm.name, realm.uri)
                        )
                    )
                    deactivated = True
                else:
                    print(outer_format.format(realm.id, display_string_id, realm.name, realm.uri))
            if deactivated:
                print(self.style.WARNING("\nRed rows represent deactivated realms."))
            sys.exit(0)

        # The remaining code path is the --all case.
        identifier_attributes = ["id", "name", "string_id"]
        for realm in realms:
            # Start with just all the fields on the object, which is
            # hacky but doesn't require any work to maintain.
            realm_dict = vars(realm).copy()
            # Remove a field that is confusingly useless
            del realm_dict["_state"]

            # This is not an attribute of realm strictly speaking, but valuable info to include.
            realm_dict["authentication_methods"] = str(realm.authentication_methods_dict())

            for key in identifier_attributes:
                if realm.deactivated:
                    print(self.style.ERROR(inner_format.format(key, realm_dict[key])))
                    deactivated = True
                else:
                    print(inner_format.format(key, realm_dict[key]))

            for key, value in sorted(realm_dict.items()):
                if key not in identifier_attributes:
                    if realm.deactivated:
                        print(self.style.ERROR(inner_format.format(key, value)))
                    else:
                        print(inner_format.format(key, value))
            print("-" * 80)

        if deactivated:
            print(self.style.WARNING("\nRed is used to highlight deactivated realms."))
