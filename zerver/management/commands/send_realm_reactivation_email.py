from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError

from zerver.actions.realm_settings import do_send_realm_reactivation_email
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    """
    Sends realm reactivation email to admins

    This command sends a reactivation email to the admins of a given realm. It
    checks if the realm is deactivated and if not, raises a CommandError. It
    then sends the reactivation email to the admins of the realm.
    """
    help = """Sends realm reactivation email to admins"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        """
        Add command line arguments

        Args:
            parser (ArgumentParser): The argument parser
            """
        self.add_realm_args(parser, required=True)

    def handle(self, *args: Any, **options: str) -> None:
        """
        Handle command execution

        Args:
            *args (Any): Variable length argument list
            **options (str): Keyword arguments
            """
        realm = self.get_realm(options)
        assert realm is not None
        if not realm.deactivated:
            raise CommandError(f"The realm {realm.name} is already active.")
        print("Sending email to admins")
        do_send_realm_reactivation_email(realm, acting_user=None)
        print("Done!")
