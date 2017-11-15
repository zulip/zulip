
from argparse import ArgumentParser
from typing import Any

from zerver.lib.management import ZulipBaseCommand
from zerver.lib.sessions import delete_all_deactivated_user_sessions, \
    delete_all_user_sessions, delete_realm_user_sessions

class Command(ZulipBaseCommand):
    help = "Log out all users."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument('--deactivated-only',
                            action='store_true',
                            default=False,
                            help="Only logout all users who are deactivated")
        self.add_realm_args(parser, help="Only logout all users in a particular realm")

    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        if realm:
            delete_realm_user_sessions(realm)
        elif options["deactivated_only"]:
            delete_all_deactivated_user_sessions()
        else:
            delete_all_user_sessions()
