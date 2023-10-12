from argparse import ArgumentParser
from typing import Any

from django.core.management.base import CommandError
from typing_extensions import override

from zerver.actions.realm_settings import do_send_realm_reactivation_email
from zerver.lib.management import ZulipBaseCommand


class Command(ZulipBaseCommand):
    help = """Sends realm reactivation email to admins"""

    @override
    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, required=True)

    @override
    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None
        if not realm.deactivated:
            raise CommandError(f"The realm {realm.name} is already active.")
        print("Sending email to admins")
        do_send_realm_reactivation_email(realm, acting_user=None)
        print("Done!")
