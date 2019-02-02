
from argparse import ArgumentParser

from zerver.lib.management import ZulipBaseCommand, CommandError
from zerver.lib.actions import do_send_realm_reactivation_email

from typing import Any

class Command(ZulipBaseCommand):
    help = """Sends realm reactivation email to admins"""

    def add_arguments(self, parser: ArgumentParser) -> None:
        self.add_realm_args(parser, True)

    def handle(self, *args: Any, **options: str) -> None:
        realm = self.get_realm(options)
        assert realm is not None
        if not realm.deactivated:
            raise CommandError("The realm %s is already active." % (realm.name,))
        print('Sending email to admins')
        do_send_realm_reactivation_email(realm)
        print('Done!')
