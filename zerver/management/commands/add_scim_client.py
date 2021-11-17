from argparse import ArgumentParser
from typing import Any

from zerver.lib.management import ZulipBaseCommand
from zerver.models import SCIMClient


class Command(ZulipBaseCommand):
    help = """Create a SCIM client entry in the database."""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser)
        parser.add_argument("name", help="name of the client")

    def handle(self, *args: Any, **options: Any) -> None:
        client_name = options["name"]
        realm = self.get_realm(options)
        assert realm

        SCIMClient.objects.create(realm=realm, name=client_name)
